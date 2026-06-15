# example-exl3-tabby

Example human manifest for an ExLlamaV3/TabbyAPI stable serving mux.

## Launch identity

- Mux: `example-exl3-tabby`
- Service: `main`
- Container: `agentmux-example-exl3-tabby-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/example-exl3-tabby/main -> /runs`

## Source

- Workspace: example `workspace-exl3`
- Backend: ExLlamaV3 via TabbyAPI
- Image: `localhost/agentmux-example-exl3-tabby:stable`

## Serving configuration

This section should be filled by the workspace export/import flow with the complete serving config
that produced the image: model, Tabby config, sampler overrides, templates, known caveats, and proving
notes.
