from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from agentmux.config import DEFAULT_CONFIG_PATH, Profile, load_profile


@dataclass(frozen=True)
class LaunchPlan:
    profile: Profile
    env: dict[str, str]
    command: list[str]

    def shell_command(self) -> str:
        return shlex.join(self.command)


def build_launch_plan(profile_name: str, config_path: Path = DEFAULT_CONFIG_PATH) -> LaunchPlan:
    load_dotenv(dotenv_path=Path(".env"))
    profile = load_profile(profile_name, config_path)

    command = [
        "uv",
        "run",
        "vllm",
        "serve",
        profile.model,
        "--host",
        profile.host,
        "--port",
        str(profile.port),
    ]

    if profile.served_model_name:
        command.extend(["--served-model-name", profile.served_model_name])
    if profile.dtype:
        command.extend(["--dtype", profile.dtype])
    if profile.gpu_memory_utilization is not None:
        command.extend(["--gpu-memory-utilization", str(profile.gpu_memory_utilization)])
    if profile.max_model_len is not None:
        command.extend(["--max-model-len", str(profile.max_model_len)])
    if profile.max_num_seqs is not None:
        command.extend(["--max-num-seqs", str(profile.max_num_seqs)])
    if profile.tensor_parallel_size is not None:
        command.extend(["--tensor-parallel-size", str(profile.tensor_parallel_size)])
    if profile.attention_backend:
        command.extend(["--attention-backend", profile.attention_backend])
    command.extend(profile.extra_args)

    env = os.environ.copy()
    env.update(profile.env)
    if profile.api_key_env:
        api_key = os.environ.get(profile.api_key_env)
        if api_key:
            env.setdefault("VLLM_API_KEY", api_key)

    return LaunchPlan(profile=profile, env=env, command=command)


def run_profile(profile_name: str, config_path: Path = DEFAULT_CONFIG_PATH) -> int:
    plan = build_launch_plan(profile_name, config_path)
    completed = subprocess.run(plan.command, env=plan.env, check=False)
    return completed.returncode
