# Implementation Plan: Hindsight-first env split

## Goal

Move Hindsight to its own dedicated environment first so it can be upgraded independently, while keeping the current shared env and current `vllm` service path intact as fallback.

## Plan

### 1. Add the smallest service runtime override needed for Hindsight
Files:
- `src/agentmux/config.py`
- `src/agentmux/runner.py`
- one real Hindsight-backed mux under `mux/`
- one example mux if needed

Steps:
- add the minimum manifest/runtime field needed to tell a service to launch from a different env or executable path
- keep the default launch path unchanged for services that do not opt in
- use the new field only for the Hindsight service in this pass
- make `render` show the real command/env boundary that will be used

Done when:
- Hindsight can be configured to launch from a dedicated env
- non-Hindsight services still launch exactly as they do today unless explicitly changed
- `agentmux render <stack>` clearly shows the Hindsight-specific runtime path

### 2. Create and validate a dedicated Hindsight env
Files:
- repo-local env/bootstrap docs if needed
- Hindsight service manifest/config wiring

Steps:
- create a new dedicated Hindsight environment
- install the target Hindsight version there
- keep the current shared env untouched
- validate that the new Hindsight env can start the memory service successfully
- keep the current local topology the same: local `vllm`, local Hindsight

Done when:
- the Hindsight service starts from its new env
- the current shared env remains available as rollback baseline
- the stack can still be launched from one `agentmux up`

### 3. Wire one real stack to use the dedicated Hindsight env
Files:
- the real Hindsight-backed mux you want to keep using
- tests covering render/plan behavior

Steps:
- point the memory service in the real stack at the dedicated Hindsight env
- keep the `vllm` service on the current shared env for now
- verify that dependency ordering and readiness behavior still work
- verify that runtime output remains understandable

Done when:
- one real stack launches with mixed envs successfully
- `render` and runtime behavior make the env split obvious and inspectable

### 4. Cover the new shape with focused tests
Files:
- `tests/test_config.py`
- `tests/test_runner.py`
- `tests/test_main.py` if render output changes materially

Steps:
- add focused coverage for the new per-service runtime override
- keep tests narrow; only cover the Hindsight-first path in this pass
- verify that services without overrides preserve current behavior

Done when:
- targeted tests pass
- the new runtime field is proven to affect launch behavior rather than act as dead metadata

### 5. Validate and stop
Steps:
- run the smallest relevant checks
- validate one real stack run
- stop after the Hindsight split is stable
- do not start the `vllm` env split in this pass

Done when:
- Hindsight is upgraded and isolated
- current `vllm` behavior remains unchanged
- the repo is ready for the later `vllm 0.20.x` env split

## Execution order
1. Add minimal per-service runtime override
2. Create dedicated Hindsight env
3. Wire one real Hindsight stack to it
4. Add focused tests
5. Run targeted validation

## Non-goals for this pass
- moving `vllm` to its own env yet
- upgrading `vllm`
- TEI integration
- dedicated CPU host work
- generalized multi-host orchestration
