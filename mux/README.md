# mux/

This directory holds stack manifests for `agentmux`.

## Layout
- `core/`: known-good stacks you actually use
- `lab/`: active experiments and tuning work
- `archive/`: reference material, retired stacks, and shapes you may want later

## Manifest Philosophy
Normal manifests should stay close to real operator intent:
- simple
- realistic
- easy to copy
- easy to read

That means a normal manifest should usually show the model name you actually want to serve and the settings you actually care about.

Examples in `core/` and `lab/` should favor clarity over completeness.

## Why The Archive Example Is Simpler Now
An earlier version of the archive example tried to show too many capabilities at once. That made it worse as documentation.

The example manifest was simplified so it stays readable.

The capabilities that were removed from the example are still supported. They are documented here instead.

## Supported Manifest Features

### Plain model targets
The normal pattern is a simple model target:

```toml
[services.main]
model = "Qwen2.5-7B-Instruct"
```

This is the preferred style when your local model store already resolves simple names the way you want.

### Environment-expanded strings
String fields support environment expansion. If a string contains `${NAME}`, `agentmux` will expand it from the loaded environment.

That means these are valid when you actually want them:

```toml
[services.main]
model = "${MODEL_ROOT}/Qwen2.5-7B-Instruct"
```

```toml
[services.main.env]
HF_HOME = "${CACHE_ROOT}/hf"
```

```toml
[[services.main.loras]]
name = "coder"
path = "${LORA_ROOT}/coder-lora"
enabled = true
```

This feature exists for real machine-specific cases. It is not the preferred style for normal examples.

### Defaults
Stacks can define shared defaults that services inherit:

```toml
[defaults]
host = "0.0.0.0"

[defaults.args]
dtype = "bfloat16"
gpu_memory_utilization = 0.85
```

A service can still override any inherited value.

### Per-service environment
Each service can define environment variables:

```toml
[services.main.env]
CUDA_VISIBLE_DEVICES = "0"
HF_TOKEN = "${HF_TOKEN}"
```

Use this for machine/runtime environment, not for stuffing large amounts of configuration into env vars.

### Generic vLLM flags with `args`
Use `args` for normal `vllm serve` flags. This is the standard path, not an escape hatch:

```toml
[services.main.args]
swap_space = 0
enable_prefix_caching = true
guided_decoding_backend = "outlines"
```

This renders to:

```bash
--swap-space 0 --enable-prefix-caching --guided-decoding-backend outlines
```

This is the preferred place for routine experimentation and day-to-day serving config.

### Server-wide generation defaults (`generation_config`)
vLLM supports a HuggingFace-style `generation_config.json` that can change server-wide default
sampling parameters (and can also impose a global output cap via `max_new_tokens`).

These are ordinary vLLM flags, so they live under `args`:

```toml
[services.main.args]
generation_config = "auto" # or "vllm" or "/path/to/dir"
override_generation_config = { temperature = 0.2, top_p = 0.95 }
```

Behavior:
- `generation_config = "auto"` loads the model's own `generation_config.json` from the model path.
- `generation_config = "vllm"` skips generation config and uses vLLM's neutral defaults.
- `generation_config = "/path/to/dir"` loads a `generation_config.json` from that directory.

Reference example: `mux/archive/example_generation_config.json` shows the shape of the file. To
use it with vLLM, copy it into a directory as `generation_config.json` and point
`generation_config` at that directory.

For multiple agent-level sampling profiles on one loaded model (without multiple vLLM
processes), see `docs/reference/sampling-profiles.md`.

### Asset references
Services can carry versioned mux assets that compile into launch behavior when the repo models them
as operational inputs.

```toml
[services.coder.assets]
chat_template = "assets/chat_templates/coder.jinja"
tokenizer = "assets/tokenizers/coder"
```

Current operational mappings:
- `assets.chat_template` -> `--chat-template`
- `assets.tokenizer` -> `--tokenizer`

These are not passive metadata. If the repo models an asset as launch-relevant, `agentmux` should
compile it into the final `vllm serve` command.

Prompt assets are different. Files under `assets/prompts/` are reference material for frontends and
request composition right now. They do not compile into launch flags unless the repo gets an explicit
contract for that behavior later.

### Raw pass-through with `extra_args`
Use `extra_args` only when you need the raw CLI form:
- repeated flags
- odd ordering
- arguments that do not fit cleanly in `args`

```toml
[services.main]
extra_args = ["--disable-log-requests"]
```

### LoRA shape
LoRAs are part of the stack shape even if you are not actively using them yet:

```toml
[[services.main.loras]]
name = "coder"
path = "coder-lora"
base_model = "Qwen2.5-7B-Instruct"
enabled = false
```

### Stack memory sidecar (`[stack.memory]`)
A stack can optionally launch Hindsight as a local memory sidecar.

```toml
[stack.memory]
provider = "hindsight"
host = "127.0.0.1"
port = 8888
data_dir = "~/data/hindsight"
```

Behavior:
- `provider = "hindsight"` enables memory sidecar launch.
- If omitted, no Hindsight process is launched.
- Hindsight LLM settings are derived from the stack primary service.
- `llm_provider`, `llm_model`, `llm_api_key`, and `llm_base_url` are not allowed in `[stack.memory]`.

### Multi-service stacks
A stack can contain more than one service. That is useful for future team-style topologies even if you usually run one primary service today.

```toml
[stack]
name = "example_team"
primary_service = "generalist"

[services.generalist]
model = "Qwen2.5-3B-Instruct"
port = 8010

[services.coder]
model = "Qwen2.5-Coder-7B-Instruct"
port = 8011
```

Service names like `main`, `generalist`, `coder`, or `reasoner` are just labels you choose.
They are not special keywords. `primary_service` points at whichever named service should be
treated as the stack default.

## Guidance
- Copy from `core/` or `lab/` when you want a real starting point.
- Use `archive/` for reference shapes and retired ideas.
- Keep examples realistic.
- Use advanced features only when you actually need them.
