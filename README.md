# agentmux

`agentmux` is a container-first launch cockpit for local agent-serving stacks.

Backend workspaces build images, prove models, generate backend configs, and export deployment-ready service shapes. `agentmux` only owns the clean serving surface: mux manifests, rendered `podman run` commands, container lifecycle, status, and logs.

## What agentmux does

- read mux manifests from `mux/`
- render the exact Podman commands that will run
- launch already-built backend images
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

## Manifest shape

```toml
[mux]
name = "example-gguf"
primary_service = "main"

[defaults]
podman_args = ["--security-opt", "label=disable", "--device", "nvidia.com/gpu=all"]

[defaults.env]
HF_HOME = "/models/hf"

[[defaults.volumes]]
source = "~/models"
target = "/models"
mode = "ro"

[services.main]
image = "localhost/llm-gguf:latest"
container_name = "agentmux-example-gguf-main"
host = "127.0.0.1"
port = 8002
ports = ["8002:8002"]
command = ["llama-server", "--config", "/workspace/configs/llama-server.yml"]
health_path = "/v1/models"

[[services.main.volumes]]
source = "~/code/dev/workspace-gguf/configs/deployments/example.yml"
target = "/workspace/configs/llama-server.yml"
mode = "ro"
```

## Commands

```bash
agentmux list
agentmux show example-gguf
agentmux render example-gguf
agentmux up example-gguf
agentmux status
agentmux logs main -f
agentmux down
```

Use `agentmux render <mux>` before `up` whenever you want to inspect the exact launch command.
