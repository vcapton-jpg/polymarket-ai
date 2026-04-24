"""CLI for the embedding eval harness.

Examples:
  python -m scripts.eval_embeddings --variant v1 --surface news
  python -m scripts.eval_embeddings --variant v2 --surface news \\
      --baseline docs/eval_baselines/embeddings_2026-04-24_v1.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.db.database import get_session_factory
from app.eval.runner import EvalReport, diff_reports, report_to_json, run_eval

_SURFACES = ("news", "market", "event", "all")


async def _run_one(variant: str, surface: str) -> EvalReport:
    factory = get_session_factory()
    async with factory() as s:
        return await run_eval(s, variant=variant, surface=surface)


def _load_baseline(path: Path) -> EvalReport:
    d = json.loads(path.read_text())
    d["generated_at"] = datetime.fromisoformat(d["generated_at"])
    return EvalReport(**d)


def _print_summary(report: EvalReport) -> None:
    print(f"variant={report.variant} surface={report.surface} "
          f"n_pairs={report.n_pairs} n_skipped={report.n_skipped} "
          f"git_sha={report.git_sha}")
    for metric, stats in report.metrics.items():
        print(f"  {metric}: mean={stats['mean']:.4f} "
              f"[{stats['ci_low']:.4f}, {stats['ci_high']:.4f}] n={stats['n']}")


def _print_diff(diff: dict) -> None:
    for metric, info in diff.items():
        arrow = {"improved": "↑", "regressed": "↓", "flat": "="}[info["verdict"]]
        print(f"  {metric}: {info['baseline_mean']:.4f} → {info['candidate_mean']:.4f} "
              f"(Δ={info['delta']:+.4f}) {arrow} {info['verdict']}")


async def _main(args: argparse.Namespace) -> int:
    surfaces = (["news", "market", "event"] if args.surface == "all" else [args.surface])
    reports: list[EvalReport] = []
    for surf in surfaces:
        r = await _run_one(args.variant, surf)
        reports.append(r)
        _print_summary(r)

    if args.out:
        payload = {r.surface: json.loads(report_to_json(r)) for r in reports}
        Path(args.out).write_text(json.dumps(payload, indent=2, default=str))
        print(f"wrote {args.out}")

    if args.baseline:
        baseline_data = json.loads(Path(args.baseline).read_text())
        for r in reports:
            bd = baseline_data.get(r.surface)
            if bd is None:
                print(f"  [{r.surface}] no baseline found, skipping diff")
                continue
            bd["generated_at"] = datetime.fromisoformat(bd["generated_at"])
            baseline_report = EvalReport(**bd)
            diff = diff_reports(baseline_report, r)
            print(f"--- diff for {r.surface} ---")
            _print_diff(diff)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("v1", "v2"), required=True)
    parser.add_argument("--surface", choices=_SURFACES, required=True)
    parser.add_argument("--out", help="Write JSON report to this path.")
    parser.add_argument("--baseline", help="Diff against this baseline JSON file.")
    args = parser.parse_args()
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())
