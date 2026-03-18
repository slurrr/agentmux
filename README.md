# agentmux

`agentmux` is a profile-driven launcher for `vllm serve`. It keeps model presets, runtime flags,
and environment choices in one repo so you can start a known-good server shape without retyping a
huge command line every time.

## Setup
```bash
uv sync
uv pip install vllm --torch-backend=auto
```

## Common Commands
```bash
uv run agentmux list
uv run agentmux show qwen2_5_7b
uv run agentmux render deepseek_r1_distill_qwen_14b
uv run agentmux serve qwen2_5_7b --dry-run
uv run agentmux serve qwen2_5_7b
```

## Config
Profiles live in `agentmux.toml`.

Each profile can define:
- `model`
- `served_model_name`
- `host` / `port`
- `dtype`
- `gpu_memory_utilization`
- `max_model_len`
- `max_num_seqs`
- `tensor_parallel_size`
- `attention_backend`
- `env`
- `extra_args`
- `notes`

## Notes
- Start with stable vLLM on Python 3.12.
- Use `uv pip install vllm --torch-backend=auto` for the initial GPU-aware install.
- `.env` is loaded automatically by `agentmux` before rendering or launching profiles.
- Keep global env locked to stable machine facts like `CUDA_VISIBLE_DEVICES=0`; prefer per-profile flags over broad vLLM env vars.
- Keep project-specific wrappers and presets here; do not rely on shell history for production-ish runs.

## Docs
- Specs: `docs/specs/`
- Decisions: `docs/decisions/`
- Reference: `docs/reference/`
