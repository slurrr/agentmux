# Bug Fix Plan: benchmark timeouts, observability, and scoring integrity

## Problem

The current benchmark path is hard to debug and too fragile for long-running model calls.
A single request timeout aborts the whole run, the result file is often never written,
and the current accounting / scoring changes make some numbers look more precise than they are.

This plan is about making the bench usable and honest again, not adding more abstraction.

## What we observed

### Failure mode
- A single `requests` timeout bubbles out of the per-case code path.
- `main.py` catches it as a generic exception and exits the whole bench with `benchmark failed: ...`.
- There is no per-case failure recording or continue-on-error behavior.
- There is no durable partial result artifact when the run dies mid-benchmark.

### Runtime behavior
- The request timeout is per request, not a total bench timeout.
- The bench can still take a very long time because the request budget is large and the run includes many calls.
- The serving cases were changed from short caps to a much larger request budget, which changes what is being measured.
- The current thinking budget / max token setup is not a realistic substitute for the use case that wants concise answers with preserved reasoning.

### Observability gaps
- When a request fails, there is no per-case timing / payload summary in the output.
- There is no clear breadcrumb trail for which case, turn, or request caused the failure.
- The bench does not save enough intermediate state to diagnose slow or stuck cases after an abort.

### Accounting / scoring risks
- Derived thinking tokens are computed as `completion_tokens - visible_response_tokens`.
- That is useful for rough diagnostics, but it is not pure “thinking” in tool cases because tool-call serialization also consumes completion tokens.
- The tokenizer source can be wrong or fall back silently to whitespace counting.
- `trust_remote_code=True` is an unsafe assumption for a measurement-only tool.

## Priorities

### P0 — make the benchmark resilient to individual failures
This is the biggest functional bug.
A single request timeout, request failure, or tool-case failure must not kill the whole benchmark run.
The bench should continue on to the next case, record the failing case as a failure, and still produce a usable result file.

### P0 — make failures debuggable
The current bench is effectively opaque once it aborts.
We need per-case artifacts and enough timing detail to understand what happened without rerunning blind.
Partial reports are part of the fix, but not the whole fix.
The benchmark must keep running after recoverable failures so the partial report is actually worth something.

### P1 — separate “real bench behavior” from “measurement convenience”
The current request cap changes the shape of the workload.
We should preserve the intended use case instead of forcing everything through one giant completion budget.

### P1 — make token accounting explicit and safe
The benchmark should say which tokenizer it used and when it had to fall back.
It should not silently claim precise token counts when it is really guessing.

### P2 — make the thinking metric real by excluding tool-call tokens
The current metric is too crude if it treats all non-visible completion tokens as thinking.
For tool-capable cases, the bench should subtract tool-call serialization tokens from completion usage so the remaining metric is closer to actual thinking.

### P2 — remove dead code and unused parameters
Clean up the obvious leftovers after the behavior is fixed.

## Proposed fix plan

### 1) Add per-case error handling and partial-result recording
For each case:
- catch request timeout / request failure locally
- record a case failure entry instead of aborting the whole run
- include the exception class, message, case id, and turn index where possible
- continue to the next case unless the benchmark is in a truly unrecoverable state

For serving concurrency cells:
- capture future exceptions per request
- aggregate them into the serving result instead of failing the whole suite immediately

### 2) Write a partial result file even on failure
If the benchmark aborts halfway through:
- persist whatever result object exists
- include a top-level run status like `completed`, `partial`, or `failed`
- include the final exception details separately from the case results

### 3) Add real debug breadcrumbs
Add lightweight observability to the benchmark result and/or console output:
- case id
- group
- request index / turn index
- elapsed time for the request
- request timeout used
- token budget used
- whether a fallback tokenizer was used
- whether the request produced no final answer

Keep this human-readable in `bench-show` and structured in the JSON result.

### 4) Revisit the request budgeting strategy
The bench should reflect actual intended use.
Do not assume one large max-token cap is the right stand-in for “thinking allowed.”
The next decision should be explicit:
- either keep smaller caps for short-answer cases and separate them from reasoning allowance
- or switch to a scoring rule that treats overlong or overthinking responses as quality failures

The important thing is to stop mixing that decision into hidden implementation behavior.

### 5) Tighten token counting
- Prefer explicit tokenizer assets when present.
- Fall back to model tokenizer path only if that is the intended source.
- If tokenization falls back to whitespace counting, record that fact in the result.
- Avoid `trust_remote_code=True` unless the benchmark explicitly needs it.

### 6) Make the thinking metric exclude tool-call tokens
For tool-capable cases, the metric should be computed from completion usage minus visible answer tokens minus tool-call serialization tokens when those are available.
If exact tool-call token accounting is not available from the server, the code should say so explicitly instead of pretending the number is exact.
For workspace cases, separate accounting should at least distinguish:
- visible answer tokens
- tool-call tokens
- residual thinking tokens

## Risks

- Changing error handling may hide real failures if it becomes too permissive.
- Adding partial-result output could make it harder to distinguish a partial run from a valid run unless the status is explicit.
- Changing token budgeting could alter benchmark meaning, so any revision needs to be documented.
- More observability can create noisy output if it is not kept concise.

## Validation plan

Run the smallest meaningful checks first:

```bash
uv run pytest tests/test_bench.py -q
```

Then exercise the real benchmark path:

```bash
time uv run agentmux bench <stack-name>
uv run agentmux bench-show <result-file>
```

Add targeted tests for:
- one timed-out request inside a multi-case benchmark
- partial-result writing on failure
- tokenization fallback reporting
- per-case error continuation behavior
- workspace/tool cases with long reasoning and a final answer

## Open questions

- Should a single failed case fail the whole run, or should the run complete with a partial verdict?
- Should serving concurrency failures be aggregated as degraded scores or surfaced as case failures?
- Do we want derived thinking tokens in the default summary, or only in detailed output?
- Which tokenizer source is authoritative for a given stack when an explicit tokenizer asset is present?
