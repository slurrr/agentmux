# vLLM CLI Capabilities

This document reorganizes the registered local `vllm` CLI surface for fast human lookup. It keeps broad serving coverage while excluding obvious non-serving noise like `bench` and `collect-env`.

Source of truth:
- [vllm-cli-flags.md](/home/poop/projects/agentmux/docs/reference/vllm-cli-flags.md)

## Quick Find

If you want to find:
- basic serving and addressing: `Serving Identity And Addressing`
- OpenAI-compatible HTTP/API behavior: `API Server And Request Surface`
- tool-capable agents: `Tools And Structured Outputs`
- multimodal serving: `Multimodal And Media`
- LoRA or adapter routing: `LoRA And Adapters`
- model loading and tokenizer control: `Model, Tokenizer, And Loading`
- scaling and topology: `Parallelism And Topology`
- cache, memory, and throughput knobs: `Memory, Cache, And Throughput`
- logs, traces, and metrics: `Logging, Metrics, And Debugging`
- lower-level execution internals: `Advanced Execution Controls`
- batch processing: `Batch Command Surface`
- interactive chat/completion clients: `Client Commands`

## Relevant Commands

- `vllm serve [model_tag] [options]`
- `vllm run-batch -i INPUT.jsonl -o OUTPUT.jsonl --model <model>`
- `vllm chat [options]`
- `vllm complete [options]`

## Common Operator Questions

- Context length / window: `--max-model-len` under `Model, Tokenizer, And Loading`.
- Output cap at serve boot: there is no obvious `vllm serve --max-new-tokens` style launch flag in this registered CLI surface.
- Output cap at client/request time: `vllm complete` exposes `--max-tokens`; OpenAI-compatible request bodies are where generation limits usually live.
- Sampling controls: they do not appear as normal `vllm serve` launch flags in this installed CLI surface. For this environment, treat sampling as primarily request-level rather than boot-time configuration.
- Tool-capable serving: start with `Tools And Structured Outputs`.
- Multimodal serving: start with `Multimodal And Media`.
- LoRA/adapters: start with `LoRA And Adapters`.
- Throughput and memory tuning: start with `Memory, Cache, And Throughput` and `Parallelism And Topology`.

## Serving Identity And Addressing

Primary command:
- `vllm serve`

Core identity and addressing flags:

Serve mode and process shape:

- `model_tag`: The model tag to serve (optional if specified in config)
- `--model <MODEL>`:  Default: `"Qwen/Qwen3-0.6B"`.
- `--served-model-name <SERVED_MODEL_NAME>`:
- `--host <HOST>`:
- `--port <int>`:  Default: `8000`.
- `--uds <UDS>`:
- `--root-path <ROOT_PATH>`:
- `--headless`: Run in headless mode. See multi-node data parallel documentation for more details.
- `--api-server-count <int>, -asc <int>`: How many API server processes to run. Defaults to data_parallel_size if not specified.
- `--config <CONFIG>`: Read CLI options from a config file. Must be a YAML with the following options: https://docs.vllm.ai/en/latest/configuration/serve_args.html

Related batch/client identity flags:
- `--host <HOST>`:
- `--port <int>`:  Default: `8000`.
- `--url <URL>`:  Default: `"0.0.0.0"`.
- `--url <URL>`: url of the running OpenAI-Compatible RESTful API server Default: `"http://localhost:8000/v1"`.
- `--model-name <MODEL_NAME>`: The model name used in prompt completion, default to the first model in list models API call.
- `--url <URL>`: url of the running OpenAI-Compatible RESTful API server Default: `"http://localhost:8000/v1"`.
- `--model-name <MODEL_NAME>`: The model name used in prompt completion, default to the first model in list models API call.

## API Server And Request Surface

Primary command:
- `vllm serve`

OpenAI-compatible frontend behavior:

- `--api-key <API_KEY>`:
- `--response-role <RESPONSE_ROLE>`:  Default: `"assistant"`.
- `--return-tokens-as-token-ids, --no-return-tokens-as-token-ids`:
- `--tokens-only, --no-tokens-only`:
- `--enable-force-include-usage, --no-enable-force-include-usage`:
- `--enable-prompt-tokens-details, --no-enable-prompt-tokens-details`:
- `--enable-request-id-headers, --no-enable-request-id-headers`:
- `--enable-tokenizer-info-endpoint, --no-enable-tokenizer-info-endpoint`:
- `--enable-server-load-tracking, --no-enable-server-load-tracking`:

Docs and operator-facing HTTP surface:
- `--disable-fastapi-docs, --no-disable-fastapi-docs`:
- `--enable-offline-docs, --no-enable-offline-docs`:

Access logging and HTTP parser limits:
- `--disable-uvicorn-access-log, --no-disable-uvicorn-access-log`:
- `--disable-access-log-for-endpoints <DISABLE_ACCESS_LOG_FOR_ENDPOINTS>`:
- `--uvicorn-log-level <critical|debug|error|info|trace|warning>`:  Default: `"info"`.
- `--h11-max-header-count <int>`:  Default: `256`.
- `--h11-max-incomplete-event-size <int>`:  Default: `4194304`.

CORS and middleware surface:
- `--allow-credentials, --no-allow-credentials`:
- `--allowed-origins <ALLOWED_ORIGINS>`:  Default: `["*"]`.
- `--allowed-methods <ALLOWED_METHODS>`:  Default: `["*"]`.
- `--allowed-headers <ALLOWED_HEADERS>`:  Default: `["*"]`.
- `--middleware <MIDDLEWARE>`:

TLS and HTTPS:
- `--ssl-keyfile <SSL_KEYFILE>`:
- `--ssl-certfile <SSL_CERTFILE>`:
- `--ssl-ca-certs <SSL_CA_CERTS>`:
- `--enable-ssl-refresh, --no-enable-ssl-refresh`:
- `--ssl-cert-reqs <int>`:
- `--ssl-ciphers <SSL_CIPHERS>`:

## Tools And Structured Outputs

Primary command:
- `vllm serve`

Tool-capable agent controls:

- `--enable-auto-tool-choice, --no-enable-auto-tool-choice`:
- `--exclude-tools-when-tool-choice-none, --no-exclude-tools-when-tool-choice-none`:
- `--tool-call-parser {deepseek_v3,deepseek_v31,deepseek_v32,ernie45,functiongemma,gigachat3,glm45,glm47,granite,granite-20b-fc,hermes,hunyuan_a13b,internlm,jamba,kimi_k2,llama3_json,llama4_json,llama4_pythonic,longcat,minimax,minimax_m2,mistral,olmo3,openai,phi4_mini_json,pythonic,qwen3_coder,qwen3_xml,seed_oss,step3,step3p5,xlam} or name registered in --tool-parser-plugin`:
- `--tool-parser-plugin <TOOL_PARSER_PLUGIN>`:  Default: `""`.
- `--tool-server <TOOL_SERVER>`:

Prompt/template trust and chat rendering:
- `--chat-template <CHAT_TEMPLATE>`:
- `--chat-template-content-format <auto|openai|string>`:  Default: `"auto"`.
- `--default-chat-template-kwargs <DEFAULT_CHAT_TEMPLATE_KWARGS>`: Should either be a valid JSON string or JSON keys passed individually.
- `--trust-request-chat-template, --no-trust-request-chat-template`:

Structured output and reasoning-related flags:
- `--reasoning-parser <REASONING_PARSER>`:  Default: `""`.
- `--reasoning-parser-plugin <REASONING_PARSER_PLUGIN>`:  Default: `""`.
- `--structured-outputs-config <STRUCTURED_OUTPUTS_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `StructuredOutputsConfig(backend='auto', disable_fallback=False, disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False)`.
- `--speculative-config <SPECULATIVE_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--generation-config <GENERATION_CONFIG>`:  Default: `"auto"`.
- `--override-generation-config <OVERRIDE_GENERATION_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--max-logprobs <int>`:  Default: `20`.
- `--logprobs-mode <processed_logits|processed_logprobs|raw_logits|raw_logprobs>`:  Default: `"raw_logprobs"`.

## Multimodal And Media

Primary command:
- `vllm serve`

Model/media permissions:

Multimodal execution controls:

- `--allowed-local-media-path <ALLOWED_LOCAL_MEDIA_PATH>`:  Default: `""`.
- `--allowed-media-domains <ALLOWED_MEDIA_DOMAINS>`:
- `--enable-mm-embeds, --no-enable-mm-embeds`:
- `--interleave-mm-strings, --no-interleave-mm-strings`:
- `--language-model-only, --no-language-model-only`:
- `--limit-mm-per-prompt <LIMIT_MM_PER_PROMPT>`: Should either be a valid JSON string or JSON keys passed individually.
- `--media-io-kwargs <MEDIA_IO_KWARGS>`: Should either be a valid JSON string or JSON keys passed individually.
- `--mm-encoder-attn-backend <MM_ENCODER_ATTN_BACKEND>`:
- `--mm-encoder-only, --no-mm-encoder-only`:
- `--mm-encoder-tp-mode <data|weights>`:  Default: `"weights"`.
- `--mm-processor-kwargs <MM_PROCESSOR_KWARGS>`: Should either be a valid JSON string or JSON keys passed individually.
- `--skip-mm-profiling, --no-skip-mm-profiling`:
- `--video-pruning-rate <VIDEO_PRUNING_RATE>`:
- `--mm-processor-cache-gb <float>`:  Default: `4`.
- `--mm-processor-cache-type <lru|shm>`:  Default: `"lru"`.
- `--mm-shm-cache-max-object-size-mb <int>`:  Default: `128`.
- `--io-processor-plugin <IO_PROCESSOR_PLUGIN>`:
- `--default-mm-loras <DEFAULT_MM_LORAS>`: Should either be a valid JSON string or JSON keys passed individually.

## LoRA And Adapters

Primary command:
- `vllm serve`

Runtime LoRA enablement and modules:

LoRA scaling and capacity:

- `--enable-lora, --no-enable-lora`: If True, enable handling of LoRA adapters.
- `--lora-modules <LORA_MODULES>`:
- `--max-loras <int>`:  Default: `1`.
- `--max-lora-rank <1|8|16|32|64|128|256|320|512>`:  Default: `16`.
- `--max-cpu-loras <MAX_CPU_LORAS>`:
- `--lora-dtype <auto|bfloat16|float16>`:  Default: `"auto"`.
- `--fully-sharded-loras, --no-fully-sharded-loras`:
- `--specialize-active-lora, --no-specialize-active-lora`:
- `--enable-tower-connector-lora, --no-enable-tower-connector-lora`:

## Model, Tokenizer, And Loading

Primary command:
- `vllm serve`

Model selection and implementation:

- `--model <MODEL>`:  Default: `"Qwen/Qwen3-0.6B"`.
- `--model-impl ['auto', 'terratorch', 'transformers', 'vllm']`:  Default: `"auto"`.
- `--runner <auto|draft|generate|pooling>`:  Default: `"auto"`.
- `--convert <auto|classify|embed|none>`:  Default: `"auto"`.
- `--tokenizer <TOKENIZER>`:
- `--tokenizer-mode ['auto', 'deepseek_v32', 'hf', 'mistral', 'slow']`:  Default: `"auto"`.
- `--tokenizer-revision <TOKENIZER_REVISION>`:
- `--skip-tokenizer-init, --no-skip-tokenizer-init`:
- `--revision <REVISION>`:
- `--code-revision <CODE_REVISION>`:
- `--trust-remote-code, --no-trust-remote-code`:
- `--hf-token <HF_TOKEN>`:
- `--dtype <auto|bfloat16|float|float16|float32|half>`:  Default: `"auto"`.
- `--quantization <QUANTIZATION>, -q <QUANTIZATION>`:
- `--allow-deprecated-quantization, --no-allow-deprecated-quantization`:
- `--enforce-eager, --no-enforce-eager`:
- `--enable-sleep-mode, --no-enable-sleep-mode`:
- `--override-attention-dtype <OVERRIDE_ATTENTION_DTYPE>`:
- `--max-model-len <MAX_MODEL_LEN>`: Parse human-readable integers like '1k', '2M', etc.     Including decimal values with decimal multipliers.     Also accepts -1 or 'auto' as a special value for auto-detection.      Examples:     - '1k' -> 1,000     - '1K' -> 1,024     - '25.6k' -> 25,600     - '-1' or 'auto' -> -1 (special value for auto-detection)
- `--seed <int>`:
- `--disable-sliding-window, --no-disable-sliding-window`:
- `--disable-cascade-attn, --no-disable-cascade-attn`:
- `--enable-prompt-embeds, --no-enable-prompt-embeds`:
- `--enable-return-routed-experts, --no-enable-return-routed-experts`:
- `--pooler-config <POOLER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--logits-processors <LOGITS_PROCESSORS>`:
- `--download-dir <DOWNLOAD_DIR>`:
- `--load-format <LOAD_FORMAT>`:  Default: `"auto"`.
- `--model-loader-extra-config <MODEL_LOADER_EXTRA_CONFIG>`:
- `--pt-load-map-location <PT_LOAD_MAP_LOCATION>`:  Default: `"cpu"`.
- `--safetensors-load-strategy <SAFETENSORS_LOAD_STRATEGY>`:  Default: `"lazy"`.
- `--ignore-patterns <IGNORE_PATTERNS>`:  Default: `["original/**/*"]`.
- `--use-tqdm-on-load, --no-use-tqdm-on-load`:  Default: `true`.
- `--hf-config-path <HF_CONFIG_PATH>`:
- `--hf-overrides <HF_OVERRIDES>`:
- `--config-format ['auto', 'hf', 'mistral']`:  Default: `"auto"`.

## Parallelism And Topology

Primary command:
- `vllm serve`

Core topology and cluster coordination:

- `--tensor-parallel-size <int>, -tp <int>`:  Default: `1`.
- `--pipeline-parallel-size <int>, -pp <int>`:  Default: `1`.
- `--data-parallel-size <int>, -dp <int>`:  Default: `1`.
- `--data-parallel-size-local <int>, -dpl <int>`: Number of data parallel replicas to run on this node.
- `--decode-context-parallel-size <int>, -dcp <int>`:  Default: `1`.
- `--prefill-context-parallel-size <int>, -pcp <int>`:  Default: `1`.
- `--nnodes <int>, -n <int>`:  Default: `1`.
- `--node-rank <int>, -r <int>`:
- `--data-parallel-address <DATA_PARALLEL_ADDRESS>, -dpa <DATA_PARALLEL_ADDRESS>`: Address of data parallel cluster head-node.
- `--data-parallel-rpc-port <int>, -dpp <int>`: Port for data parallel RPC communication.
- `--data-parallel-rank <int>, -dpn <int>`: Data parallel rank of this instance. When set, enables external load balancer mode.
- `--data-parallel-start-rank <int>, -dpr <int>`: Starting data parallel rank for secondary nodes.
- `--data-parallel-backend <DATA_PARALLEL_BACKEND>, -dpb <DATA_PARALLEL_BACKEND>`: Backend for data parallel, either "mp" or "ray". Default: `"mp"`.
- `--master-addr <MASTER_ADDR>`:  Default: `"127.0.0.1"`.
- `--master-port <int>`:  Default: `29501`.
- `--data-parallel-external-lb, --no-data-parallel-external-lb, -dpe`:
- `--data-parallel-hybrid-lb, --no-data-parallel-hybrid-lb, -dph`:
- `--all2all-backend <allgather_reducescatter|deepep_high_throughput|deepep_low_latency|flashinfer_all2allv|mori|naive|pplx>`:  Default: `"allgather_reducescatter"`.
- `--enable-expert-parallel, --no-enable-expert-parallel, -ep`:
- `--enable-elastic-ep, --no-enable-elastic-ep`:
- `--enable-eplb, --no-enable-eplb`:
- `--eplb-config <EPLB_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `EPLBConfig(window_size=1000, step_interval=3000, num_redundant_experts=0, log_balancedness=False, log_balancedness_interval=1, use_async=False, policy='default')`.
- `--expert-placement-strategy <linear|round_robin>`:  Default: `"linear"`.
- `--distributed-executor-backend ['external_launcher', 'mp', 'ray', 'uni']`:
- `--max-parallel-loading-workers <MAX_PARALLEL_LOADING_WORKERS>`:
- `--worker-cls <WORKER_CLS>`:  Default: `"auto"`.
- `--worker-extension-cls <WORKER_EXTENSION_CLS>`:  Default: `""`.
- `--ray-workers-use-nsight, --no-ray-workers-use-nsight`:
- `--disable-custom-all-reduce, --no-disable-custom-all-reduce`:
- `--disable-nccl-for-dp-synchronization, --no-disable-nccl-for-dp-synchronization`:
- `--ubatch-size <int>`:
- `--cp-kv-cache-interleave-size <int>`:  Default: `1`.
- `--dcp-kv-cache-interleave-size <int>`:  Default: `1`.
- `--dbo-decode-token-threshold <int>`:  Default: `32`.
- `--dbo-prefill-token-threshold <int>`:  Default: `512`.
- `--enable-dbo, --no-enable-dbo`:

## Memory, Cache, And Throughput

Primary command:
- `vllm serve`

GPU, cache, batching, and offload knobs:

- `--gpu-memory-utilization <float>`:  Default: `0.9`.
- `--kv-cache-dtype <auto|bfloat16|fp8|fp8_ds_mla|fp8_e4m3|fp8_e5m2|fp8_inc>`:  Default: `"auto"`.
- `--kv-cache-memory-bytes <KV_CACHE_MEMORY_BYTES>`: Parse human-readable integers like '1k', '2M', etc.     Including decimal values with decimal multipliers.      Examples:     - '1k' -> 1,000     - '1K' -> 1,024     - '25.6k' -> 25,600
- `--block-size <1|8|16|32|64|128|256>`:
- `--num-gpu-blocks-override <NUM_GPU_BLOCKS_OVERRIDE>`:
- `--calculate-kv-scales, --no-calculate-kv-scales`:
- `--enable-prefix-caching, --no-enable-prefix-caching`:
- `--prefix-caching-hash-algo <sha256|sha256_cbor|xxhash|xxhash_cbor>`:  Default: `"sha256"`.
- `--kv-sharing-fast-prefill, --no-kv-sharing-fast-prefill`:
- `--enable-chunked-prefill, --no-enable-chunked-prefill`:
- `--disable-chunked-mm-input, --no-disable-chunked-mm-input`:
- `--long-prefill-token-threshold <int>`:
- `--max-long-partial-prefills <int>`:  Default: `1`.
- `--max-num-partial-prefills <int>`:  Default: `1`.
- `--disable-hybrid-kv-cache-manager, --no-disable-hybrid-kv-cache-manager`:
- `--max-num-batched-tokens <MAX_NUM_BATCHED_TOKENS>`: Parse human-readable integers like '1k', '2M', etc.     Including decimal values with decimal multipliers.      Examples:     - '1k' -> 1,000     - '1K' -> 1,024     - '25.6k' -> 25,600
- `--max-num-seqs <int>`:
- `--scheduler-cls <SCHEDULER_CLS>`:
- `--scheduling-policy <fcfs|priority>`:  Default: `"fcfs"`.
- `--async-scheduling, --no-async-scheduling`:
- `--stream-interval <int>`:  Default: `1`.
- `--swap-space <float>`:  Default: `4`.
- `--cpu-offload-gb <float>`:
- `--cpu-offload-params <CPU_OFFLOAD_PARAMS>`:  Default: `set()`.
- `--offload-backend <auto|prefetch|uva>`:  Default: `"auto"`.
- `--offload-group-size <int>`:
- `--offload-num-in-group <int>`:  Default: `1`.
- `--offload-params <OFFLOAD_PARAMS>`:  Default: `set()`.
- `--offload-prefetch-step <int>`:  Default: `1`.
- `--kv-offloading-backend <lmcache|native>`:  Default: `"native"`.
- `--kv-offloading-size <KV_OFFLOADING_SIZE>`:
- `--mamba-block-size <MAMBA_BLOCK_SIZE>`:
- `--mamba-cache-dtype <auto|float16|float32>`:  Default: `"auto"`.
- `--mamba-cache-mode <align|all|none>`:  Default: `"none"`.
- `--mamba-ssm-cache-dtype <auto|float16|float32>`:  Default: `"auto"`.

## Logging, Metrics, And Debugging

Primary command:
- `vllm serve`

General logging, metrics, and validation:

- `--disable-log-stats`: Disable logging statistics.
- `--aggregate-engine-logging`: Log aggregate rather than per-engine statistics when using data parallelism.
- `--enable-log-requests, --no-enable-log-requests`: Enable logging request information, dependant on log level: - INFO: Request ID, parameters and LoRA request. - DEBUG: Prompt inputs (e.g: text, token IDs). You can set the minimum log level via `VLLM_LOGGING_LEVEL`.
- `--enable-log-outputs, --no-enable-log-outputs`:
- `--enable-log-deltas, --no-enable-log-deltas`:  Default: `true`.
- `--max-log-len <MAX_LOG_LEN>`:
- `--log-config-file <LOG_CONFIG_FILE>`:
- `--log-error-stack, --no-log-error-stack`:
- `--fail-on-environ-validation, --no-fail-on-environ-validation`: If set, the engine will raise an error if environment validation fails.
- `--collect-detailed-traces {all,model,worker,None}`:
- `--cudagraph-metrics, --no-cudagraph-metrics`:
- `--enable-layerwise-nvtx-tracing, --no-enable-layerwise-nvtx-tracing`:
- `--enable-logging-iteration-details, --no-enable-logging-iteration-details`:
- `--enable-mfu-metrics, --no-enable-mfu-metrics`:
- `--kv-cache-metrics, --no-kv-cache-metrics`:
- `--kv-cache-metrics-sample <float>`:  Default: `0.01`.
- `--otlp-traces-endpoint <OTLP_TRACES_ENDPOINT>`:
- `--show-hidden-metrics-for-version <SHOW_HIDDEN_METRICS_FOR_VERSION>`:

## Advanced Execution Controls

Primary command:
- `vllm serve`

Lower-level backend, compilation, transfer, and profiler knobs:

- `--attention-backend <ATTENTION_BACKEND>`:
- `--kernel-config <KERNEL_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `KernelConfig(enable_flashinfer_autotune=None, moe_backend='auto')`.
- `--attention-config <ATTENTION_CONFIG>, -ac <ATTENTION_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `AttentionConfig(backend=None, flash_attn_version=None, use_prefill_decode_attention=False, flash_attn_max_num_splits_for_cuda_graph=32, use_cudnn_prefill=False, use_trtllm_ragged_deepseek_prefill=True, use_trtllm_attention=None, disable_flashinfer_prefill=False, disable_flashinfer_q_quantization=False, use_prefill_query_quantization=False)`.
- `--enable-flashinfer-autotune, --no-enable-flashinfer-autotune`:
- `--moe-backend <aiter|auto|cutlass|deep_gemm|flashinfer_cutedsl|flashinfer_cutlass|flashinfer_trtllm|marlin|triton>`:  Default: `"auto"`.
- `--cudagraph-capture-sizes <CUDAGRAPH_CAPTURE_SIZES>`:
- `--max-cudagraph-capture-size <int>`:
- `--compilation-config <COMPILATION_CONFIG>, -cc <COMPILATION_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `{'level': None, 'mode': None, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': [], 'splitting_ops': None, 'compile_mm_encoder': False, 'compile_sizes': None, 'compile_ranges_split_points': None, 'inductor_compile_config': {'enable_auto_functionalized_v2': False}, 'inductor_passes': {}, 'cudagraph_mode': None, 'cudagraph_num_of_warmups': 0, 'cudagraph_capture_sizes': None, 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': None, 'pass_config': {}, 'max_cudagraph_capture_size': None, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': False}, 'local_cache_dir': None, 'fast_moe_cold_start': None, 'static_all_moe_layers': []}`.
- `--optimization-level <OPTIMIZATION_LEVEL>`:  Default: `2`.
- `--performance-mode <balanced|interactivity|throughput>`:  Default: `"balanced"`.
- `--additional-config <ADDITIONAL_CONFIG>`:
- `--kv-transfer-config <KV_TRANSFER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--kv-events-config <KV_EVENTS_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--ec-transfer-config <EC_TRANSFER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--weight-transfer-config <WEIGHT_TRANSFER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--profiler-config <PROFILER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `ProfilerConfig(profiler=None, torch_profiler_dir='', torch_profiler_with_stack=True, torch_profiler_with_flops=False, torch_profiler_use_gzip=True, torch_profiler_dump_cuda_time_total=True, torch_profiler_record_shapes=False, torch_profiler_with_memory=False, ignore_frontend=False, delay_iterations=0, max_iterations=0)`.

## Batch Command Surface

Primary command:
- `vllm run-batch`

Purpose:
- run prompts from input file(s) and write results out, while still inheriting most of the same engine/config groups as `serve`

- `-i <INPUT_FILE>, --input-file <INPUT_FILE>`:
- `-o <OUTPUT_FILE>, --output-file <OUTPUT_FILE>`:
- `--output-tmp-dir <OUTPUT_TMP_DIR>`:
- `--url <URL>`:  Default: `"0.0.0.0"`.
- `--host <HOST>`:
- `--port <int>`:  Default: `8000`.
- `--enable-metrics`:
- `--chat-template <CHAT_TEMPLATE>`:
- `--chat-template-content-format <auto|openai|string>`:  Default: `"auto"`.
- `--default-chat-template-kwargs <DEFAULT_CHAT_TEMPLATE_KWARGS>`: Should either be a valid JSON string or JSON keys passed individually.
- `--disable-frontend-multiprocessing, --no-disable-frontend-multiprocessing`:
- `--enable-auto-tool-choice, --no-enable-auto-tool-choice`:
- `--enable-force-include-usage, --no-enable-force-include-usage`:
- `--enable-log-deltas, --no-enable-log-deltas`:  Default: `true`.
- `--enable-log-outputs, --no-enable-log-outputs`:
- `--enable-prompt-tokens-details, --no-enable-prompt-tokens-details`:
- `--enable-server-load-tracking, --no-enable-server-load-tracking`:
- `--enable-tokenizer-info-endpoint, --no-enable-tokenizer-info-endpoint`:
- `--exclude-tools-when-tool-choice-none, --no-exclude-tools-when-tool-choice-none`:
- `--lora-modules <LORA_MODULES>`:
- `--response-role <RESPONSE_ROLE>`:  Default: `"assistant"`.
- `--return-tokens-as-token-ids, --no-return-tokens-as-token-ids`:
- `--tokens-only, --no-tokens-only`:
- `--tool-call-parser {deepseek_v3,deepseek_v31,deepseek_v32,ernie45,functiongemma,gigachat3,glm45,glm47,granite,granite-20b-fc,hermes,hunyuan_a13b,internlm,jamba,kimi_k2,llama3_json,llama4_json,llama4_pythonic,longcat,minimax,minimax_m2,mistral,olmo3,openai,phi4_mini_json,pythonic,qwen3_coder,qwen3_xml,seed_oss,step3,step3p5,xlam} or name registered in --tool-parser-plugin`:
- `--tool-parser-plugin <TOOL_PARSER_PLUGIN>`:  Default: `""`.
- `--tool-server <TOOL_SERVER>`:
- `--trust-request-chat-template, --no-trust-request-chat-template`:

Shared inherited config groups:
- `ModelConfig`
- `LoadConfig`
- `AttentionConfig`
- `StructuredOutputsConfig`
- `ParallelConfig`
- `CacheConfig`
- `OffloadConfig`
- `MultiModalConfig`
- `LoRAConfig`
- `ObservabilityConfig`
- `SchedulerConfig`
- `CompilationConfig`
- `KernelConfig`
- `VllmConfig`

## Client Commands

These do not launch a server. They talk to a running OpenAI-compatible endpoint.

### `vllm chat`

- `--url <URL>`: url of the running OpenAI-Compatible RESTful API server Default: `"http://localhost:8000/v1"`.
- `--model-name <MODEL_NAME>`: The model name used in prompt completion, default to the first model in list models API call.
- `--api-key <API_KEY>`: API key for OpenAI services. If provided, this api key will overwrite the api key obtained through environment variables. It is important to note that this option only applies to the OpenAI-compatible API endpoints and NOT other endpoints that may be present in the server. See the security guide in the vLLM docs for more details.
- `--system-prompt <SYSTEM_PROMPT>`: The system prompt to be added to the chat template, used for models that support system prompts.
- `-q MESSAGE, --quick MESSAGE`: Send a single prompt as MESSAGE and print the response, then exit.

### `vllm complete`

- `--url <URL>`: url of the running OpenAI-Compatible RESTful API server Default: `"http://localhost:8000/v1"`.
- `--model-name <MODEL_NAME>`: The model name used in prompt completion, default to the first model in list models API call.
- `--api-key <API_KEY>`: API key for OpenAI services. If provided, this api key will overwrite the api key obtained through environment variables. It is important to note that this option only applies to the OpenAI-compatible API endpoints and NOT other endpoints that may be present in the server. See the security guide in the vLLM docs for more details.
- `--max-tokens <int>`: Maximum number of tokens to generate per output sequence.
- `-q PROMPT, --quick PROMPT`: Send a single prompt and print the completion output, then exit.

Sampling note:
- The registered local CLI does not expose a normal `vllm serve` sampling block with flags like `--temperature` or `--top-p`.
- Inference from the installed CLI surface: sampling appears to live mainly at request time for OpenAI-compatible serving, not as a primary server boot-time knob.
- The only directly exposed client-side generation cap in these kept commands is `vllm complete --max-tokens`.

## Deliberately Excluded

- `vllm bench ...`
- `vllm collect-env`

Reason:
- they are useful, but they are not part of the first-pass question of what this environment can serve and route agent traffic through
