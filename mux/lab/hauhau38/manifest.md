# hauhau38

Lab-editable AgentMux export for the proven `qwen38-hauhau-fastmtp-q3` GGUF / llama.cpp serving preset.

AgentMux is the stable serving cockpit. `workspace-gguf` remains the source/proving ground. This export lets AgentMux launch the same already-built backend image and copied config while allowing lab tweaks before promotion.

## Launch identity

- Mux: `hauhau38`
- Service: `main`
- Container: `agentmux-hauhau38-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/hauhau38/main -> /runs` (added by AgentMux)
- Models: `~/models -> /models:ro`
- Config: `./config -> /mux-config:ro`

## Source

- Workspace: `/home/poop/code/dev/workspace-gguf`
- Preset name: `qwen38-hauhau-fastmtp-q3`
- Backend: `llama.cpp` / GGUF
- Image: `localhost/llm-gguf:qwen38-hauhau-fastmtp-4df29be`
- Image info at export: `localhost/llm-gguf:qwen38-hauhau-fastmtp-4df29be 631d5376555c 6 days ago`
- Model identifier/path: `/models/active-gguf/qwen38-hauhau-fastmtp-q3.gguf`
- Served model name: `qwen38-hauhau-fastmtp-q3`
- Export timestamp: `2026-09-08T23:48:54-06:00`

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
  parallel: 1
  cont-batching: true
  flash-attn: true
  metrics: true
  fit: false
  cache-type-k: q8_0
  cache-type-v: q5_1
  split-mode: none
  threads-batch: 8
  batch-size: 1024
  ubatch-size: 256
  cache-ram: 0
  spec-type: draft-mtp
  spec-draft-model: /models/hf/hub/models--HauhauCS--Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/snapshots/993a5971fda8f30dd1b7eb2654792ba4415c7460/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf
  spec-draft-ngl: -1
  spec-draft-n-max: 3
  spec-draft-p-min: 0
  spec-draft-type-k: q8_0
  spec-draft-type-v: q8_0
  log-verbosity: 4
  model: /models/active-gguf/qwen38-hauhau-fastmtp-q3.gguf
  alias: qwen38-hauhau-fastmtp-q3
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
1
--cont-batching
--flash-attn
on
--metrics
--fit
off
--cache-type-k
q8_0
--cache-type-v
q5_1
--split-mode
none
--threads-batch
8
--batch-size
1024
--ubatch-size
256
--cache-ram
0
--spec-type
draft-mtp
--spec-draft-model
/models/hf/hub/models--HauhauCS--Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/snapshots/993a5971fda8f30dd1b7eb2654792ba4415c7460/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf
--spec-draft-ngl
-1
--spec-draft-n-max
3
--spec-draft-p-min
0
--spec-draft-type-k
q8_0
--spec-draft-type-v
q8_0
--log-verbosity
4
--model
/models/active-gguf/qwen38-hauhau-fastmtp-q3.gguf
--alias
qwen38-hauhau-fastmtp-q3
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
- HauhauCS FastMTP sidecar paired with the Q3_K_P target.
- Runtime uses llama.cpp 4df29be4f4c3673f428170fda944a5b19f743bb8 plus the
  signed HauhauCS-FastMTP-llama.cpp.patch and the separately tagged FastMTP
  image.
- This profile preserves the target's native 262144-token context and is
  single-slot. Plain Qwen3.8 remains the shared-serving profile.
- q8_0 target K and q5_1 target V are the highest-bit K/V combination that
  fits with the FastMTP sidecar at full native context. q8_0 draft K/V is
  retained as the draft-cache choice.
- The sidecar is read-only in the HF-managed cache.
```

- Chat template/tokenizer metadata is read from the GGUF unless the lab config is edited otherwise.
- Files under `config/` are lab-editable. Meaningful tweaks should be backported to `workspace-gguf` before AgentMux core promotion.
- AgentMux owns `/runs`; this export intentionally does not mount runtime data.

## Recommended agent/harness use

```text
base_url: http://127.0.0.1:8002/v1
model: qwen38-hauhau-fastmtp-q3
```
