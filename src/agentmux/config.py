from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("agentmux.toml")


@dataclass(frozen=True)
class Profile:
    name: str
    model: str
    served_model_name: str | None
    host: str
    port: int
    dtype: str | None
    gpu_memory_utilization: float | None
    max_model_len: int | None
    max_num_seqs: int | None
    tensor_parallel_size: int | None
    attention_backend: str | None
    api_key_env: str | None
    env: dict[str, str]
    extra_args: list[str]
    notes: str | None


def _as_str_dict(value: object, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a table")

    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{field_name} keys and values must be strings")
        result[key] = item
    return result


def _as_str_list(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return list(value)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Config file must contain a TOML table")
    return data


def profile_names(path: Path = DEFAULT_CONFIG_PATH) -> list[str]:
    config = load_config(path)
    profiles = config.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("[profiles] must be a table")
    return sorted(profiles)


def load_profile(name: str, path: Path = DEFAULT_CONFIG_PATH) -> Profile:
    config = load_config(path)
    defaults = config.get("defaults", {})
    profiles = config.get("profiles", {})

    if not isinstance(defaults, dict):
        raise ValueError("[defaults] must be a table")
    if not isinstance(profiles, dict):
        raise ValueError("[profiles] must be a table")
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "none"
        raise KeyError(f"Unknown profile '{name}'. Available profiles: {available}")

    raw_profile = profiles[name]
    if not isinstance(raw_profile, dict):
        raise ValueError(f"[profiles.{name}] must be a table")

    merged = dict(defaults)
    merged.update(raw_profile)

    model = merged.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError(f"profiles.{name}.model must be a non-empty string")

    served_model_name = merged.get("served_model_name")
    if served_model_name is not None and not isinstance(served_model_name, str):
        raise ValueError(f"profiles.{name}.served_model_name must be a string")

    host = merged.get("host", "0.0.0.0")
    port = merged.get("port", 8000)
    dtype = merged.get("dtype")
    gpu_memory_utilization = merged.get("gpu_memory_utilization")
    max_model_len = merged.get("max_model_len")
    max_num_seqs = merged.get("max_num_seqs")
    tensor_parallel_size = merged.get("tensor_parallel_size")
    attention_backend = merged.get("attention_backend")
    api_key_env = merged.get("api_key_env")
    notes = merged.get("notes")

    if not isinstance(host, str):
        raise ValueError(f"profiles.{name}.host must be a string")
    if not isinstance(port, int):
        raise ValueError(f"profiles.{name}.port must be an integer")

    optional_ints = {
        "max_model_len": max_model_len,
        "max_num_seqs": max_num_seqs,
        "tensor_parallel_size": tensor_parallel_size,
    }
    for field_name, value in optional_ints.items():
        if value is not None and not isinstance(value, int):
            raise ValueError(f"profiles.{name}.{field_name} must be an integer")

    if gpu_memory_utilization is not None and not isinstance(gpu_memory_utilization, (int, float)):
        raise ValueError(f"profiles.{name}.gpu_memory_utilization must be numeric")

    optional_strings = {
        "dtype": dtype,
        "attention_backend": attention_backend,
        "api_key_env": api_key_env,
        "notes": notes,
    }
    for field_name, value in optional_strings.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f"profiles.{name}.{field_name} must be a string")

    return Profile(
        name=name,
        model=model,
        served_model_name=served_model_name,
        host=host,
        port=port,
        dtype=dtype,
        gpu_memory_utilization=(
            float(gpu_memory_utilization) if gpu_memory_utilization is not None else None
        ),
        max_model_len=max_model_len,
        max_num_seqs=max_num_seqs,
        tensor_parallel_size=tensor_parallel_size,
        attention_backend=attention_backend,
        api_key_env=api_key_env,
        env=_as_str_dict(merged.get("env"), f"profiles.{name}.env"),
        extra_args=_as_str_list(merged.get("extra_args"), f"profiles.{name}.extra_args"),
        notes=notes,
    )
