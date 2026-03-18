from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

STACK_ROOT = Path("mux")
TRACKS = ("core", "lab", "archive")


@dataclass(frozen=True)
class LoraSpec:
    name: str
    path: str
    base_model: str | None
    enabled: bool


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    engine: str
    model: str
    host: str
    port: int
    served_model_name: str | None
    dtype: str | None
    gpu_memory_utilization: float | None
    max_model_len: int | None
    max_num_seqs: int | None
    tensor_parallel_size: int | None
    attention_backend: str | None
    api_key_env: str | None
    env: dict[str, str]
    extra_args: list[str]
    loras: list[LoraSpec]
    notes: str | None


@dataclass(frozen=True)
class StackSpec:
    name: str
    track: str
    path: Path
    primary_service: str
    notes: str | None
    env: dict[str, str]
    services: dict[str, ServiceSpec]


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid TOML document: {path}")
    return data


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


def _as_loras(value: object, field_name: str) -> list[LoraSpec]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array of tables")

    loras: list[LoraSpec] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{field_name}[{index}] must be a table")
        name = item.get("name")
        path = item.get("path")
        base_model = item.get("base_model")
        enabled = item.get("enabled", True)
        if not isinstance(name, str) or not name:
            raise ValueError(f"{field_name}[{index}].name must be a non-empty string")
        if not isinstance(path, str) or not path:
            raise ValueError(f"{field_name}[{index}].path must be a non-empty string")
        if base_model is not None and not isinstance(base_model, str):
            raise ValueError(f"{field_name}[{index}].base_model must be a string")
        if not isinstance(enabled, bool):
            raise ValueError(f"{field_name}[{index}].enabled must be a boolean")
        loras.append(LoraSpec(name=name, path=path, base_model=base_model, enabled=enabled))
    return loras


def _merge_service(defaults: dict[str, object], service: dict[str, object]) -> dict[str, object]:
    merged = dict(defaults)
    service_env = _as_str_dict(service.get("env"), "services.<name>.env")
    defaults_env = _as_str_dict(defaults.get("env"), "defaults.env")
    merged.update(service)
    merged["env"] = {**defaults_env, **service_env}
    return merged


def _service_from_data(
    name: str,
    raw: dict[str, object],
    defaults: dict[str, object],
) -> ServiceSpec:
    merged = _merge_service(defaults, raw)

    engine = merged.get("engine", "vllm")
    model = merged.get("model")
    host = merged.get("host", "0.0.0.0")
    port = merged.get("port")
    served_model_name = merged.get("served_model_name")
    dtype = merged.get("dtype")
    gpu_memory_utilization = merged.get("gpu_memory_utilization")
    max_model_len = merged.get("max_model_len")
    max_num_seqs = merged.get("max_num_seqs")
    tensor_parallel_size = merged.get("tensor_parallel_size")
    attention_backend = merged.get("attention_backend")
    api_key_env = merged.get("api_key_env")
    notes = merged.get("notes")

    if not isinstance(engine, str) or not engine:
        raise ValueError(f"services.{name}.engine must be a non-empty string")
    if not isinstance(model, str) or not model:
        raise ValueError(f"services.{name}.model must be a non-empty string")
    if not isinstance(host, str):
        raise ValueError(f"services.{name}.host must be a string")
    if not isinstance(port, int):
        raise ValueError(f"services.{name}.port must be an integer")

    for field_name, value in {
        "served_model_name": served_model_name,
        "dtype": dtype,
        "attention_backend": attention_backend,
        "api_key_env": api_key_env,
        "notes": notes,
    }.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f"services.{name}.{field_name} must be a string")

    for field_name, value in {
        "max_model_len": max_model_len,
        "max_num_seqs": max_num_seqs,
        "tensor_parallel_size": tensor_parallel_size,
    }.items():
        if value is not None and not isinstance(value, int):
            raise ValueError(f"services.{name}.{field_name} must be an integer")

    if gpu_memory_utilization is not None and not isinstance(gpu_memory_utilization, (int, float)):
        raise ValueError(f"services.{name}.gpu_memory_utilization must be numeric")

    served_model_name = cast(str | None, served_model_name)
    dtype = cast(str | None, dtype)
    max_model_len = cast(int | None, max_model_len)
    max_num_seqs = cast(int | None, max_num_seqs)
    tensor_parallel_size = cast(int | None, tensor_parallel_size)
    attention_backend = cast(str | None, attention_backend)
    api_key_env = cast(str | None, api_key_env)
    notes = cast(str | None, notes)

    return ServiceSpec(
        name=name,
        engine=engine,
        model=model,
        host=host,
        port=port,
        served_model_name=served_model_name,
        dtype=dtype,
        gpu_memory_utilization=(
            float(gpu_memory_utilization) if gpu_memory_utilization is not None else None
        ),
        max_model_len=max_model_len,
        max_num_seqs=max_num_seqs,
        tensor_parallel_size=tensor_parallel_size,
        attention_backend=attention_backend,
        api_key_env=api_key_env,
        env=_as_str_dict(merged.get("env"), f"services.{name}.env"),
        extra_args=_as_str_list(merged.get("extra_args"), f"services.{name}.extra_args"),
        loras=_as_loras(merged.get("loras"), f"services.{name}.loras"),
        notes=notes,
    )


def load_stack(path: Path) -> StackSpec:
    if not path.exists():
        raise FileNotFoundError(f"Stack file not found: {path}")

    data = _load_toml(path)
    stack = data.get("stack", {})
    defaults = data.get("defaults", {})
    services = data.get("services", {})

    if not isinstance(stack, dict):
        raise ValueError("[stack] must be a table")
    if not isinstance(defaults, dict):
        raise ValueError("[defaults] must be a table")
    if not isinstance(services, dict):
        raise ValueError("[services] must be a table")
    if not services:
        raise ValueError("At least one service is required")

    name = stack.get("name", path.stem)
    track = stack.get("track", path.parent.name)
    primary_service = stack.get("primary_service")
    notes = stack.get("notes")

    if not isinstance(name, str) or not name:
        raise ValueError("stack.name must be a non-empty string")
    if not isinstance(track, str) or track not in TRACKS:
        raise ValueError(f"stack.track must be one of {', '.join(TRACKS)}")
    if primary_service is None:
        primary_service = next(iter(services))
    if not isinstance(primary_service, str) or not primary_service:
        raise ValueError("stack.primary_service must be a non-empty string")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("stack.notes must be a string")
    if primary_service not in services:
        raise ValueError("stack.primary_service must reference an existing service")

    stack_env = _as_str_dict(defaults.get("env"), "defaults.env")
    parsed_services = {
        service_name: _service_from_data(service_name, raw_service, defaults)
        for service_name, raw_service in services.items()
        if isinstance(raw_service, dict)
    }

    if len(parsed_services) != len(services):
        raise ValueError("Each [services.<name>] entry must be a table")

    return StackSpec(
        name=name,
        track=track,
        path=path,
        primary_service=primary_service,
        notes=notes,
        env=stack_env,
        services=parsed_services,
    )


def stack_directories(root: Path = STACK_ROOT) -> dict[str, Path]:
    return {track: root / track for track in TRACKS}


def discover_stack_paths(root: Path = STACK_ROOT, include_archive: bool = True) -> list[Path]:
    paths: list[Path] = []
    for track, directory in stack_directories(root).items():
        if track == "archive" and not include_archive:
            continue
        if directory.exists():
            paths.extend(sorted(directory.glob("*.toml")))
    return paths


def list_stacks(root: Path = STACK_ROOT, include_archive: bool = True) -> list[StackSpec]:
    paths = discover_stack_paths(root, include_archive=include_archive)
    return [load_stack(path) for path in paths]


def resolve_stack(name: str, root: Path = STACK_ROOT, include_archive: bool = True) -> StackSpec:
    stacks = list_stacks(root, include_archive=include_archive)
    matches = [stack for stack in stacks if stack.name == name]
    if not matches:
        available = ", ".join(stack.name for stack in stacks)
        raise KeyError(f"Unknown stack '{name}'. Available stacks: {available or 'none'}")
    if len(matches) > 1:
        raise ValueError(f"Stack name '{name}' is ambiguous across tracks")
    return matches[0]
