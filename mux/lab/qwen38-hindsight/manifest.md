# qwen38-hindsight

Lab-editable AgentMux export for the proven `qwen38-hindsight` GGUF / llama.cpp serving preset.

AgentMux is the stable serving cockpit. `workspace-gguf` remains the source/proving ground. This export lets AgentMux launch the same already-built backend image and copied config while allowing lab tweaks before promotion.

## Launch identity

- Mux: `qwen38-hindsight`
- Service: `main`
- Container: `agentmux-qwen38-hindsight-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/qwen38-hindsight/main -> /runs` (added by AgentMux)
- Models: `~/models -> /models:ro`
- Config: `./config -> /mux-config:ro`

## Source

- Workspace: `/home/poop/code/dev/workspace-gguf`
- Preset name: `qwen38-hindsight`
- Backend: `llama.cpp` / GGUF
- Image: `localhost/llm-gguf:qwen38-hauhau-fastmtp-4df29be`
- Image info at export: `localhost/llm-gguf:qwen38-hauhau-fastmtp-4df29be 631d5376555c 2 weeks ago`
- Model identifier/path: `/models/active-gguf/qwen38-hindsight.gguf`
- Served model name: `qwen38-hindsight`
- Export timestamp: `2026-09-23T15:17:59-06:00`

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
  cache-type-k: q4_0
  cache-type-v: q4_0
  split-mode: none
  threads-batch: 8
  kv-unified: true
  batch-size: 2048
  ubatch-size: 512
  cache-ram: 24576
  cache-idle-slots: true
  spec-type: draft-mtp
  spec-draft-model: /models/hf/hub/models--HauhauCS--Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/snapshots/993a5971fda8f30dd1b7eb2654792ba4415c7460/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf
  spec-draft-ngl: -1
  spec-draft-n-max: 1
  spec-draft-p-min: 0
  spec-draft-type-k: q4_0
  spec-draft-type-v: q4_0
  log-verbosity: 3
  model: /models/active-gguf/qwen38-hindsight.gguf
  alias: qwen38-hindsight
sampling:
  temperature: 1.0
  top-p: 0.95
  top-k: 20
  min-p: 0.0
runtime:
  image: localhost/llm-gguf:qwen38-hauhau-fastmtp-4df29be
  container_name: llama-server
metadata:
  architecture: qwen35
  native_context: 262144
  weights_gb: 12.518
  mtp:
    enabled: true
    mode: fastmtp-sidecar
    sidecar: Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf
    sidecar_sha256: 115e618e1f73cb50817ed5856f0551c6bf9c3d94df96f440eaca78dc63b8968b
    sidecar_canonical_tensor_sha256: 49e248e799f169b6ccc6a8127b9300a95f06cf3d96a8353266f5d457e81d1c87
    source_repository: HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF
    source_revision: 993a5971fda8f30dd1b7eb2654792ba4415c7460
    runtime_base: ggerganov/llama.cpp@4df29be4f4c3673f428170fda944a5b19f743bb8
    runtime_patch: patches/0002-qwen38-hauhau-fastmtp.patch
    runtime_patch_sha256: 981285400b59dc45cf99936b6ff66d4b3aa0f1b532f85fa51418cb407e51d615
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
q4_0
--cache-type-v
q4_0
--split-mode
none
--threads-batch
8
--kv-unified
--batch-size
2048
--ubatch-size
512
--cache-ram
24576
--cache-idle-slots
--spec-type
draft-mtp
--spec-draft-model
/models/hf/hub/models--HauhauCS--Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/snapshots/993a5971fda8f30dd1b7eb2654792ba4415c7460/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf
--spec-draft-ngl
-1
--spec-draft-n-max
1
--spec-draft-p-min
0
--spec-draft-type-k
q4_0
--spec-draft-type-v
q4_0
--log-verbosity
3
--model
/models/active-gguf/qwen38-hindsight.gguf
--alias
qwen38-hindsight
--temperature
1.0
--top-p
0.95
--top-k
20
--min-p
0.0
```

## Notes / caveats

```text
- Hindsight concurrency profile for the Q3_K_P Qwen3.8 target with the HauhauCS FastMTP draft model.
- Uses one shared 262144-token KV pool with 8 concurrent sequences: eight 32k retain calls fit within the pool.
- Benchmark selection on the RTX 4090: parallel=8, kv-unified=true, target/draft q4_0 KV, batch-size=2048,
  ubatch-size=512, and FastMTP n-max=1 with the draft fully on GPU. This consumed about 23092 MiB and served
  eight concurrent 32k-token prompts successfully.
- A six-slot profile with n-max=2 also fit and measured slightly higher aggregate prompt throughput, but cannot
  absorb Hindsight's eight simultaneous retain calls. The ten-slot / ten-times-32k profile exceeded available GPU
  memory during MTP context initialization, so eight is the concurrency ceiling for this model on this GPU.
- Host prompt-cache space is 24576 MiB so idle slots can be ejected for consolidation and later restored.
- Runtime uses llama.cpp 4df29be4f4c3673f428170fda944a5b19f743bb8 plus the signed HauhauCS FastMTP patch.
```

- Chat template/tokenizer metadata is read from the GGUF unless the lab config is edited otherwise.
- Files under `config/` are lab-editable. Meaningful tweaks should be backported to `workspace-gguf` before AgentMux core promotion.
- AgentMux owns `/runs`; this export intentionally does not mount runtime data.

## Recommended agent/harness use

```text
base_url: http://127.0.0.1:8002/v1
model: qwen38-hindsight
```
