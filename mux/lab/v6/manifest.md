# v6

Lab-editable AgentMux export for the proven `v6` EXL3 / TabbyAPI serving preset.

AgentMux is the stable serving cockpit. `workspace-exl3` remains the source/proving ground. This export lets AgentMux launch the same already-built backend image and copied config while allowing lab tweaks before promotion.

## Launch identity

- Mux: `v6`
- Service: `main`
- Container: `agentmux-v6-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/v6/main -> /runs` (added by AgentMux)
- Model artifact: `/home/poop/models/hf/hub/models--turboderp--Qwen3.8-27B-exl3/snapshots/516bf129059031c6da9416768ea6b7a1be00a8fc -> /models/v6:ro`
- Dependency closure: `/home/poop/models/hf/hub/models--turboderp--Qwen3.8-27B-exl3/blobs -> /blobs:ro`

## Source

- Workspace: `/home/poop/code/dev/workspace-exl3`
- Preset name: `v6`
- Backend: `TabbyAPI` / `ExLlamaV3`
- Image: `localhost/llm-tabby:exllamav3-1.4.4-cu132-tabby-fcc1a107-cuda13.2.1`
- Image info at export: `localhost/llm-tabby:exllamav3-1.4.4-cu132-tabby-fcc1a107-cuda13.2.1 a2a1d0dc7f9a 6 hours ago`
- Model identifier/path: `/home/poop/models/hf/hub/models--turboderp--Qwen3.8-27B-exl3/snapshots/516bf129059031c6da9416768ea6b7a1be00a8fc`
- Direct artifact bind source: `/home/poop/models/hf/hub/models--turboderp--Qwen3.8-27B-exl3/snapshots/516bf129059031c6da9416768ea6b7a1be00a8fc`
- Served model name: `v6`
- Export timestamp: `2026-08-27T15:54:58-06:00`

## Exported files

- `mux.toml` — AgentMux launch recipe.
- `config/tabby-config.direct-bind.yml` — next-start direct-bind serving config.
- config/sampler_overrides/v6.yml
- config/templates/
- config/api_tokens.yml

## Complete serving config

```yaml
draft_model:
  draft_cache_mode: Q4
  draft_mode: mtp
  draft_num_tokens: 2
logging:
  log_generation_params: false
  log_prompt: false
  log_requests: false
memory:
  cuda_malloc_async: true
  sysmem_kv_cache: 4096
  sysmem_recurrent_cache: 4096
model:
  autosplit_reserve:
  - 96
  backend: exllamav3
  cache_mode: 8,6
  cache_size: 262144
  chunk_size: 2048
  force_enable_thinking: true
  gpu_split_auto: true
  max_batch_size: 4
  max_seq_len: 262144
  model_dir: /models
  model_name: v6
  output_chunking: true
  reasoning: true
  reasoning_end_token: </think>
  reasoning_start_token: <think>
  tool_format: qwen3_5
network:
  api_servers:
  - OAI
  disable_auth: true
  host: 0.0.0.0
  port: 5000
sampling:
  override_preset: v6
```

## Sampler/template/LoRA/token notes

- Active sampler override: `v6`.
- Templates directory copied if present in the workspace.
- `api_tokens.yml` copied if present; keep lab/core promotion security in mind.
- `loras/` copied only when a `lora:` config section is present.

## Notes / caveats

```text
- [2026-08-27] Onboarded /home/poop/models/hf/hub/models--turboderp--Qwen3.8-27B-exl3/snapshots/516bf129059031c6da9416768ea6b7a1be00a8fc (Qwen3_5ForConditionalGeneration).
- Native context length: 262144 tokens.
- Detected host GPU VRAM: 23.99 GB (1 GPU(s)).
- VRAM-aware selection: max_seq_len=65536, cache_mode=4,4, output_chunking=True.
- Extracted recommended sampling params & stop tokens into override preset 'v6'.
  * Custom stop strings: <|im_end|>
- Runtime/cache plan summary:
  * confidence: medium
  * rules_used: ['explicit_head_dim', 'hf_config', 'layer_types', 'quantization_metadata']
  * cache_plan_summary: {'cache_mode': '4,4', 'full_context_layers': 64, 'layers': 64, 'memory_manager': 'preallocated_or_backend_native', 'sliding_window': None, 'sliding_window_layers': 0, 'selected_context': 65536, 'output_chunking': True, 'max_batch_size': 8}
  * assumptions: ['disk_size_used_as_resident_weight_estimate']
  * missing_metadata: []
- Model VRAM Estimations (Weights: 15.23 GB):
  * 4k context (FP16): ~16.23 GB total VRAM
  * 8k context (FP16): ~17.23 GB total VRAM
  * 8k context (8-bit): ~16.23 GB total VRAM
  * Native 256k context (4,4): ~31.23 GB total VRAM
```

- Files under `config/` are lab-editable. Meaningful tweaks should be backported to `workspace-exl3` before AgentMux core promotion.
- AgentMux owns `/runs`; this export intentionally does not mount runtime data.
- The selected artifact is mounted directly at `/models/v6`. Its container basename, Tabby loaded-model identity, advertised model ID, and client request ID therefore agree.
- Hugging Face snapshot symlinks are supported when their external targets form one safe directory mount (normally the repository `blobs/` directory); unsupported closures are rejected instead of emitting a broken direct mount.
- `EXLLAMAV3_TUNE_CACHE` points into `/runs` so cooperative GEMM tuning survives container replacement instead of penalizing the first real requests after every launch.
- Q4/Q4 cache serving uses online quantized-cache Triton prefill (`EXL3_QC_STAGING=0`) and keeps graph-captured full-attention decode enabled (`EXL3_BC_ATTN=1`).

## Recommended agent/harness use

```text
base_url: http://127.0.0.1:8002/v1
model: v6
```
