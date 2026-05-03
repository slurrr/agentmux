# mux/bench/

Benchmark-only muxes live here.

Use this track when you want apples-to-apples comparisons across:
- full-weight models
- quantized variants
- different model families

## Recommended workflow

1. Copy `mux/examples/example_bench_mux.toml` into this directory.
2. Change only the fields that identify the target model:
   - `model`
   - `served_model_name`
   - `port`
3. Keep the rest of the serving shape fixed unless you intentionally want to benchmark a different envelope.

## Why keep this separate?

Your normal-use muxes may be tuned for their real day-to-day purpose:
- different `max_model_len`
- different cache settings
- different generation defaults
- different runtime tradeoffs

That is good for real use, but it can make benchmarks unfair or hard to compare.

`bench/` exists so the benchmark serving shape can stay stable while the model artifact changes.

## Current baseline guidance

The example bench mux uses a simple default benchmark envelope:
- `generation_config = "vllm"` to avoid model-specific HF generation defaults
- `max_model_len = 8192` as a sane benchmark context length for Phase 1
- `gpu_memory_utilization = 0.9`
- `host = "127.0.0.1"`

Adjust only if you intentionally want a different benchmark baseline.
