# Spec: Mux Compiler Contract

## Problem
The repo needs an explicit compiler contract so agents do not drift between two bad extremes:
- turning the repo into an app that owns the entire upstream serving surface
- reducing the repo to a thin raw-flag wrapper that leaves mux concepts half-implemented

## Scope
Define the contract for how a mux manifest compiles into a real `vllm serve` command and related
launch behavior.

## Requirements
- A mux manifest must compile into a real `vllm serve` command.
- `render` must show the exact command that will run.
- `args` are the raw backend/runtime flag surface.
- assets and other mux fields are first-class stack inputs, not passive metadata.
- If an asset corresponds to a real `vllm serve` flag, the repo should compile it into that flag.
- If a manifest field describes a real stack part but does not affect launch behavior, treat that as
  a bug or missing implementation.
- LoRAs remain stack composition inputs that compile into launch flags.
- Name handling must be explicit: no silent normalization of served model names or stack names.
- Precedence between stack inputs must be explicit. Silent overlap is not allowed.

## Compiler Domains
### Raw Backend Runtime
These fields describe direct backend/runtime configuration and compile directly into CLI flags.

Examples:
- `[defaults.args]`
- `[services.<name>.args]`
- `extra_args`

### Mux Composition
These fields describe the mux in human terms and must compile into launch behavior where relevant.

Examples:
- assets such as chat templates and tokenizer-related files
- LoRAs
- env-backed paths
- stack/service identity fields used to build the final command

## Asset Contract
At minimum, the repo should support asset-backed launch behavior for the mux parts it models.

Initial expected mappings:
- `assets.chat_template` -> `--chat-template`
- `assets.tokenizer` -> `--tokenizer`

Other asset keys may remain metadata only if they do not yet correspond to an agreed launch-time
behavior. That distinction must be explicit, not accidental.

## Overlap Rules
If `args` and another mux domain both try to control the same operational flag or behavior, the repo
must not rely on accidental command ordering.

Required precedence:
- `defaults.args` < `services.<name>.args`
- `defaults.assets` < `services.<name>.assets`
- asset-backed launch fields override same-name raw args

Disallowed outcome:
- silent “last one wins” behavior that is not part of the repo contract

## Validation
Good validation here means:
- catching missing required fields
- catching malformed mux structures
- catching overlap between stack domains when the contract forbids it
- preserving freedom to pass normal upstream flags through `args`

Bad validation here means:
- trying to own the whole upstream CLI surface
- forcing Python changes for routine backend experimentation

## Acceptance Criteria
- A mux manifest can describe a human-oriented agent stack and compile into a real `vllm serve` command.
- `render` shows the exact command that will launch.
- Assets that the repo models as launch-relevant affect the final command.
- Dead metadata is treated as a bug, not as an acceptable steady state.
- Naming and precedence behavior are explicit in docs and tests.
