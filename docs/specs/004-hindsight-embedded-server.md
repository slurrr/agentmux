# Spec: Hindsight memory sidecar in stack launch

## Problem
Frontends expect a Hindsight HTTP API (typically `http://localhost:8888`) for long-term memory.
When it is missing, retain/recall/reflect calls fail.

## Decision Shape (implemented)
Hindsight is launched from `agentmux` as a **stack sidecar**, not as a permanently-on default process.

- Memory config lives under `[stack.memory]`.
- `provider = "hindsight"` implies enabled.
- `agentmux up <stack>` launches vLLM services as usual and also launches Hindsight when configured.
- If Hindsight is already running on the configured port, `agentmux` reuses it.

## Manifest Contract
Supported v1 shape:

```toml
[stack.memory]
provider = "hindsight"
host = "127.0.0.1"    # optional, default 127.0.0.1
port = 8888            # optional, default 8888
data_dir = "~/data/hindsight" # optional, default ~/data/hindsight
```

Rules:
- `provider` is required when `[stack.memory]` exists.
- Only `hindsight` is supported in v1.
- LLM fields are **derived from the stack primary service** and cannot be overridden in `[stack.memory]`.
- Attempting to set any of these fields in `[stack.memory]` is a config error:
  - `llm_provider`
  - `llm_model`
  - `llm_api_key`
  - `llm_base_url`

## Runtime Behavior
When memory is enabled:
- bind defaults to `127.0.0.1:8888`.
- persistence defaults to `~/data/hindsight`.
- server process is launched via `scripts/hindsight_dev.py`.
- server env is derived by `agentmux`:
  - `HINDSIGHT_LLM_PROVIDER=openai`
  - `HINDSIGHT_LLM_MODEL=<primary served_model_name or primary model>`
  - `HINDSIGHT_LLM_BASE_URL=http://<primary_host_or_127.0.0.1>:<primary_port>/v1`
  - `HINDSIGHT_LLM_API_KEY` defaults to `dummy` if unset.

Port conflict behavior:
- If configured memory port is already used and healthy HTTP responds (`/health` or `/`), treat it as reusable Hindsight and continue.
- If port is used and not reusable, fail stack launch.

## Client Contract
Frontend repos remain env-configured:
- `HINDSIGHT_BASE_URL`
- `HINDSIGHT_BANK_ID`

Bank selection stays client-side.
