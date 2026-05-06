# Spec: bench-show v2 + perf defaults + bench launch overrides

## Status
Draft (locked decisions captured from iteration).

## Context
We are reframing the benchmark so that automated scoring is truly deterministic.
- Deterministic scoring remains for hard constraints and workspace/tool outcomes.
- Judge behavior is defined separately (see `docs/specs/019-judge-audit-json-and-bench-show-suspicion-driven-view.md`).
- `bench-show` must be redesigned to match the new trust model.
- Endpoint perf is the most important part of the bench and must be **on by default**.

---

## A. Perf defaults (endpoint perf is on by default)

### A1. Default behavior
- The benchmark always runs **endpoint perf** unless explicitly disabled via a CLI flag.
- Perf is not gated behind hidden environment variables.

### A2. Perf profile ("2-lane" endpoint perf)
Perf runs as two lanes against the launched OpenAI-compatible endpoint.

#### Lane A — interactive feel
- concurrency: 1
- requests: 12
- max output tokens: 512

Reports (headline):
- TTFT p50/p95
- end-to-end latency p50/p95
- output tok/s p50/p95
- error rate

#### Lane B — sustained load
- concurrency sweep: 2, 4, 8, 16
- requests per concurrency: 12
- max output tokens: 2048

Reports (headline):
- aggregate throughput (tok/s) per concurrency
- TTFT p95 per concurrency
- error rate per concurrency
- degradation ratios (e.g. TTFT_p95@16 / TTFT_p95@1)

### A3. Offline perf
- Offline perf is not part of the default bench run.
- It may be added later as an opt-in command.

---

## B. Bench launch override (server-side)

### B1. Override rule
For benchmark runs, agentmux launches vLLM with:
- `--max-num-seqs 32`

Rationale:
- The perf profile standardizes concurrency up to 16.
- Some stacks declare low `max-num-seqs` (e.g. 10 or 1), which would cause queueing/rejection and distort perf.
- This repo owns the serving command composition; it is reasonable for bench mode to apply bench-specific overrides.

### B2. Scope
- The override applies to the **entire bench run** (launch once).

### B3. Capture
The run JSON must capture:
- the bench override(s) applied
- before/after values (if present in manifest)
- a reason string

---

## C. bench-show v2 (default output)

### C1. Default output goals
- Ultra-compact.
- Shows the most important run-level info first.
- Shows perf immediately under the summary.
- Does not dump all cases.
- Only expands details for:
  - deterministic failures
  - judge-flagged cases (per spec 019)

### C2. Default output structure

1) **Header**
- stack name + profile
- result path
- timestamp (if present)
- run status
- model path + served model name
- dtype / kv cache dtype / max model len
- tool call parser + reasoning parser
- bench launch overrides summary (e.g. `max-num-seqs: 10 -> 32 (bench override)`)

2) **Perf (endpoint)**
- Lane A headline metrics
- Lane B headline metrics
- perf artifacts path(s)

3) **Deterministic bench scorecard**
- drills (no-tools): passed/total
- workspace/tool outcomes: passed/total
- invalid tool calls
- reference link: `docs/reference/bench-prompts.md`

4) **Failures (expanded blocks)**
For each failed case:
- case id + group + score
- prompt (truncated to 1200 chars)
- response (truncated to 1200 chars)
- deterministic failures list
- if workspace case: changed_files + failing file checks summary (if present)

5) **Judge-flagged (expanded blocks)**
For each judge-flagged case (even if passed deterministically):
- case id + group + score
- prompt (truncated to 1200 chars)
- response (truncated to 1200 chars)
- judge flag reason + comment (per spec 019)

Ordering:
- Failures first
- Judge-flagged second

Truncation:
- prompt and response are truncated by characters, max 1200 each, with a clear marker.
- `--full` prints untruncated prompt/response.

### C3. Flags
- `--full`: do not truncate prompt/response
- `--case <id>`: show full detail for one case
- `--failures-only`: only failures
- `--judge-flagged-only`: only judge-flagged
- `--json`: emit machine-readable JSON (unchanged)

### C4. Judge messaging
- bench-show must not print the old "judge unavailable, rerun" warning.
- If judge is disabled or absent, bench-show should either:
  - omit judge sections entirely, or
  - print a single concise line in the header (implementation choice).

---

## D. Open items (explicitly deferred)
- Whether to keep showing any legacy rubric_passes/failures in bench-show.
  - Current direction: keep them if useful, but they do not affect scoring.
- Offline perf command surface.
- Phase 3 manual sandbox session UX (covered elsewhere).
