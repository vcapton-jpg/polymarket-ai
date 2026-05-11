"""ASCII table report of /api/admin/metrics/variants.

Calls the API in-process via httpx + ASGITransport — no need to spin up a
webserver or pass auth tokens. Exits non-zero on API error.

Usage:
    docker compose exec app python -m scripts.report_metrics --window 30d
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from app.api.main import app


async def _fetch(window: str, token: str | None) -> dict:
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with AsyncClient(transport=transport, base_url="http://cli") as c:
        r = await c.get(
            f"/api/admin/metrics/variants?window={window}", headers=headers
        )
    if r.status_code != 200:
        sys.stderr.write(f"API error {r.status_code}: {r.text}\n")
        sys.exit(1)
    return r.json()


def _fmt(v: float | None, width: int, decimals: int = 3) -> str:
    if v is None:
        return "n/a".rjust(width)
    return f"{v:.{decimals}f}".rjust(width)


def _render_table(data: dict, window: str) -> str:
    lines: list[str] = []
    header = (
        "Variant                   |  n  | Winrate (CI95)          | Brier "
        "| PnL/trade | PnL total"
    )
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)
    for v in data["variants"]:
        name = v["variant"][:26].ljust(26)
        n = str(v["n"]).rjust(3)
        if v["winrate"] is None:
            wr = "       n/a             "
        else:
            wr = (
                f"{v['winrate']:.3f} "
                f"[{v['winrate_ci95_low']:.2f}-{v['winrate_ci95_high']:.2f}]"
            ).rjust(23)
        br = _fmt(v["brier"], width=5)
        ppt = _fmt(v["pnl_per_trade_eur"], width=8, decimals=2) + "€"
        pt = _fmt(v["pnl_total_eur"], width=8, decimals=2) + "€"
        lines.append(f"{name} | {n} | {wr} | {br} | {ppt}  | {pt}")

    try:
        days = int(window.rstrip("d"))
        start = (datetime.now(UTC) - timedelta(days=days)).date().isoformat()
        end = datetime.now(UTC).date().isoformat()
        lines.append("")
        lines.append(f"Window: {start} → {end} ({window})")
    except ValueError:
        pass
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--window", default="30d")
    p.add_argument("--token", default=None, help="Bearer JWT for an admin account")
    p.add_argument("--json", action="store_true", help="emit raw JSON, no table")
    args = p.parse_args()

    data = asyncio.run(_fetch(args.window, args.token))
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(_render_table(data, args.window))


if __name__ == "__main__":
    main()
