# agentmux

`agentmux` is a container-first launch cockpit and library for proven local agent-serving stacks.

Backend workspaces prove models and build images. AgentMux keeps the stable serving entries: a tiny
launch recipe plus a human-readable manifest explaining what is actually being served.

## Mux shape

A mux is a directory:

```text
mux/lab/gemma-4-12b-it-exl3/
  mux.toml
  manifest.md
```

- `mux.toml` is operational and intentionally small.
- `manifest.md` is the human manifest: source workspace, model, backend, image tag, serving config,
  proving notes, caveats, and promotion history.

## What agentmux does

- render exact `podman run` commands
- launch already-built, proven images
- map host port to container port
- mount AgentMux runtime state at `/runs`
- track active containers under `~/runs/agentmux`
- stop/status/log managed containers

## What agentmux does not do

- build images
- manage backend envs
- generate backend configs
- know Tabby/llama/vLLM internals
- resolve model caches
- prove or benchmark models

## Launch recipe example

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

AgentMux automatically appends:

```bash
--publish 8002:5000
--volume ~/runs/agentmux/gemma-4-12b-it-exl3/main:/runs:rw
```

AgentMux does **not** automatically mount models. If a promoted container needs extra mounts, they
must be explicit in `mux.toml` or baked into the proven image/launch shape by the workspace export.

## Workflow

1. Prove model/backend in a workspace.
2. Export/import into `mux/lab/<mux>/mux.toml` and `manifest.md`.
3. Run `agentmux render <mux>`.
4. Run `agentmux up <mux>`.
5. Test in real agent workflows and update `manifest.md`.
6. Promote directory to `mux/core` when stable.

To prove an existing export against a new compatible image without rewriting
its `mux.toml`, use the temporary image override. It preserves the exported
volumes, environment, command, and health check:

```bash
agentmux render <mux-name> --image localhost/llm-tabby:<new-tag>
agentmux up <mux-name> --image localhost/llm-tabby:<new-tag>
```

The override is runtime-only and is recorded in active runtime state; it does
not change the mux manifest.

## Commands

```bash
agentmux list
agentmux show gemma-4-12b-it-exl3
agentmux render gemma-4-12b-it-exl3
agentmux up gemma-4-12b-it-exl3
agentmux status
agentmux logs main -f
agentmux down
```

## Workspace handoff

See `docs/specs/workspace-export-contract-v1.md`.
