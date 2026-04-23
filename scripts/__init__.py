"""One-off maintenance scripts (backfills, migrations).

Not part of the runtime import graph — only invoked via
`docker compose exec app python -m scripts.<name>`.
"""
