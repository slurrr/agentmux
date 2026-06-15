# example-gguf

Example human manifest for a GGUF/llama.cpp stable serving mux.

## Launch identity

- Mux: `example-gguf`
- Service: `main`
- Container: `agentmux-example-gguf-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/example-gguf/main -> /runs`

## Source

- Workspace: example `workspace-gguf`
- Backend: llama.cpp / GGUF
- Image: `localhost/agentmux-example-gguf:stable`

## Serving configuration

This section should be filled by the workspace export/import flow with the complete serving config
that produced the image: model, quant, llama-server args/config, sampling defaults, templates, known
caveats, and proving notes.
