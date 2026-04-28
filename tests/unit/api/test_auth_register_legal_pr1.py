"""Legal-PR-1 regression tests for /auth/register validations.

Covers:
  * `_normalised_blocked_countries` parser
  * `_enforce_geo_restriction` allow / block / missing / VPN-evasion paths
  * `RegisterRequest` validation rejects missing age + country

The full register endpoint integration test (DB roundtrip + UserLimits row)
lives separately under tests/integration. Here we only exercise the pure
helpers + Pydantic schema so the suite stays fast.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.routes.auth import (
    RegisterRequest,
    _enforce_geo_restriction,
    _normalised_blocked_countries,
)


class _FakeRequest:
    """Stand-in for fastapi.Request — only the .headers dict is read."""

    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {}


# ---------------------------------------------------------------------------
# _normalised_blocked_countries
# ---------------------------------------------------------------------------


def test_blocked_countries_parses_default():
    blocked = _normalised_blocked_countries("US,UK,GB,KP,IR,SY,CU,RU,BY")
    assert blocked == {"US", "UK", "GB", "KP", "IR", "SY", "CU", "RU", "BY"}


def test_blocked_countries_normalises_case_and_whitespace():
    blocked = _normalised_blocked_countries(" us , Uk,gb ")
    assert blocked == {"US", "UK", "GB"}


def test_blocked_countries_empty_string_yields_empty_set():
    """Empty value disables the gate — operators can use this for staging."""
    assert _normalised_blocked_countries("") == set()


# ---------------------------------------------------------------------------
# _enforce_geo_restriction
# ---------------------------------------------------------------------------


def test_geo_allowed_country_returns_uppercase():
    """France is allowed — returned country is normalised to upper-case."""
    assert _enforce_geo_restriction("fr", _FakeRequest()) == "FR"


def test_geo_blocked_country_raises_451():
    with pytest.raises(HTTPException) as exc:
        _enforce_geo_restriction("US", _FakeRequest())
    assert exc.value.status_code == 451
    assert "US" in exc.value.detail


def test_geo_missing_country_raises_400():
    """Pre-fix the frontend collected age but never sent it; same shape
    of bug for country must hard-fail with 400 instead of silently
    defaulting to allow."""
    with pytest.raises(HTTPException) as exc:
        _enforce_geo_restriction(None, _FakeRequest())
    assert exc.value.status_code == 400


def test_geo_vpn_evasion_caught_via_cf_ipcountry():
    """User declares FR but Cloudflare reports US — refuse. We trust the
    network-level signal over the self-declared value when they
    disagree."""
    req = _FakeRequest(headers={"cf-ipcountry": "US"})
    with pytest.raises(HTTPException) as exc:
        _enforce_geo_restriction("FR", req)
    assert exc.value.status_code == 451


def test_geo_cf_ipcountry_lower_case_normalised():
    req = _FakeRequest(headers={"cf-ipcountry": "us"})
    with pytest.raises(HTTPException) as exc:
        _enforce_geo_restriction("FR", req)
    assert exc.value.status_code == 451


def test_geo_cf_ipcountry_disagreeing_with_allowed_passes_through():
    """User declares FR, Cloudflare reports DE — both allowed → pass.
    We only block when CF reports a value that is in the blocklist."""
    req = _FakeRequest(headers={"cf-ipcountry": "DE"})
    assert _enforce_geo_restriction("FR", req) == "FR"


def test_geo_no_cf_header_trusts_declared():
    """When the edge isn't passing the country header (no Cloudflare in
    front yet), we fall back to trusting the user-declared value."""
    assert _enforce_geo_restriction("FR", _FakeRequest()) == "FR"


def test_geo_blocklist_disabled_via_empty_setting():
    """Empty `signup_blocked_countries` allows all — operator override."""
    fake = type("S", (), {"signup_blocked_countries": ""})()
    with patch("app.api.routes.auth.get_settings", return_value=fake):
        assert _enforce_geo_restriction("US", _FakeRequest()) == "US"


# ---------------------------------------------------------------------------
# RegisterRequest schema
# ---------------------------------------------------------------------------


def test_register_request_age_defaults_to_false():
    """Pydantic must NOT silently default age_confirmed_18 to True. The
    register endpoint is responsible for raising 400 when the value is
    False; the schema only enforces the type."""
    req = RegisterRequest(email="a@b.com", password="password123")
    assert req.age_confirmed_18 is False


def test_register_request_accepts_explicit_age_and_country():
    req = RegisterRequest(
        email="a@b.com",
        password="password123",
        age_confirmed_18=True,
        country_residence="FR",
    )
    assert req.age_confirmed_18 is True
    assert req.country_residence == "FR"


def test_register_request_country_must_be_two_chars():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="a@b.com",
            password="password123",
            age_confirmed_18=True,
            country_residence="FRA",  # ISO 3166-1 alpha-3 — not accepted
        )
