#!/usr/bin/env python3
"""Watch pi-ghosty memory receipts and print per-turn retain/recall cost signals.

This is meant to be a temporary profiling helper while tuning Hindsight.
Run it in a separate terminal and Ctrl-C to stop.

What it reports for each new turn folder:
- recallMs, factsCount, injectedChars (from meta.json)
- personal/procedural transcriptChars (from retain-request-*.json)
- largest single entry size in procedural transcript (helps catch big tool_result spikes)

Usage:
  python scripts/pg_memory_metrics_watch.py \
    --session 18725fdc-75db-4420-8a4c-867f0be86991

Defaults assume local runs under ~/runs/pi-ghosty.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _load_json(path: Path):
    return json.loads(path.read_text())


def _largest_entry_chars_from_retain_request(req: dict) -> tuple[int, int, str]:
    """Return (max_chars, index, role) from the JSON conversation array in items[0].content."""
    content = req["body"]["items"][0]["content"]
    arr = json.loads(content)
    best = (0, -1, "")
    for i, e in enumerate(arr):
        c = e.get("content", "")
        role = e.get("role", "")
        l = len(c)
        if l > best[0]:
            best = (l, i, role)
    return best


def summarize_turn(turn_dir: Path) -> dict:
    meta = _load_json(turn_dir / "meta.json")
    personal_req = _load_json(turn_dir / "retain-request-personal.json")
    procedural_req = _load_json(turn_dir / "retain-request-procedural.json")

    p_chars = int(personal_req.get("transcriptChars", -1))
    pr_chars = int(procedural_req.get("transcriptChars", -1))
    maxc, maxi, maxrole = _largest_entry_chars_from_retain_request(procedural_req)

    return {
        "turn": meta.get("turnId"),
        "ts": meta.get("ts"),
        "recallMs": meta.get("recallMs"),
        "factsCount": meta.get("factsCount"),
        "injectedChars": meta.get("injectedChars"),
        "personalTranscriptChars": p_chars,
        "proceduralTranscriptChars": pr_chars,
        "proceduralLargestEntry": {"chars": maxc, "index": maxi, "role": maxrole},
    }


def fmt(summary: dict) -> str:
    le = summary["proceduralLargestEntry"]
    return (
        f"{summary['turn']} recallMs={summary['recallMs']} facts={summary['factsCount']} injChars={summary['injectedChars']} | "
        f"retainChars personal={summary['personalTranscriptChars']} procedural={summary['proceduralTranscriptChars']} | "
        f"procMaxEntry={le['chars']} (idx={le['index']} role={le['role']})"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--runs-root",
        default=str(Path.home() / "runs" / "pi-ghosty" / "data" / "memory" / "receipts" / "corroborator"),
        help="Root receipts/corroborator directory",
    )
    ap.add_argument("--session", required=True, help="pi-ghosty corroborator sessionId")
    ap.add_argument("--poll", type=float, default=1.0, help="poll interval seconds")
    args = ap.parse_args()

    turns_dir = Path(args.runs_root) / args.session / "turns"
    if not turns_dir.exists():
        raise SystemExit(f"turns dir not found: {turns_dir}")

    seen: set[str] = set()
    print(f"Watching: {turns_dir}")

    while True:
        for d in sorted(turns_dir.iterdir()):
            if not d.is_dir():
                continue
            key = d.name
            if key in seen:
                continue
            # only report once the expected files exist
            if not (d / "meta.json").exists():
                continue
            if not (d / "retain-request-personal.json").exists():
                continue
            if not (d / "retain-request-procedural.json").exists():
                continue

            try:
                summary = summarize_turn(d)
                print(fmt(summary))
                seen.add(key)
            except Exception as e:
                print(f"{d.name}: error: {e}")

        time.sleep(args.poll)


if __name__ == "__main__":
    raise SystemExit(main())
