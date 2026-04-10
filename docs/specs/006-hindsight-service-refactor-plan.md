# Implementation Plan: Hindsight service refactor

## Goal
Replace the special `[stack.memory]` sidecar path with normal service-shaped Hindsight under `[services.<name>]`, while keeping the refactor small and aligned with the repo’s existing multi-service model.

## Plan

### 1. Normalize the manifest contract around services
Files:
- `src/agentmux/config.py`
- `mux/core/memory_omnicoder_9b.toml`
- `mux/examples/example_hindsight_memory.toml`

Steps:
- remove `MemorySpec` and `StackSpec.memory`
- make `ServiceSpec` engine-aware enough to represent both `vllm` and `hindsight`
- validate fields by engine instead of assuming every service is vLLM-shaped
- require `llm_service` for `engine = "hindsight"`
- reject `[stack.memory]` rather than carrying compatibility logic
- convert the real memory stack and example manifest to `[services.memory]`

Done when:
- `resolve_stack("pi_ghosty")` and `resolve_stack("example_hindsight_memory")` parse successfully
- Hindsight appears as a normal entry in `stack.services`

### 2. Collapse launch planning into one service list
Files:
- `src/agentmux/runner.py`
- `src/agentmux/main.py`

Steps:
- remove `MemoryLaunchPlan`
- make `StackLaunchPlan` carry only `services`
- add a hindsight service planner that derives env from `llm_service`
- preserve external Hindsight reuse detection on the configured port
- make rendered output treat Hindsight like any other named service

Done when:
- `agentmux render example_hindsight_memory` shows `main` and `memory`
- there is no separate top-level memory plan branch in code

### 3. Make startup ordering service-directed
Files:
- `src/agentmux/runner.py`

Steps:
- launch services in manifest order
- when a Hindsight service declares `llm_service`, wait for that referenced vLLM service to become ready before starting Hindsight
- keep the existing Hindsight retry loop and readiness probe

Done when:
- `agentmux up pi_ghosty` still launches vLLM first and then Hindsight
- Hindsight startup failure points at the actual dependent service/log path

### 4. Update docs and examples to the new source of truth
Files:
- `mux/README.md`
- `docs/specs/005-hindsight-as-service.md`
- example manifests under `mux/examples/`

Steps:
- document Hindsight as `engine = "hindsight"`
- remove `[stack.memory]` from active docs
- keep the multi-service example as the mental model
- align example track names with the real `mux/examples/` directory

Done when:
- docs no longer present sidecar-shaped memory as supported
- examples are loadable by the current parser

### 5. Cover the new shape with focused tests
Files:
- `tests/test_config.py`
- `tests/test_runner.py`
- `tests/test_main.py`

Steps:
- update track expectations from `archive` to `examples`
- add a config test for `engine = "hindsight"`
- add a runner test that checks derived Hindsight env and dependency wiring
- keep existing multi-service vLLM coverage

Done when:
- targeted tests pass under `pytest`

## Execution order
1. Config/model refactor
2. Runner/CLI refactor
3. Manifest/example updates
4. Test updates
5. Targeted test run
6. Follow-up doc cleanup if any stale sidecar references remain

## Non-goals for this pass
- generalized engine plugins
- per-service smoke matrix
- systemd promotion
- backward compatibility for `[stack.memory]`
