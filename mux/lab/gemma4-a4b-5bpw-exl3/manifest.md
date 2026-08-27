# gemma4-a4b-5bpw-exl3

Lab-editable AgentMux export for the proven `gemma4-a4b-4-20-5-00bpw-h8-hq` EXL3 / TabbyAPI serving preset.

AgentMux is the stable serving cockpit. `workspace-exl3` remains the source/proving ground. This export lets AgentMux launch the same already-built backend image and copied config while allowing lab tweaks before promotion.

## Launch identity

- Mux: `gemma4-a4b-5bpw-exl3`
- Service: `main`
- Container: `agentmux-gemma4-a4b-5bpw-exl3-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/gemma4-a4b-5bpw-exl3/main -> /runs` (added by AgentMux)
- Model artifact: `/home/poop/models/local/exl3/gemma4-a4b-4.20-5.00bpw-h8-hq -> /models/gemma4-a4b-4-20-5-00bpw-h8-hq:ro`

## Source

- Workspace: `/home/poop/code/dev/workspace-exl3`
- Preset name: `gemma4-a4b-4-20-5-00bpw-h8-hq`
- Backend: `TabbyAPI` / `ExLlamaV3`
- Image: `localhost/llm-tabby:exllamav3-1.4.4-cu132-tabby-fcc1a107-cuda13.2.1`
- Image info after 1.4.4 upgrade: `localhost/llm-tabby:exllamav3-1.4.4-cu132-tabby-fcc1a107-cuda13.2.1 a2a1d0dc7f9a 2026-08-27`
- Model identifier/path: `/home/poop/models/local/exl3/gemma4-a4b-4.20-5.00bpw-h8-hq`
- Direct artifact bind source: `/home/poop/models/local/exl3/gemma4-a4b-4.20-5.00bpw-h8-hq`
- Served model name: `gemma4-a4b-4-20-5-00bpw-h8-hq`
- Export timestamp: `2026-07-18T14:38:20-06:00`

## Exported files

- `mux.toml` — AgentMux launch recipe.
- `config/tabby-config.direct-bind.yml` — next-start direct-bind serving config.
- config/sampler_overrides/gemma4-a4b-4-20-5-00bpw-h8-hq.yml
- config/templates/
- config/api_tokens.yml

## Complete serving config

```yaml
draft_model:
  draft_mode: ngram
  draft_num_tokens: 4
  ngram_match_min: 2
logging:
  log_generation_params: false
  log_prompt: false
  log_requests: false
memory:
  cuda_malloc_async: true
  sysmem_recurrent_cache: 4096
model:
  autosplit_reserve:
  - 96
  backend: exllamav3
  cache_mode: 4,4
  cache_size: 262144
  chunk_size: 4096
  force_enable_thinking: true
  gpu_split_auto: true
  max_batch_size: 10
  max_seq_len: 262144
  model_dir: /models
  model_name: gemma4-a4b-4-20-5-00bpw-h8-hq
  output_chunking: true
  reasoning: true
  reasoning_end_token: <channel|>
  reasoning_start_token: <|channel>
  reasoning_suppress_header: thought
  tool_format: gemma4
network:
  api_servers:
  - OAI
  disable_auth: true
  host: 0.0.0.0
  port: 5000
sampling:
  override_preset: gemma4-a4b-4-20-5-00bpw-h8-hq
```

## Sampler/template/LoRA/token notes

- Active sampler override: `gemma4-a4b-4-20-5-00bpw-h8-hq`.
- Templates directory copied if present in the workspace.
- `api_tokens.yml` copied if present; keep lab/core promotion security in mind.
- `loras/` copied only when a `lora:` config section is present.

## Notes / caveats

```text
- [2026-07-11] Onboarded /home/poop/models/local/exl3/gemma4-a4b-4.20-cook/candidates/gemma4-a4b-4.20-5.00bpw-h8-hq (Gemma4ForConditionalGeneration).
- Native context length: 262144 tokens.
- Detected host GPU VRAM: 23.99 GB (1 GPU(s)).
- VRAM-aware selection: max_seq_len=262144, cache_mode=4,4, output_chunking=True.
- Extracted recommended sampling params & stop tokens into override preset 'gemma4-a4b-4-20-5-00bpw-h8-hq'.
  * Custom stop strings: <eos>, <turn|>
- Runtime/cache plan summary:
  * confidence: medium
  * rules_used: ['explicit_head_dim', 'hf_config', 'layer_types', 'quantization_metadata']
  * cache_plan_summary: {'cache_mode': '4,4', 'full_context_layers': 5, 'layers': 30, 'memory_manager': 'preallocated_or_backend_native', 'sliding_window': 1024, 'sliding_window_layers': 25, 'selected_context': 262144, 'output_chunking': True}
  * assumptions: ['disk_size_used_as_resident_weight_estimate']
  * missing_metadata: []
- Model VRAM Estimations (Weights: 19.03 GB):
  * 4k context (FP16): ~19.38 GB total VRAM
  * 8k context (FP16): ~19.54 GB total VRAM
  * 8k context (8-bit): ~19.28 GB total VRAM
  * Native 256k context (4,4): ~21.58 GB total VRAM
- [2026-07-13] Agentic serve baseline validated on RTX 4090: 262144 shared cache, 4,4 KV, output_chunking=true, max_batch_size=8 loaded at ~21.5 GiB; 8,8 with 8 slots failed VRAM load; eight concurrent short requests completed; gemma4 parser produced a valid OAI tool call.
```

- Files under `config/` are lab-editable. Meaningful tweaks should be backported to `workspace-exl3` before AgentMux core promotion.
- AgentMux owns `/runs`; this export intentionally does not mount runtime data.
- The selected artifact is mounted directly at `/models/gemma4-a4b-4-20-5-00bpw-h8-hq`. Its container basename, Tabby loaded-model identity, advertised model ID, and client request ID therefore agree.
- Export rejects artifacts with symlink dependencies outside their own directory instead of emitting a broken direct mount.
- `EXLLAMAV3_TUNE_CACHE` points into `/runs` so cooperative GEMM tuning survives container replacement instead of penalizing the first real requests after every launch.

## Recommended agent/harness use

```text
base_url: http://127.0.0.1:8002/v1
model: gemma4-a4b-4-20-5-00bpw-h8-hq
```
