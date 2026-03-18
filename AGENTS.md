# AGENTS.md

## Project Overview
- Purpose: manage repeatable `vllm serve` launches through named profiles
- Primary user: local operator running models on a single RTX 4090 24 GB machine
- Non-goals: generic distributed orchestration, Kubernetes deployment, or multi-node scheduling

## Stack
- Python: 3.12 via `uv`
- Tooling: `uv`, `ruff`, `pytest`, `pyright`, `vllm`
- Entry point: `uv run agentmux ...`

## Working Agreements
- Keep launch profiles declarative in `agentmux.toml`.
- Prefer standard-library Python unless a dependency materially improves reliability.
- Add or update tests whenever profile parsing or command rendering changes.
- Record durable architecture choices in `docs/decisions/`.
- Write concrete requirements in `docs/specs/` before large features.

## Commands
- Setup: `uv sync && uv pip install vllm --torch-backend=auto`
- Checks: `./scripts/dev.sh`
- List profiles: `uv run agentmux list`
- Render command: `uv run agentmux render qwen2_5_7b`
- Serve: `uv run agentmux serve qwen2_5_7b`

## Conventions
- Repo name may use dashes; Python package name uses underscores.
- Profile names should describe model plus notable runtime shape.
- Keep secrets out of `agentmux.toml`; prefer env vars for tokens and API keys.
- Lock only stable machine-wide env defaults here, currently `CUDA_VISIBLE_DEVICES=0`; prefer explicit profile flags over global vLLM env overrides.
