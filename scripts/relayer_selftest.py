"""Operator self-test for the P2 gasless relayer Safe deploy.

This is the OPERATOR path only — it signs with YOUR own key
(`OPERATOR_TEST_PRIVATE_KEY`) so you can validate the end-to-end
Polymarket relayer deploy on your own wallet before the user-facing
(browser-wallet) flow ships. It never acts for a real user.

Required env on the host (all three, or the run is refused):
    ENABLE_RELAYER_DEPLOY=true
    OPERATOR_TEST_PRIVATE_KEY=0x...          # YOUR test EOA key
    BUILDER_API_KEY / BUILDER_API_SECRET / BUILDER_API_PASSPHRASE
Optional:
    RELAYER_URL=https://relayer-v2.polymarket.com   (default)

Usage:
    # dry run — derive + cross-check + is-deployed, NO deploy:
    docker compose exec app python -m scripts.relayer_selftest --check
    # actually deploy (gasless; idempotent if already deployed):
    docker compose exec app python -m scripts.relayer_selftest

NOTE: this targets Polygon **mainnet**. The deploy is gasless (the
relayer pays) but it is a real on-chain Safe. It is idempotent —
re-running after a successful deploy just prints the address.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.trading.relayer_deployer import RelayerDeployer, RelayerError


async def _run(check_only: bool) -> int:
    d = RelayerDeployer()
    try:
        operator = d._operator_address()
    except RelayerError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"operator EOA      : {operator}")

    try:
        # _cross_check derives via our compute_safe_address AND the
        # Polymarket SDK and asserts they agree before anything else.
        client = d._build_client()
        safe = d._cross_check(client)
        print(f"derived Safe      : {safe}  (our derivation == SDK ✓)")

        deployed = await d.is_operator_safe_deployed()
        print(f"already deployed  : {deployed}")

        if check_only:
            print("--check: no deploy attempted.")
            return 0
        if deployed:
            print("Nothing to do — Safe already on-chain.")
            return 0

        print("Submitting gasless relayer deploy …")
        result = await d.deploy_operator_safe()
        print(f"DEPLOYED          : {result}")
        return 0
    except RelayerError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="dry run: derive + cross-check + is-deployed only, no deploy",
    )
    args = ap.parse_args()
    sys.exit(asyncio.run(_run(args.check)))


if __name__ == "__main__":
    main()
