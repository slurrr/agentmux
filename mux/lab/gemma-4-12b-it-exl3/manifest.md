# gemma-4-12b-it-exl3

## Status

- Track: lab
- State: placeholder pending first generated workspace export/import
- Intended role: local agent-serving generalist

## Launch identity

- Mux: `gemma-4-12b-it-exl3`
- Service: `main`
- Container: `agentmux-gemma-4-12b-it-exl3-main`
- Host port: `8002`
- Container port: `5000`
- Runtime: `~/runs/agentmux/gemma-4-12b-it-exl3/main -> /runs`

## Source

- Workspace: `~/code/dev/workspace-exl3`
- Backend: ExLlamaV3 via TabbyAPI
- Image: `localhost/agentmux-gemma-4-12b-it-exl3:stable`

## Serving configuration

Fill this from the workspace export/import flow:

- source model / local artifact
- exact backend serving config
- Tabby config sections that matter
- sampler overrides
- templates / prompt format
- image build provenance
- proving notes
- caveats
- promotion history

## Notes

The `.toml` beside this file is only the launch recipe. This Markdown file is the human manifest for
what the mux actually represents.
