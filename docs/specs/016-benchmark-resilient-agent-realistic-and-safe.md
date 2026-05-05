# Spec: resilient benchmark for realistic agent use, truthful thinking metrics, and safe accounting

## Problem

The benchmark should reflect how these models are actually used as agents:

- models should be allowed to think
- tool use should remain part of the real workflow
- concise-answer cases should still be judged on the final answer, not on hidden reasoning runway
- failures should not kill the whole run
- metrics should be truthful, not just precise-looking
- accounting and tokenization should be safe and explicit

Right now the bench has three major problems:

1. A single request timeout can abort the entire run.
2. The current “thinking” metric is not actually separating tool-call overhead from reasoning.
3. Token counting and failure handling are not observable enough to debug a bad run.

## Scope

This spec covers:

- resilient per-case benchmark execution
- partial result generation after recoverable failures
- truthful thinking-token accounting for tool-capable cases
- explicit observability for failures, fallbacks, and timing
- safe tokenizer selection and fallback reporting
- keeping the benchmark realistic for agent workflows

It does not cover:

- redesigning the whole benchmark suite
- adding new judge models or new judging policy
- suppressing model thinking in templates
- inventing a new abstract metrics schema beyond what is needed here

## Principles

1. **Realistic agent environment**
   - The benchmark should behave like an actual agent workload.
   - Thinking should remain enabled.
   - Tool use should remain real, not simulated away.

2. **Truthful metrics**
   - Report what the model actually did.
   - Do not label tool-call overhead as thinking.
   - If the code cannot measure something exactly, say so.

3. **Safety first**
   - Do not execute unsafe remote code just to count tokens.
   - Prefer explicit local tokenizer sources.
   - Avoid silent fallbacks that hide uncertainty.

4. **Resilience over fail-fast**
   - A single request timeout must not kill the whole run.
   - Recoverable failures should be recorded per case and the benchmark should continue.

## Requirements

### Resilience

1. Each benchmark case must be isolated enough that a timeout or request failure in one case does not abort later cases.
2. Serving and workspace cases must record failures per request or per turn.
3. The benchmark must still write a result artifact when some cases fail.
4. The final result must indicate whether the run is complete, partial, or failed.
5. The CLI must present partial results clearly instead of only exiting on the first error.

### Thinking metric

6. The benchmark must not treat all non-visible completion tokens as thinking.
7. For tool-capable cases, the metric must subtract tool-call serialization tokens from completion usage where possible.
8. The metric should also subtract visible final-answer tokens.
9. The result must clearly state how the thinking number was computed.
10. If exact tool-call token accounting is unavailable, the result must say that the number is estimated or incomplete.

### Observability

11. Each failed case should record:
    - case id
    - case group
    - request or turn index
    - error class
    - error message
    - elapsed time
    - timeout used
12. `bench-show` should surface the failure context in a readable way.
13. The saved JSON should contain enough data to debug a failure without rerunning blindly.

### Safety

14. Token counting should prefer explicit local tokenizer assets when present.
15. Token counting should not rely on `trust_remote_code=True` unless there is no safe alternative and the choice is explicit.
16. If token counting falls back to a heuristic, that fallback must be recorded in the result.
17. Unsafe or ambiguous tokenizer resolution must never be hidden.

## Constraints

- Keep the benchmark aligned with actual agent use.
- Keep thinking enabled.
- Keep tool use real.
- Keep the benchmark useful for comparing models, but not at the cost of pretending to measure something it does not.
- vLLM usage data is limited; the implementation must work with what vLLM actually returns.
- The code should prefer explicit provenance over inferred precision.

## Proposed implementation shape

### 1) Per-case failure containment

Wrap each benchmark case in its own failure boundary.

For each case:
- catch request timeout / request failure
- capture the case outcome as failed
- keep going to later cases
- preserve any partial response or partial tool trace if available

For workspace cases:
- catch failures per turn
- keep the conversation trace up to the failure
- still write a case result describing where it stopped

For serving cases:
- capture errors per request cell or per stream request
- do not let one slow prompt abort all benchmark collection

### 2) Partial result writing

The benchmark result file should be written even if the run is only partially complete.

The saved output should include:
- a top-level run status
- a list of completed cases
- a list of failed cases or failures embedded in each case
- the last exception if the whole run aborts for an unrecoverable reason

### 3) Truthful thinking accounting

Replace the current single derived number with a more honest breakdown.

For tool-capable cases, try to record:
- total completion tokens from vLLM
- visible response tokens
- tool-call tokens
- residual thinking tokens

If exact tool-call token counts are not available from the server:
- record that the value is estimated
- record the source used for the estimate
- do not present the number as exact

For pure text cases, the benchmark may use a simpler completion-minus-visible-response calculation if that is all that is available.

### 4) Safe tokenizer selection

Token counting should resolve in this order, if available:

1. explicit tokenizer asset from the service/stack
2. explicit launcher/runtime tokenizer configuration
3. local model tokenizer path
4. a clearly marked heuristic fallback

The implementation must record which path was used.
If a tokenizer cannot be loaded safely, the result should note the failure instead of silently pretending precision.

### 5) Debuggable output

`bench-show` should show, for each failed case:
- what failed
- where it failed
- how long it ran
- whether the failure was a timeout or other request error

For thinking metrics, the summary should show:
- the source of the metric
- whether the number is exact or estimated
- enough per-case detail to spot outliers

### 6) Preserve realism

Do not reintroduce the old “everything must fit in one tiny max_tokens cap” model just to force short outputs.
Instead:
- keep model thinking enabled
- keep agent/tool behavior intact
- let the scoring and accounting reveal whether the model over-generated or over-thought

## Priorities

### P0
- one request timeout must not kill the entire run
- partial results must be written when recoverable failures occur
- failures must be recorded per case and per turn/request

### P1
- thinking accounting must exclude tool-call tokens where possible
- thinking output must be labeled as exact vs estimated
- tokenizer provenance must be explicit and safe

### P2
- `bench-show` should make failures and metric provenance easy to inspect
- remove dead code and unused parameters after the behavioral fixes land

## Acceptance criteria

1. A timed-out request in one case does not prevent later cases from running.
2. The benchmark still writes a result file when some cases fail.
3. `bench-show` can explain which cases failed and why.
4. The thinking metric no longer counts tool-call tokens as pure thinking when tool-call token data is available.
5. The result explicitly says whether thinking tokens are exact or estimated.
6. Token counting uses a safe, explicit local source when available.
7. No unsafe tokenizer loading path is used silently.
8. The benchmark remains useful for realistic agent workflows with thinking and tools enabled.

## Open Questions

- Do we want a hard distinction between `partial` and `failed`, or should `failed` simply mean “some cases failed but the run completed”? 
- What is the best available source of tool-call token accounting in this repo’s vLLM setup?
- Should the default summary include the thinking metric, or only the detailed case output?
- Which tokenizer source is authoritative when both a service model path and a tokenizer asset exist?
