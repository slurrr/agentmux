**Implementation Plan**

This plan reflects the agreed reset:

- keep the repo layout
- keep the CLI shape
- remove Python ownership of the `vllm` flag surface
- keep and strengthen the sugar layer
- make manifests the source of truth for rendered `vllm serve` commands

**Target Outcome**
`agentmux` becomes a thin-schema, sugar-heavy wrapper for reproducible backend recipes.

Python will own:
- manifest loading
- defaults merging
- env expansion
- repo sugar like LoRAs and assets
- command rendering
- launch/runtime metadata
- smoke checks

Python will not own:
- a growing typed list of `vllm serve` flags
- the need to add code every time you want to try a new serving option

## **Manifest Contract**

### Repo-Owned Fields
These remain explicit because they describe `agentmux` behavior rather than the upstream CLI.

`[stack]`
- `name: str`
- `track: "core" | "lab" | "archive"`
- `primary_service: str`
- `notes: str | optional`

`[defaults]`
- repo-level default values for service fields
- expected useful fields:
  - `host`
  - `env`
  - `args`
  - possibly repo sugar defaults later if needed

`[services.<name>]`
- `engine: str`
- `model: str`
- `port: int`
- `host: str | optional`
- `served_model_name: str | optional`
- `notes: str | optional`
- `env: table[str, str] | optional`
- `args: table | optional`
- `extra_args: list[str] | optional`
- `loras: array[table] | optional`
- `assets: table | optional`

### Engine-Owned Fields
Anything intended to become `vllm serve` flags belongs in `args`.

Example:

```toml
[services.main.args]
dtype = "bfloat16"
gpu_memory_utilization = 0.9
max_num_seqs = 8
tensor_parallel_size = 1
enable_prefix_caching = true
guided_decoding_backend = "outlines"
```

No Python change should be required to use those fields.

### `args` Rules
`args` is the standard generic flag table.

Supported values:
- `bool`
- `int`
- `float`
- `str`

Rendering rules:
- `snake_case` key becomes `--kebab-case`
- `true` renders as presence flag
- `false` omits flag
- scalar values render as `--flag value`

Example:
- `enable_prefix_caching = true` -> `--enable-prefix-caching`
- `max_num_seqs = 8` -> `--max-num-seqs 8`

### `extra_args` Rules
`extra_args` stays for edge cases only.

Use it when:
- raw ordering matters
- repeated flags matter
- a table form is awkward or insufficient

Example:

```toml
extra_args = ["--allowed-local-media-path", "/models", "--some-repeatable-flag", "x"]
```

### LoRA Sugar
LoRAs remain repo sugar.

Example:
```toml
[[services.main.loras]]
name = "coder"
path = "${LORA_ROOT}/coder-lora"
base_model = "Qwen3.5-9B"
enabled = true
```

Renderer behavior:
- expand to the needed `vllm serve` flags
- keep the manifest cleaner than hand-writing every CLI detail

If `base_model` is not needed for current rendering, it may remain metadata for now.

### Asset Sugar
Assets should be lightweight references, not hardcoded app policy.

Example direction:
```toml
[services.main.assets]
chat_template = "assets/chat_templates/qwen3.jinja"
tokenizer_config = "assets/tokenizers/foo.json"
system_prompt = "assets/prompts/bar.md"
```

Plan rule:
- only implement asset rendering where it clearly maps to real serving behavior you want now
- do not invent speculative asset abstractions
- unresolved asset fields can remain loaded metadata until a real use is locked in

## **Merge Rules**

### Stack Merge
Merge order:
1. repo defaults
2. service-local values

Service values win.

### Env Merge
Merge order:
1. process env
2. `defaults.env`
3. `services.<name>.env`

Service env wins over defaults.

### Args Merge
Merge order:
1. `defaults.args`
2. `services.<name>.args`

Service args win on key conflict.

### Sugar Expansion Order
Final command assembly should be:

1. base launch command
- `uv run vllm serve <model>`

2. repo-owned explicit service basics
- `--host`
- `--port`
- `--served-model-name` if present

3. merged `args`

4. sugar expansions
- LoRAs
- asset-derived flags if implemented

5. `extra_args`

This preserves a predictable rendering contract.

## **Validation Rules**

### Keep
Validation should catch:
- missing required stack/service fields
- malformed tables/lists
- wrong scalar types
- unset env references
- unsupported engine in v1
- malformed LoRA entries
- malformed asset references if used

### Remove
Validation should not:
- enumerate supported `vllm` flags
- reject unknown keys inside `args`
- require first-class support for ordinary serving options

## **Code Rewrite Scope**

### [src/agentmux/config.py](/home/poop/projects/agentmux/src/agentmux/config.py)
Rewrite this file substantially.

Goals:
- remove hardcoded per-flag service fields
- replace typed `vllm` option ownership with a small repo-owned service model
- support `defaults.args` and `services.<name>.args`
- keep env expansion
- keep stack discovery/resolution
- keep validation thin

Target data shape should be closer to:
- `StackSpec`
- `ServiceSpec` with:
  - `name`
  - `engine`
  - `model`
  - `host`
  - `port`
  - `served_model_name`
  - `env`
  - `args`
  - `extra_args`
  - `loras`
  - `assets`
  - `notes`

Delete from Python-owned schema:
- `dtype`
- `gpu_memory_utilization`
- `max_model_len`
- `max_num_seqs`
- `tensor_parallel_size`
- `attention_backend`
- `api_key_env` unless you explicitly want to keep it as repo sugar
- any similar field whose only purpose is mapping to a `vllm` flag

Decision:
- `api_key_env` should probably be removed with the rest unless you consider it important sugar. My bias is remove it for consistency unless you rely on it.

### [src/agentmux/runner.py](/home/poop/projects/agentmux/src/agentmux/runner.py)
Rewrite command construction.

Goals:
- build from merged generic args
- generic flag renderer becomes the main path
- keep LoRA sugar expansion
- append `extra_args`
- preserve existing launch/runtime behavior unless a separate change is requested

Implementation shape:
- `_render_flag_table(args)` or equivalent generic renderer
- `_apply_loras(...)`
- optional `_apply_assets(...)` only if there is a concrete asset-to-flag mapping needed now
- `_build_vllm_command(service)` becomes much smaller and more generic

### [src/agentmux/main.py](/home/poop/projects/agentmux/src/agentmux/main.py)
Keep CLI shape.

Adjust only where necessary:
- `show` payload should present `args` rather than a curated subset of fields
- `render` output should continue to show final commands and relevant env
- avoid reintroducing the old philosophy in output formatting

### Runtime and Smoke
Likely minimal or no conceptual changes needed for:
- runtime tracking
- history
- status
- smoke checks

Only adapt these if config object shapes change.

## **Manifest Migration Plan**
Because the repo is early, optimize for the correct shape now.

Plan:
- update the example manifests to use `args`
- do not spend energy on long-term backward compatibility unless it is trivial
- if easy, accept `lab_args` temporarily with a deprecation path
- if not easy, remove it cleanly and update manifests/tests at once

My recommendation:
- do a clean switch to `args`
- update the existing manifests and tests in the same rewrite
- no extended compatibility layer unless it is nearly free

## **Test Plan**

### Keep and Update
Tests should lock down the new contract, not the old schema.

Core test areas:

1. Manifest loading
- valid stack loads
- required fields enforced
- env expansion works
- missing env vars fail clearly

2. Merge behavior
- `defaults.args` merges into service args
- service args override defaults
- env merges correctly
- host/service overrides behave correctly

3. Generic flag rendering
- bool true renders flag
- bool false omits flag
- numeric/string values render correctly
- snake_case becomes kebab-case

4. `extra_args`
- preserved exactly
- appended in order

5. LoRA sugar
- enabled LoRAs render to CLI
- disabled LoRAs are omitted

6. CLI render output
- `render` shows the expected final command
- `show` reflects manifest data without relying on curated per-flag fields

7. Launch/runtime smoke
- existing runtime tests stay if still valid
- only update them for object shape changes, not philosophy drift

### Remove
Delete or rewrite tests that assert:
- Python owns specific `vllm` flags as first-class config fields
- new serving options require code changes

## **Implementation Sequence**

1. Rewrite config model
- remove per-flag schema ownership
- introduce `args`
- keep env/default/service merge behavior

2. Rewrite command renderer
- render generic flags from `args`
- preserve LoRA sugar
- keep `extra_args`

3. Update CLI output
- ensure `show` and `render` reflect the new model cleanly

4. Update manifests
- convert existing examples from `lab_args` and first-class flags to `args`

5. Update tests
- remove schema-driven assumptions
- add generic rendering and merge tests

6. Run local checks
- use the repo’s canonical check path
- confirm manifest load/render behavior and CLI behavior

## **Open Decisions To Confirm Before Implementation**

1. `api_key_env`
- keep as sugar
- or remove as part of de-schematizing

Recommendation: remove unless you actively value it.

2. `host`
- keep first-class
- or move into `args`

Recommendation: keep first-class because it is part of local launch ergonomics, not really “upstream exploration”.

3. `served_model_name`
- keep first-class
- or move into `args`

Recommendation: keep first-class. It is common enough and central enough to recipe identity to justify sugar.

4. `assets`
- define only the container now
- or implement concrete mappings immediately

Recommendation: keep the field available, but only implement actual flag rendering for assets you currently need.

## **Definition Of Done**

The rewrite is done when:
- manifests use `args` for normal `vllm` flags
- command rendering no longer depends on a hardcoded Python list of supported `vllm` options
- the CLI surface remains stable
- manifests are cleaner and more flexible
- LoRA/env/default sugar still works
- tests verify the new contract
- the code clearly reads like a wrapper for recipes, not a controller of `vllm`

If you want, next I’ll turn this into a tighter implementation checklist and start the rewrite from [src/agentmux/config.py](/home/poop/projects/agentmux/src/agentmux/config.py) and [src/agentmux/runner.py](/home/poop/projects/agentmux/src/agentmux/runner.py).