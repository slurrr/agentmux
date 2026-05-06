# bench-show v2 UI (reference)

This document describes the intended **human-facing CLI formatting** for `agentmux bench-show`.
It is aesthetic guidance (layout, density, tables), not a schema/contract spec.

Invariants:
- Default output is compact.
- Perf is the main event.
- Only **failures** and **judge-flagged** cases expand into prompt/response blocks.
- Prompt/response are truncated by default; `--full` disables truncation.

## Default layout

### 1) Header card
- Large title rule (80-ish width).
- Align key/value fields.
- Include bench overrides (e.g. max-num-seqs override) and perf status/artifacts.

Suggested fields:
- stack + profile
- run status + failed case count + judge flagged count
- result path
- model path + served model name
- dtype / kv cache dtype / max model len / tool parser / reasoning parser
- bench overrides (if applied)
- perf status + artifacts directory

### 2) 📊 PERF (ENDPOINT)
Perf uses the 2-lane profile:
- Lane A (interactive): c=1, n=12, max_tokens=512
- Lane B (sustained): c=2/4/8/16, n=12 each, max_tokens=2048

Default rendering shows:

#### Lane A table (includes tok/s)
Columns (default): p50 / p95 / p99 / mean
Rows:
- TTFT (s)
- Latency (s)
- Output tok/s

Plus a short Errors line (e.g. `Errors: 0/12 (0.0%)`).

#### Lane B table
Columns (default): Conc / tok/s / TTFT p95 / Lat p95 / Err rate / Notes
- Notes column contains **auto-derived tags only** from observed errors (no free text).

Degradation block (default):
- TTFT p95 @16 / @1
- Lat  p95 @16 / @1

### 3) ✅ PROMPT BENCH
Compact scorecard table:
- drills (no-tools): passed/total
- workspace/tool outcomes: passed/total
- invalid tool calls

Include pointer to prompt reference:
- `docs/reference/bench-prompts.md`

### 4) ⚠ FAILURES
Expanded blocks for each failing case.

Block format:
- Header line: status glyph + case id + group + score
- Deterministic failures (bulleted)
- Optional workspace summary lines (changed files, failing checks)
- Prompt subheader + indented body (truncated)
- Response subheader + indented body (truncated)
- If truncated, add a separate marker line: `[truncated; use --full]`

Ordering:
- failures first

### 5) 🧪 JUDGE-FLAGGED
Expanded blocks for each judge-flagged case.
Same block format as failures, but includes:
- judge flag reason + comment (per judge spec)

Ordering:
- judge-flagged after failures

## Flags
- `--full`: do not truncate prompt/response
- `--perf-full`: pretty-print normalized perf summary JSON
- `--case <id>`: show one case in detail
- `--failures-only`: only failures
- `--judge-flagged-only`: only judge flagged

## Truncation policy
- Default truncation is by characters:
  - prompt: 1200 chars
  - response: 1200 chars
- Marker is a separate line:
  - `[truncated; use --full]`
