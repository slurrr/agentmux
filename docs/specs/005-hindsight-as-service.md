# Spec: Refactor Hindsight from sidecar shape to service shape

## Problem
Hindsight memory was added under `[stack.memory]` as a special sidecar shape.
That worked, but it drifted away from the repo’s actual model:

- stacks are supposed to contain one or more named services
- manifests already support multi-service stacks under `[services.<name>]`
- runtime state already records launched processes as a flat service list
- the current implementation still treats Hindsight as a special extra process outside the normal service model

The result is structural drift:

- `config.py` had separate `MemorySpec` and `ServiceSpec`
- `runner.py` had separate `MemoryLaunchPlan` and `_build_memory_plan()`
- `StackLaunchPlan` was split into `services + memory`
- the code said “multi-service”, but the implementation was really “vLLM services plus one ad hoc sidecar”

Hindsight should be modeled as a normal service so it is declared, rendered, launched, and tracked like every other stack process.

## Current observed state

### Multi-service intent is already real in this repo
The repo already documents and demonstrates the intended shape:

- `docs/decisions/0001-profile-driven-launcher.md`: a stack contains one or more named services
- `mux/examples/example_two_service.toml`: stacks can contain multiple peer services
- `docs/decisions/0006-memory-sidecar-shape-is-transitional.md`: the sidecar shape was explicitly transitional

### The active implementation was still vLLM-first and memory-special-cased
Before this refactor:

- `src/agentmux/config.py` had a dedicated `MemorySpec`
- `src/agentmux/runner.py` only treated `[services.<name>]` as `engine = "vllm"`
- Hindsight launch/reuse/readiness lived in a separate memory branch
- `src/agentmux/main.py` exposed memory separately from services

So the required direction is not a new feature idea. It is a return to the repo’s stated service-first model.

## Scope
This spec covers:

- moving Hindsight to `[services.<name>]` with `engine = "hindsight"`
- removing `[stack.memory]` from the active manifest contract
- making internal planning/runtime use one service list
- preserving current Hindsight operational behavior in the hindsight service engine path
- updating docs/examples/tests to make service-shaped Hindsight the source of truth

This spec does not require:

- a generic plugin framework for arbitrary engines
- always-on or `systemd`-managed Hindsight
- a full multi-service smoke framework
- changes to frontend memory env contracts

## Requirements

### 1. Hindsight is declared as a normal service
A stack declares Hindsight under `[services.<name>]`.

Expected shape:

```toml
[stack]
name = "pi_ghosty"
primary_service = "main"

[services.main]
engine = "vllm"
model = "..."
port = 8002
served_model_name = "omnicoder-9b"

[services.memory]
engine = "hindsight"
host = "127.0.0.1"
port = 8888
data_dir = "${HINDSIGHT_DATA_ROOT}"
llm_service = "main"
```

Rules:
- `engine = "hindsight"` selects Hindsight launch behavior.
- `llm_service` is required.
- `llm_service` must reference an existing in-stack service.
- `llm_service` must reference a `vllm` service in v1.
- `stack.primary_service` remains the default frontend/backend target, not the implicit source for memory derivation.

### 2. `[stack.memory]` is removed from the manifest contract
We do not need a compatibility path.
There is only one real stack using `[stack.memory]`, and it will be converted.

Required behavior:
- loader no longer accepts `[stack.memory]`
- docs/examples stop presenting `[stack.memory]` as a supported shape
- migration is done by updating the affected manifest(s), not by carrying a parser bridge

### 3. Internal planning becomes one service list
`StackLaunchPlan` should carry one list of service launch plans.
There should be no separate top-level memory plan.

### 4. Config validation becomes engine-aware
The config layer must support at least:

- `engine = "vllm"`
- `engine = "hindsight"`

Required behavior:
- do not require `model` for every service regardless of engine
- validate fields by engine
- keep shared fields simple (`name`, `engine`, `host`, `port`, `env`, `notes`)

A small tagged service model is enough. No large abstraction layer is required.

### 5. Hindsight launch behavior moves under the hindsight service engine
Current operational behavior should be preserved, but attached to the service engine.

Required Hindsight behavior:
- bind to configured `host` and `port`
- persist to configured `data_dir`
- launch via `uv run python scripts/hindsight_dev.py`
- derive LLM env from `llm_service`:
  - `HINDSIGHT_LLM_PROVIDER=openai`
  - `HINDSIGHT_LLM_MODEL=<served_model_name or model of llm_service>`
  - `HINDSIGHT_LLM_BASE_URL=http://<display-host>:<port>/v1`
  - `HINDSIGHT_LLM_API_KEY` defaults to `dummy` if unset
- preserve reuse behavior:
  - if the configured port is already serving healthy Hindsight, mark it as external/reused
  - if the port is occupied by something else, fail launch

### 6. Startup ordering becomes service-directed
Hindsight should wait for its referenced `llm_service`, not for a hard-coded sidecar path.

Required v1 behavior:
- vLLM services launch normally
- Hindsight waits for its referenced vLLM service to become ready before launch
- launch order remains deterministic and simple

A full dependency graph is not required.

### 7. `render` still shows the exact command that will run
Hindsight must appear as a normal rendered service entry.
Reused external Hindsight must still be visible as reuse.

### 8. Runtime/status remain service-oriented
Runtime state should continue to record a flat service list.
No separate memory runtime field should exist.

### 9. Docs/examples/tests flip to the service shape
Once implemented:
- `mux/README.md` documents Hindsight under `services`
- example manifests use `engine = "hindsight"`
- tests cover mixed `vllm + hindsight` stacks

## Constraints
- Keep the refactor minimal and repo-shaped.
- Do not invent a generic engine framework just because multiple engines now exist.
- Do not flatten Hindsight into raw `args`; its important fields should remain explicit and human-shaped.
- Do not keep `[stack.memory]` around just for transition convenience.

## Acceptance criteria
- A stack can declare Hindsight under `[services.<name>]` with `engine = "hindsight"`.
- `agentmux render` shows Hindsight as a normal service entry.
- `agentmux up` launches Hindsight through the normal service path, with reuse behavior preserved.
- Internal planning/runtime no longer need a separate top-level memory field.
- The active manifest contract no longer includes `[stack.memory]`.
- Docs/examples/tests identify service-shaped Hindsight as the supported form.
