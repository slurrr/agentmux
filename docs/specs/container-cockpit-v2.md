# Spec: Container Cockpit v2

## Intent

AgentMux is the stable serving cockpit and library for proven local agent stacks.

Backend workspaces are proving grounds. They can be messy. They build images, tune backend config,
prove models, and generate exports. AgentMux keeps the stable result: a tiny launch recipe plus a
human-readable manifest for what the mux actually represents.

## Boundary

AgentMux owns:

- stable mux names
- `mux/lab` and `mux/core` library organization
- tiny launch recipes (`mux.toml`)
- human manifests (`manifest.md`)
- exact `podman run` command rendering
- `up`, `down`, `status`, and `logs`
- active runtime state under `~/runs/agentmux`

AgentMux does not own:

- image builds
- backend virtualenvs
- CUDA/Python dependency management
- quantization
- backend-specific config generation
- Hugging Face cache discovery
- model proving/benchmarking loops
- backend workspace runtime layout

## Normal mux directory

A mux is a directory:

```text
mux/lab/gemma-4-12b-it-exl3/
  mux.toml
  manifest.md
```

`mux.toml` is intentionally tiny and operational. It is only what AgentMux needs to render and launch
the stable container.

`manifest.md` is the human manifest. It should contain everything needed to remember what this mux is
after six months: source workspace, model, backend, image tag, full serving config, launch-relevant
backend flags, caveats, proving notes, and promotion history.

## Launch recipe

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

AgentMux renders:

```text
--publish 8002:5000
--volume ~/runs/agentmux/gemma-4-12b-it-exl3/main:/runs:rw
```

AgentMux does not add a models mount automatically. If a promoted image still needs extra mounts,
those mounts must be explicit in `mux.toml` or already handled by the exported launch recipe before
it is imported into AgentMux.

## Import/export model

Workspace exports are handoff artifacts, not permanent AgentMux library objects.

The desired flow is:

1. workspace proves the backend/model/container
2. workspace exports enough data to create an AgentMux mux directory
3. AgentMux import converts that export into:
   - `mux.toml`
   - `manifest.md`
4. the temporary export can be deleted or archived outside the active mux library

Until import automation exists, create the pair manually.

## Runtime convention

AgentMux always mounts a writable runtime directory at `/runs`:

```text
~/runs/agentmux/<mux>/<service> -> /runs
```

Promoted images should use `/runs` for logs, db files, generated runtime state, and any other
container-writable serving data. If a backend naturally wants another path, the image should adapt
internally.

## Workflow

1. Prove in backend workspace.
2. Export/import into `mux/lab/<mux>/`.
3. Run `agentmux render <mux>` and inspect the launch command.
4. Run `agentmux up <mux>` and test in real agentic workflows.
5. Add notes to `manifest.md`.
6. Promote directory from `mux/lab` to `mux/core` when stable.

## Acceptance criteria

- `agentmux render <mux>` shows the exact `podman run` command that `up` will execute.
- `agentmux up <mux>` launches managed containers from already-built images.
- `agentmux down` removes active managed containers.
- `agentmux status` reports container running state through Podman.
- `agentmux logs <service>` delegates to `podman logs`.
- AgentMux has no backend runtime dependencies.
