"""Audit follow-up: `app/api/main.py` lifespan ran
`Base.metadata.create_all` on every startup despite 25 Alembic migrations
existing. Concurrent boots can race, schemas drift between Alembic state
and SQLAlchemy model state, and migrations become impossible to test in
isolation. The DB schema must be owned exclusively by Alembic.

This pin is a regression net: any reintroduction of `create_all` (or
`metadata.create_all`) into the FastAPI lifespan will break this test.
"""

from __future__ import annotations

from pathlib import Path


def test_main_lifespan_does_not_call_create_all():
    src = Path("app/api/main.py").read_text(encoding="utf-8")
    # The lifespan must not auto-create tables — Alembic owns the schema.
    assert "create_all" not in src, (
        "app/api/main.py reintroduced Base.metadata.create_all in the "
        "lifespan. Schema is owned by Alembic — run `alembic upgrade head` "
        "from the Docker entrypoint instead."
    )


def test_main_lifespan_imports_engine_for_dispose_only():
    """The lifespan should still dispose the engine on shutdown — that's
    the only legitimate use of `engine` here. If neither create_all nor
    dispose appear, someone forgot the cleanup."""
    src = Path("app/api/main.py").read_text(encoding="utf-8")
    assert "engine.dispose" in src, "lifespan must dispose the engine on shutdown"
