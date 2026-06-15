from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MUX_ROOT = Path("mux")
TRACKS = ("core", "lab", "examples")
EXPORT_FILENAME = "agentmux-service.toml"
ENV_PATTERN = re.compile(
    r"\$(?:\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|(?P<bare>[A-Za-z_][A-Za-z0-9_]*))"
)


@dataclass(frozen=True)
class VolumeSpec:
    source: str
    target: str
    mode: str | None = None

    def podman_value(self) -> str:
        if self.mode:
            return f"{self.source}:{self.target}:{self.mode}"
        return f"{self.source}:{self.target}"


@dataclass(frozen=True)
class WorkspaceExportSpec:
    path: str
    name: str | None
    backend: str | None


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    image: str
    container_name: str
    host: str
    port: int
    container_port: int
    podman_args: list[str]
    env: dict[str, str]
    labels: dict[str, str]
    ports: list[str]
    volumes: list[VolumeSpec]
    command: list[str]
    health_path: str
    runtime_target: str | None
    runtime_dir: str | None
    workspace_export: WorkspaceExportSpec | None = None
    notes: str | None = None


@dataclass(frozen=True)
class MuxSpec:
    name: str
    track: str
    path: Path
    primary_service: str
    notes: str | None
    services: dict[str, ServiceSpec]


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


def _expand_path(text: str, field_name: str, base_path: Path) -> str:
    expanded = Path(_expand_env(text, field_name)).expanduser()
    if not expanded.is_absolute():
        expanded = (base_path.parent / expanded).resolve()
    return str(expanded)


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid TOML document: {path}")
    return data


def _as_str(value: object, field_name: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return _expand_env(value, field_name)


def _as_int(value: object, field_name: str, *, required: bool = False) -> int | None:
    if value is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return None
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _as_str_list(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return [_expand_env(item, f"{field_name}[{index}]") for index, item in enumerate(value)]


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


def _as_volumes(value: object, field_name: str, base_path: Path) -> list[VolumeSpec]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array of tables")
    volumes: list[VolumeSpec] = []
    for index, item in enumerate(value):
        item_field = f"{field_name}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{item_field} must be a table")
        source = item.get("source")
        target = item.get("target")
        mode = item.get("mode")
        if not isinstance(source, str) or not source:
            raise ValueError(f"{item_field}.source must be a non-empty string")
        if not isinstance(target, str) or not target:
            raise ValueError(f"{item_field}.target must be a non-empty string")
        if mode is not None and (not isinstance(mode, str) or not mode):
            raise ValueError(f"{item_field}.mode must be a non-empty string")
        volumes.append(
            VolumeSpec(
                source=_expand_path(source, f"{item_field}.source", base_path),
                target=_expand_env(target, f"{item_field}.target"),
                mode=_expand_env(mode, f"{item_field}.mode") if mode is not None else None,
            )
        )
    return volumes


def _merge_dicts(*dicts: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for values in dicts:
        merged.update(values)
    return merged


def _raw_table(data: dict[str, object], key: str, field_name: str) -> dict[str, object]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a table")
    return value


def _resolve_export_path(value: object, field_name: str, manifest_path: Path) -> Path | None:
    if value is None:
        return None
    raw = _as_str(value, field_name, required=True)
    assert raw is not None
    export_path = Path(_expand_path(raw, field_name, manifest_path))
    if export_path.is_dir():
        export_path = export_path / EXPORT_FILENAME
    if not export_path.exists():
        raise ValueError(f"{field_name} does not exist: {export_path}")
    return export_path


def _load_workspace_export(
    value: object,
    field_name: str,
    manifest_path: Path,
) -> tuple[dict[str, object], Path | None, WorkspaceExportSpec | None]:
    export_path = _resolve_export_path(value, field_name, manifest_path)
    if export_path is None:
        return {}, None, None

    data = _load_toml(export_path)
    meta = _raw_table(data, "agentmux_export", f"{field_name}.agentmux_export")
    version = meta.get("version")
    if version != 1:
        raise ValueError(f"{field_name}.agentmux_export.version must be 1")
    service = _raw_table(data, "service", f"{field_name}.service")
    return (
        service,
        export_path,
        WorkspaceExportSpec(
            path=str(export_path),
            name=_as_str(meta.get("name"), f"{field_name}.agentmux_export.name"),
            backend=_as_str(meta.get("backend"), f"{field_name}.agentmux_export.backend"),
        ),
    )


def _first_value(*values: object) -> object:
    for value in values:
        if value is not None:
            return value
    return None


def _runtime_volume(
    mux_name: str,
    service_name: str,
    runtime_target: str | None,
    runtime_dir: str | None,
    manifest_path: Path,
) -> VolumeSpec | None:
    if runtime_target is None:
        return None
    source = runtime_dir or str(Path.home() / "runs" / "agentmux" / mux_name / service_name)
    return VolumeSpec(
        source=_expand_path(source, f"services.{service_name}.runtime_dir", manifest_path),
        target=runtime_target,
        mode="rw",
    )


def _parse_service(
    mux_name: str,
    name: str,
    raw: dict[str, object],
    defaults: dict[str, object],
    manifest_path: Path,
) -> ServiceSpec:
    allowed = {
        "workspace_export",
        "image",
        "container_name",
        "host",
        "port",
        "container_port",
        "podman_args",
        "env",
        "labels",
        "ports",
        "volumes",
        "command",
        "health_path",
        "runtime_target",
        "runtime_dir",
        "notes",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError(f"services.{name} contains unsupported field(s): {', '.join(unknown)}")

    export_raw, export_path, export_spec = _load_workspace_export(
        raw.get("workspace_export"), f"services.{name}.workspace_export", manifest_path
    )
    export_base_path = export_path or manifest_path

    image = _as_str(
        _first_value(raw.get("image"), export_raw.get("image")),
        f"services.{name}.image",
        required=True,
    )
    container_name = _as_str(
        raw.get("container_name"), f"services.{name}.container_name", required=True
    )
    port = _as_int(raw.get("port"), f"services.{name}.port", required=True)
    container_port = _as_int(
        _first_value(raw.get("container_port"), export_raw.get("container_port"), port),
        f"services.{name}.container_port",
        required=True,
    )
    assert image is not None
    assert container_name is not None
    assert port is not None
    assert container_port is not None

    default_env = _as_str_dict(defaults.get("env"), "defaults.env")
    export_env = _as_str_dict(export_raw.get("env"), f"services.{name}.workspace_export.env")
    service_env = _as_str_dict(raw.get("env"), f"services.{name}.env")
    default_labels = _as_str_dict(defaults.get("labels"), "defaults.labels")
    export_labels = _as_str_dict(
        export_raw.get("labels"), f"services.{name}.workspace_export.labels"
    )
    service_labels = _as_str_dict(raw.get("labels"), f"services.{name}.labels")

    runtime_target = _as_str(
        _first_value(raw.get("runtime_target"), export_raw.get("runtime_target")),
        f"services.{name}.runtime_target",
    )
    runtime_dir = _as_str(raw.get("runtime_dir"), f"services.{name}.runtime_dir")

    export_volumes = _as_volumes(
        export_raw.get("volumes"),
        f"services.{name}.workspace_export.volumes",
        export_base_path,
    )
    volumes = (
        _as_volumes(defaults.get("volumes"), "defaults.volumes", manifest_path)
        + export_volumes
        + _as_volumes(raw.get("volumes"), f"services.{name}.volumes", manifest_path)
    )
    runtime_mount = _runtime_volume(mux_name, name, runtime_target, runtime_dir, manifest_path)
    if runtime_mount is not None:
        volumes.append(runtime_mount)

    ports = _as_str_list(defaults.get("ports"), "defaults.ports") + _as_str_list(
        raw.get("ports"), f"services.{name}.ports"
    )
    if not ports:
        ports = [f"{port}:{container_port}"]

    return ServiceSpec(
        name=name,
        image=image,
        container_name=container_name,
        host=_as_str(raw.get("host", defaults.get("host", "127.0.0.1")), f"services.{name}.host")
        or "127.0.0.1",
        port=port,
        container_port=container_port,
        podman_args=_as_str_list(defaults.get("podman_args"), "defaults.podman_args")
        + _as_str_list(
            export_raw.get("podman_args"),
            f"services.{name}.workspace_export.podman_args",
        )
        + _as_str_list(raw.get("podman_args"), f"services.{name}.podman_args"),
        env=_merge_dicts(default_env, export_env, service_env),
        labels=_merge_dicts(default_labels, export_labels, service_labels),
        ports=ports,
        volumes=volumes,
        command=_as_str_list(
            _first_value(raw.get("command"), export_raw.get("command")),
            f"services.{name}.command",
        ),
        health_path=_as_str(
            _first_value(raw.get("health_path"), export_raw.get("health_path"), "/v1/models"),
            f"services.{name}.health_path",
        )
        or "/v1/models",
        runtime_target=runtime_target,
        runtime_dir=runtime_mount.source if runtime_mount is not None else runtime_dir,
        workspace_export=export_spec,
        notes=_as_str(raw.get("notes"), f"services.{name}.notes"),
    )


def load_mux(path: Path, *, root: Path = MUX_ROOT) -> MuxSpec:
    data = _load_toml(path)
    mux_raw = data.get("mux")
    if not isinstance(mux_raw, dict):
        raise ValueError(f"{path} is missing [mux]")
    services_raw = data.get("services")
    if not isinstance(services_raw, dict) or not services_raw:
        raise ValueError(f"{path} is missing [services.<name>] tables")
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("defaults must be a table")

    name = _as_str(mux_raw.get("name"), "mux.name", required=True)
    primary_service = _as_str(mux_raw.get("primary_service"), "mux.primary_service")
    notes = _as_str(mux_raw.get("notes"), "mux.notes")
    assert name is not None

    services: dict[str, ServiceSpec] = {}
    for service_name, raw_service in services_raw.items():
        if not isinstance(service_name, str) or not service_name:
            raise ValueError("service names must be non-empty strings")
        if not isinstance(raw_service, dict):
            raise ValueError(f"services.{service_name} must be a table")
        services[service_name] = _parse_service(name, service_name, raw_service, defaults, path)

    if primary_service is None:
        primary_service = next(iter(services))
    if primary_service not in services:
        raise ValueError(f"mux.primary_service references unknown service: {primary_service}")

    track = _track_for_path(path, root)
    return MuxSpec(
        name=name,
        track=track,
        path=path,
        primary_service=primary_service,
        notes=notes,
        services=services,
    )


def _track_for_path(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return "external"
    return relative.parts[0] if relative.parts else "external"


def iter_muxes(root: Path = MUX_ROOT) -> list[MuxSpec]:
    muxes: list[MuxSpec] = []
    if not root.exists():
        return muxes
    for track in TRACKS:
        track_dir = root / track
        if not track_dir.is_dir():
            continue
        for path in sorted(track_dir.rglob("*.toml")):
            if path.name == EXPORT_FILENAME:
                continue
            muxes.append(load_mux(path, root=root))
    return muxes


def resolve_mux(name: str, root: Path = MUX_ROOT) -> MuxSpec:
    matches = [mux for mux in iter_muxes(root) if mux.name == name or mux.path.stem == name]
    if not matches:
        raise ValueError(f"Mux not found: {name}")
    if len(matches) > 1:
        paths = ", ".join(str(mux.path) for mux in matches)
        raise ValueError(f"Mux name is ambiguous: {name} ({paths})")
    return matches[0]
