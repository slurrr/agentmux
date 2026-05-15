# Spec: llama.cpp (`llama-server`) as an LLM service engine

## Status
Draft

## Goal
Add a new mux service engine to `agentmux` so a stack can launch a local **llama.cpp** server (`llama-server`) that serves **GGUF** models over an **OpenAI-compatible** HTTP API.

This should preserve the current cockpit workflow:
- `agentmux render <stack>` shows the exact command that will run
- `agentmux up <stack>` launches the stack services (managed processes + logs)
- `agentmux status` / `history` continue to work as expected
- `agentmux smoke <stack>` works against llama.cpp services

This integration should keep runtime surfaces **isolated**:
- llama.cpp is a native binary and should not be pulled into `.venv-vllm` or `.venv-hindsight`
- CUDA/toolchain configuration should remain **non-ambient**; agentmux should only launch an already-built `llama-server`

## Non-goals
- Feature parity with vLLM (LoRAs, vLLM-only flags, xgrammar integration, etc.)
- Benchmark/perf integration for llama.cpp
- General multi-host orchestration
- Embeddings/reranking services

## Background / constraints
### Repo constraints
- Manifests must remain human-composable.
- Manifest fields must compile into real launch behavior (avoid dead metadata).
- Prefer minimal schema and minimal diffs.

### Machine constraints
- Source should live under `~/code/...`.
- User-facing command surface should be exposed via `~/.local/bin` (symlink or wrapper), not by adding whole repos to `PATH`.
- Avoid making CUDA/toolchain ambient via shell init changes.

### Verified local behavior (machine-specific note)
On this machine, a CUDA-enabled `llama-server` build was verified to provide:
- `GET /health` -> 200 + `{"status":"ok"}`
- `GET /v1/models`
- `POST /v1/chat/completions`

The server supports the following relevant CLI flags (non-exhaustive):
- `--host`, `--port`, `-m/--model`
- `--n-gpu-layers all|auto|0` (GPU offload control)
- `--threads`, `--ctx-size`
- `--chat-template-file`, `--chat-template-kwargs`, `--reasoning`
- `--json-schema-file`, `--grammar-file`

## Proposed manifest shape
Add support for a new service engine:

```toml
[services.llm]
engine = "llamacpp"

# If llama-server is on PATH (preferred via ~/.local/bin), this may be omitted.
# If set, agentmux should invoke ${runtime_bin_dir}/llama-server.
runtime_bin_dir = "~/.local/bin"

# Required: GGUF model path.
model = "/path/to/model.gguf"

host = "127.0.0.1"
port = 18080

# Optional: desired stable model name for clients. Whether this can affect
# llama-server's reported model id depends on upstream capabilities.
served_model_name = "qwen3.5-4b-gguf"

# Preferred initial configuration surface: raw pass-through flags.
extra_args = [
  "--n-gpu-layers", "all",
  "--ctx-size", "8192",
  "--threads", "8",
]

[services.llm.env]
CUDA_VISIBLE_DEVICES = "0"

[services.llm.assets]
# Future mapping candidate:
# chat_template = "assets/chat_templates/your_template.jinja" # -> --chat-template-file
```

### Rationale: use `extra_args` first
`llama-server` has a fast-moving CLI surface and does not align 1:1 with vLLM flags. Using `extra_args`:
- keeps the manifest-to-command compilation literal and inspectable
- avoids over-modeling upstream flag types
- matches the existing agentmux escape hatch for raw flags

## Implementation plan

### Phase 0: decision lock-in (no code)
Decide:
1. Engine name: `llamacpp` (preferred) vs `llama_cpp`.
2. Whether `served_model_name` must affect runtime behavior immediately.
3. Whether to map `assets.chat_template` -> `--chat-template-file` in v1.
4. Whether Hindsight may target llama.cpp services via `llm_service`.


### Phase 1: config parsing (`src/agentmux/config.py`)
Add a new service parser:
- Implement `_service_from_llamacpp(name, raw, defaults) -> ServiceSpec`
- Extend `_service_from_data()` with:
  - `if engine == "llamacpp": return _service_from_llamacpp(...)`

Validation:
- require `model` to be a non-empty string
- accept `runtime_bin_dir` optional string
- accept `extra_args` list[str]
- accept `env` dict[str,str]

Keep allowed keys minimal:
- `engine`, `model`, `host`, `port`, `served_model_name`, `env`, `args`, `extra_args`, `assets`, `notes`, `runtime_bin_dir`


### Phase 2: command construction + planning (`src/agentmux/runner.py`)
Add a llama.cpp command builder:
- `_build_llamacpp_command(service: ServiceSpec) -> list[str]`

Command shape:
- executable:
  - if `runtime_bin_dir`: `${runtime_bin_dir}/llama-server`
  - else: `llama-server`
- required flags:
  - `--host <host>`
  - `--port <port>`
  - `-m <model>`
- append `extra_args` verbatim

Integrate engine dispatch in `build_stack_plan()`:
- new branch `if service.engine == "llamacpp": ...`


### Phase 3: readiness + dependencies (`src/agentmux/runner.py`)
Add readiness probe:
- `_llamacpp_models_ready(host, port) -> bool`
  - `GET http://{host}:{port}/v1/models`

Add wait loop:
- `_wait_for_llamacpp_ready(service: RuntimeService, host: str) -> bool`
  - mirror `_wait_for_vllm_ready` but use `_llamacpp_models_ready`

Extend dependency waiting:
- `_wait_for_dependency()` currently only supports vLLM
- add support for `dependency_spec.engine == "llamacpp"`

This enables Hindsight to declare `waits_for = <llm service>` even when LLM is llama.cpp.


### Phase 4: smoke test robustness (`src/agentmux/smoke.py`)
Current smoke flow:
- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

Recommended change:
- keep `/health` probe, but if it fails, fall back to treating `/v1/models` as readiness/health.

Rationale:
- keeps smoke compatible across engines that are OpenAI-compatible but may not implement `/health`.


### Phase 5: docs + examples
Update:
- `mux/README.md` to document `engine = "llamacpp"`
  - clarify that llama.cpp config is currently via `extra_args`
  - document any asset mappings that are implemented

Add a runnable example (once engine support exists):
- `mux/examples/example_llamacpp_gguf.toml`


### Phase 6: tests
Add focused tests (keep them narrow):
1. Config parsing:
   - engine `llamacpp` parses
2. Render/plan:
   - command contains `llama-server`, `--host`, `--port`, `-m <model>`
3. Dependency readiness (optional but recommended):
   - Hindsight waits for `llamacpp` engine via `_wait_for_dependency`


## Open questions
1. Model identity / aliasing:
   - Does llama-server support forcing a stable model id? If not, do we accept filename-as-id?
2. Asset mapping:
   - Should `assets.chat_template` map to `--chat-template-file` for llama.cpp in v1?
3. Hindsight targeting rule:
   - Today `config.py` requires hindsight.llm_service to reference a vLLM service.
   - Should it be generalized to allow any OpenAI-compatible LLM engine (`vllm` or `llamacpp`)?

## Acceptance criteria
This spec is satisfied when:
- a mux can declare `engine = "llamacpp"` and `agentmux render` shows a real `llama-server` command
- `agentmux up` launches the service and writes runtime state/logs as usual
- `agentmux smoke` succeeds against the llama.cpp service
- no new Python dependency coupling is introduced (llama.cpp remains a native binary dependency)
- CUDA/toolchain is not made ambient by this change
