# Current Goal
Refactor Hindsight from special `[stack.memory]` sidecar shape into a normal service-shaped engine in `agentmux`.

# Current State
- Added refactor spec: `docs/specs/005-hindsight-as-service.md`.
- Added implementation plan: `docs/specs/006-hindsight-service-refactor-plan.md`.
- `src/agentmux/config.py` no longer has `MemorySpec` / `StackSpec.memory`.
- Service parsing is now engine-aware for:
  - `engine = "vllm"`
  - `engine = "hindsight"`
- `[stack]` now rejects unsupported fields, so `[stack.memory]` is no longer part of the active manifest contract.
- `src/agentmux/runner.py` now uses one `ServiceLaunchPlan` list; no separate memory launch plan remains.
- Hindsight launch/reuse logic now lives in the `engine = "hindsight"` service path with `llm_service` dependency wiring.
- `mux/core/memory_omnicoder_9b.toml` was converted to:
  - `[services.memory]`
  - `engine = "hindsight"`
  - `llm_service = "main"`
- `mux/examples/example_hindsight_memory.toml` was converted to service-shaped Hindsight.
- Example track names were aligned to the real `mux/examples/` directory.
- Updated docs/tests for the new service shape.
- Targeted checks passing:
  - `pytest tests/test_config.py tests/test_runner.py tests/test_main.py`
  - `uv run agentmux render pi_ghosty`

# Decisions
- Do not keep `[stack.memory]` compatibility; migrate the one real stack instead.
- Keep the refactor minimal: engine-aware services, not a generic engine plugin system.
- Hindsight should derive its LLM backend from explicit `llm_service`, not implicitly from `primary_service`.

# Open Problems
- Some historical docs still describe the old sidecar shape:
  - `docs/specs/004-hindsight-embedded-server.md`
  - `docs/decisions/0005-hindsight-local-memory-service.md`
  - `docs/decisions/0006-memory-sidecar-shape-is-transitional.md`
- `smoke.py` still only probes `primary_service`, which is acceptable for now but still vLLM-primary in workflow.
- Full test suite has not been run yet; only targeted tests were run.

# Resume Instructions
1. Review and clean up stale sidecar language in:
   - `docs/specs/004-hindsight-embedded-server.md`
   - `docs/decisions/0005-hindsight-local-memory-service.md`
   - `docs/decisions/0006-memory-sidecar-shape-is-transitional.md`
2. Run broader validation from repo root:
   - `pytest`
3. If behavior checks are needed, inspect:
   - `src/agentmux/config.py`
   - `src/agentmux/runner.py`
   - `mux/core/memory_omnicoder_9b.toml`
4. If continuing implementation, next likely follow-up is making CLI/docs output a bit more engine-aware without adding abstraction.
