#!/usr/bin/env python3
"""Inspect Hindsight DB content for a specific pi-ghosty session.

Goal: stop guessing from receipts. Pull the *actual stored* memory units + chunks
from the running Hindsight API, and highlight any "thinking" leakage patterns.

Usage:
  python scripts/hs_inspect_session.py \
    --base-url http://127.0.0.1:8888 \
    --bank pi-ghosty-personal --bank pi-ghosty-procedural \
    --session-id <corroborator-session-uuid>

Notes:
- We identify relevant rows by matching session-id in chunk_id and/or document_id.
- Requires Hindsight API reachable at base-url.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from typing import Any


THINKING_PATTERNS = [
    re.compile(r"\bI should respond\b"),
    re.compile(r"\bThe user has (given|sent)\b"),
    re.compile(r"\bI should\b"),
    re.compile(r"<\|think\|>"),
    re.compile(r"<\|channel>thought"),
]


def _get_json(url: str, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _q(s: str) -> str:
    return urllib.parse.quote(s, safe="")


def _has_thinking_leak(text: str) -> bool:
    return any(p.search(text or "") for p in THINKING_PATTERNS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8888")
    ap.add_argument("--bank", action="append", required=True)
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    session_id = args.session_id

    print(f"hindsight_base_url={base}")
    print(f"session_id={session_id}")

    for bank in args.bank:
        print("\n" + "=" * 80)
        print(f"BANK: {bank}")
        print("=" * 80)

        # 1) Find documents matching the session id (document_id includes it in pi-ghosty)
        docs_url = f"{base}/v1/default/banks/{_q(bank)}/documents?q={_q(session_id)}&limit=50"
        docs = _get_json(docs_url)
        doc_items = docs.get("items", []) if isinstance(docs, dict) else []
        print(f"documents matched: {len(doc_items)}")
        for d in doc_items[:10]:
            print(
                f"  - document_id={d.get('document_id') or d.get('id') or d.get('documentId')} tags={d.get('tags')}"
            )

        # Collect document_ids
        document_ids: list[str] = []
        for d in doc_items:
            did = d.get("document_id") or d.get("documentId") or d.get("id")
            if isinstance(did, str) and did:
                document_ids.append(did)

        # 2) Pull memory units list (paged) and filter by chunk_id containing the session id
        matched_units: list[dict[str, Any]] = []
        offset = 0
        while offset < args.limit:
            url = f"{base}/v1/default/banks/{_q(bank)}/memories/list?limit=200&offset={offset}"
            page = _get_json(url)
            items = page.get("items", [])
            if not items:
                break
            for it in items:
                chunk_id = it.get("chunk_id") or ""
                if isinstance(chunk_id, str) and session_id in chunk_id:
                    matched_units.append(it)
            offset += len(items)
            if offset >= page.get("total", offset):
                break

        print(f"memory units matched by chunk_id contains session_id: {len(matched_units)}")

        # 3) Summarize + print samples
        by_type: dict[str, list[dict[str, Any]]] = {}
        for it in matched_units:
            by_type.setdefault(str(it.get("fact_type") or "unknown"), []).append(it)

        for t, items in sorted(by_type.items(), key=lambda kv: len(kv[1]), reverse=True):
            leaks = sum(1 for it in items if _has_thinking_leak(it.get("text") or ""))
            print(f"\nTYPE={t} count={len(items)} thinking_leak_hits={leaks}")

            for it in items[:5]:
                txt = (it.get("text") or "").replace("\n", " ")
                if len(txt) > 240:
                    txt = txt[:240] + "..."
                print(
                    f"  - id={it.get('id')} consolidated_at={it.get('consolidated_at')} failed_at={it.get('consolidation_failed_at')}\n    text={txt}"
                )

        # 4) If we found documents, dump their chunks (this is the raw input to extraction)
        if document_ids:
            did = document_ids[0]
            print("\n--- document chunks (first matched document) ---")
            chunks_url = f"{base}/v1/default/banks/{_q(bank)}/documents/{_q(did)}/chunks?limit=50"
            try:
                chunks = _get_json(chunks_url)
                chunk_items = chunks.get("items", []) if isinstance(chunks, dict) else []
                print(f"document_id={did} chunks={len(chunk_items)}")
                for ch in chunk_items[:5]:
                    preview = (ch.get("text") or "").replace("\n", " ")
                    if len(preview) > 240:
                        preview = preview[:240] + "..."
                    print(
                        f"  - chunk_id={ch.get('chunk_id')} tokens={ch.get('tokens')} truncated={ch.get('truncated')}\n    text={preview}"
                    )
            except Exception as exc:
                print(f"failed to fetch chunks for document_id={did}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
