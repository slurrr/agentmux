# agentmux

`agentmux` is a cockpit for building and launching muxes.

A mux is an agent-serving stack that compiles into a real `vllm serve` command. The point of this
repo is to keep that stack human-composable and organized so you do not have to hand-build the
exact serve command every time.

## What A Mux Contains
- model target
- backend/runtime args
- chat templates
- LoRAs
- tokenizer-related assets
- prompt assets and other parts that turn a raw served model into an agent backend

## Composition Model
- `[defaults.args]` and `[services.<name>.args]` are for direct `vllm serve` flags.
- assets are for mux parts like chat templates, tokenizers, and other files that belong to the
  stack as an agent backend, not just as raw backend flags.
- LoRAs are stack composition inputs that compile into the final serve command.
- `render` should always show the real command that will run.

## Goal
This repo exists to:
- create muxes
- experiment with muxes
- serve muxes
- let configured agent frontends request those muxes over an OpenAI-compatible API

## Workflow
- define or edit a mux manifest
- inspect the rendered command
- launch it from the CLI or from a UI such as VS Code
- point agent frontends at the running backend

## Setup
```bash
uv venv .venv-vllm
uv pip install --python .venv-vllm/bin/python -e '.[dev]'
uv pip install --python .venv-vllm/bin/python 'vllm==0.20.0'

uv venv .venv-hindsight
uv pip install --python .venv-hindsight/bin/python 'hindsight-all==0.5.6' pg0-embedded
```

## Stack Layout
- `mux/core/`: known-good muxes you actually use
- `mux/lab/`: active experiments
- `mux/bench/`: benchmark-only muxes kept consistent for fair comparisons
- `mux/archive/`: reference-only shapes and retired ideas

## Common Commands
```bash
.venv-vllm/bin/agentmux list --include-archive
.venv-vllm/bin/agentmux show qwen3_5_9b
.venv-vllm/bin/agentmux render qwen3_5_9b
.venv-vllm/bin/agentmux up qwen3_5_9b --dry-run
.venv-vllm/bin/agentmux status
.venv-vllm/bin/agentmux smoke qwen3_5_9b --json
.venv-vllm/bin/agentmux history
```

## Runtime Model
- `agentmux` launches real vLLM and Hindsight executables from their service-specific envs
- `vllm` owns serving and logs
- `agentmux` keeps thin runtime metadata under `~/runs/agentmux/`
- `.env` is loaded automatically before rendering or launching

## Notes
- Keep large model and LoRA stores outside the repo and reference them through `.env`-backed paths.
- Runtime state and logs belong in `~/runs/agentmux/{state,logs}`, not inside the repo tree.
- Use `render` to verify exactly what command a mux becomes.
- This repo is for composing agent-serving stacks, not just storing raw backend flags.
