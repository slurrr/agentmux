from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agentmux.config import STACK_ROOT, resolve_stack
from agentmux.runner import build_stack_plan, launch_stack
from agentmux.runtime import read_active
from agentmux.smoke import smoke_stack_safe

DEFAULT_MODEL_STORE = Path.home() / "models"
DEFAULT_LOCAL_MODEL_ROOT = DEFAULT_MODEL_STORE / "local" / "hf-snapshots"
DEFAULT_ACTIVE_MODEL_ROOT = DEFAULT_MODEL_STORE / "active"
DEFAULT_MODEL_MANIFEST_ROOT = DEFAULT_MODEL_STORE / "manifests"
DEFAULT_ONBOARDING_ROOT = Path.home() / "runs" / "agentmux" / "onboarding"
DEFAULT_MEMORY_DATA_DIR = Path.home() / "data" / "hindsight"
DEFAULT_STACK_TRACK = "lab"
DEFAULT_STACK_PORT = 8002
DEFAULT_MEMORY_PORT = 8888


@dataclass(frozen=True)
class OnboardRoots:
    model_root: Path = DEFAULT_MODEL_STORE
    local_model_root: Path = DEFAULT_LOCAL_MODEL_ROOT
    active_model_root: Path = DEFAULT_ACTIVE_MODEL_ROOT
    model_manifest_root: Path = DEFAULT_MODEL_MANIFEST_ROOT
    onboarding_root: Path = DEFAULT_ONBOARDING_ROOT


@dataclass(frozen=True)
class OnboardResult:
    requested_source: str
    resolved_source: str
    slug: str
    stack_name: str
    track: str
    local_model_path: str
    active_model_path: str
    manifest_path: str
    model_manifest_path: str
    onboarding_dir: str
    launch_attempted: bool
    launch_performed: bool
    smoke: dict[str, Any] | None
    benchmark: dict[str, Any] | None
    render: dict[str, Any]
    notes: str | None
    services: list[str]
    created_at: str


class OnboardingError(RuntimeError):
    pass


def _json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_value(value: object) -> str:
    if isinstance(value, str):
        return _json_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value)!r}")


def _write_toml_table(lines: list[str], table_path: str, values: dict[str, object]) -> None:
    lines.append(f"[{table_path}]")
    for key, value in values.items():
        lines.append(f"{key} = {_toml_value(value)}")
    lines.append("")


def _slugify(text: str) -> str:
    lowered = text.lower().strip()
    lowered = lowered.replace("_", "-").replace(" ", "-")
    lowered = re.sub(r"[^a-z0-9.\-]+", "-", lowered)
    lowered = re.sub(r"-+", "-", lowered)
    return lowered.strip("-")


def _decode_hf_repo_name(name: str) -> str:
    if name.startswith("models--"):
        parts = name.split("--")
        if len(parts) >= 3:
            return parts[-1]
    return name


def _resolve_hf_source(source: Path) -> Path:
    source = source.expanduser()
    if not source.exists():
        raise OnboardingError(f"model source does not exist: {source}")

    if source.is_file():
        return source.resolve()

    if (source / "snapshots").is_dir() and (source / "refs" / "main").exists():
        ref = (source / "refs" / "main").read_text(encoding="utf-8").strip()
        if ref:
            candidate = source / "snapshots" / ref
            if candidate.exists():
                return candidate.resolve()
        snapshots = sorted(path for path in (source / "snapshots").iterdir() if path.is_dir())
        if len(snapshots) == 1:
            return snapshots[0].resolve()
        raise OnboardingError(
            f"could not resolve a snapshot under cache repo root: {source}"
        )

    if source.name == "snapshots" and source.parent.is_dir():
        snapshots = sorted(path for path in source.iterdir() if path.is_dir())
        if len(snapshots) == 1:
            return snapshots[0].resolve()

    if source.parent.name == "snapshots":
        return source.resolve()

    config_json = source / "config.json"
    if config_json.exists():
        return source.resolve()

    return source.resolve()


def _source_label(source: Path) -> str:
    parent = source.parent
    if parent.name == "snapshots" and parent.parent.name.startswith("models--"):
        return _decode_hf_repo_name(parent.parent.name)
    if source.name.startswith("models--"):
        return _decode_hf_repo_name(source.name)
    return source.name


def _is_gguf_source(source: Path) -> bool:
    if source.is_file():
        return source.suffix == ".gguf"
    if source.is_dir():
        ggufs = [
            path
            for path in source.glob("*.gguf")
            if path.is_file() and not path.name.startswith("mmproj")
        ]
        return len(ggufs) > 0 and not (source / "config.json").exists()
    return False


def _resolve_gguf_target(source: Path) -> Path | None:
    if source.is_file() and source.suffix == ".gguf":
        return source.resolve()
    if not source.is_dir():
        return None
    candidates = sorted(
        path
        for path in source.glob("*.gguf")
        if path.is_file() and not path.name.startswith("mmproj")
    )
    if len(candidates) == 1:
        return candidates[0].resolve()
    if len(candidates) > 1:
        raise OnboardingError(
            f"multiple gguf model files found in {source}; specify a single gguf artifact"
        )
    return None


def _select_profile(source_text: str, slug: str, *, gguf: bool = False) -> dict[str, Any]:
    lowered = f"{source_text} {slug}".lower()
    profile: dict[str, Any] = {
        "args": {
            "dtype": "bfloat16",
            "gpu_memory_utilization": 0.95,
            "max_num_seqs": 4,
            "tensor_parallel_size": 1,
            "enable_prefix_caching": True,
            "enable_force_include_usage": True,
        },
        "assets": {},
        "notes": "standard vLLM-onboarding defaults",
    }

    if "gpt-oss" in lowered:
        profile["args"].update(
            {
                "load_format": "auto",
                "generation_config": "vllm",
                "enable_auto_tool_choice": True,
                "tool_call_parser": "openai",
                "reasoning_parser": "openai_gptoss",
                "exclude_tools_when_tool_choice_none": True,
            }
        )
        profile["args"]["max_num_seqs"] = 12
        profile["notes"] = "gpt-oss-style defaults with openai tool parsing"
        return profile

    if "qwen" in lowered:
        profile["args"].update(
            {
                "load_format": "auto",
                "gpu_memory_utilization": 0.98,
                "max_num_seqs": 36,
                "enable_auto_tool_choice": True,
                "tool_call_parser": "qwen3_xml",
                "reasoning_parser": "qwen3",
                "exclude_tools_when_tool_choice_none": True,
                "chat_template_content_format": "openai",
                "default_chat_template_kwargs": '{"enable_thinking":false}',
                "max_model_len": 73728,
            }
        )
        profile["assets"]["chat_template"] = (
            "assets/chat_templates/qwen3.5_hf_fix_chat_template.jinja"
        )
        profile["notes"] = "qwen-style defaults with the HF-fix chat template"
        return profile

    if "gemma" in lowered:
        profile["args"].update(
            {
                "load_format": "gguf" if gguf else "auto",
                "gpu_memory_utilization": 0.95,
                "max_num_seqs": 20 if gguf else 36,
                "enable_auto_tool_choice": True,
                "tool_call_parser": "gemma4",
                "reasoning_parser": "gemma4",
                "exclude_tools_when_tool_choice_none": True,
                "chat_template_content_format": "openai",
                "generation_config": "auto",
                "default_chat_template_kwargs": '{"enable_thinking":true}',
                "structured_outputs_config": (
                    '{"backend":"xgrammar","reasoning_parser":"gemma4",'
                    '"enable_in_reasoning":false,"disable_any_whitespace":false}'
                ),
                "async_scheduling": True,
                "max_model_len": 131072,
            }
        )
        if gguf:
            profile["args"]["tokenizer"] = (
                "/home/poop/models/local/hf-snapshots/gemma-4-e4b-it/current"
            )
        profile["assets"]["chat_template"] = "assets/chat_templates/tool_chat_template_gemma4.jinja"
        profile["notes"] = "gemma-style defaults with a tool chat template"
        if gguf:
            profile["args"]["dtype"] = "auto"
            profile["notes"] = "gemma gguf defaults with a tool chat template"
        return profile

    return profile


def _ensure_parent_dirs(roots: OnboardRoots) -> None:
    roots.local_model_root.mkdir(parents=True, exist_ok=True)
    (roots.model_root / "local" / "gguf").mkdir(parents=True, exist_ok=True)
    roots.active_model_root.mkdir(parents=True, exist_ok=True)
    roots.model_manifest_root.mkdir(parents=True, exist_ok=True)
    roots.onboarding_root.mkdir(parents=True, exist_ok=True)


def _safe_symlink(source: Path, target: Path, *, force: bool = False) -> None:
    if target.exists() or target.is_symlink():
        if not force:
            raise OnboardingError(f"target already exists: {target}")
        if target.is_dir() and not target.is_symlink():
            raise OnboardingError(f"target is an existing directory: {target}")
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)


def _render_manifest(
    *,
    stack_name: str,
    source_path: Path,
    source_label: str,
    active_model_path: Path,
    track: str,
    instructions: str | None,
    services: list[str],
    gguf: bool = False,
) -> str:
    profile = _select_profile(f"{source_path} {source_label} {stack_name}", stack_name, gguf=gguf)
    notes_parts = [
        f"Onboarded from {source_path}",
        profile["notes"],
    ]
    if instructions:
        notes_parts.append(f"Instructions: {instructions}")
    notes = " | ".join(notes_parts)

    lines: list[str] = []
    lines.append("[stack]")
    lines.append(f"name = {_toml_value(stack_name)}")
    lines.append(f"track = {_toml_value(track)}")
    lines.append(f"primary_service = {_toml_value('main')}")
    lines.append(f"notes = {_toml_value(notes)}")
    lines.append("")
    lines.append("[defaults]")
    lines.append(f"host = {_toml_value('0.0.0.0')}")
    lines.append("")
    _write_toml_table(lines, "defaults.args", profile["args"])

    lines.append("[services.main]")
    lines.append(f"engine = {_toml_value('vllm')}")
    runtime_bin_dir = (
        "scripts/gemma4-vllm-bin" if gguf and "gemma" in stack_name.lower() else ".venv-vllm/bin"
    )
    lines.append(f"runtime_bin_dir = {_toml_value(runtime_bin_dir)}")
    lines.append(f"model = {_toml_value(str(active_model_path))}")
    lines.append(f"port = {_toml_value(DEFAULT_STACK_PORT)}")
    lines.append(f"served_model_name = {_toml_value(stack_name)}")
    lines.append(f"extra_args = {_toml_value(['--disable-uvicorn-access-log'])}")
    lines.append("")
    if profile["assets"]:
        _write_toml_table(lines, "services.main.assets", profile["assets"])

    if "memory" in services:
        lines.append("[services.memory]")
        lines.append(f"engine = {_toml_value('hindsight')}")
        lines.append(f"host = {_toml_value('127.0.0.1')}")
        lines.append(f"port = {_toml_value(DEFAULT_MEMORY_PORT)}")
        lines.append(f"runtime_bin_dir = {_toml_value('.venv-hindsight/bin')}")
        lines.append(f"data_dir = {_toml_value(str(DEFAULT_MEMORY_DATA_DIR))}")
        lines.append(f"llm_service = {_toml_value('main')}")
        lines.append("")
        _write_toml_table(
            lines,
            "services.memory.env",
            {
                "HINDSIGHT_API_EMBEDDINGS_PROVIDER": "local",
                "HINDSIGHT_API_EMBEDDINGS_LOCAL_FORCE_CPU": "true",
                "HINDSIGHT_API_RERANKER_PROVIDER": "local",
                "HINDSIGHT_API_RERANKER_LOCAL_FORCE_CPU": "true",
                "HINDSIGHT_API_LAZY_RERANKER": "true",
            },
        )

    return "\n".join(lines).rstrip() + "\n"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def onboard_model(
    source: Path,
    *,
    stack_name: str | None = None,
    track: str = DEFAULT_STACK_TRACK,
    instructions: str | None = None,
    services: list[str] | None = None,
    launch: bool = True,
    smoke: bool = True,
    bench: bool = False,
    force: bool = False,
    roots: OnboardRoots | None = None,
    mux_root: Path = STACK_ROOT,
) -> OnboardResult:
    roots = roots or OnboardRoots()
    services = services or []
    _ensure_parent_dirs(roots)

    resolved_source = _resolve_hf_source(source)
    slug_source = _source_label(resolved_source)
    slug = _slugify(stack_name or slug_source)
    if not slug:
        raise OnboardingError("could not derive a stack name from the source path")

    gguf_target = _resolve_gguf_target(resolved_source)
    gguf = gguf_target is not None

    stack_path = mux_root / track / f"{slug}.toml"
    if stack_path.exists() and not force:
        raise OnboardingError(f"stack manifest already exists: {stack_path}")

    if gguf:
        local_model_path = roots.model_root / "local" / "gguf" / f"{slug}.gguf"
    else:
        local_model_path = roots.local_model_root / slug / "current"
    active_model_path = roots.active_model_root / slug
    if not force and (local_model_path.exists() or local_model_path.is_symlink()):
        raise OnboardingError(f"local model pointer already exists: {local_model_path}")
    if not force and (active_model_path.exists() or active_model_path.is_symlink()):
        raise OnboardingError(f"active model pointer already exists: {active_model_path}")

    _safe_symlink(gguf_target or resolved_source, local_model_path, force=force)
    _safe_symlink(local_model_path, active_model_path, force=force)

    manifest_text = _render_manifest(
        stack_name=slug,
        source_path=resolved_source,
        source_label=slug_source,
        active_model_path=active_model_path,
        track=track,
        instructions=instructions,
        services=services,
        gguf=gguf,
    )
    _write_text(stack_path, manifest_text)

    onboarding_dir = roots.onboarding_root / f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}"
    onboarding_dir.mkdir(parents=True, exist_ok=True)
    model_manifest_path = roots.model_manifest_root / f"{slug}.md"
    render_plan = build_stack_plan(slug, root=mux_root)
    render_summary = {
        "stack": render_plan.stack.name,
        "track": render_plan.stack.track,
        "manifest": str(stack_path),
        "services": [
            {
                "name": service.service,
                "command": service.command,
                "shell_command": service.shell_command(),
                "managed": service.managed,
            }
            for service in render_plan.services
        ],
    }
    _write_text(onboarding_dir / "render.json", json.dumps(render_summary, indent=2) + "\n")
    render_text = "\n".join(
        item["shell_command"] for item in render_summary["services"]
    )
    _write_text(onboarding_dir / "render.txt", render_text + "\n")

    launch_attempted = bool(launch or bench)
    launch_performed = False
    smoke_result: dict[str, Any] | None = None
    benchmark_result: dict[str, Any] | None = None

    active = read_active(prune_stale=True)
    active_same_stack = active is not None and active.stack == slug
    if launch_attempted:
        if active is not None and not active_same_stack:
            bench = False
        elif active is None:
            try:
                launch_stack(slug, root=mux_root)
                launch_performed = True
                active_same_stack = True
            except Exception as exc:
                smoke_result = {"ok": False, "error": str(exc), "launched": False}
                bench = False

    if smoke and (launch_performed or active_same_stack):
        smoke_result = smoke_stack_safe(resolve_stack(slug, root=mux_root))
        _write_text(onboarding_dir / "smoke.json", json.dumps(smoke_result, indent=2) + "\n")

    if bench and (launch_performed or active_same_stack):
        from agentmux.bench import run_benchmark

        _result, result_path, summary = run_benchmark(slug, mux_root)
        benchmark_result = {
            "summary": summary,
            "result_path": str(result_path),
        }
        _write_text(
            onboarding_dir / "benchmark.json",
            json.dumps(benchmark_result, indent=2) + "\n",
        )

    model_manifest_lines = [
        f"# {slug}",
        "",
        f"- track: {track}",
        f"- source: {resolved_source}",
        f"- local model path: {local_model_path}",
        f"- active model path: {active_model_path}",
        f"- mux manifest: {stack_path}",
        f"- onboarding dir: {onboarding_dir}",
        f"- services: {', '.join(services) if services else 'none'}",
        "- notes: "
        f"{profile_notes(source_path=resolved_source, stack_name=slug, instructions=instructions)}",
        "",
        "## Render",
    ]
    for item in render_summary["services"]:
        model_manifest_lines.append(f"- {item['name']}: `{item['shell_command']}`")
    if smoke_result is not None:
        model_manifest_lines.extend([
            "",
            "## Smoke",
            f"- ok: {smoke_result.get('ok')}",
        ])
    if benchmark_result is not None:
        model_manifest_lines.extend([
            "",
            "## Benchmark",
            f"- result path: {benchmark_result['result_path']}",
            f"- summary: {benchmark_result['summary']}",
        ])
    _write_text(model_manifest_path, "\n".join(model_manifest_lines).rstrip() + "\n")

    summary = OnboardResult(
        requested_source=str(source),
        resolved_source=str(resolved_source),
        slug=slug,
        stack_name=slug,
        track=track,
        local_model_path=str(local_model_path),
        active_model_path=str(active_model_path),
        manifest_path=str(stack_path),
        model_manifest_path=str(model_manifest_path),
        onboarding_dir=str(onboarding_dir),
        launch_attempted=launch_attempted,
        launch_performed=launch_performed,
        smoke=smoke_result,
        benchmark=benchmark_result,
        render=render_summary,
        notes=(
            profile_notes(
                source_path=resolved_source,
                stack_name=slug,
                instructions=instructions,
            )
        ),
        services=services,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    _write_text(onboarding_dir / "summary.json", json.dumps(asdict(summary), indent=2) + "\n")
    return summary


def profile_notes(*, source_path: Path, stack_name: str, instructions: str | None) -> str:
    notes = [f"source={source_path}", f"stack={stack_name}"]
    if instructions:
        notes.append(f"instructions={instructions}")
    return " | ".join(notes)


def render_onboard_summary(result: OnboardResult) -> str:
    lines = [
        f"onboarded stack: {result.stack_name}",
        f"source: {result.resolved_source}",
        f"local model: {result.local_model_path}",
        f"active model: {result.active_model_path}",
        f"mux manifest: {result.manifest_path}",
        f"model manifest: {result.model_manifest_path}",
        f"onboarding dir: {result.onboarding_dir}",
        f"launch: {'yes' if result.launch_performed else 'no'}",
    ]
    if result.smoke is not None:
        lines.append(f"smoke: {'ok' if result.smoke.get('ok') else 'failed'}")
    if result.benchmark is not None:
        lines.append(f"benchmark: {result.benchmark['result_path']}")
    return "\n".join(lines) + "\n"
