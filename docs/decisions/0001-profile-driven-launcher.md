# 0001: Profile-Driven Launcher

## Status
Accepted

## Context
The operator needs repeatable local vLLM launch commands with machine-specific defaults and a clean
path to extend profiles with new runtime flags.

## Decision
Use a small Python CLI that reads `agentmux.toml`, merges defaults into named profiles, and renders
or executes `uv run vllm serve ...` commands.

## Consequences
- Launch behavior is reviewable in Git.
- The first version stays lightweight and stdlib-only.
- Some vLLM flags will remain in `extra_args` until repeated usage justifies first-class config keys.
