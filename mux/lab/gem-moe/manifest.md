# gem-moe

Lab-editable AgentMux export for the proven `gm26b-a4b-hau-q4` GGUF / llama.cpp serving preset.

AgentMux is the stable serving cockpit. `workspace-gguf` remains the source/proving ground. This export lets AgentMux launch the same already-built backend image and copied config while allowing lab tweaks before promotion.

## Launch identity

- Mux: `gem-moe`
- Service: `main`
- Container: `agentmux-gem-moe-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/gem-moe/main -> /runs` (added by AgentMux)
- Models: `~/models -> /models:ro`
- Config: `./config -> /mux-config:ro`

## Source

- Workspace: `/home/poop/code/dev/workspace-gguf`
- Preset name: `gm26b-a4b-hau-q4`
- Backend: `llama.cpp` / GGUF
- Image: `localhost/llm-gguf:latest`
- Image info at export: `localhost/llm-gguf:latest 2bfecd790745 3 weeks ago`
- Model identifier/path: `/home/poop/models/hf/hub/models--HauhauCS--Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced/snapshots/96c11c22b1128c3c8c655b21557b409f307c557f/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced-Q4_K_P.gguf`
- Served model name: `gm26b-a4b-hau-q4`
- Export timestamp: `2026-07-08T14:20:50-06:00`

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
  parallel: 8
  cont-batching: true
  flash-attn: true
  metrics: true
  fit: false
  cache-type-k: q8_0
  cache-type-v: q8_0
  cache-reuse: 256
  kv-unified: true
  log-verbosity: 4
  model: /models/active-gguf/gm26b-a4b-hau-q4.gguf
  alias: gm26b-a4b-hau-q4
sampling:
  temperature: 1.0
  top-p: 0.949999988079071
  top-k: 64
runtime:
  image: localhost/llm-gguf:latest
  container_name: llama-server
metadata:
  architecture: gemma4
  source_gguf: /home/poop/models/hf/hub/models--HauhauCS--Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced/snapshots/96c11c22b1128c3c8c655b21557b409f307c557f/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced-Q4_K_P.gguf
  weights_gb: 15.755
  sampling_provenance:
    source: gguf_metadata
    origin: /home/poop/models/hf/hub/models--HauhauCS--Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced/snapshots/96c11c22b1128c3c8c655b21557b409f307c557f/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced-Q4_K_P.gguf
    extracted_keys:
    - general.sampling.temp
    - general.sampling.top_p
    - general.sampling.top_k
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
8
--cont-batching
--flash-attn
on
--metrics
--fit
off
--cache-type-k
q8_0
--cache-type-v
q8_0
--cache-reuse
256
--kv-unified
--log-verbosity
4
--model
/models/active-gguf/gm26b-a4b-hau-q4.gguf
--alias
gm26b-a4b-hau-q4
--temperature
1.0
--top-p
0.949999988079071
--top-k
64
```

## Notes / caveats

```text
- [2026-06-18] Onboarded /home/poop/models/hf/hub/models--HauhauCS--Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced/snapshots/96c11c22b1128c3c8c655b21557b409f307c557f/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced-Q4_K_P.gguf (gemma4).
- Resolved GGUF: /home/poop/models/hf/hub/models--HauhauCS--Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced/snapshots/96c11c22b1128c3c8c655b21557b409f307c557f/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced-Q4_K_P.gguf
- Native context length: 262144 tokens.
- Model shape: 30 layers, mixed KV heads/layer min=2, max=8, sum=210, SWA layers=25 window=1024, key_dim=512, value_dim=512.
- Weights on disk: 15.76 GB.
- Detected host GPU VRAM: 23.99 GB (1 GPU(s)).
- VRAM-aware selection: ctx-size=262144, cache-type-k=f16, cache-type-v=f16, n-gpu-layers=-1.
- VRAM estimates:
  * Selection budget: detected VRAM 23.99 GiB - llama.cpp allocator/graph reserve 2.20 GiB = 21.79 GiB
  * 4k (f16/f16 KV): weights ~15.76 GiB + KV ~0.27 GiB = ~16.03 GiB
  * 4k (q8_0/q8_0 KV): weights ~15.76 GiB + KV ~0.15 GiB = ~15.90 GiB
  * 4k (q4_0/q4_0 KV): weights ~15.76 GiB + KV ~0.08 GiB = ~15.83 GiB
  * 8k (f16/f16 KV): weights ~15.76 GiB + KV ~0.35 GiB = ~16.11 GiB
  * 8k (q8_0/q8_0 KV): weights ~15.76 GiB + KV ~0.19 GiB = ~15.94 GiB
  * 8k (q4_0/q4_0 KV): weights ~15.76 GiB + KV ~0.10 GiB = ~15.85 GiB
  * 16k (f16/f16 KV): weights ~15.76 GiB + KV ~0.51 GiB = ~16.26 GiB
  * 16k (q8_0/q8_0 KV): weights ~15.76 GiB + KV ~0.27 GiB = ~16.02 GiB
  * 16k (q4_0/q4_0 KV): weights ~15.76 GiB + KV ~0.14 GiB = ~15.90 GiB
  * 32k (f16/f16 KV): weights ~15.76 GiB + KV ~0.82 GiB = ~16.58 GiB
  * 32k (q8_0/q8_0 KV): weights ~15.76 GiB + KV ~0.44 GiB = ~16.19 GiB
  * 32k (q4_0/q4_0 KV): weights ~15.76 GiB + KV ~0.23 GiB = ~15.99 GiB
  * 64k (f16/f16 KV): weights ~15.76 GiB + KV ~1.45 GiB = ~17.20 GiB
  * 64k (q8_0/q8_0 KV): weights ~15.76 GiB + KV ~0.77 GiB = ~16.52 GiB
  * 64k (q4_0/q4_0 KV): weights ~15.76 GiB + KV ~0.41 GiB = ~16.16 GiB
  * 128k (f16/f16 KV): weights ~15.76 GiB + KV ~2.70 GiB = ~18.45 GiB
  * 128k (q8_0/q8_0 KV): weights ~15.76 GiB + KV ~1.43 GiB = ~17.19 GiB
  * 128k (q4_0/q4_0 KV): weights ~15.76 GiB + KV ~0.76 GiB = ~16.51 GiB
  * 256k (f16/f16 KV): weights ~15.76 GiB + KV ~5.20 GiB = ~20.95 GiB
  * 256k (q8_0/q8_0 KV): weights ~15.76 GiB + KV ~2.76 GiB = ~18.52 GiB
  * 256k (q4_0/q4_0 KV): weights ~15.76 GiB + KV ~1.46 GiB = ~17.22 GiB
- Sampling extracted from gguf_metadata: {'temperature': 1.0, 'top-p': 0.949999988079071, 'top-k': 64}
```

- Chat template/tokenizer metadata is read from the GGUF unless the lab config is edited otherwise.
- Files under `config/` are lab-editable. Meaningful tweaks should be backported to `workspace-gguf` before AgentMux core promotion.
- AgentMux owns `/runs`; this export intentionally does not mount runtime data.

## Recommended agent/harness use

```text
base_url: http://127.0.0.1:8002/v1
model: gm26b-a4b-hau-q4
```
