# Reference

Capture external facts here:
- APIs and SDK notes
- links to official docs
- environment setup details
- command snippets worth keeping

## vLLM CLI Snapshot

Use [generate_vllm_cli_flags.py](/home/poop/projects/agentmux/scripts/generate_vllm_cli_flags.py)
to regenerate the local `vllm` CLI references for this environment:

```bash
./scripts/generate_vllm_cli_flags.py
```

This script:
- rebuilds `docs/reference/vllm-cli-flags.md` from the installed `vllm` parser tree
- copies the current snapshot to `docs/reference/vllm-cli-flags-prev.md` before overwrite
- dedupes identical named flag groups across commands and replaces repeats with `Same as ...` references
- rebuilds `docs/reference/vllm-cli-capabilities.md` as a capability-oriented serving reference without a `prev` copy
- is useful after changing `vllm`, adding optional dependencies, or changing plugins that may expose new registered flags
