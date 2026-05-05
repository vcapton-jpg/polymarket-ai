"""Tests for `app.db.database` env-driven configuration.

Audit follow-up 2026-05-05 — these tests pin behavior introduced in
PR #43 (`echo=False` by default, opt-in via `DB_ECHO=1`). Pre-PR, the
`echo` flag was tied to `is_development`, which silently defaulted to
True on every Celery worker container and triggered the OOM bug whose
diagnosis took six days.

The cost of this regression to ship was zero — `_DB_ECHO` is read at
module import time from `os.environ`. A future contributor who tries
to "simplify" the helper by going back to `echo=settings.is_development`
will trip these tests immediately.
"""

from __future__ import annotations

import importlib
import os
from unittest.mock import patch


def _reload_database_module() -> object:
    """Re-import `app.db.database` so the module-level `_DB_ECHO` constant
    is recomputed against the *current* `os.environ`. Pytest order doesn't
    guarantee this module hasn't been imported earlier in the run, so the
    cached `_DB_ECHO` could be stale otherwise.
    """
    import app.db.database as db_mod

    return importlib.reload(db_mod)


def test_db_echo_default_false_when_env_unset():
    """Without `DB_ECHO` in the environment, echo MUST be False.

    This is the regression gate for PR #43 — pre-PR, an unset env var
    plus `is_development=True` (the worker default) yielded `echo=True`
    and fed the 30 KB embedding bind parameters into the log buffer
    twice per INSERT.
    """
    env = {k: v for k, v in os.environ.items() if k != "DB_ECHO"}
    with patch.dict(os.environ, env, clear=True):
        db_mod = _reload_database_module()
        assert db_mod._DB_ECHO is False


def test_db_echo_true_when_env_set_to_one():
    """The opt-in path remains usable for dev SQL trace."""
    with patch.dict(os.environ, {"DB_ECHO": "1"}):
        db_mod = _reload_database_module()
        assert db_mod._DB_ECHO is True


def test_db_echo_true_when_env_set_to_yes_or_true():
    """`DB_ECHO` accepts truthy strings — `1`, `true`, `yes` all enable."""
    for value in ("true", "TRUE", "yes", "YES"):
        with patch.dict(os.environ, {"DB_ECHO": value}):
            db_mod = _reload_database_module()
            assert db_mod._DB_ECHO is True, (
                f"DB_ECHO={value!r} should enable echo"
            )


def test_db_echo_false_for_unrecognised_truthy_strings():
    """`DB_ECHO=on` and `DB_ECHO=2` are NOT accepted — only the explicit
    set `{1, true, yes}` (case-insensitive). This protects against
    accidental enablement from upstream tooling that uses a different
    truthy convention.
    """
    for value in ("on", "2", "enabled", ""):
        with patch.dict(os.environ, {"DB_ECHO": value}):
            db_mod = _reload_database_module()
            assert db_mod._DB_ECHO is False, (
                f"DB_ECHO={value!r} must NOT enable echo"
            )
