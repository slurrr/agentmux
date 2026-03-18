# AGENTS.md

## Project Overview
- Purpose:
- Primary user:
- Non-goals:

## Stack
- Python:
- Tooling: uv, ruff, pytest, pyright via `uv run --with pyright pyright`
- Entry point:

## Working Agreements
- Keep imports from `src/` package boundaries clean.
- Add or update tests for behavior changes.
- Record durable architecture choices in `docs/decisions/`.
- Write concrete requirements in `docs/specs/` before large features.

## Commands
- Setup: `uv sync`
- Checks: `./scripts/dev.sh`
- Run: `uv run python -m PACKAGE_NAME.main`
- Type check: `uv run --with pyright pyright`

## Conventions
- Repo name may use dashes; Python package name uses underscores.
- Prefer small modules with explicit interfaces.
- Keep environment-specific values out of code and document them in `.env.example`.

