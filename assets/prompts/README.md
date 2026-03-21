# prompts/

This directory is for prompt reference material.

Current contract in this repo:
- prompt files here do not compile into `vllm serve` flags
- `agentmux` does not inject them into backend launch behavior
- frontends and agent clients are expected to own prompt composition and prompt injection

Why this is separate from chat templates:
- chat templates are backend launch inputs and map to real `vllm serve` behavior
- prompt files are request-side content unless the repo defines an explicit different contract later

Use this directory for:
- reusable prompt fragments
- prompt references you want versioned alongside muxes
- notes or starting points for frontend-side system prompts

Do not assume putting a prompt file here changes a running mux. It does not.
