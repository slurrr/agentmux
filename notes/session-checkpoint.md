# Current Goal
Refactor Hindsight into a normal service shape, stabilize local stack behavior, and keep enough session context to resume quickly.

# Current State
- Hindsight was refactored from `[stack.memory]` into `[services.memory]` with `engine = "hindsight"`.
- Added specs:
  - `docs/specs/005-hindsight-as-service.md`
  - `docs/specs/006-hindsight-service-refactor-plan.md`
- `src/agentmux/config.py` now parses engine-aware services and no longer uses `MemorySpec`.
- `src/agentmux/runner.py` now plans one flat service list; Hindsight launch/reuse logic lives in the hindsight service path.
- `mux/core/memory_omnicoder_9b.toml` was converted to service-shaped memory, then the whole `[services.memory]` block was commented out temporarily for no-memory testing.
- Hindsight backend review against local docs concluded:
  - current CPU-first local setup is basically fine
  - missions are better treated as bank/app config than backend infra env
  - do not raise `HINDSIGHT_API_RECALL_MAX_QUERY_TOKENS`; fix recall query construction client-side
  - explicit provider pins and optional reranker bucket batching are the only backend tweaks really worth considering
- Latest investigated failure was **not** a Hindsight issue.
- Latest `pi-vera` failure log:
  - `/home/poop/runs/agentmux/logs/20260414-192655-pi-vera-llm.log`
  - failure is vLLM startup for Gemma4 with fp8 KV cache + `calculate_kv_scales = true`
  - key error: `AssertionError: A non 1.0 q_scale is not currently supported.`
  - log also shows Gemma4 forcing `TRITON_ATTN`, which is part of the failing backend path
- Conclusion for that failure:
  - not OOM / not generic KV cache exhaustion
  - likely fix is to remove `calculate_kv_scales = true`
  - if still needed, next fallback is removing `kv_cache_dtype = "fp8"` for that stack/model

# Decisions
- Do not keep `[stack.memory]` compatibility; migrate manifests to service-shaped memory directly.
- Treat Hindsight as an optional service; clients should decide when to call it.
- Keep backend Hindsight config minimal and infra-focused; memory semantics like missions belong closer to app/bank config.
- Keep recall query max tokens at the default `500`; oversized recall queries should be fixed client-side.

# Open Problems
- `agentmux up` currently no longer mirrors/follows primary vLLM startup logs for single-service stacks unless another service depends on them. This was identified but not fixed in this session.
- Historical docs still mention the old Hindsight sidecar shape:
  - `docs/specs/004-hindsight-embedded-server.md`
  - `docs/decisions/0005-hindsight-local-memory-service.md`
  - `docs/decisions/0006-memory-sidecar-shape-is-transitional.md`
- `pi-vera` mux still needs the actual manifest fix for the Gemma4 fp8/q_scale failure.

# Resume Instructions
1. For the Gemma4 startup failure, inspect and edit the `pi-vera` mux/service args to remove `calculate_kv_scales = true` first.
2. Re-test startup and, if it still fails, remove `kv_cache_dtype = "fp8"` for that model.
3. If returning to Hindsight backend tuning, keep changes limited to backend-owned knobs only (provider pins, optional reranker batching), and leave missions/query policy to app or bank config.
4. If resuming `agentmux` UX work, the next code issue is restoring startup log following/readiness handling for single-service stacks.
