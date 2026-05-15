---
title: "Getting Started with LLaMA.cpp (A Complete Guide)"
source: "https://llama-cpp.com/getting-started/#how-to-install-llama-cpp-on-linux"
author:
  - "[[Llama cpp]]"
published: 2026-03-19
created: 2026-05-14
description: "Get started with Llama.cpp. A free and open-source tool that allows you run your favorite AI models locally on Windows PC, Linux and macOS."
tags:
  - "clippings"
---
## How To Install Llama.cpp on Linux

Llama.cpp works on multiple Linux distributions and supports both CPU-only inference and GPU acceleration for Nvidia, AMD and Vulkan backends.

Llama.cpp works on Ubuntu, Debian, Fedora and Arch Linux. Just the package manager commands differ but the overall process remains the same.

**Step 1: Install Required Dependencies**

What you will need is a compiler, build tools and CMake.

For Ubuntu/Debian systems:

```
sudo apt update
sudo apt install -y git build-essential cmake
```

For Fedora:

```
sudo dnf install git gcc gcc-c++ make cmake
```

For Arch Linux:

```
sudo pacman -S git base-devel cmake
```

Now verify your above installations:

```
gcc --version
cmake --version
git --version
```

**Step 2: Clone the Llama.cpp Repository**

Create a build directory and compile in that directory:

```
mkdir build
cd build

cmake ..
cmake --build . --config Release
```

After building binaries will be available in:

```
./build/bin/
```

**Step 4: Verify your Installation:**

```
./build/bin/llama-cli --help
```

After running the above command you will now see all the available runtime options.

## Linux Performance Enhancements

Linux provides the widest range of optimization options for llama.cpp:

**Enable OpenBLAS CPU Acceleration**

BLAS libraries improve matrix multiplication performance on CPUs

Install OpenBLAS:

```
sudo apt install libopenblas-dev   # Ubuntu/Debian
```

Build with BLAS:

```
cmake -B build -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS
cmake --build build --config Release
```

Nvidia GPU Support with CUDA:

If you have an Nvidia GPU, you can significantly accelerate inference with the help of the [CUDA Toolkit](https://developer.nvidia.com/cuda/toolkit).

Build with CUDA:

```
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release
```

Verify GPU Usage:

```
nvidia-smi
```

**Vulkan Support (Cross-Platform GPU)**

For broader GPU compatibility you can use Vulkan.

Install Vulkan SDK:

```
sudo apt install vulkan-tools libvulkan-dev
```

Build with Vulkan:

```
cmake -B build -DGGML_VULKAN=ON
cmake --build build
```

**AMD GPU Support with ROCm**

On supported AMD hardware, ROCm can be used for acceleration.

Build with ROCm:

```
cmake -B build -DGGML_HIPBLAS=ON
cmake --build build
```