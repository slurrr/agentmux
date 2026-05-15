#!/usr/bin/env python3
"""Summarize Hindsight memory performance from agentmux memory logs.

Why:
- Hindsight memory logs already contain useful timing summaries.
- This script extracts two signals:
  1) retain_extract_facts LLM call durations (from "slow llm call" lines)
  2) consolidation per-memory averages (from "[CONSOLIDATION] ... avg=Xs/memory")

Usage:
  python scripts/hs_log_metrics.py /path/to/*-mem_gem_hs-memory.log

You can pass multiple log files; stats are computed per file.

Notes:
- "retain" timing is per *LLM call*, not per memory unit.
- "consolidation" avg is per *memory unit* and is the best apples-to-apples measure.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


RE_RETAIN_SLOW = re.compile(
    r"slow llm call: scope=retain_extract_facts.*?input_tokens=(\d+), output_tokens=(\d+).*?time=([0-9.]+)s"
)
RE_CONS_AVG = re.compile(r"\[CONSOLIDATION\].*?avg=([0-9.]+)s/memory")


def _stats(vals: list[float]) -> str:
    if not vals:
        return "n=0"
    vals = sorted(vals)
    n = len(vals)
    p50 = vals[n // 2]
    p90 = vals[int(n * 0.9) - 1] if n > 1 else vals[0]
    return (
        f"n={n} min={min(vals):.3f}s p50={p50:.3f}s p90={p90:.3f}s max={max(vals):.3f}s avg={sum(vals)/n:.3f}s"
    )


def summarize_log(path: Path) -> None:
    retain_times: list[float] = []
    cons_avg: list[float] = []

    for line in path.read_text(errors="replace").splitlines():
        m = RE_RETAIN_SLOW.search(line)
        if m:
            retain_times.append(float(m.group(3)))
            continue
        m = RE_CONS_AVG.search(line)
        if m:
            cons_avg.append(float(m.group(1)))

    print(f"\n== {path} ==")
    print("retain_extract_facts (LLM call duration):", _stats(retain_times))
    print("consolidation (avg seconds per memory):", _stats(cons_avg))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+", help="Paths to *-memory.log files")
    args = ap.parse_args()

    for p in args.logs:
        summarize_log(Path(p))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
