# agentmux

`agentmux` is a container-first launch cockpit for local agent-serving stacks.

Backend workspaces build images, prove models, generate backend configs, and export deployment-ready service bundles. `agentmux` only owns the clean serving surface: mux manifests, rendered `podman run` commands, container lifecycle, status, and logs.

## What agentmux does

- read mux manifests from `mux/`
- consume workspace exports from backend workspaces
- render the exact Podman commands that will run
- launch already-built backend images
- choose final container names, host ports, and runtime dirs
- track active containers under `~/runs/agentmux`
- stop, show status, and follow logs for managed containers

## What agentmux does not do

- build backend images
- manage Python/CUDA/backend environments
- quantize or evaluate models
- resolve Hugging Face cache paths
- benchmark model quality
- mutate backend-specific configs

Those jobs belong in backend workspaces such as `workspace-exl3` and `workspace-gguf`.

## Normal workflow

1. Prove a backend/model/preset in its workspace.
2. Export an AgentMux service bundle from the workspace.
3. Reference that export from a mux in `mux/lab`.
4. Try it in real agentic workflows.
5. Promote it to `mux/core` when it becomes a known-good stack.

## Normal manifest shape

```toml
[mux]
name = "gemma-4-12b-it-exl3"
primary_service = "main"

[services.main]
workspace_export = "~/code/dev/workspace-exl3/exports/agentmux/gemma-4-12b-it-exl3"
container_name = "agentmux-gemma-4-12b-it-exl3-main"
port = 8002
```

The workspace export owns the backend appliance details: image, internal container port, backend command, backend-required mounts, env vars, GPU/security args, and health path.

AgentMux owns the final mux identity: mux name, service name, managed container name, host-facing port, and runtime directory.

## Low-level escape hatch

AgentMux can still add mux-local Podman details when needed:

```toml
[services.main]
workspace_export = "~/code/dev/workspace-gguf/exports/agentmux/hauhau"
container_name = "agentmux-hauhau-main"
port = 8002
podman_args = ["--cpus", "8"]

[[services.main.volumes]]
source = "~/data/agentmux-extra"
target = "/agentmux/extra"
mode = "ro"
```

This should be for mux-local additions, not for backend workspace internals.

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

Use `agentmux render <mux>` before `up` whenever you want to inspect the exact launch command.

## Contract for workspaces

See `docs/specs/workspace-export-contract-v1.md`.
