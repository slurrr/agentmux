from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

STACK_ROOT = Path("mux")
TRACKS = ("core", "lab", "archive")
ENV_PATTERN = re.compile(
    r"\$(?:\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|(?P<bare>[A-Za-z_][A-Za-z0-9_]*))"
)

FlagValue = bool | int | float | str


@dataclass(frozen=True)
class LoraSpec:
    name: str
    path: str
    base_model: str | None
    enabled: bool


@dataclass(frozen=True)
class AssetSpec:
    values: dict[str, str]


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    engine: str
    model: str
    host: str
    port: int
    served_model_name: str | None
    env: dict[str, str]
    args: dict[str, FlagValue]
    extra_args: list[str]
    loras: list[LoraSpec]
    assets: AssetSpec
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


def _expand_env(text: str, field_name: str) -> str:
    expanded = os.path.expandvars(text)
    unresolved = [
        match.group("braced") or match.group("bare") or ""
        for match in ENV_PATTERN.finditer(expanded)
    ]
    if unresolved:
        names = ", ".join(unresolved)
        raise ValueError(f"{field_name} references unset environment variable(s): {names}")
    return expanded


def _as_str_dict(value: object, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a table")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{field_name} keys and values must be strings")
        result[key] = _expand_env(item, f"{field_name}.{key}")
    return result


def _as_str_list(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return [_expand_env(item, f"{field_name}[{index}]") for index, item in enumerate(value)]


def _as_flag_map(value: object, field_name: str) -> dict[str, FlagValue]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a table")

    result: dict[str, FlagValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{field_name} keys must be strings")
        if isinstance(item, bool):
            result[key] = item
        elif isinstance(item, (int, float)):
            result[key] = item
        elif isinstance(item, str):
            result[key] = _expand_env(item, f"{field_name}.{key}")
        else:
            raise ValueError(f"{field_name}.{key} must be a string, boolean, integer, or float")
    return result


def _as_assets(value: object, field_name: str) -> AssetSpec:
    return AssetSpec(values=_as_str_dict(value, field_name))


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
        loras.append(
            LoraSpec(
                name=name,
                path=_expand_env(path, f"{field_name}[{index}].path"),
                base_model=(
                    _expand_env(base_model, f"{field_name}[{index}].base_model")
                    if base_model is not None
                    else None
                ),
                enabled=enabled,
            )
        )
    return loras


def _merge_table_dict(
    defaults: dict[str, object],
    service: dict[str, object],
    key: str,
    defaults_field: str,
    service_field: str,
) -> dict[str, object]:
    default_values = defaults.get(key)
    service_values = service.get(key)
    if default_values is None and service_values is None:
        return {}
    if default_values is not None and not isinstance(default_values, dict):
        raise ValueError(f"{defaults_field} must be a table")
    if service_values is not None and not isinstance(service_values, dict):
        raise ValueError(f"{service_field} must be a table")
    merged: dict[str, object] = {}
    if isinstance(default_values, dict):
        merged.update(default_values)
    if isinstance(service_values, dict):
        merged.update(service_values)
    return merged


def _merge_service(defaults: dict[str, object], service: dict[str, object]) -> dict[str, object]:
    merged = dict(defaults)
    merged.update(service)
    merged["env"] = _merge_table_dict(defaults, service, "env", "defaults.env", "services.<name>.env")
    merged["args"] = _merge_table_dict(
        defaults,
        service,
        "args",
        "defaults.args",
        "services.<name>.args",
    )
    merged["assets"] = _merge_table_dict(
        defaults,
        service,
        "assets",
        "defaults.assets",
        "services.<name>.assets",
    )
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
    notes = merged.get("notes")

    if not isinstance(engine, str) or not engine:
        raise ValueError(f"services.{name}.engine must be a non-empty string")
    if not isinstance(model, str) or not model:
        raise ValueError(f"services.{name}.model must be a non-empty string")
    if not isinstance(host, str) or not host:
        raise ValueError(f"services.{name}.host must be a non-empty string")
    if not isinstance(port, int):
        raise ValueError(f"services.{name}.port must be an integer")
    if served_model_name is not None and not isinstance(served_model_name, str):
        raise ValueError(f"services.{name}.served_model_name must be a string")
    if notes is not None and not isinstance(notes, str):
        raise ValueError(f"services.{name}.notes must be a string")

    return ServiceSpec(
        name=name,
        engine=engine,
        model=_expand_env(model, f"services.{name}.model"),
        host=host,
        port=port,
        served_model_name=(
            _expand_env(served_model_name, f"services.{name}.served_model_name")
            if served_model_name is not None
            else None
        ),
        env=_as_str_dict(merged.get("env"), f"services.{name}.env"),
        args=_as_flag_map(merged.get("args"), f"services.{name}.args"),
        extra_args=_as_str_list(merged.get("extra_args"), f"services.{name}.extra_args"),
        loras=_as_loras(merged.get("loras"), f"services.{name}.loras"),
        assets=_as_assets(merged.get("assets"), f"services.{name}.assets"),
        notes=notes,
    )


def load_stack(path: Path) -> StackSpec:
    load_dotenv(dotenv_path=Path(".env"))
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
