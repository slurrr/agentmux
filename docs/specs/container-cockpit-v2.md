# Spec: Container Cockpit v2

## Intent

AgentMux v2 is a clean launch cockpit for containerized local agent-serving stacks.

The backend workspaces own backend construction and proving. AgentMux owns the serving contract and lifecycle for promoted stacks.

## Boundary

AgentMux owns:

- mux manifests
- workspace export contract
- exact `podman run` command rendering
- `up`, `down`, `status`, and `logs`
- active runtime state under `~/runs/agentmux`

AgentMux does not own:

- image builds
- backend virtualenvs
- CUDA/Python dependency management
- quantization
- model quality/performance benchmarking
- backend-specific config generation
- Hugging Face cache discovery

## Workspace export contract

Backend workspaces should export service definitions that can be copied into, or generated as, AgentMux manifest service blocks.

Required service fields:

- `image`: already-built local or remote image tag
- `container_name`: exact managed container name
- `port`: host-facing service port used for status/readiness

Common operational fields:

- `host`: host used by AgentMux for health checks, default `127.0.0.1`
- `podman_args`: raw Podman arguments before image name
- `env`: environment variables passed with `--env`
- `ports`: Podman publish mappings passed with `--publish`
- `volumes`: bind mounts passed with `--volume`
- `command`: container command and arguments after image name
- `health_path`: HTTP path used for readiness, default `/v1/models`

## Manifest precedence

- `defaults.podman_args` are appended before service `podman_args`.
- `defaults.ports` are appended before service `ports`.
- `defaults.volumes` are appended before service `volumes`.
- `defaults.env` is overridden by service `env` on key collision.
- `defaults.labels` is overridden by service `labels` on key collision.

No backend semantics are inferred from image names or mux names.

## Runtime model

Runtime state is container-centric:

- container name
- container id
- image
- host/port
- launch command
- started timestamp

PID tracking is not part of AgentMux v2.

## Acceptance criteria

- `agentmux render <mux>` shows the exact `podman run` command that `up` will execute.
- `agentmux up <mux>` launches managed containers from already-built images.
- `agentmux down` removes active managed containers.
- `agentmux status` reports container running state through Podman.
- `agentmux logs <service>` delegates to `podman logs`.
- The project has no backend runtime dependencies.
