# AgentMux Containerization Plan: The "Disposable Appliance" Vision

## 1. Core Philosophy
Stop treating LLM runtimes as permanent installations on the host. Transition from "managing environments" to "deploying disposable appliances." 

The goal is to eliminate the "Infrastructure Trap" where backend debugging, CUDA version fights, and `pip` pin-breaking consume more time than actual development.

## 2. Layered Image Architecture
To maximize disk efficiency and build speed, we move to a hierarchical image structure using Podman/Dockerfiles.

### Level 1: `base-hacker` (The Foundation)
- **Purpose**: A heavy, stable base that contains everything needed to build *any* LLM backend.
- **Contents**: 
    - CUDA Toolkit (locked version)
    - Build-essential / C++ compilers / CMake
    - Base Python installation
    - Git and essential system utilities.
- **Value**: Built once, shared by all backends.

### Level 2: `backend-specific` (The Runtimes)
- **Purpose**: Lightweight layers that inherit from `base-hacker` and install a specific runtime.
- **Examples**:
    - `backend-vllm`: Custom vLLM build + specific `transformers` pins.
    - `backend-sglang`: SGLang installation + RadixAttention config.
    - `backend-exllama`: TabbyAI / ExLlamaV2 + Paged Attention patches.
- **Value**: If a backend segfaults or requires a breaking update, only this layer is rebuilt.

## 3. "Close-to-Metal" Runtime Strategy
We leverage Podman's rootless architecture to achieve near-native performance while maintaining logical isolation.

### High-Performance Flags
- **GPU Access**: Use `--gpus all` (via `nvidia-container-toolkit`) for direct CUDA driver access.
- **Networking**: Use `--net=host` to allow the harness and backends to communicate with zero virtualization overhead and simplify service discovery.
- **Filesystem**: Use **Bind Mounts** (`-v`) instead of `COPY` for code and models.
    - `/home/poop/models` $\rightarrow$ `/models` (Read-only or Read-Write)
    - `/home/poop/code/harness` $\rightarrow$ `/app` (Read-Write for live hacking)

### The "YOLO with Exceptions" Security Model
- **No `--privileged`**: Avoid giving containers full host root access.
- **Selective Mounting**: Only mount the directories the backend needs.
- **Sacred Zones**: Keep `~/.ssh`, `~/.gnupg`, and other private keys outside of all mount points, making them invisible to the containerized process.

## 4. AgentMux Integration
The `agentmux` cockpit evolves from a config-manager to a container-orchestrator.

### Manifest Evolution
Mux manifests will be updated to include:
- `image`: The specific backend image to use (e.g., `backend-exllama:latest`).
- `podman_args`: Specific flags for that instance (e.g., `--gpus all`, `--net=host`).
- `volumes`: A list of host-to-container mappings.

### The "Quant-to-Harness" Pipeline
1. **Quantization**: Performed in a dedicated "Build" container or on-host.
2. **Deployment**: Update `agentmux` manifest $\rightarrow$ `agentmux up`.
3. **Verification**: `podman exec` for deep inspection; API calls for functional testing.

## 5. Expected Outcomes
- **Backend Switching**: Switching from vLLM to SGLang takes seconds (changing a tag) rather than hours of environment rebuilding.
- **Stability**: "Frozen" runtimes prevent random segfaults caused by host-level package updates.
- **Hacking Speed**: Live-editing code on the host while the runtime stays isolated in the container.
- **Resource Efficiency**: Layered images reduce redundant copies of Torch/CUDA.
