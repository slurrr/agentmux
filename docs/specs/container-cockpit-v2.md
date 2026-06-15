# Spec: Container Cockpit v2

## Intent

AgentMux v2 is a clean launch cockpit for containerized local agent-serving stacks.

Backend workspaces own backend construction, model proving, backend config generation, and export bundles. AgentMux owns the serving contract and lifecycle for promoted stacks.

## Boundary

AgentMux owns:

- mux manifests
- workspace export contract
- exact `podman run` command rendering
- `up`, `down`, `status`, and `logs`
- active runtime state under `~/runs/agentmux`
- lab-to-core promotion of proven agent-serving stacks

AgentMux does not own:

- image builds
- backend virtualenvs
- CUDA/Python dependency management
- quantization
- model quality/performance benchmarking
- backend-specific config generation
- Hugging Face cache discovery
- backend workspace mutation during launch

## Normal workflow

1. Prove a backend/model/preset in a backend workspace such as `workspace-exl3` or `workspace-gguf`.
2. Export an AgentMux service bundle from that workspace.
3. Reference the export from `mux/lab/<mux>.toml`.
4. Use `agentmux render <mux>` to inspect the exact launch command.
5. Use `agentmux up <mux>` to try the stack in real agentic workflows.
6. Promote the mux from `lab` to `core` when it becomes a known-good tool.

## Workspace export contract

See `docs/specs/workspace-export-contract-v1.md`.

Normal AgentMux manifests should usually reference a workspace export instead of spelling out backend-specific mounts:

```toml
[mux]
name = "gemma-4-12b-it-exl3"
primary_service = "main"

[services.main]
workspace_export = "~/code/dev/workspace-exl3/exports/agentmux/gemma-4-12b-it-exl3"
container_name = "agentmux-gemma-4-12b-it-exl3-main"
port = 8002
```

The workspace export tells AgentMux the image, internal container port, backend command, backend-required volumes, env vars, and health path. AgentMux chooses the final host-facing port, container identity, and runtime directory.

## Manifest fields

Required service fields for normal exported services:

- `workspace_export`: directory containing `agentmux-service.toml`, or a direct path to that file
- `container_name`: exact managed container name
- `port`: host-facing service port

Low-level service fields remain available as escape hatches:

- `image`
- `container_port`
- `podman_args`
- `env`
- `labels`
- `ports`
- `volumes`
- `command`
- `health_path`
- `runtime_target`
- `runtime_dir`

A service may omit `workspace_export` and use only low-level fields, but that is not the preferred workflow for backend workspace promotion.

## Precedence

Order is:

1. AgentMux manifest `[defaults]`
2. workspace export
3. AgentMux service block
4. AgentMux automatic runtime mount

Rules:

- `defaults.podman_args` + export `podman_args` + service `podman_args` are appended in order.
- `defaults.volumes` + export `volumes` + service `volumes` are appended in order.
- `defaults.env` < export `env` < service `env`.
- `defaults.labels` < export `labels` < service `labels`.
- service `command`, `health_path`, and `container_port` override export values.
- if no raw `ports` are declared, AgentMux generates `<port>:<container_port>`.
- if raw `ports` are declared, AgentMux uses them as-is.

No backend semantics are inferred from image names or mux names.

## Runtime model

Runtime state is container-centric:

- container name
- container id
- image
- host/port
- health URL
- launch command
- started timestamp

PID tracking is not part of AgentMux v2.

## Acceptance criteria

- `agentmux render <mux>` shows the exact `podman run` command that `up` will execute.
- `agentmux up <mux>` launches managed containers from already-built images and workspace exports.
- `agentmux down` removes active managed containers.
- `agentmux status` reports container running state through Podman.
- `agentmux logs <service>` delegates to `podman logs`.
- The project has no backend runtime dependencies.
