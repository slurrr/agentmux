# hauhau-gguf

Lab-editable AgentMux export for the proven `hauhau` GGUF / llama.cpp serving preset.

AgentMux is the stable serving cockpit. `workspace-gguf` remains the source/proving ground. This export lets AgentMux launch the same already-built backend image and copied config while allowing lab tweaks before promotion.

## Launch identity

- Mux: `hauhau-gguf`
- Service: `main`
- Container: `agentmux-hauhau-gguf-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/hauhau-gguf/main -> /runs` (added by AgentMux)
- Models: `~/models -> /models:ro`
- Config: `./config -> /mux-config:ro`

## Source

- Workspace: `/home/poop/code/dev/workspace-gguf`
- Preset name: `hauhau`
- Backend: `llama.cpp` / GGUF
- Image: `localhost/llm-gguf:latest`
- Image info at export: `localhost/llm-gguf:latest 575945e57754 7 hours ago`
- Model identifier/path: `/home/poop/models/hf/hub/models--HauhauCS--Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive/snapshots/f12a584fecbeb5f20001130d8ecd66c9327ae685/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q3_K_P.gguf`
- Served model name: `hauhau`
- Export timestamp: `2026-06-15T17:15:56-06:00`

## Exported files

- `mux.toml` — AgentMux launch recipe.
- `config/llama-server.yml` — lab-editable copied serving config.
- `config/launch-llama-server.sh` — converts the simple copied YAML into `llama-server` args.
- `config/llama-server.args` — static args snapshot for review.

No sampler override directory, template directory, API token file, or LoRA directory is required for this GGUF/llama.cpp export.

## Complete serving config

```yaml
server:
  host: 0.0.0.0
  port: 5000
  ctx-size: 131072
  n-gpu-layers: -1
  threads: 8
  parallel: 1
  cont-batching: true
  flash-attn: true
  metrics: true
  model: /models/active-gguf/hauhau.gguf
  alias: hauhau
  cache-type-k: q4_0
  cache-type-v: q4_0
  spec-type: ngram-cache
  reasoning: false
  reasoning-format: none
  reasoning-budget: 0
sampling:
  temperature: 1.0
  top-p: 0.95
  top-k: 64
  min-p: 0.05
  xtc-probability: 0.5
  xtc-threshold: 0.08
  dry-multiplier: 1.0
  dry-base: 1.75
  dry-allowed-length: 3
runtime:
  image: localhost/llm-gguf:latest
  container_name: llama-server
metadata:
  architecture: qwen35moe
  source_gguf: /home/poop/models/hf/hub/models--HauhauCS--Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive/snapshots/f12a584fecbeb5f20001130d8ecd66c9327ae685/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q3_K_P.gguf
  weights_gb: 17.717
```

## llama-server args snapshot

```text
--host
0.0.0.0
--port
5000
--ctx-size
131072
--n-gpu-layers
-1
--threads
8
--parallel
1
--cont-batching
--flash-attn
on
--metrics
--model
/models/active-gguf/hauhau.gguf
--alias
hauhau
--cache-type-k
q4_0
--cache-type-v
q4_0
--spec-type
ngram-cache
--reasoning
off
--reasoning-format
none
--reasoning-budget
0
--temperature
1.0
--top-p
0.95
--top-k
64
--min-p
0.05
--xtc-probability
0.5
--xtc-threshold
0.08
--dry-multiplier
1.0
--dry-base
1.75
--dry-allowed-length
3
```

## Notes / caveats

```text
- [2026-06-15] Onboarded /home/poop/models/hf/hub/models--HauhauCS--Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive (qwen35moe).
- Resolved GGUF: /home/poop/models/hf/hub/models--HauhauCS--Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive/snapshots/f12a584fecbeb5f20001130d8ecd66c9327ae685/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q3_K_P.gguf
- Native context length: 262144 tokens.
- Model shape: 40 layers, 2 KV heads, key_dim=256, value_dim=256.
- Weights on disk: 17.72 GB.
- Detected host GPU VRAM: 23.99 GB (1 GPU(s)).
- VRAM-aware selection: ctx-size=131072, cache-type-k=q4_0, cache-type-v=q4_0, n-gpu-layers=-1.
- VRAM estimates:
  * 4k (f16/f16 KV): weights ~17.72 GB + KV ~0.31 GB = ~18.03 GB
  * 4k (q8_0/q8_0 KV): weights ~17.72 GB + KV ~0.16 GB = ~17.87 GB
  * 4k (q4_0/q4_0 KV): weights ~17.72 GB + KV ~0.08 GB = ~17.79 GB
  * 8k (f16/f16 KV): weights ~17.72 GB + KV ~0.62 GB = ~18.34 GB
  * 8k (q8_0/q8_0 KV): weights ~17.72 GB + KV ~0.31 GB = ~18.03 GB
  * 8k (q4_0/q4_0 KV): weights ~17.72 GB + KV ~0.16 GB = ~17.87 GB
  * 16k (f16/f16 KV): weights ~17.72 GB + KV ~1.25 GB = ~18.97 GB
  * 16k (q8_0/q8_0 KV): weights ~17.72 GB + KV ~0.62 GB = ~18.34 GB
  * 16k (q4_0/q4_0 KV): weights ~17.72 GB + KV ~0.31 GB = ~18.03 GB
  * 32k (f16/f16 KV): weights ~17.72 GB + KV ~2.50 GB = ~20.22 GB
  * 32k (q8_0/q8_0 KV): weights ~17.72 GB + KV ~1.25 GB = ~18.97 GB
  * 32k (q4_0/q4_0 KV): weights ~17.72 GB + KV ~0.62 GB = ~18.34 GB
  * 64k (f16/f16 KV): weights ~17.72 GB + KV ~5.00 GB = ~22.72 GB
  * 64k (q8_0/q8_0 KV): weights ~17.72 GB + KV ~2.50 GB = ~20.22 GB
  * 64k (q4_0/q4_0 KV): weights ~17.72 GB + KV ~1.25 GB = ~18.97 GB
  * 128k (f16/f16 KV): weights ~17.72 GB + KV ~10.00 GB = ~27.72 GB
  * 128k (q8_0/q8_0 KV): weights ~17.72 GB + KV ~5.00 GB = ~22.72 GB
  * 128k (q4_0/q4_0 KV): weights ~17.72 GB + KV ~2.50 GB = ~20.22 GB
  * 256k (f16/f16 KV): weights ~17.72 GB + KV ~20.00 GB = ~37.72 GB
  * 256k (q8_0/q8_0 KV): weights ~17.72 GB + KV ~10.00 GB = ~27.72 GB
  * 256k (q4_0/q4_0 KV): weights ~17.72 GB + KV ~5.00 GB = ~22.72 GB
- Sampling defaults: {'temperature': 0.7, 'top-p': 0.95, 'top-k': 40}
- [2026-06-15] Refreshed preset with GGUF metadata-driven VRAM/context/KV auto-selection ported from workspace-exl3 onboarding.
- [2026-06-15] confirmed llama.cpp CUDA arch fixed for RTX 4090 (ARCHS=890) and server works on port 5000
```

- Chat template/tokenizer metadata is read from the GGUF unless the lab config is edited otherwise.
- Files under `config/` are lab-editable. Meaningful tweaks should be backported to `workspace-gguf` before AgentMux core promotion.
- AgentMux owns `/runs`; this export intentionally does not mount runtime data.

## Recommended agent/harness use

```text
base_url: http://127.0.0.1:8002/v1
model: hauhau
```
