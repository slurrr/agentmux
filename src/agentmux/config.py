from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

STACK_ROOT = Path("mux")
TRACKS = ("core", "lab", "bench", "archive", "examples")
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
    host: str
    port: int
    env: dict[str, str]
    notes: str | None
    runtime_bin_dir: str | None = None
    model: str | None = None
    hf_repo: str | None = None
    hf_file: str | None = None
    served_model_name: str | None = None
    args: dict[str, FlagValue] | None = None
    extra_args: list[str] | None = None
    loras: list[LoraSpec] | None = None
    assets: AssetSpec | None = None
    data_dir: str | None = None
    llm_service: str | None = None


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


def _get_service_host(raw: dict[str, object], defaults: dict[str, object], name: str) -> str:
    host = raw.get("host", defaults.get("host", "0.0.0.0"))
    if not isinstance(host, str) or not host:
        raise ValueError(f"services.{name}.host must be a non-empty string")
    return host


def _get_service_port(raw: dict[str, object], name: str) -> int:
    port = raw.get("port")
    if not isinstance(port, int):
        raise ValueError(f"services.{name}.port must be an integer")
    return port


def _get_service_notes(raw: dict[str, object], name: str) -> str | None:
    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ValueError(f"services.{name}.notes must be a string")
    return notes


def _service_from_vllm(
    name: str,
    raw: dict[str, object],
    defaults: dict[str, object],
) -> ServiceSpec:
    allowed_keys = {
        "engine",
        "model",
        "host",
        "port",
        "served_model_name",
        "env",
        "args",
        "extra_args",
        "loras",
        "assets",
        "notes",
        "runtime_bin_dir",
    }
    unknown = sorted(set(raw.keys()) - allowed_keys)
    if unknown:
        names = ", ".join(unknown)
        raise ValueError(f"services.{name} contains unsupported field(s) for engine='vllm': {names}")

    model = raw.get("model")
    served_model_name = raw.get("served_model_name")

    if not isinstance(model, str) or not model:
        raise ValueError(f"services.{name}.model must be a non-empty string")
    if served_model_name is not None and not isinstance(served_model_name, str):
        raise ValueError(f"services.{name}.served_model_name must be a string")

    runtime_bin_dir = raw.get("runtime_bin_dir")
    if runtime_bin_dir is not None and (not isinstance(runtime_bin_dir, str) or not runtime_bin_dir):
        raise ValueError(f"services.{name}.runtime_bin_dir must be a non-empty string")

    return ServiceSpec(
        name=name,
        engine="vllm",
        host=_get_service_host(raw, defaults, name),
        port=_get_service_port(raw, name),
        env=_as_str_dict(
            _merge_table_dict(defaults, raw, "env", "defaults.env", f"services.{name}.env"),
            f"services.{name}.env",
        ),
        notes=_get_service_notes(raw, name),
        runtime_bin_dir=(
            _expand_env(runtime_bin_dir, f"services.{name}.runtime_bin_dir")
            if runtime_bin_dir is not None
            else None
        ),
        model=_expand_env(model, f"services.{name}.model"),
        served_model_name=(
            _expand_env(served_model_name, f"services.{name}.served_model_name")
            if served_model_name is not None
            else None
        ),
        args=_as_flag_map(
            _merge_table_dict(defaults, raw, "args", "defaults.args", f"services.{name}.args"),
            f"services.{name}.args",
        ),
        extra_args=_as_str_list(raw.get("extra_args"), f"services.{name}.extra_args"),
        loras=_as_loras(raw.get("loras"), f"services.{name}.loras"),
        assets=_as_assets(
            _merge_table_dict(
                defaults,
                raw,
                "assets",
                "defaults.assets",
                f"services.{name}.assets",
            ),
            f"services.{name}.assets",
        ),
    )


def _service_from_llamacpp(
    name: str,
    raw: dict[str, object],
    defaults: dict[str, object],
) -> ServiceSpec:
    allowed_keys = {
        "engine",
        "model",
        "hf_repo",
        "hf_file",
        "host",
        "port",
        "served_model_name",
        "env",
        "args",
        "extra_args",
        "assets",
        "notes",
        "runtime_bin_dir",
    }
    unknown = sorted(set(raw.keys()) - allowed_keys)
    if unknown:
        names = ", ".join(unknown)
        raise ValueError(
            f"services.{name} contains unsupported field(s) for engine='llamacpp': {names}"
        )

    model = raw.get("model")
    hf_repo = raw.get("hf_repo")
    hf_file = raw.get("hf_file")
    served_model_name = raw.get("served_model_name")
    runtime_bin_dir = raw.get("runtime_bin_dir")

    if model is not None and (not isinstance(model, str) or not model):
        raise ValueError(f"services.{name}.model must be a non-empty string")
    if hf_repo is not None and (not isinstance(hf_repo, str) or not hf_repo):
        raise ValueError(f"services.{name}.hf_repo must be a non-empty string")
    if hf_file is not None and (not isinstance(hf_file, str) or not hf_file):
        raise ValueError(f"services.{name}.hf_file must be a non-empty string")
    if model is None and hf_repo is None:
        raise ValueError(f"services.{name} must set either model or hf_repo")
    if served_model_name is not None and not isinstance(served_model_name, str):
        raise ValueError(f"services.{name}.served_model_name must be a string")
    if runtime_bin_dir is not None and (not isinstance(runtime_bin_dir, str) or not runtime_bin_dir):
        raise ValueError(f"services.{name}.runtime_bin_dir must be a non-empty string")

    return ServiceSpec(
        name=name,
        engine="llamacpp",
        host=_get_service_host(raw, defaults, name),
        port=_get_service_port(raw, name),
        env=_as_str_dict(
            _merge_table_dict(defaults, raw, "env", "defaults.env", f"services.{name}.env"),
            f"services.{name}.env",
        ),
        notes=_get_service_notes(raw, name),
        runtime_bin_dir=(
            _expand_env(runtime_bin_dir, f"services.{name}.runtime_bin_dir")
            if runtime_bin_dir is not None
            else None
        ),
        model=(
            _expand_env(model, f"services.{name}.model")
            if model is not None
            else None
        ),
        hf_repo=(
            _expand_env(hf_repo, f"services.{name}.hf_repo")
            if hf_repo is not None
            else None
        ),
        hf_file=(
            _expand_env(hf_file, f"services.{name}.hf_file")
            if hf_file is not None
            else None
        ),
        served_model_name=(
            _expand_env(served_model_name, f"services.{name}.served_model_name")
            if served_model_name is not None
            else None
        ),
        args=_as_flag_map(
            _merge_table_dict(defaults, raw, "args", "defaults.args", f"services.{name}.args"),
            f"services.{name}.args",
        ),
        extra_args=_as_str_list(raw.get("extra_args"), f"services.{name}.extra_args"),
        assets=_as_assets(
            _merge_table_dict(
                defaults,
                raw,
                "assets",
                "defaults.assets",
                f"services.{name}.assets",
            ),
            f"services.{name}.assets",
        ),
    )


def _service_from_hindsight(
    name: str,
    raw: dict[str, object],
    defaults: dict[str, object],
) -> ServiceSpec:
    allowed_keys = {
        "engine",
        "host",
        "port",
        "data_dir",
        "llm_service",
        "env",
        "notes",
        "runtime_bin_dir",
    }
    unknown = sorted(set(raw.keys()) - allowed_keys)
    if unknown:
        names = ", ".join(unknown)
        raise ValueError(
            f"services.{name} contains unsupported field(s) for engine='hindsight': {names}"
        )

    data_dir = raw.get("data_dir", "~/data/hindsight")
    llm_service = raw.get("llm_service")
    runtime_bin_dir = raw.get("runtime_bin_dir")

    if not isinstance(data_dir, str) or not data_dir:
        raise ValueError(f"services.{name}.data_dir must be a non-empty string")
    if not isinstance(llm_service, str) or not llm_service:
        raise ValueError(f"services.{name}.llm_service must be a non-empty string")
    if runtime_bin_dir is not None and (not isinstance(runtime_bin_dir, str) or not runtime_bin_dir):
        raise ValueError(f"services.{name}.runtime_bin_dir must be a non-empty string")

    expanded_data_dir = _expand_env(data_dir, f"services.{name}.data_dir")

    return ServiceSpec(
        name=name,
        engine="hindsight",
        host=_get_service_host(raw, defaults, name),
        port=_get_service_port(raw, name),
        env=_as_str_dict(
            _merge_table_dict(defaults, raw, "env", "defaults.env", f"services.{name}.env"),
            f"services.{name}.env",
        ),
        notes=_get_service_notes(raw, name),
        runtime_bin_dir=(
            _expand_env(runtime_bin_dir, f"services.{name}.runtime_bin_dir")
            if runtime_bin_dir is not None
            else None
        ),
        data_dir=str(Path(expanded_data_dir).expanduser()),
        llm_service=llm_service,
    )


def _service_from_data(
    name: str,
    raw: dict[str, object],
    defaults: dict[str, object],
) -> ServiceSpec:
    engine = raw.get("engine", "vllm")
    if not isinstance(engine, str) or not engine:
        raise ValueError(f"services.{name}.engine must be a non-empty string")
    if engine == "vllm":
        return _service_from_vllm(name, raw, defaults)
    if engine == "llamacpp":
        return _service_from_llamacpp(name, raw, defaults)
    if engine == "hindsight":
        return _service_from_hindsight(name, raw, defaults)
    raise ValueError(f"Unsupported engine in v1: {engine}")


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

    allowed_stack_keys = {"name", "track", "primary_service", "notes"}
    unknown_stack_keys = sorted(set(stack.keys()) - allowed_stack_keys)
    if unknown_stack_keys:
        names = ", ".join(unknown_stack_keys)
        raise ValueError(f"[stack] contains unsupported field(s): {names}")

    name = stack.get("name", path.stem)
    inferred_track = path.parent.name
    track = stack.get("track", inferred_track)
    primary_service = stack.get("primary_service")
    notes = stack.get("notes")

    if not isinstance(name, str) or not name:
        raise ValueError("stack.name must be a non-empty string")
    if not isinstance(track, str) or track not in TRACKS:
        raise ValueError(f"stack.track must be one of {', '.join(TRACKS)}")
    if track != inferred_track:
        raise ValueError(
            f"stack.track={track!r} does not match manifest directory {inferred_track!r}: {path}"
        )
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

    for service_name, service in parsed_services.items():
        if service.engine != "hindsight":
            continue
        llm_service = service.llm_service
        if llm_service not in parsed_services:
            raise ValueError(
                f"services.{service_name}.llm_service must reference an existing service"
            )
        target = parsed_services[llm_service]
        if target.engine not in {"vllm", "llamacpp"}:
            raise ValueError(
                f"services.{service_name}.llm_service must reference an LLM service (vllm or llamacpp)"
            )

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
