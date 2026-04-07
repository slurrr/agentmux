# Current Goal
Stabilize Hindsight sidecar integration for `pi_ghosty` so `agentmux up` reliably brings up vLLM + Hindsight with CPU embeddings/reranker and explicit persistence path.

# Current State
- `uv run agentmux up pi_ghosty` now starts both services successfully in latest runs.
- Runtime status shows both processes active:
  - `main` on `:8002`
  - `hindsight` on `:8888`
- Health checks pass: `curl http://127.0.0.1:8888/health` returns healthy.
- Hindsight launch now uses `hindsight-api` with explicit DB URL wiring from an embedded `pg0` instance started by `scripts/hindsight_dev.py`.
- Hindsight logs now show explicit startup config lines, including persistence and DB URL.
- Manifest updated so Hindsight CPU flags are in `[defaults.env]` (so sidecar sees them), not in `[services.main.env]`.
- New decision doc added: `docs/decisions/0006-memory-sidecar-shape-is-transitional.md`.
- Local skill placement fixed:
  - custom checkpoint skill moved to `~/.pi/agent/skills/local/checkpointing/SKILL.md`
  - README moved to `~/.pi/agent/skills/local/README.md` to avoid skill parser conflict.

# Decisions
- Keep `[stack.memory]` shape for now as transitional; defer service-shaped refactor (documented in `0006`).
- Do not expand `.memory` surface further in this stabilization pass.
- Treat Hindsight as optional for clients; client repos own bank/base-url env usage.
- Force Hindsight embeddings/reranker to CPU via env knobs in stack defaults.

# Open Problems
- Confirm long-run persistence semantics of `HINDSIGHT_DATA_DIR` mapping to pg0 data root are exactly what is desired (current logs show explicit DB URL + data dir, but path policy should be documented/verified).
- Potential memory accounting confusion remains (vLLM allocator growth during Hindsight verification call vs Hindsight GPU use); operational guidance should call this out.
- Sidecar model remains special-cased; planned future refactor is to service-shaped memory orchestration.

# Resume Instructions
1. From repo root: `uv run agentmux status --json` and verify both `main` and `hindsight` are running.
2. Check newest logs:
   - `/home/poop/runs/agentmux/logs/*pi_ghosty-main.log`
   - `/home/poop/runs/agentmux/logs/*pi_ghosty-hindsight.log`
3. Confirm Hindsight startup lines include:
   - `hindsight persistence data_dir=...`
   - `Database: postgresql://...`
   - `Embeddings: forcing CPU mode`
4. If continuing refactor discussion, start at:
   - `docs/decisions/0006-memory-sidecar-shape-is-transitional.md`
   - `mux/core/memory_omnicoder_9b.toml`
   - `src/agentmux/runner.py` and `scripts/hindsight_dev.py`
