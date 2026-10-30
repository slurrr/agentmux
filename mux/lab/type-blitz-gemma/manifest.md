# type-blitz-gemma-gguf

Lab-editable AgentMux export for the proven `type-blitz-gemma` GGUF / llama.cpp serving preset.

AgentMux is the stable serving cockpit. `workspace-gguf` remains the source/proving ground. This export lets AgentMux launch the same already-built backend image and copied config while allowing lab tweaks before promotion.

## Launch identity

- Mux: `type-blitz-gemma-gguf`
- Service: `main`
- Container: `agentmux-type-blitz-gemma-gguf-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/type-blitz-gemma-gguf/main -> /runs` (added by AgentMux)
- Models: `~/models -> /models:ro`
- Config: `./config -> /mux-config:ro`

## Source

- Workspace: `/home/poop/code/dev/workspace-gguf`
- Preset name: `type-blitz-gemma`
- Backend: `llama.cpp` / GGUF
- Image: `localhost/llm-gguf:latest`
- Image info at export: `localhost/llm-gguf:latest 11548e8f624b 8 weeks ago`
- Model identifier/path: `/home/poop/models/hf/hub/models--HauhauCS--Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced/snapshots/96c11c22b1128c3c8c655b21557b409f307c557f/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced-Q4_K_P.gguf`
- Served model name: `type-blitz-gemma`
- Export timestamp: `2026-10-27T15:28:49-06:00`

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
  parallel: 16
  cont-batching: true
  flash-attn: true
  metrics: true
  fit: false
  kv-unified: true
  batch-size: 8192
  ubatch-size: 2048
  cache-type-k: q4_0
  cache-type-v: q4_0
  cache-ram: 0
  reasoning: 'off'
  jinja: true
  model: /models/active-gguf/type-blitz-gemma.gguf
  alias: type-blitz-gemma
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
  use_case: type-blitz
  concurrency: 16
  per_request_ctx: 8192
  thinking: false
  output_schema: configs/schemas/type-blitz-passage.json
  requires_breeze_stopped: true
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
131072
--n-gpu-layers
-1
--threads
8
--parallel
16
--cont-batching
--flash-attn
on
--metrics
--fit
off
--kv-unified
--batch-size
8192
--ubatch-size
2048
--cache-type-k
q4_0
--cache-type-v
q4_0
--cache-ram
0
--reasoning
off
--jinja
--model
/models/active-gguf/type-blitz-gemma.gguf
--alias
type-blitz-gemma
--temperature
1.0
--top-p
0.949999988079071
--top-k
64
```

## Notes / caveats

```text
- Type-Blitz concurrent profile for the existing HauhauCS Gemma4 26B A4B Q4_K_P model. Final decision: thinking is off for this serve.
- 16 parallel slots x 8192-token budget = 131072 ctx. No speculative drafter: the official Q4_0 MTP assistant was tested but only helps decode-heavy thinking runs and adds memory pressure. Thinking was rejected for this serve.
- RUN WITH BREEZE STOPPED. Breeze ranged from ~2.5 to ~5.0 GiB during testing. At the high end, ubatch 1024 OOMs at startup and ubatch 512 leaves ~189 MiB free. Without Breeze this profile uses ubatch 2048 with 2 graph splits and leaves ~4.5 GiB free. Re-check Breeze's footprint if that changes.
- VALIDITY: 100% requires the client to send response_format with configs/schemas/type-blitz-passage.json. Without the schema, thinking-off returned 13-14/16 valid JSON (markdown fences or plain text). A server-wide --json-schema-file fails to initialize with this chat template (HTTP 400), so the schema must be per request.
- Schema/thinking observation: 4096 thinking without the schema was 16/16 valid in one run; 2048 without the schema was 10/16; lower budgets without the schema were not tested. More thinking reduces the fence/plain-text failures but does not make them deterministic. The schema is the guarantee.
- Measured on the real 16 saved Type-Blitz prompts, 16 concurrent, thinking off, JSON schema, max_tokens 300: 9.5-9.9s wall without Breeze, 16/16 valid, ~100-120 completion tokens each. With Breeze loaded at ubatch 512: 10.8s, also 16/16, but only ~189 MiB free.
- GPU/CPU: the limiter is the llama.cpp server loop, not raw hardware. One CPU core sits at ~100% while the GPU averages ~70-78% utilization (max 100%), memory utilization ~42-47%, power ~310W average / ~410W max, clocks at max. --backend-sampling did not help. Beating this requires a different serving stack, not another llama.cpp flag.
- Thinking data retained for comparison: 512/1024/2048/4096 budgets took 28.6/41.3/74.4/121.6s for the same 16 requests and produced more artificial prose. Full comparison: notes/type-blitz-gemma-thinking-comparison.md.
- reasoning is "off" so llama.cpp does not force the template's thinking path. This is a server default; a client can still send chat_template_kwargs {"enable_thinking": true} and thinking_budget_tokens, but this serve does not use it.
```

- Chat template/tokenizer metadata is read from the GGUF unless the lab config is edited otherwise.
- Files under `config/` are lab-editable. Meaningful tweaks should be backported to `workspace-gguf` before AgentMux core promotion.
- AgentMux owns `/runs`; this export intentionally does not mount runtime data.

## Recommended agent/harness use

```text
base_url: http://127.0.0.1:8002/v1
model: type-blitz-gemma
```
