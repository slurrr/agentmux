# vLLM CLI Flag Map

This document is generated from the `vllm` installation in this repo environment. It lists commands, help layers, and registered flags that are actually present here.

## Probe Context
- Date: `2026-03-19`
- Repo: `/home/poop/projects/agentmux`
- Python: `3.12.12`
- vLLM: `0.17.1`
- vLLM entrypoint: `/home/poop/projects/agentmux/.venv/bin/vllm`
- Host: `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.35`
- Probe mode: force `vllm.platforms.current_platform = CpuPlatform()` before parser construction so help can be introspected on this host.
- Why the force is needed: plain `uv run vllm --help` currently aborts here with `RuntimeError: Failed to infer device type` while building the `serve` parser.

## Command Tree
- Top-level commands: `bench`, `chat`, `collect-env`, `complete`, `run-batch`, `serve`
- Nested commands: `vllm bench latency`, `vllm bench mm-processor`, `vllm bench serve`, `vllm bench startup`, `vllm bench sweep`, `vllm bench throughput`

## Help Layers
- `vllm --help`: top-level command list.
- `vllm <command> --help`: command-level help.
- `vllm bench <subcommand> --help`: nested benchmark help.
- Bottom-level parsers built with `FlexibleArgumentParser` also support `--help=<group>`, `--help=all`, and substring matching such as `--help=tokenizer`.
- Identical named flag groups are emitted once and later occurrences point back to the canonical command section.

## `vllm`
- Usage: `generate_vllm_cli_flags.py [-h] [-v]                                   {chat,complete,serve,bench,collect-env,run-batch}                                   ...`
- Subcommands: `bench`, `chat`, `collect-env`, `complete`, `run-batch`, `serve`
### options
- `-h, --help`: show this help message and exit
- `-v, --version`: show program's version number and exit

### `vllm bench`
- Usage: `vllm bench <bench_type> [options]`
- Subcommands: `latency`, `mm-processor`, `serve`, `startup`, `sweep`, `throughput`
### options
- Same as `vllm bench sweep` -> `options`.

#### `vllm bench latency`
- Usage: `vllm bench latency [options]`
- Help groups: `options`, `ModelConfig`, `LoadConfig`, `AttentionConfig`, `StructuredOutputsConfig`, `ParallelConfig`, `CacheConfig`, `OffloadConfig`, `MultiModalConfig`, `LoRAConfig`, `ObservabilityConfig`, `SchedulerConfig`, `CompilationConfig`, `KernelConfig`, `VllmConfig`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--aggregate-engine-logging`: Log aggregate rather than per-engine statistics when using data parallelism.
- `--batch-size <int>`:  Default: `8`.
- `--disable-detokenize`: Do not detokenize responses (i.e. do not include detokenization time in the latency measurement)
- `--disable-log-stats`: Disable logging statistics.
- `--fail-on-environ-validation, --no-fail-on-environ-validation`: If set, the engine will raise an error if environment validation fails.
- `--input-len <int>`:  Default: `32`.
- `--n <int>`: Number of generated sequences per prompt. Default: `1`.
- `--num-iters <int>`: Number of iterations to run. Default: `30`.
- `--num-iters-warmup <int>`: Number of iterations to run for warmup. Default: `10`.
- `--output-json <OUTPUT_JSON>`: Path to save the latency results in JSON format.
- `--output-len <int>`:  Default: `128`.
- `--profile`: profile the generation process of a single batch
- `--use-beam-search`:
- `-h, --help`: show this help message and exit
### ModelConfig
- Same as `vllm serve` -> `ModelConfig`.
### LoadConfig
- Same as `vllm serve` -> `LoadConfig`.
### AttentionConfig
- Same as `vllm serve` -> `AttentionConfig`.
### StructuredOutputsConfig
- Same as `vllm serve` -> `StructuredOutputsConfig`.
### ParallelConfig
- Same as `vllm serve` -> `ParallelConfig`.
### CacheConfig
- Same as `vllm serve` -> `CacheConfig`.
### OffloadConfig
- Same as `vllm serve` -> `OffloadConfig`.
### MultiModalConfig
- Same as `vllm serve` -> `MultiModalConfig`.
### LoRAConfig
- Same as `vllm serve` -> `LoRAConfig`.
### ObservabilityConfig
- Same as `vllm serve` -> `ObservabilityConfig`.
### SchedulerConfig
- Same as `vllm serve` -> `SchedulerConfig`.
### CompilationConfig
- Same as `vllm serve` -> `CompilationConfig`.
### KernelConfig
- Same as `vllm serve` -> `KernelConfig`.
### VllmConfig
- Same as `vllm serve` -> `VllmConfig`.

#### `vllm bench mm-processor`
- Usage: `vllm bench mm-processor [options]`
- Help groups: `options`, `ModelConfig`, `LoadConfig`, `AttentionConfig`, `StructuredOutputsConfig`, `ParallelConfig`, `CacheConfig`, `OffloadConfig`, `MultiModalConfig`, `LoRAConfig`, `ObservabilityConfig`, `SchedulerConfig`, `CompilationConfig`, `KernelConfig`, `VllmConfig`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--aggregate-engine-logging`: Log aggregate rather than per-engine statistics when using data parallelism.
- `--dataset-name <random-mm|hf>`: Name of the dataset to benchmark on. Defaults to 'random-mm'. Default: `"random-mm"`.
- `--dataset-path <DATASET_PATH>`: Path to the dataset file or HuggingFace dataset name (e.g., 'yale-nlp/MMVU', 'lmarena-ai/VisionArena-Chat').
- `--disable-log-stats`: Disable logging statistics.
- `--disable-tqdm`: Disable tqdm progress bar.
- `--fail-on-environ-validation, --no-fail-on-environ-validation`: If set, the engine will raise an error if environment validation fails.
- `--hf-split <HF_SPLIT>`: Split of the HuggingFace dataset (e.g., 'train', 'test', 'validation').
- `--hf-subset <HF_SUBSET>`: Subset of the HuggingFace dataset (optional).
- `--metric-percentiles <METRIC_PERCENTILES>`: Comma-separated list of percentiles to calculate (e.g., '50,90,99'). Default: `"99"`.
- `--no-reranker`: Whether the model supports reranking natively. Only used for reranker benchmark.
- `--num-prompts <int>`: Number of prompts to process. Default: `10`.
- `--num-warmups <int>`: Number of warmup prompts to process. Default: `1`.
- `--output-json <OUTPUT_JSON>`: Path to save the benchmark results in JSON format.
- `--output-len <int>`: Output length for each request. Overrides the default output lengths from the dataset.
- `--random-batch-size <int>`: Batch size for random sampling. Only used for embeddings benchmark. Default: `1`.
- `--random-input-len <int>`: Number of input tokens per request, used only for random sampling. Default: `1024`.
- `--random-mm-base-items-per-request <int>`: Base number of multimodal items per request for random-mm. Actual per-request count is sampled around this base using --random-mm-num-mm-items-range-ratio. Default: `1`.
- `--random-mm-bucket-config <RANDOM_MM_BUCKET_CONFIG>`: The bucket config is a dictionary mapping a multimodal itemsampling configuration to a probability.Currently allows for 2 modalities: images and videos. An bucket key is a tuple of (height, width, num_frames)The value is the probability of sampling that specific item. Example: --random-mm-bucket-config {(256, 256, 1): 0.5, (720, 1280, 1): 0.4, (720, 1280, 16): 0.10} First item: images with resolution 256x256 w.p. 0.5Second item: images with resolution 720x1280 w.p. 0.4 Third item: videos with resolution 720x1280 and 16 frames w.p. 0.1OBS.: If the probabilities do not sum to 1, they are normalized.OBS bis.: Only image sampling is supported for now. Default: `{(256, 256, 1): 0.5, (720, 1280, 1): 0.5, (720, 1280, 16): 0.0}`.
- `--random-mm-limit-mm-per-prompt <RANDOM_MM_LIMIT_MM_PER_PROMPT>`: Per-modality hard caps for items attached per request, e.g. '{"image": 3, "video": 0}'. The sampled per-request item count is clamped to the sum of these limits. When a modality reaches its cap, its buckets are excluded and probabilities are renormalized.OBS.: Only image sampling is supported for now. Default: `{"image": 255, "video": 1}`.
- `--random-mm-num-mm-items-range-ratio <float>`: Range ratio r in [0, 1] for sampling items per request. We sample uniformly from the closed integer range [floor(n*(1-r)), ceil(n*(1+r))] where n is the base items per request. r=0 keeps it fixed; r=1 allows 0 items. The maximum is clamped to the sum of per-modality limits from --random-mm-limit-mm-per-prompt. An error is raised if the computed min exceeds the max.
- `--random-output-len <int>`: Number of output tokens per request, used only for random sampling. Default: `128`.
- `--random-prefix-len <int>`: Number of fixed prefix tokens before the random context in a request. The total input length is the sum of `random-prefix-len` and a random context length sampled from [input_len * (1 - range_ratio), input_len * (1 + range_ratio)].
- `--random-range-ratio <float>`: Range ratio for sampling input/output length, used only for random sampling. Must be in the range [0, 1) to define a symmetric sampling range[length * (1 - range_ratio), length * (1 + range_ratio)].
- `-h, --help`: show this help message and exit
### ModelConfig
- Same as `vllm serve` -> `ModelConfig`.
### LoadConfig
- Same as `vllm serve` -> `LoadConfig`.
### AttentionConfig
- Same as `vllm serve` -> `AttentionConfig`.
### StructuredOutputsConfig
- Same as `vllm serve` -> `StructuredOutputsConfig`.
### ParallelConfig
- Same as `vllm serve` -> `ParallelConfig`.
### CacheConfig
- Same as `vllm serve` -> `CacheConfig`.
### OffloadConfig
- Same as `vllm serve` -> `OffloadConfig`.
### MultiModalConfig
- Same as `vllm serve` -> `MultiModalConfig`.
### LoRAConfig
- Same as `vllm serve` -> `LoRAConfig`.
### ObservabilityConfig
- Same as `vllm serve` -> `ObservabilityConfig`.
### SchedulerConfig
- Same as `vllm serve` -> `SchedulerConfig`.
### CompilationConfig
- Same as `vllm serve` -> `CompilationConfig`.
### KernelConfig
- Same as `vllm serve` -> `KernelConfig`.
### VllmConfig
- Same as `vllm serve` -> `VllmConfig`.

#### `vllm bench serve`
- Usage: `vllm bench serve [options]`
- Help groups: `options`, `custom dataset options`, `spec bench dataset options`, `sonnet dataset options`, `sharegpt dataset options`, `blazedit dataset options`, `asr dataset options`, `random dataset options`, `random multimodal dataset options extended from random dataset`, `hf dataset options`, `prefix repetition dataset options`, `sampling parameters`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--append-result`: Append the benchmark result to the existing json file.
- `--backend <vllm|openai|openai-chat|openai-audio|openai-embeddings|openai-embeddings-chat|openai-embeddings-clip|openai-embeddings-vlm2vec|infinity-embeddings|infinity-embeddings-clip|vllm-pooling|vllm-rerank>`: The type of backend or endpoint to use for the benchmark. Default: `"openai"`.
- `--base-url <BASE_URL>`: Server or API base url if not using http host and port.
- `--burstiness <float>`: Burstiness factor of the request generation. Only take effect when request_rate is not inf. Default value is 1, which follows Poisson process. Otherwise, the request intervals follow a gamma distribution. A lower burstiness value (0 < burstiness < 1) results in more bursty requests. A higher burstiness value (burstiness > 1) results in a more uniform arrival of requests. Default: `1.0`.
- `--dataset-name <sharegpt|burstgpt|sonnet|random|random-mm|random-rerank|hf|custom|custom_mm|prefix_repetition|spec_bench>`: Name of the dataset to benchmark on. Default: `"random"`.
- `--dataset-path <DATASET_PATH>`: Path to the sharegpt/sonnet dataset. Or the huggingface dataset ID if using HF dataset.
- `--disable-shuffle`: Disable shuffling of dataset samples for deterministic ordering.
- `--disable-tqdm`: Specify to disable tqdm progress bar.
- `--enable-multimodal-chat`: Enable multimodal chat transformation for datasets that support it.
- `--endpoint <ENDPOINT>`: API endpoint. Default: `"/v1/completions"`.
- `--extra-body <EXTRA_BODY>`: A JSON string representing extra body parameters to include in each request.Example: '{"chat_template_kwargs":{"enable_thinking":false}}'
- `--goodput <GOODPUT>`: Specify service level objectives for goodput as "KEY:VALUE" pairs, where the key is a metric name, and the value is in milliseconds. Multiple "KEY:VALUE" pairs can be provided, separated by spaces. Allowed request level metric names are "ttft", "tpot", "e2el". For more context on the definition of goodput, refer to DistServe paper: https://arxiv.org/pdf/2401.09670 and the blog: https://hao-ai-lab.github.io/blogs/distserve
- `--header KEY=VALUE`: Key-value pairs (e.g, --header x-additional-info=0.3.3) for headers to be passed with each request. These headers override per backend constants and values set via environment variable, and will be overridden by other arguments (such as request ids).
- `--host <HOST>`:  Default: `"127.0.0.1"`.
- `--ignore-eos`: Set ignore_eos flag when sending the benchmark request.Warning: ignore_eos is not supported in deepspeed_mii and tgi.
- `--input-len <int>`: General input length for datasets. Maps to dataset-specific input length arguments (e.g., --random-input-len, --sonnet-input-len). If not specified, uses dataset defaults.
- `--insecure`: Disable SSL certificate verification. Use this option when connecting to servers with self-signed certificates.
- `--label <LABEL>`: The label (prefix) of the benchmark results. If not specified, the value of '--backend' will be used as the label.
- `--logprobs <int>`: Number of logprobs-per-token to compute & return as part of the request. If unspecified, then either (1) if beam search is disabled, no logprobs are computed & a single dummy logprob is returned for each token; or (2) if beam search is enabled 1 logprob per token is computed
- `--lora-modules <LORA_MODULES>`: A subset of LoRA module names passed in when launching the server. For each request, the script chooses a LoRA module at random.
- `--max-concurrency <int>`: Maximum number of concurrent requests. This can be used to help simulate an environment where a higher level component is enforcing a maximum number of concurrent requests. While the --request-rate argument controls the rate at which requests are initiated, this argument will control how many are actually allowed to execute at a time. This means that when used in combination, the actual request rate may be lower than specified with --request-rate, if the server is not processing requests fast enough to keep up.
- `--metadata KEY=VALUE`: Key-value pairs (e.g, --metadata version=0.3.3 tp=1) for metadata of this run to be saved in the result JSON file for record keeping purposes.
- `--metric-percentiles <METRIC_PERCENTILES>`: Comma-separated list of percentiles for selected metrics. To report 25-th, 50-th, and 75-th percentiles, use "25,50,75". Default value is "99".Use "--percentile-metrics" to select metrics. Default: `"99"`.
- `--model <MODEL>`: Name of the model. If not specified, will fetch the first model from the server's /v1/models endpoint.
- `--no-oversample`: Do not oversample if the dataset has fewer samples than num-prompts.
- `--no-stream`: Do not load the dataset in streaming mode.
- `--num-prompts <int>`: Number of prompts to process. Default: `1000`.
- `--num-warmups <int>`: Number of warmup requests.
- `--output-len <int>`: General output length for datasets. Maps to dataset-specific output length arguments (e.g., --random-output-len, --sonnet-output-len). If not specified, uses dataset defaults.
- `--percentile-metrics <PERCENTILE_METRICS>`: Comma-separated list of selected metrics to report percentiles. This argument specifies the metrics to report percentiles. Allowed metric names are "ttft", "tpot", "itl", "e2el". If not specified, defaults to "ttft,tpot,itl" for generative models and "e2el" for pooling models.
- `--plot-dataset-stats`: Generate a matplotlib figure with dataset statistics showing prompt tokens, output tokens, and combined token distributions.
- `--plot-timeline`: Generate an HTML timeline plot showing request execution. The plot will be saved alongside the results JSON file.
- `--port <int>`:  Default: `8000`.
- `--profile`: Use vLLM Profiling. --profiler-config must be provided on the server.
- `--ramp-up-end-rps <int>`: The ending request rate for ramp-up (RPS). Needs to be specified when --ramp-up-strategy is used.
- `--ramp-up-start-rps <int>`: The starting request rate for ramp-up (RPS). Needs to be specified when --ramp-up-strategy is used.
- `--ramp-up-strategy <linear|exponential>`: The ramp-up strategy. This would be used to ramp up the request rate from initial RPS to final RPS rate (specified by --ramp-up-start-rps and --ramp-up-end-rps.) over the duration of the benchmark.
- `--ready-check-timeout-sec <int>`: Maximum time to wait for the endpoint to become ready in seconds. Ready check will be skipped by default.
- `--request-id-prefix <REQUEST_ID_PREFIX>`: Specify the prefix of request id. Default: `"bench-08e47118-"`.
- `--request-rate <float>`: Number of requests per second. If this is inf, then all the requests are sent at time 0. Otherwise, we use Poisson process or gamma distribution to synthesize the request arrival times. Default: `Infinity`.
- `--result-dir <RESULT_DIR>`: Specify directory to save benchmark json results.If not specified, results are saved in the current directory.
- `--result-filename <RESULT_FILENAME>`: Specify the filename to save benchmark json results.If not specified, results will be saved in {label}-{args.request_rate}qps-{base_model_id}-{current_dt}.json format.
- `--save-detailed`: When saving the results, whether to include per request information such as response, error, ttfts, tpots, etc.
- `--save-result`: Specify to save benchmark results to a json file
- `--seed <int>`:
- `--served-model-name <SERVED_MODEL_NAME>`: The model name used in the API. If not specified, the model name will be the same as the `--model` argument.
- `--skip-chat-template`: Skip applying chat template to prompt for datasets that support it.
- `--skip-tokenizer-init`: Skip initialization of tokenizer and detokenizer
- `--timeline-itl-thresholds THRESHOLD1 THRESHOLD2`: ITL thresholds in milliseconds for timeline plot coloring. Specify two values to categorize inter-token latencies into three groups: below first threshold (green), between thresholds (orange), and above second threshold (red). Default: 25 50 (milliseconds). Default: `[25.0, 50.0]`.
- `--tokenizer <TOKENIZER>`: Name or path of the tokenizer, if not using the default tokenizer.
- `--tokenizer-mode <TOKENIZER_MODE>`: Tokenizer mode:          - "auto" will use the tokenizer from `mistral_common` for Mistral models         if available, otherwise it will use the "hf" tokenizer.          - "hf" will use the fast tokenizer if available.          - "slow" will always use the slow tokenizer.          - "mistral" will always use the tokenizer from `mistral_common`.          - "deepseek_v32" will always use the tokenizer from `deepseek_v32`.          - "qwen_vl" will always use the tokenizer from `qwen_vl`.          - Other custom values can be supported via plugins. Default: `"auto"`.
- `--trust-remote-code`: Trust remote code from huggingface
- `--use-beam-search`:
- `-h, --help`: show this help message and exit
### custom dataset options
- `--custom-output-len <int>`: Number of output tokens per request. Unless it is set to -1, the value overrides potential output length loaded from the dataset. It is used only for custom dataset. Default: `256`.
### spec bench dataset options
- `--spec-bench-category <SPEC_BENCH_CATEGORY>`: Category for spec bench dataset. If None, use all categories.
- `--spec-bench-output-len <int>`: Num of output tokens per request, used only for spec bench dataset. Default: `256`.
### sonnet dataset options
- `--sonnet-input-len <int>`: Number of input tokens per request, used only for sonnet dataset. Default: `550`.
- `--sonnet-output-len <int>`: Number of output tokens per request, used only for sonnet dataset. Default: `150`.
- `--sonnet-prefix-len <int>`: Number of prefix tokens per request, used only for sonnet dataset. Default: `200`.
### sharegpt dataset options
- `--sharegpt-output-len <int>`: Output length for each request. Overrides the output length from the ShareGPT dataset.
### blazedit dataset options
- `--blazedit-max-distance <float>`: Maximum distance for blazedit dataset. Min: 0, Max: 1.0 Default: `1.0`.
- `--blazedit-min-distance <float>`: Minimum distance for blazedit dataset. Min: 0, Max: 1.0
### asr dataset options
- `--asr-max-audio-len-sec <float>`: Maximum audio length in seconds for ASR dataset. Default: `Infinity`.
- `--asr-min-audio-len-sec <float>`: Minimum audio length in seconds for ASR dataset.
### random dataset options
- `--no-reranker`: Whether the model supports reranking natively. Only used for reranker benchmark.
- `--random-batch-size <int>`: Batch size for random sampling. Only used for embeddings benchmark. Default: `1`.
- `--random-input-len <int>`: Number of input tokens per request, used only for random sampling. Default: `1024`.
- `--random-output-len <int>`: Number of output tokens per request, used only for random sampling. Default: `128`.
- `--random-prefix-len <int>`: Number of fixed prefix tokens before the random context in a request. The total input length is the sum of `random-prefix-len` and a random context length sampled from [input_len * (1 - range_ratio), input_len * (1 + range_ratio)].
- `--random-range-ratio <float>`: Range ratio for sampling input/output length, used only for random sampling. Must be in the range [0, 1) to define a symmetric sampling range[length * (1 - range_ratio), length * (1 + range_ratio)].
### random multimodal dataset options extended from random dataset
- `--random-mm-base-items-per-request <int>`: Base number of multimodal items per request for random-mm. Actual per-request count is sampled around this base using --random-mm-num-mm-items-range-ratio. Default: `1`.
- `--random-mm-bucket-config <RANDOM_MM_BUCKET_CONFIG>`: The bucket config is a dictionary mapping a multimodal itemsampling configuration to a probability.Currently allows for 2 modalities: images and videos. An bucket key is a tuple of (height, width, num_frames)The value is the probability of sampling that specific item. Example: --random-mm-bucket-config {(256, 256, 1): 0.5, (720, 1280, 1): 0.4, (720, 1280, 16): 0.10} First item: images with resolution 256x256 w.p. 0.5Second item: images with resolution 720x1280 w.p. 0.4 Third item: videos with resolution 720x1280 and 16 frames w.p. 0.1OBS.: If the probabilities do not sum to 1, they are normalized.OBS bis.: Only image sampling is supported for now. Default: `{(256, 256, 1): 0.5, (720, 1280, 1): 0.5, (720, 1280, 16): 0.0}`.
- `--random-mm-limit-mm-per-prompt <RANDOM_MM_LIMIT_MM_PER_PROMPT>`: Per-modality hard caps for items attached per request, e.g. '{"image": 3, "video": 0}'. The sampled per-request item count is clamped to the sum of these limits. When a modality reaches its cap, its buckets are excluded and probabilities are renormalized.OBS.: Only image sampling is supported for now. Default: `{"image": 255, "video": 1}`.
- `--random-mm-num-mm-items-range-ratio <float>`: Range ratio r in [0, 1] for sampling items per request. We sample uniformly from the closed integer range [floor(n*(1-r)), ceil(n*(1+r))] where n is the base items per request. r=0 keeps it fixed; r=1 allows 0 items. The maximum is clamped to the sum of per-modality limits from --random-mm-limit-mm-per-prompt. An error is raised if the computed min exceeds the max.
### hf dataset options
- `--hf-name <HF_NAME>`: Name of the dataset on HuggingFace (e.g., 'lmarena-ai/VisionArena-Chat'). Specify this if your dataset-path is a local path.
- `--hf-output-len <int>`: Output length for each request. Overrides the output lengths from the sampled HF dataset.
- `--hf-split <HF_SPLIT>`: Split of the HF dataset.
- `--hf-subset <HF_SUBSET>`: Subset of the HF dataset.
### prefix repetition dataset options
- `--prefix-repetition-num-prefixes <int>`: Number of prefixes to generate, used only for prefix repetition dataset. Prompts per prefix is num_requests // num_prefixes. Default: `10`.
- `--prefix-repetition-output-len <int>`: Number of output tokens per request, used only for prefix repetition dataset. Default: `128`.
- `--prefix-repetition-prefix-len <int>`: Number of prefix tokens per request, used only for prefix repetition dataset. Default: `256`.
- `--prefix-repetition-suffix-len <int>`: Number of suffix tokens per request, used only for prefix repetition dataset. Total input length is prefix_len + suffix_len. Default: `256`.
### sampling parameters
- `--frequency-penalty <float>`: Frequency penalty sampling parameter. Only has effect on openai-compatible backends.
- `--min-p <float>`: Min-p sampling parameter. Only has effect on openai-compatible backends.
- `--presence-penalty <float>`: Presence penalty sampling parameter. Only has effect on openai-compatible backends.
- `--repetition-penalty <float>`: Repetition penalty sampling parameter. Only has effect on openai-compatible backends.
- `--temperature <float>`: Temperature sampling parameter. Only has effect on openai-compatible backends.
- `--top-k <int>`: Top-k sampling parameter. Only has effect on openai-compatible backends.
- `--top-p <float>`: Top-p sampling parameter. Only has effect on openai-compatible backends.

#### `vllm bench startup`
- Usage: `vllm bench startup [options]`
- Help groups: `options`, `ModelConfig`, `LoadConfig`, `AttentionConfig`, `StructuredOutputsConfig`, `ParallelConfig`, `CacheConfig`, `OffloadConfig`, `MultiModalConfig`, `LoRAConfig`, `ObservabilityConfig`, `SchedulerConfig`, `CompilationConfig`, `KernelConfig`, `VllmConfig`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--aggregate-engine-logging`: Log aggregate rather than per-engine statistics when using data parallelism.
- `--disable-log-stats`: Disable logging statistics.
- `--fail-on-environ-validation, --no-fail-on-environ-validation`: If set, the engine will raise an error if environment validation fails.
- `--num-iters-cold <int>`: Number of cold startup iterations. Default: `3`.
- `--num-iters-warm <int>`: Number of warm startup iterations. Default: `3`.
- `--num-iters-warmup <int>`: Number of warmup iterations before benchmarking warm startups. Default: `1`.
- `--output-json <OUTPUT_JSON>`: Path to save the startup time results in JSON format.
- `-h, --help`: show this help message and exit
### ModelConfig
- Same as `vllm serve` -> `ModelConfig`.
### LoadConfig
- Same as `vllm serve` -> `LoadConfig`.
### AttentionConfig
- Same as `vllm serve` -> `AttentionConfig`.
### StructuredOutputsConfig
- Same as `vllm serve` -> `StructuredOutputsConfig`.
### ParallelConfig
- Same as `vllm serve` -> `ParallelConfig`.
### CacheConfig
- Same as `vllm serve` -> `CacheConfig`.
### OffloadConfig
- Same as `vllm serve` -> `OffloadConfig`.
### MultiModalConfig
- Same as `vllm serve` -> `MultiModalConfig`.
### LoRAConfig
- Same as `vllm serve` -> `LoRAConfig`.
### ObservabilityConfig
- Same as `vllm serve` -> `ObservabilityConfig`.
### SchedulerConfig
- Same as `vllm serve` -> `SchedulerConfig`.
### CompilationConfig
- Same as `vllm serve` -> `CompilationConfig`.
### KernelConfig
- Same as `vllm serve` -> `KernelConfig`.
### VllmConfig
- Same as `vllm serve` -> `VllmConfig`.

#### `vllm bench sweep`
- Usage: `vllm bench sweep [options]`
- Subcommands: `plot`, `plot_pareto`, `serve`, `serve_workload`, `startup`
### options
- `-h, --help`: show this help message and exit

##### `vllm bench sweep plot`
- Usage: `vllm bench sweep plot [options]`
- Help groups: `positional arguments`, `options`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### positional arguments
- `EXPERIMENT_DIR`: The directory containing the sweep results to plot.
### options
- `--bin-by <BIN_BY>`: A comma-separated list of statements indicating values to bin by. This is useful to avoid plotting points that are too close together. Example: `request_throughput%%1` means use a bin size of 1 for the `request_throughput` variable. Default: `""`.
- `--col-by <COL_BY>`: A comma-separated list of variables, such that a separate column is created for each combination of these variables. Default: `""`.
- `--curve-by <CURVE_BY>`: A comma-separated list of variables, such that a separate curve is created for each combination of these variables.
- `--dry-run`: If set, prints the information about each figure to plot, then exits without drawing them.
- `--fig-by <FIG_BY>`: A comma-separated list of variables, such that a separate figure is created for each combination of these variables. Default: `""`.
- `--fig-dir <FIG_DIR>`: The directory to save the figures, relative to `OUTPUT_DIR`. By default, the same directory is used. Default: `""`.
- `--fig-dpi <int>`: Resolution of the output figure in dots per inch. Default: 300 Default: `300`.
- `--fig-height <float>`: Height of each subplot in inches. Default: 6.4 Default: `6.4`.
- `--fig-name <FIG_NAME>`: Name prefix for the output figure file. Group data is always appended when present. Default: 'FIGURE'. Example: --fig-name my_performance_plot Default: `"FIGURE"`.
- `--filter-by <FILTER_BY>`: A comma-separated list of statements indicating values to filter by. This is useful to remove outliers. Example: `max_concurrency<1000,max_num_batched_tokens<=4096` means plot only the points where `max_concurrency` is less than 1000 and `max_num_batched_tokens` is no greater than 4096. Default: `""`.
- `--no-error-bars`: If set, disables error bars on the plot. By default, error bars are shown.
- `--row-by <ROW_BY>`: A comma-separated list of variables, such that a separate row is created for each combination of these variables. Default: `""`.
- `--scale-x <SCALE_X>`: The scale to use for the x-axis. Currently only accepts string values such as 'log' and 'sqrt'. See also: https://seaborn.pydata.org/generated/seaborn.objects.Plot.scale.html
- `--scale-y <SCALE_Y>`: The scale to use for the y-axis. Currently only accepts string values such as 'log' and 'sqrt'. See also: https://seaborn.pydata.org/generated/seaborn.objects.Plot.scale.html
- `--var-x <VAR_X>`: The variable for the x-axis. Default: `"total_token_throughput"`.
- `--var-y <VAR_Y>`: The variable for the y-axis Default: `"median_ttft_ms"`.
- `-h, --help`: show this help message and exit

##### `vllm bench sweep plot_pareto`
- Usage: `vllm bench sweep plot_pareto [options]`
- Help groups: `positional arguments`, `options`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### positional arguments
- Same as `vllm bench sweep plot` -> `positional arguments`.
### options
- `--dry-run`: If set, prints the figures to plot without drawing them.
- `--gpu-count-var <GPU_COUNT_VAR>`: Result key that stores GPU count. If not provided, falls back to num_gpus/gpu_count or tensor_parallel_size * pipeline_parallel_size.
- `--label-by <LABEL_BY>`: Comma-separated list of fields to annotate on Pareto frontier points. Default: `"max_concurrency,gpu_count"`.
- `--user-count-var <USER_COUNT_VAR>`: Result key that stores concurrent user count. Falls back to max_concurrent_requests if missing. Default: `"max_concurrency"`.
- `-h, --help`: show this help message and exit

##### `vllm bench sweep serve`
- Usage: `vllm bench sweep serve [options]`
- Help groups: `options`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--after-bench-cmd <AFTER_BENCH_CMD>`: After a benchmark run is complete, invoke this command instead of the default `ServerWrapper.clear_cache()`.
- `--bench-cmd <BENCH_CMD>`: The command used to run the benchmark: `vllm bench serve ...`
- `--bench-params <BENCH_PARAMS>`: Path to JSON file containing parameter combinations for the `vllm bench serve` command. Can be either a list of dicts or a dict where keys are benchmark names. If both `serve_params` and `bench_params` are given, this script will iterate over their Cartesian product.
- `--dry-run`: If set, prints the commands to run, then exits without executing them.
- `--link-vars <LINK_VARS>`: Comma-separated list of linked variables between serve and bench, e.g. max_num_seqs=max_concurrency,max_model_len=random_input_len Default: `""`.
- `--num-runs <int>`: Number of runs per parameter combination. Default: `3`.
- `--resume`: Resume a previous execution of this script, i.e., only run parameter combinations for which there are still no output files under `output_dir/experiment_name`.
- `--serve-cmd <SERVE_CMD>`: The command used to run the server: `vllm serve ...`
- `--serve-params <SERVE_PARAMS>`: Path to JSON file containing parameter combinations for the `vllm serve` command. Can be either a list of dicts or a dict where keys are benchmark names. If both `serve_params` and `bench_params` are given, this script will iterate over their Cartesian product.
- `--server-ready-timeout <int>`: Timeout in seconds to wait for the server to become ready. Default: `300`.
- `--show-stdout`: If set, logs the standard output of subcommands. Useful for debugging but can be quite spammy.
- `-e <EXPERIMENT_NAME>, --experiment-name <EXPERIMENT_NAME>`: The name of this experiment (defaults to current timestamp). Results will be stored under `output_dir/experiment_name`.
- `-h, --help`: show this help message and exit
- `-o <OUTPUT_DIR>, --output-dir <OUTPUT_DIR>`: The main directory to which results are written. Default: `"results"`.

##### `vllm bench sweep serve_workload`
- Usage: `vllm bench sweep serve_workload [options]`
- Help groups: `options`, `workload options`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- Same as `vllm bench sweep serve` -> `options`.
### workload options
- `--workload-iters <int>`: Number of workload levels to explore. This includes the first two iterations used to interpolate the value of `workload_var` for remaining iterations. Default: `10`.
- `--workload-var <request_rate|max_concurrency>`: The variable to adjust in each iteration. Default: `"request_rate"`.

##### `vllm bench sweep startup`
- Usage: `vllm bench sweep startup [options]`
- Help groups: `options`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--dry-run`: If set, prints the commands to run, then exits without executing them.
- `--num-runs <int>`: Number of runs per parameter combination. Default: `1`.
- `--resume`: Resume a previous execution of this script, i.e., only run parameter combinations for which there are still no output files under `output_dir/experiment_name`.
- `--serve-params <SERVE_PARAMS>`: Path to JSON file containing parameter combinations for the `vllm serve` command. Only parameters supported by `vllm bench startup` will be applied.
- `--show-stdout`: If set, logs the standard output of subcommands.
- `--startup-cmd <STARTUP_CMD>`: The command used to run the startup benchmark. Default: `"vllm bench startup"`.
- `--startup-params <STARTUP_PARAMS>`: Path to JSON file containing parameter combinations for the `vllm bench startup` command.
- `--strict-params`: If set, unknown parameters in sweep files raise an error instead of being ignored.
- `-e <EXPERIMENT_NAME>, --experiment-name <EXPERIMENT_NAME>`: The name of this experiment (defaults to current timestamp). Results will be stored under `output_dir/experiment_name`.
- `-h, --help`: show this help message and exit
- `-o <OUTPUT_DIR>, --output-dir <OUTPUT_DIR>`: The main directory to which results are written. Default: `"results"`.

#### `vllm bench throughput`
- Usage: `vllm bench throughput [options]`
- Help groups: `options`, `ModelConfig`, `LoadConfig`, `AttentionConfig`, `StructuredOutputsConfig`, `ParallelConfig`, `CacheConfig`, `OffloadConfig`, `MultiModalConfig`, `LoRAConfig`, `ObservabilityConfig`, `SchedulerConfig`, `CompilationConfig`, `KernelConfig`, `VllmConfig`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--aggregate-engine-logging`: Log aggregate rather than per-engine statistics when using data parallelism.
- `--async-engine`: Use vLLM async engine rather than LLM class.
- `--backend <vllm|hf|mii|vllm-chat>`:  Default: `"vllm"`.
- `--dataset <DATASET>`: Path to the ShareGPT dataset, will be deprecated in            the next release. The dataset is expected to be a json in form of list[dict[..., conversations: list[dict[..., value: <prompt_or_response>]]]]
- `--dataset-name <sharegpt|random|sonnet|burstgpt|hf|prefix_repetition|random-mm|random-rerank>`: Name of the dataset to benchmark on. Default: `"sharegpt"`.
- `--dataset-path <DATASET_PATH>`: Path to the dataset
- `--disable-detokenize`: Do not detokenize the response (i.e. do not include detokenization time in the measurement)
- `--disable-frontend-multiprocessing`: Disable decoupled async engine frontend.
- `--disable-log-stats`: Disable logging statistics.
- `--enable-log-requests, --no-enable-log-requests`: Enable logging request information, dependant on log level: - INFO: Request ID, parameters and LoRA request. - DEBUG: Prompt inputs (e.g: text, token IDs). You can set the minimum log level via `VLLM_LOGGING_LEVEL`.
- `--fail-on-environ-validation, --no-fail-on-environ-validation`: If set, the engine will raise an error if environment validation fails.
- `--hf-max-batch-size <int>`: Maximum batch size for HF backend.
- `--hf-split <HF_SPLIT>`: Split of the HF dataset.
- `--hf-subset <HF_SUBSET>`: Subset of the HF dataset.
- `--input-len <int>`: Input prompt length for each request
- `--lora-path <LORA_PATH>`: Path to the lora adapters to use. This can be an absolute path, a relative path, or a Hugging Face model identifier.
- `--n <int>`: Number of generated sequences per prompt. Default: `1`.
- `--no-reranker`: Whether the model supports reranking natively. Only used for reranker benchmark.
- `--num-prompts <int>`: Number of prompts to process. Default: `1000`.
- `--output-json <OUTPUT_JSON>`: Path to save the throughput results in JSON format.
- `--output-len <int>`: Output length for each request. Overrides the output length from the dataset.
- `--prefix-len <int>`: Number of fixed prefix tokens before the random context in a request (default: 0).
- `--prefix-repetition-num-prefixes <int>`: Number of prefixes to generate, used only for prefix repetition dataset. Prompts per prefix is num_requests // num_prefixes.
- `--prefix-repetition-output-len <int>`: Number of output tokens per request, used only for prefix repetition dataset.
- `--prefix-repetition-prefix-len <int>`: Number of prefix tokens per request, used only for prefix repetition dataset.
- `--prefix-repetition-suffix-len <int>`: Number of suffix tokens per request, used only for prefix repetition dataset. Total input length is prefix_len + suffix_len.
- `--profile`: Use vLLM Profiling. --profiler-config must be provided on the server.
- `--random-batch-size <int>`: Batch size for random sampling. Only used for embeddings benchmark. Default: `1`.
- `--random-input-len <int>`: Number of input tokens per request, used only for random sampling. Default: `1024`.
- `--random-mm-base-items-per-request <int>`: Base number of multimodal items per request for random-mm. Actual per-request count is sampled around this base using --random-mm-num-mm-items-range-ratio. Default: `1`.
- `--random-mm-bucket-config <RANDOM_MM_BUCKET_CONFIG>`: The bucket config is a dictionary mapping a multimodal itemsampling configuration to a probability.Currently allows for 2 modalities: images and videos. An bucket key is a tuple of (height, width, num_frames)The value is the probability of sampling that specific item. Example: --random-mm-bucket-config {(256, 256, 1): 0.5, (720, 1280, 1): 0.4, (720, 1280, 16): 0.10} First item: images with resolution 256x256 w.p. 0.5Second item: images with resolution 720x1280 w.p. 0.4 Third item: videos with resolution 720x1280 and 16 frames w.p. 0.1OBS.: If the probabilities do not sum to 1, they are normalized.OBS bis.: Only image sampling is supported for now. Default: `{(256, 256, 1): 0.5, (720, 1280, 1): 0.5, (720, 1280, 16): 0.0}`.
- `--random-mm-limit-mm-per-prompt <RANDOM_MM_LIMIT_MM_PER_PROMPT>`: Per-modality hard caps for items attached per request, e.g. '{"image": 3, "video": 0}'. The sampled per-request item count is clamped to the sum of these limits. When a modality reaches its cap, its buckets are excluded and probabilities are renormalized.OBS.: Only image sampling is supported for now. Default: `{"image": 255, "video": 1}`.
- `--random-mm-num-mm-items-range-ratio <float>`: Range ratio r in [0, 1] for sampling items per request. We sample uniformly from the closed integer range [floor(n*(1-r)), ceil(n*(1+r))] where n is the base items per request. r=0 keeps it fixed; r=1 allows 0 items. The maximum is clamped to the sum of per-modality limits from --random-mm-limit-mm-per-prompt. An error is raised if the computed min exceeds the max.
- `--random-output-len <int>`: Number of output tokens per request, used only for random sampling. Default: `128`.
- `--random-prefix-len <int>`: Number of fixed prefix tokens before the random context in a request. The total input length is the sum of `random-prefix-len` and a random context length sampled from [input_len * (1 - range_ratio), input_len * (1 + range_ratio)].
- `--random-range-ratio <float>`: Range ratio for sampling input/output length, used only for random sampling. Must be in the range [0, 1) to define a symmetric sampling range[length * (1 - range_ratio), length * (1 + range_ratio)].
- `-h, --help`: show this help message and exit
### ModelConfig
- Same as `vllm serve` -> `ModelConfig`.
### LoadConfig
- Same as `vllm serve` -> `LoadConfig`.
### AttentionConfig
- Same as `vllm serve` -> `AttentionConfig`.
### StructuredOutputsConfig
- Same as `vllm serve` -> `StructuredOutputsConfig`.
### ParallelConfig
- Same as `vllm serve` -> `ParallelConfig`.
### CacheConfig
- Same as `vllm serve` -> `CacheConfig`.
### OffloadConfig
- Same as `vllm serve` -> `OffloadConfig`.
### MultiModalConfig
- Same as `vllm serve` -> `MultiModalConfig`.
### LoRAConfig
- Same as `vllm serve` -> `LoRAConfig`.
### ObservabilityConfig
- Same as `vllm serve` -> `ObservabilityConfig`.
### SchedulerConfig
- Same as `vllm serve` -> `SchedulerConfig`.
### CompilationConfig
- Same as `vllm serve` -> `CompilationConfig`.
### KernelConfig
- Same as `vllm serve` -> `KernelConfig`.
### VllmConfig
- Same as `vllm serve` -> `VllmConfig`.

### `vllm chat`
- Usage: `vllm chat [options]`
- Help groups: `options`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--api-key <API_KEY>`: API key for OpenAI services. If provided, this api key will overwrite the api key obtained through environment variables. It is important to note that this option only applies to the OpenAI-compatible API endpoints and NOT other endpoints that may be present in the server. See the security guide in the vLLM docs for more details.
- `--model-name <MODEL_NAME>`: The model name used in prompt completion, default to the first model in list models API call.
- `--system-prompt <SYSTEM_PROMPT>`: The system prompt to be added to the chat template, used for models that support system prompts.
- `--url <URL>`: url of the running OpenAI-Compatible RESTful API server Default: `"http://localhost:8000/v1"`.
- `-h, --help`: show this help message and exit
- `-q MESSAGE, --quick MESSAGE`: Send a single prompt as MESSAGE and print the response, then exit.

### `vllm collect-env`
- Usage: `vllm collect-env`
- Help groups: `options`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- Same as `vllm bench sweep` -> `options`.

### `vllm complete`
- Usage: `vllm complete [options]`
- Help groups: `options`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--api-key <API_KEY>`: API key for OpenAI services. If provided, this api key will overwrite the api key obtained through environment variables. It is important to note that this option only applies to the OpenAI-compatible API endpoints and NOT other endpoints that may be present in the server. See the security guide in the vLLM docs for more details.
- `--max-tokens <int>`: Maximum number of tokens to generate per output sequence.
- `--model-name <MODEL_NAME>`: The model name used in prompt completion, default to the first model in list models API call.
- `--url <URL>`: url of the running OpenAI-Compatible RESTful API server Default: `"http://localhost:8000/v1"`.
- `-h, --help`: show this help message and exit
- `-q PROMPT, --quick PROMPT`: Send a single prompt and print the completion output, then exit.

### `vllm run-batch`
- Usage: `vllm run-batch -i INPUT.jsonl -o OUTPUT.jsonl --model <model>`
- Help groups: `options`, `BatchFrontend`, `ModelConfig`, `LoadConfig`, `AttentionConfig`, `StructuredOutputsConfig`, `ParallelConfig`, `CacheConfig`, `OffloadConfig`, `MultiModalConfig`, `LoRAConfig`, `ObservabilityConfig`, `SchedulerConfig`, `CompilationConfig`, `KernelConfig`, `VllmConfig`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### options
- `--aggregate-engine-logging`: Log aggregate rather than per-engine statistics when using data parallelism.
- `--disable-log-stats`: Disable logging statistics.
- `--enable-log-requests, --no-enable-log-requests`: Enable logging request information, dependant on log level: - INFO: Request ID, parameters and LoRA request. - DEBUG: Prompt inputs (e.g: text, token IDs). You can set the minimum log level via `VLLM_LOGGING_LEVEL`.
- `--fail-on-environ-validation, --no-fail-on-environ-validation`: If set, the engine will raise an error if environment validation fails.
- `-h, --help`: show this help message and exit
### BatchFrontend
- `--chat-template <CHAT_TEMPLATE>`:
- `--chat-template-content-format <auto|openai|string>`:  Default: `"auto"`.
- `--default-chat-template-kwargs <DEFAULT_CHAT_TEMPLATE_KWARGS>`: Should either be a valid JSON string or JSON keys passed individually.
- `--disable-frontend-multiprocessing, --no-disable-frontend-multiprocessing`:
- `--enable-auto-tool-choice, --no-enable-auto-tool-choice`:
- `--enable-force-include-usage, --no-enable-force-include-usage`:
- `--enable-log-deltas, --no-enable-log-deltas`:  Default: `true`.
- `--enable-log-outputs, --no-enable-log-outputs`:
- `--enable-metrics`:
- `--enable-prompt-tokens-details, --no-enable-prompt-tokens-details`:
- `--enable-server-load-tracking, --no-enable-server-load-tracking`:
- `--enable-tokenizer-info-endpoint, --no-enable-tokenizer-info-endpoint`:
- `--exclude-tools-when-tool-choice-none, --no-exclude-tools-when-tool-choice-none`:
- `--host <HOST>`:
- `--log-config-file <LOG_CONFIG_FILE>`:
- `--log-error-stack, --no-log-error-stack`:
- `--lora-modules <LORA_MODULES>`:
- `--max-log-len <MAX_LOG_LEN>`:
- `--output-tmp-dir <OUTPUT_TMP_DIR>`:
- `--port <int>`:  Default: `8000`.
- `--response-role <RESPONSE_ROLE>`:  Default: `"assistant"`.
- `--return-tokens-as-token-ids, --no-return-tokens-as-token-ids`:
- `--tokens-only, --no-tokens-only`:
- `--tool-call-parser {deepseek_v3,deepseek_v31,deepseek_v32,ernie45,functiongemma,gigachat3,glm45,glm47,granite,granite-20b-fc,hermes,hunyuan_a13b,internlm,jamba,kimi_k2,llama3_json,llama4_json,llama4_pythonic,longcat,minimax,minimax_m2,mistral,olmo3,openai,phi4_mini_json,pythonic,qwen3_coder,qwen3_xml,seed_oss,step3,step3p5,xlam} or name registered in --tool-parser-plugin`:
- `--tool-parser-plugin <TOOL_PARSER_PLUGIN>`:  Default: `""`.
- `--tool-server <TOOL_SERVER>`:
- `--trust-request-chat-template, --no-trust-request-chat-template`:
- `--url <URL>`:  Default: `"0.0.0.0"`.
- `-i <INPUT_FILE>, --input-file <INPUT_FILE>`:
- `-o <OUTPUT_FILE>, --output-file <OUTPUT_FILE>`:
### ModelConfig
- Same as `vllm serve` -> `ModelConfig`.
### LoadConfig
- Same as `vllm serve` -> `LoadConfig`.
### AttentionConfig
- Same as `vllm serve` -> `AttentionConfig`.
### StructuredOutputsConfig
- Same as `vllm serve` -> `StructuredOutputsConfig`.
### ParallelConfig
- Same as `vllm serve` -> `ParallelConfig`.
### CacheConfig
- Same as `vllm serve` -> `CacheConfig`.
### OffloadConfig
- Same as `vllm serve` -> `OffloadConfig`.
### MultiModalConfig
- Same as `vllm serve` -> `MultiModalConfig`.
### LoRAConfig
- Same as `vllm serve` -> `LoRAConfig`.
### ObservabilityConfig
- Same as `vllm serve` -> `ObservabilityConfig`.
### SchedulerConfig
- Same as `vllm serve` -> `SchedulerConfig`.
### CompilationConfig
- Same as `vllm serve` -> `CompilationConfig`.
### KernelConfig
- Same as `vllm serve` -> `KernelConfig`.
### VllmConfig
- Same as `vllm serve` -> `VllmConfig`.

### `vllm serve`
- Usage: `vllm serve [model_tag] [options]`
- Help groups: `positional arguments`, `options`, `Frontend`, `ModelConfig`, `LoadConfig`, `AttentionConfig`, `StructuredOutputsConfig`, `ParallelConfig`, `CacheConfig`, `OffloadConfig`, `MultiModalConfig`, `LoRAConfig`, `ObservabilityConfig`, `SchedulerConfig`, `CompilationConfig`, `KernelConfig`, `VllmConfig`
- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output.
### positional arguments
- `model_tag`: The model tag to serve (optional if specified in config)
### options
- `--aggregate-engine-logging`: Log aggregate rather than per-engine statistics when using data parallelism.
- `--api-server-count <int>, -asc <int>`: How many API server processes to run. Defaults to data_parallel_size if not specified.
- `--config <CONFIG>`: Read CLI options from a config file. Must be a YAML with the following options: https://docs.vllm.ai/en/latest/configuration/serve_args.html
- `--disable-log-stats`: Disable logging statistics.
- `--enable-log-requests, --no-enable-log-requests`: Enable logging request information, dependant on log level: - INFO: Request ID, parameters and LoRA request. - DEBUG: Prompt inputs (e.g: text, token IDs). You can set the minimum log level via `VLLM_LOGGING_LEVEL`.
- `--fail-on-environ-validation, --no-fail-on-environ-validation`: If set, the engine will raise an error if environment validation fails.
- `--headless`: Run in headless mode. See multi-node data parallel documentation for more details.
- `-h, --help`: show this help message and exit
### Frontend
- `--allow-credentials, --no-allow-credentials`:
- `--allowed-headers <ALLOWED_HEADERS>`:  Default: `["*"]`.
- `--allowed-methods <ALLOWED_METHODS>`:  Default: `["*"]`.
- `--allowed-origins <ALLOWED_ORIGINS>`:  Default: `["*"]`.
- `--api-key <API_KEY>`:
- `--chat-template <CHAT_TEMPLATE>`:
- `--chat-template-content-format <auto|openai|string>`:  Default: `"auto"`.
- `--default-chat-template-kwargs <DEFAULT_CHAT_TEMPLATE_KWARGS>`: Should either be a valid JSON string or JSON keys passed individually.
- `--disable-access-log-for-endpoints <DISABLE_ACCESS_LOG_FOR_ENDPOINTS>`:
- `--disable-fastapi-docs, --no-disable-fastapi-docs`:
- `--disable-frontend-multiprocessing, --no-disable-frontend-multiprocessing`:
- `--disable-uvicorn-access-log, --no-disable-uvicorn-access-log`:
- `--enable-auto-tool-choice, --no-enable-auto-tool-choice`:
- `--enable-force-include-usage, --no-enable-force-include-usage`:
- `--enable-log-deltas, --no-enable-log-deltas`:  Default: `true`.
- `--enable-log-outputs, --no-enable-log-outputs`:
- `--enable-offline-docs, --no-enable-offline-docs`:
- `--enable-prompt-tokens-details, --no-enable-prompt-tokens-details`:
- `--enable-request-id-headers, --no-enable-request-id-headers`:
- `--enable-server-load-tracking, --no-enable-server-load-tracking`:
- `--enable-ssl-refresh, --no-enable-ssl-refresh`:
- `--enable-tokenizer-info-endpoint, --no-enable-tokenizer-info-endpoint`:
- `--exclude-tools-when-tool-choice-none, --no-exclude-tools-when-tool-choice-none`:
- `--h11-max-header-count <int>`:  Default: `256`.
- `--h11-max-incomplete-event-size <int>`:  Default: `4194304`.
- `--host <HOST>`:
- `--log-config-file <LOG_CONFIG_FILE>`:
- `--log-error-stack, --no-log-error-stack`:
- `--lora-modules <LORA_MODULES>`:
- `--max-log-len <MAX_LOG_LEN>`:
- `--middleware <MIDDLEWARE>`:
- `--port <int>`:  Default: `8000`.
- `--response-role <RESPONSE_ROLE>`:  Default: `"assistant"`.
- `--return-tokens-as-token-ids, --no-return-tokens-as-token-ids`:
- `--root-path <ROOT_PATH>`:
- `--ssl-ca-certs <SSL_CA_CERTS>`:
- `--ssl-cert-reqs <int>`:
- `--ssl-certfile <SSL_CERTFILE>`:
- `--ssl-ciphers <SSL_CIPHERS>`:
- `--ssl-keyfile <SSL_KEYFILE>`:
- `--tokens-only, --no-tokens-only`:
- `--tool-call-parser {deepseek_v3,deepseek_v31,deepseek_v32,ernie45,functiongemma,gigachat3,glm45,glm47,granite,granite-20b-fc,hermes,hunyuan_a13b,internlm,jamba,kimi_k2,llama3_json,llama4_json,llama4_pythonic,longcat,minimax,minimax_m2,mistral,olmo3,openai,phi4_mini_json,pythonic,qwen3_coder,qwen3_xml,seed_oss,step3,step3p5,xlam} or name registered in --tool-parser-plugin`:
- `--tool-parser-plugin <TOOL_PARSER_PLUGIN>`:  Default: `""`.
- `--tool-server <TOOL_SERVER>`:
- `--trust-request-chat-template, --no-trust-request-chat-template`:
- `--uds <UDS>`:
- `--use-gpu-for-pooling-score, --no-use-gpu-for-pooling-score`:
- `--uvicorn-log-level <critical|debug|error|info|trace|warning>`:  Default: `"info"`.
### ModelConfig
- `--allow-deprecated-quantization, --no-allow-deprecated-quantization`:
- `--allowed-local-media-path <ALLOWED_LOCAL_MEDIA_PATH>`:  Default: `""`.
- `--allowed-media-domains <ALLOWED_MEDIA_DOMAINS>`:
- `--code-revision <CODE_REVISION>`:
- `--config-format ['auto', 'hf', 'mistral']`:  Default: `"auto"`.
- `--convert <auto|classify|embed|none>`:  Default: `"auto"`.
- `--disable-cascade-attn, --no-disable-cascade-attn`:
- `--disable-sliding-window, --no-disable-sliding-window`:
- `--dtype <auto|bfloat16|float|float16|float32|half>`:  Default: `"auto"`.
- `--enable-prompt-embeds, --no-enable-prompt-embeds`:
- `--enable-return-routed-experts, --no-enable-return-routed-experts`:
- `--enable-sleep-mode, --no-enable-sleep-mode`:
- `--enforce-eager, --no-enforce-eager`:
- `--generation-config <GENERATION_CONFIG>`:  Default: `"auto"`.
- `--hf-config-path <HF_CONFIG_PATH>`:
- `--hf-overrides <HF_OVERRIDES>`:
- `--hf-token <HF_TOKEN>`:
- `--io-processor-plugin <IO_PROCESSOR_PLUGIN>`:
- `--logits-processors <LOGITS_PROCESSORS>`:
- `--logprobs-mode <processed_logits|processed_logprobs|raw_logits|raw_logprobs>`:  Default: `"raw_logprobs"`.
- `--max-logprobs <int>`:  Default: `20`.
- `--max-model-len <MAX_MODEL_LEN>`: Parse human-readable integers like '1k', '2M', etc.     Including decimal values with decimal multipliers.     Also accepts -1 or 'auto' as a special value for auto-detection.      Examples:     - '1k' -> 1,000     - '1K' -> 1,024     - '25.6k' -> 25,600     - '-1' or 'auto' -> -1 (special value for auto-detection)
- `--model <MODEL>`:  Default: `"Qwen/Qwen3-0.6B"`.
- `--model-impl ['auto', 'terratorch', 'transformers', 'vllm']`:  Default: `"auto"`.
- `--override-attention-dtype <OVERRIDE_ATTENTION_DTYPE>`:
- `--override-generation-config <OVERRIDE_GENERATION_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--pooler-config <POOLER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--quantization <QUANTIZATION>, -q <QUANTIZATION>`:
- `--revision <REVISION>`:
- `--runner <auto|draft|generate|pooling>`:  Default: `"auto"`.
- `--seed <int>`:
- `--served-model-name <SERVED_MODEL_NAME>`:
- `--skip-tokenizer-init, --no-skip-tokenizer-init`:
- `--tokenizer <TOKENIZER>`:
- `--tokenizer-mode ['auto', 'deepseek_v32', 'hf', 'mistral', 'slow']`:  Default: `"auto"`.
- `--tokenizer-revision <TOKENIZER_REVISION>`:
- `--trust-remote-code, --no-trust-remote-code`:
### LoadConfig
- `--download-dir <DOWNLOAD_DIR>`:
- `--ignore-patterns <IGNORE_PATTERNS>`:  Default: `["original/**/*"]`.
- `--load-format <LOAD_FORMAT>`:  Default: `"auto"`.
- `--model-loader-extra-config <MODEL_LOADER_EXTRA_CONFIG>`:
- `--pt-load-map-location <PT_LOAD_MAP_LOCATION>`:  Default: `"cpu"`.
- `--safetensors-load-strategy <SAFETENSORS_LOAD_STRATEGY>`:  Default: `"lazy"`.
- `--use-tqdm-on-load, --no-use-tqdm-on-load`:  Default: `true`.
### AttentionConfig
- `--attention-backend <ATTENTION_BACKEND>`:
### StructuredOutputsConfig
- `--reasoning-parser <REASONING_PARSER>`:  Default: `""`.
- `--reasoning-parser-plugin <REASONING_PARSER_PLUGIN>`:  Default: `""`.
### ParallelConfig
- `--all2all-backend <allgather_reducescatter|deepep_high_throughput|deepep_low_latency|flashinfer_all2allv|mori|naive|pplx>`:  Default: `"allgather_reducescatter"`.
- `--cp-kv-cache-interleave-size <int>`:  Default: `1`.
- `--data-parallel-address <DATA_PARALLEL_ADDRESS>, -dpa <DATA_PARALLEL_ADDRESS>`: Address of data parallel cluster head-node.
- `--data-parallel-backend <DATA_PARALLEL_BACKEND>, -dpb <DATA_PARALLEL_BACKEND>`: Backend for data parallel, either "mp" or "ray". Default: `"mp"`.
- `--data-parallel-external-lb, --no-data-parallel-external-lb, -dpe`:
- `--data-parallel-hybrid-lb, --no-data-parallel-hybrid-lb, -dph`:
- `--data-parallel-rank <int>, -dpn <int>`: Data parallel rank of this instance. When set, enables external load balancer mode.
- `--data-parallel-rpc-port <int>, -dpp <int>`: Port for data parallel RPC communication.
- `--data-parallel-size <int>, -dp <int>`:  Default: `1`.
- `--data-parallel-size-local <int>, -dpl <int>`: Number of data parallel replicas to run on this node.
- `--data-parallel-start-rank <int>, -dpr <int>`: Starting data parallel rank for secondary nodes.
- `--dbo-decode-token-threshold <int>`:  Default: `32`.
- `--dbo-prefill-token-threshold <int>`:  Default: `512`.
- `--dcp-kv-cache-interleave-size <int>`:  Default: `1`.
- `--decode-context-parallel-size <int>, -dcp <int>`:  Default: `1`.
- `--disable-custom-all-reduce, --no-disable-custom-all-reduce`:
- `--disable-nccl-for-dp-synchronization, --no-disable-nccl-for-dp-synchronization`:
- `--distributed-executor-backend ['external_launcher', 'mp', 'ray', 'uni']`:
- `--enable-dbo, --no-enable-dbo`:
- `--enable-elastic-ep, --no-enable-elastic-ep`:
- `--enable-eplb, --no-enable-eplb`:
- `--enable-expert-parallel, --no-enable-expert-parallel, -ep`:
- `--eplb-config <EPLB_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `EPLBConfig(window_size=1000, step_interval=3000, num_redundant_experts=0, log_balancedness=False, log_balancedness_interval=1, use_async=False, policy='default')`.
- `--expert-placement-strategy <linear|round_robin>`:  Default: `"linear"`.
- `--master-addr <MASTER_ADDR>`:  Default: `"127.0.0.1"`.
- `--master-port <int>`:  Default: `29501`.
- `--max-parallel-loading-workers <MAX_PARALLEL_LOADING_WORKERS>`:
- `--nnodes <int>, -n <int>`:  Default: `1`.
- `--node-rank <int>, -r <int>`:
- `--pipeline-parallel-size <int>, -pp <int>`:  Default: `1`.
- `--prefill-context-parallel-size <int>, -pcp <int>`:  Default: `1`.
- `--ray-workers-use-nsight, --no-ray-workers-use-nsight`:
- `--tensor-parallel-size <int>, -tp <int>`:  Default: `1`.
- `--ubatch-size <int>`:
- `--worker-cls <WORKER_CLS>`:  Default: `"auto"`.
- `--worker-extension-cls <WORKER_EXTENSION_CLS>`:  Default: `""`.
### CacheConfig
- `--block-size <1|8|16|32|64|128|256>`:
- `--calculate-kv-scales, --no-calculate-kv-scales`:
- `--enable-prefix-caching, --no-enable-prefix-caching`:
- `--gpu-memory-utilization <float>`:  Default: `0.9`.
- `--kv-cache-dtype <auto|bfloat16|fp8|fp8_ds_mla|fp8_e4m3|fp8_e5m2|fp8_inc>`:  Default: `"auto"`.
- `--kv-cache-memory-bytes <KV_CACHE_MEMORY_BYTES>`: Parse human-readable integers like '1k', '2M', etc.     Including decimal values with decimal multipliers.      Examples:     - '1k' -> 1,000     - '1K' -> 1,024     - '25.6k' -> 25,600
- `--kv-offloading-backend <lmcache|native>`:  Default: `"native"`.
- `--kv-offloading-size <KV_OFFLOADING_SIZE>`:
- `--kv-sharing-fast-prefill, --no-kv-sharing-fast-prefill`:
- `--mamba-block-size <MAMBA_BLOCK_SIZE>`:
- `--mamba-cache-dtype <auto|float16|float32>`:  Default: `"auto"`.
- `--mamba-cache-mode <align|all|none>`:  Default: `"none"`.
- `--mamba-ssm-cache-dtype <auto|float16|float32>`:  Default: `"auto"`.
- `--num-gpu-blocks-override <NUM_GPU_BLOCKS_OVERRIDE>`:
- `--prefix-caching-hash-algo <sha256|sha256_cbor|xxhash|xxhash_cbor>`:  Default: `"sha256"`.
- `--swap-space <float>`:  Default: `4`.
### OffloadConfig
- `--cpu-offload-gb <float>`:
- `--cpu-offload-params <CPU_OFFLOAD_PARAMS>`:  Default: `set()`.
- `--offload-backend <auto|prefetch|uva>`:  Default: `"auto"`.
- `--offload-group-size <int>`:
- `--offload-num-in-group <int>`:  Default: `1`.
- `--offload-params <OFFLOAD_PARAMS>`:  Default: `set()`.
- `--offload-prefetch-step <int>`:  Default: `1`.
### MultiModalConfig
- `--enable-mm-embeds, --no-enable-mm-embeds`:
- `--interleave-mm-strings, --no-interleave-mm-strings`:
- `--language-model-only, --no-language-model-only`:
- `--limit-mm-per-prompt <LIMIT_MM_PER_PROMPT>`: Should either be a valid JSON string or JSON keys passed individually.
- `--media-io-kwargs <MEDIA_IO_KWARGS>`: Should either be a valid JSON string or JSON keys passed individually.
- `--mm-encoder-attn-backend <MM_ENCODER_ATTN_BACKEND>`:
- `--mm-encoder-only, --no-mm-encoder-only`:
- `--mm-encoder-tp-mode <data|weights>`:  Default: `"weights"`.
- `--mm-processor-cache-gb <float>`:  Default: `4`.
- `--mm-processor-cache-type <lru|shm>`:  Default: `"lru"`.
- `--mm-processor-kwargs <MM_PROCESSOR_KWARGS>`: Should either be a valid JSON string or JSON keys passed individually.
- `--mm-shm-cache-max-object-size-mb <int>`:  Default: `128`.
- `--skip-mm-profiling, --no-skip-mm-profiling`:
- `--video-pruning-rate <VIDEO_PRUNING_RATE>`:
### LoRAConfig
- `--default-mm-loras <DEFAULT_MM_LORAS>`: Should either be a valid JSON string or JSON keys passed individually.
- `--enable-lora, --no-enable-lora`: If True, enable handling of LoRA adapters.
- `--enable-tower-connector-lora, --no-enable-tower-connector-lora`:
- `--fully-sharded-loras, --no-fully-sharded-loras`:
- `--lora-dtype <auto|bfloat16|float16>`:  Default: `"auto"`.
- `--max-cpu-loras <MAX_CPU_LORAS>`:
- `--max-lora-rank <1|8|16|32|64|128|256|320|512>`:  Default: `16`.
- `--max-loras <int>`:  Default: `1`.
- `--specialize-active-lora, --no-specialize-active-lora`:
### ObservabilityConfig
- `--collect-detailed-traces {all,model,worker,None}`:
- `--cudagraph-metrics, --no-cudagraph-metrics`:
- `--enable-layerwise-nvtx-tracing, --no-enable-layerwise-nvtx-tracing`:
- `--enable-logging-iteration-details, --no-enable-logging-iteration-details`:
- `--enable-mfu-metrics, --no-enable-mfu-metrics`:
- `--kv-cache-metrics, --no-kv-cache-metrics`:
- `--kv-cache-metrics-sample <float>`:  Default: `0.01`.
- `--otlp-traces-endpoint <OTLP_TRACES_ENDPOINT>`:
- `--show-hidden-metrics-for-version <SHOW_HIDDEN_METRICS_FOR_VERSION>`:
### SchedulerConfig
- `--async-scheduling, --no-async-scheduling`:
- `--disable-chunked-mm-input, --no-disable-chunked-mm-input`:
- `--disable-hybrid-kv-cache-manager, --no-disable-hybrid-kv-cache-manager`:
- `--enable-chunked-prefill, --no-enable-chunked-prefill`:
- `--long-prefill-token-threshold <int>`:
- `--max-long-partial-prefills <int>`:  Default: `1`.
- `--max-num-batched-tokens <MAX_NUM_BATCHED_TOKENS>`: Parse human-readable integers like '1k', '2M', etc.     Including decimal values with decimal multipliers.      Examples:     - '1k' -> 1,000     - '1K' -> 1,024     - '25.6k' -> 25,600
- `--max-num-partial-prefills <int>`:  Default: `1`.
- `--max-num-seqs <int>`:
- `--scheduler-cls <SCHEDULER_CLS>`:
- `--scheduling-policy <fcfs|priority>`:  Default: `"fcfs"`.
- `--stream-interval <int>`:  Default: `1`.
### CompilationConfig
- `--cudagraph-capture-sizes <CUDAGRAPH_CAPTURE_SIZES>`:
- `--max-cudagraph-capture-size <int>`:
### KernelConfig
- `--enable-flashinfer-autotune, --no-enable-flashinfer-autotune`:
- `--moe-backend <aiter|auto|cutlass|deep_gemm|flashinfer_cutedsl|flashinfer_cutlass|flashinfer_trtllm|marlin|triton>`:  Default: `"auto"`.
### VllmConfig
- `--additional-config <ADDITIONAL_CONFIG>`:
- `--attention-config <ATTENTION_CONFIG>, -ac <ATTENTION_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `AttentionConfig(backend=None, flash_attn_version=None, use_prefill_decode_attention=False, flash_attn_max_num_splits_for_cuda_graph=32, use_cudnn_prefill=False, use_trtllm_ragged_deepseek_prefill=True, use_trtllm_attention=None, disable_flashinfer_prefill=False, disable_flashinfer_q_quantization=False, use_prefill_query_quantization=False)`.
- `--compilation-config <COMPILATION_CONFIG>, -cc <COMPILATION_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `{'level': None, 'mode': None, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': [], 'splitting_ops': None, 'compile_mm_encoder': False, 'compile_sizes': None, 'compile_ranges_split_points': None, 'inductor_compile_config': {'enable_auto_functionalized_v2': False}, 'inductor_passes': {}, 'cudagraph_mode': None, 'cudagraph_num_of_warmups': 0, 'cudagraph_capture_sizes': None, 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': None, 'pass_config': {}, 'max_cudagraph_capture_size': None, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': False}, 'local_cache_dir': None, 'fast_moe_cold_start': None, 'static_all_moe_layers': []}`.
- `--ec-transfer-config <EC_TRANSFER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--kernel-config <KERNEL_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `KernelConfig(enable_flashinfer_autotune=None, moe_backend='auto')`.
- `--kv-events-config <KV_EVENTS_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--kv-transfer-config <KV_TRANSFER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--optimization-level <OPTIMIZATION_LEVEL>`:  Default: `2`.
- `--performance-mode <balanced|interactivity|throughput>`:  Default: `"balanced"`.
- `--profiler-config <PROFILER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `ProfilerConfig(profiler=None, torch_profiler_dir='', torch_profiler_with_stack=True, torch_profiler_with_flops=False, torch_profiler_use_gzip=True, torch_profiler_dump_cuda_time_total=True, torch_profiler_record_shapes=False, torch_profiler_with_memory=False, ignore_frontend=False, delay_iterations=0, max_iterations=0)`.
- `--speculative-config <SPECULATIVE_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
- `--structured-outputs-config <STRUCTURED_OUTPUTS_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually. Default: `StructuredOutputsConfig(backend='auto', disable_fallback=False, disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False)`.
- `--weight-transfer-config <WEIGHT_TRANSFER_CONFIG>`: Should either be a valid JSON string or JSON keys passed individually.
