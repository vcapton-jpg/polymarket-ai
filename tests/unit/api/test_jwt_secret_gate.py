"""Tests for `_assert_jwt_secret_safe_for_env` widened gate (M5).

Audit follow-up 2026-05-05. Pre-PR the boot-time JWT secret check
only fired on `env=production`. Any other env (`staging`, `preview`,
`qa`, …) silently booted with the public default
`foresight-dev-secret-key-change-in-prod-2026` from `.env.example`,
making forged JWTs trivial against e.g. Vercel preview URLs.

The post-PR rule: only an explicit allowlist of *local* env names
(`development`, `dev`, `test`, `testing`, `local`, ``) tolerates a
default secret. Everything else must override `JWT_SECRET_KEY`.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def _call_gate_with(env: str, secret: str) -> None:
    """Re-run the boot-time JWT assertion with a swapped settings
    snapshot. We can't change `app.api.main.settings` directly because
    it's captured at import time; patching the module-level reference
    is the surgical move.
    """
    fake_settings = type("S", (), {"env": env, "jwt_secret_key": secret})()
    from app.api import main as main_mod

    with patch.object(main_mod, "settings", fake_settings):
        main_mod._assert_jwt_secret_safe_for_env()


# ───────────────────────────────────────────────────────────────────
# DEV-SAFE ENVS — defaults are allowed
# ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "env",
    ["development", "dev", "test", "testing", "local", "", "DEVELOPMENT"],
)
def test_dev_safe_envs_allow_default_secret(env: str):
    """Local loops boot without ceremony — the default is fine here."""
    _call_gate_with(env, "change-me-in-production")
    _call_gate_with(env, "foresight-dev-secret-key-change-in-prod-2026")
    _call_gate_with(env, "")
    # Sanity: a real secret in dev is also fine
    _call_gate_with(env, "openssl-rand-hex-32-output-here")


# ───────────────────────────────────────────────────────────────────
# NON-LOCAL ENVS — defaults MUST be rejected
# ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "env",
    ["production", "staging", "preview", "qa", "uat", "demo", "PRODUCTION"],
)
def test_non_local_envs_reject_default_secret(env: str):
    """The keystone test — pre-PR these silently booted, leaking a
    forge-able token factory."""
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        _call_gate_with(env, "change-me-in-production")


@pytest.mark.parametrize(
    "env",
    ["production", "staging", "preview", "qa"],
)
def test_non_local_envs_reject_legacy_dev_secret(env: str):
    """The historic `.env.example`-shipped value must also be rejected
    in non-local envs. It's grep-able from the repo so an attacker has
    a 1-token guess for any leaked Vercel preview."""
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        _call_gate_with(env, "foresight-dev-secret-key-change-in-prod-2026")


def test_non_local_env_rejects_empty_secret():
    """Empty string is the worst-case default — accept nothing."""
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        _call_gate_with("staging", "")


def test_non_local_env_accepts_non_default_secret():
    """A real secret on staging boots fine."""
    _call_gate_with("staging", "1c0a2f8b9ed4… (32 hex chars)")
    _call_gate_with("production", "actual-strong-secret-rotated-2026")


# ───────────────────────────────────────────────────────────────────
# Error message — pointing at the runbook
# ───────────────────────────────────────────────────────────────────


def test_error_message_mentions_openssl_runbook():
    """The error must point at the one-liner fix so the operator
    doesn't have to dig through docs."""
    fake_settings = type("S", (), {
        "env": "production", "jwt_secret_key": "change-me-in-production"
    })()
    from app.api import main as main_mod

    with patch.object(main_mod, "settings", fake_settings):
        with pytest.raises(RuntimeError) as exc:
            main_mod._assert_jwt_secret_safe_for_env()
    assert "openssl rand -hex 32" in str(exc.value)
