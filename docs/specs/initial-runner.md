# Spec: Initial Runner

## Problem
Running `vllm serve` by hand is error-prone once model, backend, and memory flags start to vary.

## Scope
Create a local CLI that reads named profiles from TOML and either renders or executes the matching
`vllm serve` command.

## Requirements
- Profile-driven launch configuration
- Dry-run rendering for inspection
- Straightforward path to add LoRA-related flags later
- No dependency on Conda

## Constraints
- Single-machine RTX 4090 target
- Prefer `uv` and `.venv`
- Keep the first implementation stdlib-only

## Acceptance Criteria
- `uv run agentmux list` prints profile names
- `uv run agentmux render <profile>` prints a valid command
- `uv run agentmux serve <profile> --dry-run` prints without executing

## Open Questions
- Which LoRA flags should become first-class config fields?
- Should profiles support inheritance beyond shared defaults?
