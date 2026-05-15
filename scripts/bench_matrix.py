from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTMUX_BIN = ROOT / ".venv-vllm" / "bin" / "agentmux"
BENCH_DIR = Path.home() / "runs" / "agentmux" / "benchmarks"


def _list_bench_stacks() -> list[str]:
    proc = subprocess.run(
        [str(AGENTMUX_BIN), "list"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    stacks: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("bench/"):
            continue
        _track, _sep, name = line.partition("/")
        if name:
            stacks.append(name)
    return stacks


def _latest_result_mtime() -> float:
    if not BENCH_DIR.exists():
        return 0.0
    latest = max((p.stat().st_mtime for p in BENCH_DIR.glob("*.json")), default=0.0)
    return latest


def _find_newest_result(after_mtime: float) -> Path | None:
    if not BENCH_DIR.exists():
        return None
    candidates = [p for p in BENCH_DIR.glob("*.json") if p.stat().st_mtime >= after_mtime]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _run_one(stack: str, *, judge: bool, no_perf: bool) -> tuple[int, Path | None]:
    before = _latest_result_mtime()
    cmd = [str(AGENTMUX_BIN), "bench", stack, "--launch"]
    if judge:
        cmd.append("--judge")
    if no_perf:
        cmd.append("--no-perf")
    proc = subprocess.run(cmd, cwd=ROOT)
    result = _find_newest_result(before)
    return proc.returncode, result


def _read_summary(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    categories = summary.get("categories", {}) if isinstance(summary, dict) else {}
    quality = categories.get("quality_no_tools", {}) if isinstance(categories, dict) else {}
    quality_tools = categories.get("quality_with_tools", {}) if isinstance(categories, dict) else {}
    reliability = categories.get("reliability", {}) if isinstance(categories, dict) else {}
    return {
        "stack": payload.get("stack", {}).get("name", "?"),
        "verdict": summary.get("verdict", "?"),
        "overall": summary.get("overall_score", "?"),
        "no_tools": f"{quality.get('passed_cases', 0)}/{quality.get('total_cases', 0)}",
        "with_tools": f"{quality_tools.get('passed_cases', 0)}/{quality_tools.get('total_cases', 0)}",
        "structured_fail_rate": reliability.get("structured_output_failure_rate", "?"),
        "path": str(path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run built-in agentmux bench across bench stacks")
    parser.add_argument("stacks", nargs="*", help="Stack names. Defaults to all bench/* stacks.")
    parser.add_argument("--judge", action="store_true", help="Enable judge audit")
    parser.add_argument("--no-perf", action="store_true", help="Skip endpoint perf")
    args = parser.parse_args(argv)

    if not AGENTMUX_BIN.exists():
        raise SystemExit(f"missing agentmux binary: {AGENTMUX_BIN}")

    stacks = args.stacks or _list_bench_stacks()
    if not stacks:
        raise SystemExit("no bench stacks found")

    print("bench stacks:")
    for stack in stacks:
        print(f"- {stack}")
    print()

    summaries: list[dict[str, object]] = []
    failed = False
    for stack in stacks:
        print(f"=== running {stack} ===", flush=True)
        rc, result = _run_one(stack, judge=args.judge, no_perf=args.no_perf)
        if rc != 0:
            failed = True
            print(f"FAILED: {stack}", file=sys.stderr)
            continue
        if result is None:
            failed = True
            print(f"FAILED: {stack} produced no result file", file=sys.stderr)
            continue
        summaries.append(_read_summary(result))
        print(f"saved: {result}")
        print()

    if summaries:
        print("summary:")
        for item in summaries:
            print(
                f"- {item['stack']}: verdict={item['verdict']} overall={item['overall']} "
                f"no-tools={item['no_tools']} with-tools={item['with_tools']} "
                f"structured_fail_rate={item['structured_fail_rate']}"
            )
            print(f"  {item['path']}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
