# agentmux

`agentmux` is a stack-first backend cockpit for launching and validating model-serving backends.
Today it is `vllm`-first, but the repo is designed around OpenAI-compatible serving and stack
manifests rather than hard-coding one forever-engine.

## Setup
```bash
uv sync
uv pip install vllm --torch-backend=auto
```

## Stack Layout
- `mux/core/`: proven stacks
- `mux/lab/`: experimental stacks
- `mux/archive/`: retired/reference stacks

A stack can contain one or more services. v1 is still operationally single-stack-at-a-time, but the
manifest shape already supports future multi-service stacks.

## Common Commands
```bash
uv run agentmux list --include-archive
uv run agentmux show qwen2_5_7b
uv run agentmux render qwen2_5_7b
uv run agentmux up qwen2_5_7b --dry-run
uv run agentmux status
uv run agentmux smoke qwen2_5_7b --json
uv run agentmux history
```

## Runtime Model
- `agentmux` launches `uv run vllm serve ...`
- `vllm` owns serving and logs
- `agentmux` stores thin runtime metadata in `.agentmux/`
- `.env` is loaded automatically before rendering or launching
- keep machine-wide globals minimal; `CUDA_VISIBLE_DEVICES=0` is the current default

## Notes
- Start with known-good pinned versions.
- Use `core` for stable stacks and `lab` for experiments.
- LoRAs are part of the stack shape, even though base-model serving is the first success target.
