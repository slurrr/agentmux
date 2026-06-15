# Workspace Export To AgentMux Contract v1

## Purpose

This contract tells backend workspaces what to deliver when a proven backend/model should become an
AgentMux mux.

Exports are not meant to live forever in AgentMux. They are input material for creating an AgentMux
mux directory.

## Deliverable

A workspace should export enough information to create:

```text
mux/<track>/<mux-name>/
  mux.toml
  manifest.md
```

The preferred export can be exactly those two files. If the workspace writes an intermediate export
format, AgentMux should import/convert it and then discard or archive the intermediate artifact.

## `mux.toml` target shape

```toml
[mux]
name = "gemma-4-12b-it-exl3"
primary_service = "main"

[services.main]
image = "localhost/agentmux-gemma-4-12b-it-exl3:stable"
container_name = "agentmux-gemma-4-12b-it-exl3-main"
port = 8002
container_port = 5000
podman_args = ["--security-opt", "label=disable", "--device", "nvidia.com/gpu=all"]
health_path = "/v1/models"
```

Required service fields:

- `image`: proven prebuilt image to run
- `container_name`: stable managed container name
- `port`: host-facing port

Recommended service fields:

- `container_port`: port the service listens on inside the container; defaults to `port`
- `podman_args`: GPU/security args needed by this image
- `health_path`: readiness path; defaults to `/v1/models`
- `command`: only if the image default `CMD` is not enough
- `env`, `labels`, `volumes`: only when truly launch-relevant

## Standard AgentMux runtime mount

AgentMux always appends:

```text
~/runs/agentmux/<mux>/<service>:/runs:rw
```

Workspaces should make promoted images use `/runs` for writable runtime/log/data state. If the
backend wants another path, handle that inside the image.

## No automatic model mount

AgentMux does not automatically mount `~/models`.

If a promoted image needs host model files, the workspace export/import should make that explicit in
`mux.toml`, or the image should already contain/use whatever model access pattern was proven.

## `manifest.md` target shape

`manifest.md` is the real human manifest. It should include enough context to understand the mux long
after the workspace details are forgotten.

Recommended sections:

```markdown
# <mux-name>

## Status
- Track:
- State:
- Intended role:

## Launch identity
- Mux:
- Service:
- Container:
- Host port:
- Container port:
- Runtime:

## Source
- Workspace:
- Backend:
- Image:
- Source model/artifact:

## Serving configuration
- Full backend config relevant to serving
- Launch flags / server args
- Sampling defaults
- Templates / prompt format
- LoRA / tokenizer notes if relevant

## Proving notes
- What was tested
- Known caveats
- Promotion history
```

## Boundary

The workspace owns proving and backend-specific truth.

AgentMux owns stable serving and the durable library entry.

The export/import should preserve important metadata in `manifest.md`, but AgentMux should not turn
backend-specific serving config into Python schema.
