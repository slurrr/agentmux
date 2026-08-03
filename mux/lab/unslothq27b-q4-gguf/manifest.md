# unslothq27b-q4-gguf

Lab-editable AgentMux export for the proven `unslothq27b-q4` GGUF / llama.cpp serving preset.

AgentMux is the stable serving cockpit. `workspace-gguf` remains the source/proving ground. This export lets AgentMux launch the same already-built backend image and copied config while allowing lab tweaks before promotion.

## Launch identity

- Mux: `unslothq27b-q4-gguf`
- Service: `main`
- Container: `agentmux-unslothq27b-q4-gguf-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/unslothq27b-q4-gguf/main -> /runs` (added by AgentMux)
- Models: `~/models -> /models:ro`
- Config: `./config -> /mux-config:ro`

## Source

- Workspace: `/home/poop/code/dev/workspace-gguf`
- Preset name: `unslothQ27B_q4`
- Backend: `llama.cpp` / GGUF
- Image: `localhost/llm-gguf:latest`
- Image info at export: `localhost/llm-gguf:latest 2bfecd790745 3 weeks ago`
- Model identifier/path: `/models/active-gguf/unslothq27b-q4.gguf`
- Served model name: `unslothq27b-q4`
- Export timestamp: `2026-07-08T21:44:36-06:00`

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
  ctx-size: 262144
  n-gpu-layers: -1
  threads: 8
  parallel: 2
  cont-batching: true
  flash-attn: true
  metrics: true
  fit: false
  cache-type-k: q4_0
  cache-type-v: q4_0
  cache-reuse: 256
  kv-unified: true
  log-verbosity: 4
  model: /models/active-gguf/unslothq27b-q4.gguf
  alias: unslothq27b-q4
sampling:
  temperature: 1.0
  top-p: 0.949999988079071
  top-k: 20
runtime:
  image: localhost/llm-gguf:latest
  container_name: llama-server
metadata:
  architecture: qwen35
  native_context: 262144
  resolved_model: /home/poop/models/hf/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace/Qwen3.6-27B-UD-Q4_K_XL.gguf
  weights_gb: 16.679
  sampling:
    source: gguf_metadata
    origin: /home/poop/models/hf/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace/Qwen3.6-27B-UD-Q4_K_XL.gguf
    extracted_keys:
    - general.sampling.temp
    - general.sampling.top_p
    - general.sampling.top_k
    fallback_used: false
```

## llama-server args snapshot

```text
--host
0.0.0.0
--port
5000
--ctx-size
262144
--n-gpu-layers
-1
--threads
8
--parallel
2
--cont-batching
--flash-attn
on
--metrics
--fit
off
--cache-type-k
q4_0
--cache-type-v
q4_0
--cache-reuse
256
--kv-unified
--log-verbosity
4
--model
/models/active-gguf/unslothq27b-q4.gguf
--alias
unslothq27b-q4
--temperature
1.0
--top-p
0.949999988079071
--top-k
20
```

## Notes / caveats

```text
- [2026-06-28] Onboarded /home/poop/models/hf/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace/Qwen3.6-27B-UD-Q4_K_XL.gguf (qwen35).
- Resolved GGUF: /home/poop/models/hf/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace/Qwen3.6-27B-UD-Q4_K_XL.gguf
- Native context length: 262144 tokens.
- Model shape: 65 layers, 4 KV heads, key_dim=256, value_dim=256.
- Weights on disk: 16.68 GB.
- Detected host GPU VRAM: 23.99 GB (1 GPU(s)).
- VRAM-aware selection: ctx-size=65536, cache-type-k=q4_0, cache-type-v=q4_0, n-gpu-layers=-1.
- VRAM estimates:
  * Selection budget: detected VRAM 23.99 GiB - llama.cpp allocator/graph reserve 2.20 GiB = 21.79 GiB
  * 4k (f16/f16 KV): weights ~16.68 GiB + KV ~1.02 GiB = ~17.69 GiB
  * 4k (q8_0/q8_0 KV): weights ~16.68 GiB + KV ~0.54 GiB = ~17.22 GiB
  * 4k (q4_0/q4_0 KV): weights ~16.68 GiB + KV ~0.29 GiB = ~16.96 GiB
  * 8k (f16/f16 KV): weights ~16.68 GiB + KV ~2.03 GiB = ~18.71 GiB
  * 8k (q8_0/q8_0 KV): weights ~16.68 GiB + KV ~1.08 GiB = ~17.76 GiB
  * 8k (q4_0/q4_0 KV): weights ~16.68 GiB + KV ~0.57 GiB = ~17.25 GiB
  * 16k (f16/f16 KV): weights ~16.68 GiB + KV ~4.06 GiB = ~20.74 GiB
  * 16k (q8_0/q8_0 KV): weights ~16.68 GiB + KV ~2.16 GiB = ~18.84 GiB
  * 16k (q4_0/q4_0 KV): weights ~16.68 GiB + KV ~1.14 GiB = ~17.82 GiB
  * 32k (f16/f16 KV): weights ~16.68 GiB + KV ~8.12 GiB = ~24.80 GiB
  * 32k (q8_0/q8_0 KV): weights ~16.68 GiB + KV ~4.32 GiB = ~21.00 GiB
  * 32k (q4_0/q4_0 KV): weights ~16.68 GiB + KV ~2.29 GiB = ~18.96 GiB
  * 64k (f16/f16 KV): weights ~16.68 GiB + KV ~16.25 GiB = ~32.93 GiB
  * 64k (q8_0/q8_0 KV): weights ~16.68 GiB + KV ~8.63 GiB = ~25.31 GiB
  * 64k (q4_0/q4_0 KV): weights ~16.68 GiB + KV ~4.57 GiB = ~21.25 GiB
  * 128k (f16/f16 KV): weights ~16.68 GiB + KV ~32.50 GiB = ~49.18 GiB
  * 128k (q8_0/q8_0 KV): weights ~16.68 GiB + KV ~17.27 GiB = ~33.94 GiB
  * 128k (q4_0/q4_0 KV): weights ~16.68 GiB + KV ~9.14 GiB = ~25.82 GiB
  * 256k (f16/f16 KV): weights ~16.68 GiB + KV ~65.00 GiB = ~81.68 GiB
  * 256k (q8_0/q8_0 KV): weights ~16.68 GiB + KV ~34.53 GiB = ~51.21 GiB
  * 256k (q4_0/q4_0 KV): weights ~16.68 GiB + KV ~18.28 GiB = ~34.96 GiB
- Sampling extracted from gguf_metadata: {'temperature': 1.0, 'top-k': 20, 'top-p': 0.949999988079071}
```

- Chat template/tokenizer metadata is read from the GGUF unless the lab config is edited otherwise.
- Files under `config/` are lab-editable. Meaningful tweaks should be backported to `workspace-gguf` before AgentMux core promotion.
- AgentMux owns `/runs`; this export intentionally does not mount runtime data.

## Recommended agent/harness use

```text
base_url: http://127.0.0.1:8002/v1
model: unslothq27b-q4
```
