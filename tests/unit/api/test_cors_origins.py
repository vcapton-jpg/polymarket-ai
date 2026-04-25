"""Audit follow-up: `app/api/main.py` had `allow_origins=["*"]` +
`allow_credentials=True` — the browser rejects credentialed requests
when the wildcard is used, so cookie/auth-bearing calls would fail in
prod. Beyond that, wildcard-with-credentials is a textbook CSRF surface.

Fix: a small pure resolver that returns the right origin list per env.
"""

from __future__ import annotations


def test_prod_locks_to_app_base_url_only():
    from app.api.cors import resolve_cors_origins

    out = resolve_cors_origins(env="production", app_base_url="https://getforesight.io")
    assert out == ["https://getforesight.io"]
    # No wildcard in prod.
    assert "*" not in out


def test_prod_with_extra_origins_appends_them():
    """A future apex/www split or staging origin can be added via env."""
    from app.api.cors import resolve_cors_origins

    out = resolve_cors_origins(
        env="production",
        app_base_url="https://getforesight.io",
        extra_origins=["https://www.getforesight.io", "https://app.getforesight.io"],
    )
    assert out == [
        "https://getforesight.io",
        "https://www.getforesight.io",
        "https://app.getforesight.io",
    ]


def test_development_includes_localhost_dev_ports():
    from app.api.cors import resolve_cors_origins

    out = resolve_cors_origins(env="development", app_base_url="https://getforesight.io")
    # Vite (5173) and the public app URL must be in the dev list.
    assert "http://localhost:5173" in out
    assert "http://localhost:3000" in out
    # No wildcard even in dev — credentialed requests would still break.
    assert "*" not in out


def test_test_env_returns_safe_list():
    """Pytest runs under env='test' or unset — must not be a wildcard."""
    from app.api.cors import resolve_cors_origins

    out = resolve_cors_origins(env="test", app_base_url="https://getforesight.io")
    assert "*" not in out
    assert out  # non-empty


def test_resolver_strips_trailing_slash_from_app_base_url():
    """app_base_url='https://x.io/' must produce 'https://x.io', not 'https://x.io/'.

    Browsers compare Origin headers without trailing slash; a stored value
    with one would never match.
    """
    from app.api.cors import resolve_cors_origins

    out = resolve_cors_origins(env="production", app_base_url="https://getforesight.io/")
    assert out == ["https://getforesight.io"]


def test_resolver_dedupes_and_drops_empty():
    from app.api.cors import resolve_cors_origins

    out = resolve_cors_origins(
        env="production",
        app_base_url="https://x.io",
        extra_origins=["https://x.io", "", "https://y.io"],
    )
    assert out == ["https://x.io", "https://y.io"]
