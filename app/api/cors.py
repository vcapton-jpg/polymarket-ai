"""CORS origin resolution per environment.

Audit follow-up: `main.py` previously used `allow_origins=["*"]` with
`allow_credentials=True`. Browsers reject credentialed requests against
a wildcard, so cookie/auth-bearing calls would fail in prod; beyond
that, wildcard-with-credentials is a textbook CSRF surface. This helper
returns an explicit allow-list keyed off the env, so prod is locked to
the app's own origin (+ any extras provided via Settings).
"""

from __future__ import annotations

_DEV_ORIGINS = (
    # Vite dev server
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Legacy CRA / generic SPA dev
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def resolve_cors_origins(
    *,
    env: str,
    app_base_url: str,
    extra_origins: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Return the explicit CORS allow-list for the given env.

    - `production`: `[app_base_url] + extra_origins`. No wildcard, no localhost.
    - any other env (development / test / staging): adds the dev ports
      so Vite + the public URL both work locally.

    The base URL has its trailing slash stripped (browsers compare Origin
    without it), and the final list is de-duplicated while preserving
    insertion order. Empty strings are dropped.
    """
    base = (app_base_url or "").rstrip("/")
    extras: list[str] = list(extra_origins or [])

    if env == "production":
        candidates = [base, *extras]
    else:
        candidates = [base, *_DEV_ORIGINS, *extras]

    seen: set[str] = set()
    out: list[str] = []
    for o in candidates:
        if not o:
            continue
        if o in seen:
            continue
        seen.add(o)
        out.append(o)
    return out
