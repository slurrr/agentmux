# Current Goal
Stabilize the Phase-1 benchmark so launch, serving telemetry, and quality reporting are consistent enough to trust full-vs-variant comparisons.

# Current State
- `agentmux bench --launch` exists and now waits for startup log readiness before benchmarking.
- Teardown was tightened in:
  - `src/agentmux/runtime.py`
  - `src/agentmux/runner.py`
  - shutdown now does `SIGTERM` -> wait -> `SIGKILL` fallback -> wait.
- Judge behavior was redesigned:
  - deterministic score/pass-fail is authoritative again
  - judge is advisory only
  - one batched judge call per run, not per case
  - judge returns only:
    - `deterministic_score_fit`
    - `deterministic_notes`
    - optional `quality_note`
- `bench-show` improvements now include:
  - human-readable startup/runtime sections
  - requested vs resolved verification for dtype / kv cache dtype / max model len / chunked prefill / quantization
  - judge display as `Judge Verdict` / `Judge Note`
  - case sorting puts judge disagreements first, then failures, then passes
- Prometheus runtime capture now has two layers:
  - before/after serving deltas for counters
  - during-serving scrapes every 0.5s for gauges
- Prometheus serving output now includes useful counter-derived metrics:
  - requests completed
  - prompt / generation tokens
  - mean TTFT / E2E / queue / inference / prefill / decode
  - mean request time per output token
  - mean inter-token latency
  - mean prompt/output tokens per request
  - prefix cache queries / hits
  - prompt tokens cached
- Current gauge finding:
  - request-running gauge looks useful
  - KV cache usage gauge still stays at `0%` during active scrapes on this vLLM build / workload, so it is likely not trustworthy here
- Recent real run with batched judge:
  - `~/runs/agentmux/benchmarks/20260503-105403-qwen3_5-fp8-bench-ghosty-local-agent.json`
- This morning's successful fp8 launches were startup-consistent:
  - `dtype=torch.bfloat16`
  - `kv_cache_dtype=auto`
  - `quantization=compressed-tensors`
  - `FLASH_ATTN`
  - `62,304` KV tokens
  - compile cache hit
  - model load ~`12.72 GiB`
- This morning's intermittent launch failures were real runtime failures, not bench rendering bugs:
  - segfaults and CPU-side `MemoryError` during multimodal processor init

# Decisions
- Do not let judge affect case score or benchmark score.
- Keep judge on all cases, but as one batched advisory review call per run.
- Prefer Prometheus data over vLLM logger data for runtime truth whenever possible.
- Keep vLLM logger throughput/cache lines as secondary evidence only; do not expand reliance on them.
- Treat Prometheus counter deltas as the primary serving/runtime metrics for Phase 1.
- Treat the current KV cache usage Prometheus gauge as suspicious unless a later verification pass proves otherwise.

# Open Problems
- Need to verify whether stricter teardown reduces the intermittent first-launch failure pattern in repeated `--launch` runs.
- Need a targeted Prometheus verification pass for KV/cache-related metrics if we want a trustworthy cache-usage signal before Phase 2.
- Throughput still varies across runs more than desired; likely next tightening is a slightly longer / steadier serving window, not more logger dependence.

# Resume Instructions
1. Re-run `agentmux bench qwen3_5-fp8-bench --launch` several times and check whether stricter stop/wait reduces the fail-then-succeed pattern.
2. Inspect the newest result with `agentmux bench-show` and confirm:
   - batched judge payloads are present
   - judge disagreements sort first
   - Prometheus serving metrics look stable
3. If launch is still flaky, investigate process cleanup / resource reuse around failed launches before changing benchmark semantics again.
4. If launch is improved, do the next narrow pass on trustworthy Prometheus KV/cache metrics rather than adding more custom runtime heuristics.
