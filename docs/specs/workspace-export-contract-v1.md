# AgentMux Workspace Export Contract v1

## Purpose

Backend workspaces are the workshop. AgentMux is the launch cockpit.

A workspace export is the handoff artifact between those two worlds. It tells AgentMux how to run a proven backend serving appliance without making AgentMux understand backend internals such as TabbyAPI config paths, llama.cpp flags, templates, sampler overrides, or LoRA layout.

## Lifecycle

1. A backend workspace builds/rebuilds backend images.
2. The workspace proves a model/preset using its own CLI and lab containers.
3. The workspace exports an AgentMux service bundle.
4. AgentMux references that bundle from a mux manifest.
5. AgentMux chooses mux identity, final container name, host port, and runtime directory.
6. The mux starts in `mux/lab` for agentic workflow proving, then can graduate to `mux/core`.

## Export directory

A workspace SHOULD export a directory shaped like this:

```text
exports/agentmux/<slug>/
  agentmux-service.toml
  ...backend-owned files needed by the export...
```

The only required filename is `agentmux-service.toml`.

Relative paths inside `agentmux-service.toml` are resolved relative to that file. This lets a workspace export a self-contained deployment bundle when that is useful.

## AgentMux manifest reference

Normal AgentMux manifests should be small:

```toml
[mux]
name = "gemma-4-12b-it-exl3"
primary_service = "main"

[services.main]
workspace_export = "~/code/dev/workspace-exl3/exports/agentmux/gemma-4-12b-it-exl3"
container_name = "agentmux-gemma-4-12b-it-exl3-main"
port = 8002
```

AgentMux owns:

- mux name
- service name
- final container name
- host-facing port
- optional mux-local extra mounts/args
- managed runtime directory under `~/runs/agentmux`

The workspace export owns:

- image tag
- container-internal serving port
- backend command
- backend-required bind mounts
- backend-required env vars
- default Podman GPU/security args
- health path
- runtime mount target inside the container

## Export TOML shape

```toml
[agentmux_export]
version = 1
name = "gemma-4-12b-it-exl3"
backend = "exl3-tabby"
notes = "Human notes are allowed. AgentMux does not interpret them."

[service]
image = "localhost/llm-tabby:latest"
container_port = 5000
health_path = "/v1/models"
runtime_target = "/app/data"
podman_args = ["--security-opt", "label=disable", "--device", "nvidia.com/gpu=all"]
command = []

[service.env]
HF_HOME = "/models/hf"

[service.labels]
backend = "exl3-tabby"

[[service.volumes]]
source = "~/models"
target = "/models"
mode = "ro"

[[service.volumes]]
source = "./tabby-config.yml"
target = "/app/tabbyAPI/config.yml"
mode = "ro"
```

## Required fields

### `[agentmux_export]`

- `version`: must be `1`.

### `[service]`

- `image`: already-built image tag AgentMux should run.
- `container_port`: port the backend listens on inside the container.

## Strongly recommended fields

- `health_path`: readiness path, usually `/v1/models`.
- `runtime_target`: path inside the container where AgentMux should mount a writable runtime directory.
- `podman_args`: backend-required Podman args such as GPU/security flags.
- `volumes`: backend-required bind mounts.
- `env`: backend-required environment variables.
- `command`: command after the image name, if the image default command is not sufficient.

## Port contract

The workspace should export the container's internal serving port as `container_port`.

AgentMux maps the mux manifest's host-facing `port` to that internal port:

```bash
--publish <agentmux-port>:<container-port>
```

This lets the same proven backend appliance run on different agent-stack ports without regenerating backend configs, as long as the backend listens on a stable container-internal port.

If a backend requires the configured serving port to match the host port, the workspace may export `container_port` equal to the intended port, but that is less reusable.

## Runtime directory contract

If `runtime_target` is set, AgentMux automatically appends a writable mount:

```text
~/runs/agentmux/<mux>/<service> -> <runtime_target>
```

A mux manifest may override the source with:

```toml
[services.main]
runtime_dir = "~/runs/agentmux/custom-main"
```

Workspaces should not hard-code AgentMux runtime source paths. They should only tell AgentMux where runtime state belongs inside the container.

## Merge and override rules

Order is:

1. AgentMux manifest `[defaults]`
2. workspace export
3. AgentMux service block
4. AgentMux automatic runtime mount

Rules:

- `env`: later keys override earlier keys.
- `labels`: later keys override earlier keys.
- `podman_args`: lists append in order.
- `volumes`: lists append in order.
- `command`: service block overrides export command.
- `health_path`: service block overrides export health path.
- `container_port`: service block overrides export container port.
- `ports`: if explicitly set in the AgentMux manifest, AgentMux uses those raw mappings instead of generating `<port>:<container_port>`.

## Escape hatches

AgentMux still supports low-level service fields:

- `podman_args`
- `env`
- `labels`
- `volumes`
- `command`
- `ports`

These are for mux-local additions or unusual launches. They should not be the normal place for backend workspace details.

## Non-goals

The export must not require AgentMux to:

- build images
- generate backend configs
- inspect model caches
- understand backend-specific flags
- run benchmark/eval/proving workflows
- mutate workspace state during `agentmux up`
