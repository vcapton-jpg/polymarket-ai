"""Shared async helper for Celery workers.

Celery fork workers need their own event loop (separate from the parent process).
We maintain ONE persistent loop per worker process to avoid destroying asyncpg
connection pools between tasks.
"""

import asyncio
import os

_loop = None
_loop_pid = None


def run_async(coro):
    """Run an async coroutine on the worker-local persistent event loop."""
    global _loop, _loop_pid

    pid = os.getpid()
    if _loop is None or _loop_pid != pid or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        _loop_pid = pid

    return _loop.run_until_complete(coro)
