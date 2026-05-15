# Audit: Gemma-4-e4b as Hindsight memory LLM (pi-ghosty)

Date: 2026-05-13

This document captures the concrete investigation steps and findings used to validate that **Gemma-4-e4b** (served as `gemma-4-e4b-memory`) is safe and effective as the **Hindsight memory LLM** for pi-ghosty.

It is intentionally pragmatic: how to reproduce the inspection, what to look for, and what was observed.

---

## Scope / Goal

Validate, using **ground-truth DB/API inspection** (not guesses from UI output), that:

- “Thinking/planning/meta” text is **not stored** into Hindsight memory units.
- Structured extraction/consolidation calls are succeeding.
- We can reliably inspect **actual stored shapes + content** for a specific pi-ghosty session.

This audit does **not** attempt to redesign Hindsight dedupe logic or build a full eval harness.

---

## Relevant Services

- vLLM (OpenAI-compatible): `http://127.0.0.1:8002/v1`
  - Model served: `gemma-4-e4b-memory`
- Hindsight API: `http://127.0.0.1:8888`
  - Banks:
    - `pi-ghosty-personal`
    - `pi-ghosty-procedural`

---

## Key Backend Config Decisions (memory stacks)

Applied to the Gemma memory mux (`mem_gem_hs`):

- Disable thinking by default:
  - `--default-chat-template-kwargs '{"enable_thinking":false}'`
- Force structured outputs via xgrammar:
  - `--structured-outputs-config '{"backend":"xgrammar","reasoning_parser":"gemma4","enable_in_reasoning":false,"disable_any_whitespace":false}'`
- Disable auto tool choice for memory-serving stability:
  - `enable_auto_tool_choice = false`
- Prevent request-time chat template overrides (important for OpenWebUI parity):
  - `--no-trust-request-chat-template`

Note: OpenWebUI may still display “thinking-like” text depending on how it renders `reasoning` fields.

---

## Critical Finding: reasoning vs content (vLLM)

Direct OpenAI request against vLLM showed:

- `message.content` was clean.
- `message.reasoning` contained meta/planning text of the form:
  - “The user has given … I should respond …”

Implication:

- UI clients (e.g. OpenWebUI) may be rendering `reasoning` inline, making it look like the model is “leaking thinking”.
- The real risk is **pipeline components concatenating reasoning into stored text**.

Validation approach below checks whether such reasoning text is actually persisted into Hindsight DB.

---

## Ground-truth Inspection Approach (Hindsight DB via API)

### Why: don’t rely on receipts or recall

- `recall.json` and injection artifacts can lag or omit raw storage shapes.
- The authoritative truth is what Hindsight stored in its DB, accessible via Hindsight API.

### Core endpoints used

- List memory units:
  - `GET /v1/default/banks/{bank_id}/memories/list`
- Get a specific memory unit (full shape, better than list view):
  - `GET /v1/default/banks/{bank_id}/memories/{memory_id}`
- List documents (used to confirm a session document exists):
  - `GET /v1/default/banks/{bank_id}/documents?q=<session_id>`
- List document chunks:
  - `GET /v1/default/banks/{bank_id}/documents/{document_id}/chunks`

### Session isolation: filter by `chunk_id` contains session_id

pi-ghosty uses chunk ids that embed the corroborator session id:

- `.../corroborator/<sessionId>/<role>_<N>`

So you can reliably isolate *facts extracted from that session* by filtering memory units where:

- `session_id in memory_unit.chunk_id`

This works even when units are consolidated later.

---

## Helper Script: inspect Hindsight units for a session

Script created during this audit:

- Path: `scripts/hs_inspect_session.py`

What it does:

- Finds documents matching the session id.
- Lists memory units via `/memories/list` (paged).
- Filters units to those whose `chunk_id` includes the session id.
- Groups by `fact_type` and prints sample texts.
- Scans for “thinking leakage” patterns in stored `text`.

Example usage:

```bash
python scripts/hs_inspect_session.py \
  --base-url http://127.0.0.1:8888 \
  --bank pi-ghosty-personal \
  --bank pi-ghosty-procedural \
  --session-id <SESSION_ID> \
  --limit 800
```

### Inspect full observation shapes

The list view can omit fields / show partial projections.
For observations, use:

```bash
curl -sS \
  http://127.0.0.1:8888/v1/default/banks/pi-ghosty-personal/memories/<OBS_ID> \
  | python -m json.tool
```

---

## Helper Script: summarize memory-log performance metrics

Script added during this audit:

- Path: `scripts/hs_log_metrics.py`

What it does:

- Extracts retain LLM call durations from lines like:
  - `slow llm call: scope=retain_extract_facts ... time=...s`
- Extracts consolidation *per-memory* averages from lines like:
  - `[CONSOLIDATION] ... avg=...s/memory`

Example usage:

```bash
python scripts/hs_log_metrics.py /home/poop/runs/agentmux/logs/*-mem_gem_hs-memory.log
```

Interpretation note:

- The consolidation `avg=...s/memory` is the most apples-to-apples number.
- Retain durations are per LLM call (still useful over longer runs, but workload-dependent).

---

## Findings from Session Inspection

### Session inspected

- `77f4b16c-2087-41e6-b6bb-cc95ab454941`

### Stored extracted facts (session-bound, via chunk_id)

- Facts for that session looked structurally consistent.
- No “I should respond …” / “The user has given …” / `<|think|>` patterns were found in stored unit `text`.
- `occurred_start` / `occurred_end` were null across units (temporal grounding gap).

### Observations vs facts

- Observations retrieved via `/memories/list?type=observation` can look “thin” (e.g. empty `entities`, null `chunk_id`).
- The **full record** via `/memories/{id}` shows observations do have:
  - `entities` (as a list)
  - `tags`
  - `mentioned_at` / `date`
  - provenance linking:
    - `source_memory_ids`
    - `source_memories`

### Duplicate observation IDs with identical text

A pair of personal observations had identical `text` but different IDs.
When fetched with `GET /memories/{id}`, they differed primarily in:

- `date` (creation/earlier timestamp differed)
- `source_memory_ids` (one had a superset of sources)
- minor `entities` differences

Interpretation:

- This looks like parallel observation clusters accumulating provenance over time.
- Duplicate injection is likely a **selection/collapse** issue (how injected observations are chosen), not a Gemma capability issue.

---

## What to Watch Going Forward (Model-facing)

1) **Reasoning leakage risk**
   - vLLM may return `message.reasoning` even when `enable_thinking=false`.
   - The contract we care about: Hindsight must not store reasoning text in memory `text`.
   - Periodically scan recent stored units for:
     - “I should respond”
     - “The user has given/sent”
     - `<|think|>`

2) **Temporal grounding**
   - `occurred_start/end` often null.
   - If time grounding matters later, investigate extraction prompt/schema usage.

3) **Observation list view vs detailed view**
   - Use `GET /memories/{id}` for true observation shape.

---

## Quick “Latest Session” Recipe

1) Use pi-ghosty normally, then locate latest corroborator session id:

```bash
ls -1dt /home/poop/runs/pi-ghosty/data/memory/receipts/corroborator/*/ | head -n 1
```

2) Inspect stored DB units for that session:

```bash
python scripts/hs_inspect_session.py \
  --base-url http://127.0.0.1:8888 \
  --bank pi-ghosty-personal --bank pi-ghosty-procedural \
  --session-id <SESSION_ID>
```

3) If you see duplicates in observations, fetch detailed records:

```bash
curl -sS http://127.0.0.1:8888/v1/default/banks/pi-ghosty-personal/memories/<OBS_ID> | python -m json.tool
```

---

## Conclusion

Gemma-4-e4b appears fully capable for Hindsight memory extraction/consolidation under the current configuration.
The remaining issues observed are primarily about:

- client/UI rendering of `reasoning` vs `content`
- Hindsight observation clustering / injection selection
- temporal grounding completeness

This audit provides a repeatable, low-overhead method to validate DB truth as you continue real-world use.
