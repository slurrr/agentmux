from __future__ import annotations

import json
import re
import textwrap
import time
from pathlib import Path
from typing import Any

from agentmux.runtime import runtime_root

_NUMBERED_PATTERN = re.compile(r"^\d+[.)]\s+")
_METRIC_LABELS = {
    "vllm:gpu_cache_usage_perc": "GPU Cache Usage",
    "vllm:num_requests_running": "Requests Running",
    "vllm:num_requests_waiting": "Requests Waiting",
    "vllm:num_requests_waiting_by_reason": "Requests Waiting By Reason",
    "vllm:prefix_cache_hit_rate": "Prefix Cache Hit Rate",
    "vllm:tokens_total": "Total Tokens",
    "vllm:generation_tokens_total": "Generation Tokens",
    "vllm:prompt_tokens_total": "Prompt Tokens",
    "vllm:time_to_first_token_seconds": "Time To First Token",
    "vllm:e2e_request_latency_seconds": "End-To-End Request Latency",
    "vllm:request_queue_time_seconds": "Request Queue Time",
    "vllm:request_inference_time_seconds": "Request Inference Time",
    "vllm:estimated_time_per_output_token_seconds": "Estimated Time Per Output Token",
    "vllm:time_per_output_token_seconds": "Time Per Output Token",
    "vllm:request_prefill_time_seconds": "Request Prefill Time",
    "vllm:request_decode_time_seconds": "Request Decode Time",
    "vllm:request_max_num_generation_tokens": "Request Max Generation Tokens",
    "vllm:request_params_best_of": "Request Best Of",
    "vllm:request_success_total": "Successful Requests",
}


def benchmark_dir() -> Path:
    path = runtime_root() / "benchmarks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_result(result: dict[str, Any]) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    stack = str(result["stack"]["name"])
    profile = str(result["profile"])
    path = benchmark_dir() / f"{stamp}-{stack}-{profile}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path


def latest_result_path() -> Path | None:
    paths = sorted(benchmark_dir().glob("*.json"))
    if not paths:
        return None
    return paths[-1]


def resolve_result_path(name: str | None) -> Path:
    if name is None:
        latest = latest_result_path()
        if latest is None:
            raise FileNotFoundError("No benchmark result files found")
        return latest
    candidate = Path(name).expanduser()
    if candidate.exists():
        return candidate.resolve()
    matches = sorted(path for path in benchmark_dir().glob(f"*{name}*.json"))
    if not matches:
        raise FileNotFoundError(f"No benchmark result matched '{name}'")
    return matches[-1]


def read_result(path_or_name: str | None = None) -> tuple[dict[str, Any], Path]:
    path = resolve_result_path(path_or_name)
    return json.loads(path.read_text(encoding="utf-8")), path


def _rule(title: str, width: int = 78, fill: str = "=") -> str:
    title = f" {title} " if title else ""
    if not title:
        return fill * width
    side = max(2, (width - len(title)) // 2)
    line = f"{fill * side}{title}{fill * side}"
    return line[:width]


def _section(title: str, width: int = 80) -> list[str]:
    return ["-" * width, f" {title}", "-" * width]


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def sep(ch: str = "-") -> str:
        return "+" + "+".join(ch * (w + 2) for w in widths) + "+"

    out = [sep("-")]
    out.append("| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |")
    out.append(sep("="))
    for row in rows:
        out.append("| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)) + " |")
    out.append(sep("-"))
    return out


def _kv(label: str, value: str, *, indent: int = 2, width: int = 78) -> str:
    prefix = " " * indent + f"{label}: "
    wrapped = textwrap.fill(
        str(value),
        width=width,
        initial_indent=prefix,
        subsequent_indent=" " * len(prefix),
    )
    return wrapped


def _bullets(title: str, items: list[str], *, indent: int = 2, width: int = 78) -> list[str]:
    if not items:
        return []
    lines = [" " * indent + f"{title}:"]
    bullet_indent = " " * (indent + 2) + "- "
    for item in items:
        lines.append(
            textwrap.fill(
                str(item),
                width=width,
                initial_indent=bullet_indent,
                subsequent_indent=" " * len(bullet_indent),
            )
        )
    return lines


def _format_response_preview(text: str, *, max_chars: int = 420) -> str:
    preview = text.strip()
    if not preview:
        return ""
    try:
        parsed = json.loads(preview)
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        preview = json.dumps(parsed, indent=2)
    if len(preview) > max_chars:
        preview = preview[: max_chars - 3].rstrip() + "..."
    return preview


def _format_seconds(value: Any) -> str:
    return f"{float(value):.3f}s"


def _format_gib(value: Any) -> str:
    return f"{float(value):.2f} GiB"


def _format_percent(value: Any) -> str:
    return f"{float(value):.1f}%"


def _format_bool_status(value: Any) -> str:
    return "hit" if bool(value) else "miss"


def _clean_warning_text(text: str) -> str:
    cleaned = re.sub(r"^\([^)]*\)\s+WARNING\s+[^]]+\]\s*", "", str(text)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace(
        "Performance might be sub-optimal!",
        "Performance may be sub-optimal.",
    )
    if "Config file not found at " in cleaned:
        cleaned = cleaned.split("Config file not found at ", 1)[0].strip()
        cleaned += " Tuned kernel config file not found."
    return cleaned


def _format_metric_labels(labels: str | None) -> str | None:
    if not labels:
        return None
    inner = labels.strip()[1:-1].strip()
    if not inner:
        return None
    parts = []
    for raw_part in inner.split(","):
        piece = raw_part.strip()
        if not piece:
            continue
        if "=" in piece:
            key, value = piece.split("=", 1)
            pretty_key = key.replace("_", " ").title()
            parts.append(f"{pretty_key}={value}")
        else:
            parts.append(piece)
    return ", ".join(parts) if parts else None


def _format_metric_value(name: str, value: Any) -> str:
    numeric = float(value)
    if name.endswith("_perc"):
        return _format_percent(numeric)
    if name.endswith("_seconds"):
        return _format_seconds(numeric)
    if name.endswith("_tokens") or name.endswith("_tokens_total"):
        return f"{numeric:,.1f}"
    if name.endswith("_bytes") or name.endswith("_bytes_total"):
        return f"{numeric:,.0f} bytes"
    if name.endswith("_flops") or name.endswith("_flops_total"):
        return f"{numeric:,.0f}"
    if numeric.is_integer():
        return f"{int(numeric):,}"
    return f"{numeric:,.4f}"


def _format_metric_entry(entry: dict[str, Any]) -> tuple[str, str, str | None]:
    name = str(entry.get("name", "metric"))
    label = _METRIC_LABELS.get(name, name.removeprefix("vllm:").replace("_", " ").title())
    rendered_value = _format_metric_value(name, entry.get("value", 0.0))
    rendered_labels = _format_metric_labels(entry.get("labels"))
    return label, rendered_value, rendered_labels


def _response_block(
    text: str,
    *,
    indent: int = 2,
    width: int = 78,
    max_chars: int = 420,
) -> list[str]:
    preview = _format_response_preview(text, max_chars=max_chars)
    if not preview:
        return []
    lines = [" " * indent + "response:"]
    base_indent = " " * (indent + 2)
    for raw_line in preview.splitlines() or [preview]:
        stripped = raw_line.rstrip()
        if not stripped:
            lines.append("")
            continue
        is_bullet = bool(stripped.lstrip().startswith(("- ", "* ", "• ")))
        is_numbered = bool(_NUMBERED_PATTERN.match(stripped.lstrip()))
        initial = base_indent
        subsequent = base_indent
        if is_bullet or is_numbered:
            initial = base_indent
            subsequent = base_indent + "  "
        lines.extend(
            textwrap.fill(
                stripped,
                width=width,
                initial_indent=initial,
                subsequent_indent=subsequent,
                replace_whitespace=False,
                drop_whitespace=False,
            ).splitlines()
        )
    return lines


def render_summary(result: dict[str, Any], result_path: Path) -> str:
    WIDTH = 80

    def fmt_num(value: Any, unit: str | None = None) -> str:
        if value is None:
            return "n/a"
        try:
            out = f"{float(value):.3f}"
        except Exception:
            return str(value)
        return f"{out} {unit}" if unit else out

    def err_rate(completed: Any, failed: Any) -> str:
        try:
            c = int(completed)
            f = int(failed)
        except Exception:
            return "n/a"
        total = c + f
        pct = (f / total * 100.0) if total else 0.0
        return f"{f}/{total} ({pct:.1f}%)"

    summary = result["summary"]
    categories = summary["categories"]
    quality_no_tools = categories.get("quality_no_tools", {})
    quality_with_tools = categories.get("quality_with_tools", {})

    declared = result.get("declared_config", {})
    declared_args = declared.get("args", {}) if isinstance(declared, dict) else {}
    run = result.get("run", {}) if isinstance(result.get("run"), dict) else {}
    launch_observation = run.get("launch_observation") if isinstance(run.get("launch_observation"), dict) else {}
    overrides = launch_observation.get("bench_overrides", {}) if isinstance(launch_observation, dict) else {}
    max_num_seqs_override = None
    if isinstance(overrides, dict):
        vllm_args = overrides.get("vllm_args")
        if isinstance(vllm_args, dict):
            max_num_seqs_override = vllm_args.get("max_num_seqs")

    perf = result.get("perf") if isinstance(result.get("perf"), dict) else {}
    perf_summary_path = perf.get("perf_summary_path") if isinstance(perf.get("perf_summary_path"), str) else None
    perf_summary: dict[str, Any] | None = None
    if perf_summary_path:
        try:
            perf_summary = json.loads(Path(perf_summary_path).read_text(encoding="utf-8"))
        except Exception:
            perf_summary = None

    cases = list(result.get("cases", []))
    failed_count = sum(1 for c in cases if (not bool(c.get("passed"))) or c.get("status") == "failed")
    judge_flagged_count = 0
    audit = result.get("audit")
    if isinstance(audit, dict) and isinstance(audit.get("judge_review"), list):
        judge_flagged_count = sum(1 for item in audit["judge_review"] if isinstance(item, dict) and bool(item.get("flag")))

    lines = []
    lines.append("=" * WIDTH)
    lines.append(f" BENCH REPORT: {result['stack']['name']} ({result['profile']})")
    lines.append("=" * WIDTH)

    lines.extend(
        [
            _kv("Status", str(run.get("status", "unknown")).upper(), indent=0, width=WIDTH),
            _kv("Failures", str(failed_count), indent=0, width=WIDTH),
            _kv("Judge Flagged", str(judge_flagged_count), indent=0, width=WIDTH),
            _kv("Result", str(result_path), indent=0, width=WIDTH),
            _kv("Model", str(declared.get("model") or run.get("model") or "n/a"), indent=0, width=WIDTH),
            _kv("Served Model", str(declared.get("served_model_name") or "n/a"), indent=0, width=WIDTH),
            _kv("DType", str(declared_args.get("dtype") or "auto"), indent=0, width=WIDTH),
            _kv("KV Cache DType", str(declared_args.get("kv_cache_dtype") or "n/a"), indent=0, width=WIDTH),
            _kv("Max Model Len", str(declared_args.get("max_model_len") or "n/a"), indent=0, width=WIDTH),
        ]
    )
    if isinstance(max_num_seqs_override, dict):
        lines.append(
            _kv(
                "Bench Override",
                f"max-num-seqs: {max_num_seqs_override.get('before')} -> {max_num_seqs_override.get('after')}",
                indent=0,
                width=WIDTH,
            )
        )

    lines.extend(_section("PERF (ENDPOINT)", width=WIDTH))
    if not perf_summary:
        lines.append(" perf: missing for this run (old format or perf failed)")
    elif not perf_summary.get("available", False):
        lines.append(f" perf: unavailable ({perf_summary.get('reason')})")
    else:
        lines.append(f" provenance: vllm={perf_summary.get('vllm_version')} module={perf_summary.get('module')}")
        lane_a = perf_summary.get("lane_metrics", {}).get("lane_a", {})
        lane_b = perf_summary.get("lane_metrics", {}).get("lane_b", {})
        a_completed = lane_a.get("completed", lane_a.get("completed_requests"))
        a_failed = lane_a.get("failed", lane_a.get("failed_requests"))

        lines.append("")
        lines.extend(_table(["Lane A Metric", "Value"], [
            ["req/s", fmt_num(lane_a.get("request_throughput"))],
            ["tok/s", fmt_num(lane_a.get("output_throughput"))],
            ["total tok/s", fmt_num(lane_a.get("total_token_throughput"))],
            ["TTFT mean", fmt_num(lane_a.get("mean_ttft_ms"), "ms")],
            ["TTFT p99", fmt_num(lane_a.get("p99_ttft_ms"), "ms")],
            ["TPOT mean", fmt_num(lane_a.get("mean_tpot_ms"), "ms")],
            ["ITL mean", fmt_num(lane_a.get("mean_itl_ms"), "ms")],
            ["Duration", fmt_num(lane_a.get("duration"), "s")],
            ["Errors", err_rate(a_completed, a_failed)],
        ]))

        b_rows: list[list[str]] = []
        for level in (2, 4, 8, 16):
            row = lane_b.get(str(level), {}) if isinstance(lane_b, dict) else {}
            completed = row.get("completed", row.get("completed_requests"))
            failed = row.get("failed", row.get("failed_requests"))
            b_rows.append([
                str(level),
                fmt_num(row.get("request_throughput")),
                fmt_num(row.get("output_throughput")),
                fmt_num(row.get("mean_ttft_ms"), "ms"),
                fmt_num(row.get("p99_ttft_ms"), "ms"),
                err_rate(completed, failed),
            ])
        lines.append("")
        lines.extend(_table(["Conc", "req/s", "tok/s", "TTFT mean", "TTFT p99", "Errors"], b_rows))

    lines.extend(_section("PROMPT BENCH", width=WIDTH))
    lines.extend(
        _table(
            ["Metric", "Value"],
            [
                ["Drills (no-tools)", f"{quality_no_tools.get('passed_cases', 0)}/{quality_no_tools.get('total_cases', 0)} passed"],
                ["Workspace/tool outcomes", f"{quality_with_tools.get('passed_cases', 0)}/{quality_with_tools.get('total_cases', 0)} passed"],
                ["Invalid tool calls", str(quality_with_tools.get("invalid_tool_calls", 0))],
                ["Prompt Reference", "docs/reference/bench-prompts.md"],
            ],
        )
    )
    return "\n".join(lines)


def _append_client_observed(lines: list[str], result: dict[str, Any]) -> None:
    serving = result.get("summary", {}).get("categories", {}).get("serving", {})
    aggregate = serving.get("aggregate", {}) if isinstance(serving, dict) else {}
    if not isinstance(aggregate, dict):
        return
    lines.extend(["", _rule("client observed")])
    lines.append(
        _kv(
            "Average Turn Latency",
            _format_seconds(aggregate.get("client_observed_avg_request_wall_time_seconds", 0.0)),
            indent=0,
        )
    )
    lines.append(
        _kv(
            "Average First Stream Event",
            _format_seconds(
                aggregate.get("client_observed_avg_time_to_first_stream_event_seconds", 0.0)
            ),
            indent=0,
        )
    )
    avg_client_output = float(aggregate.get("client_observed_avg_output_tokens_per_second", 0.0))
    lines.append(
        _kv(
            "Average Client Output Rate",
            f"{avg_client_output:.2f} tok/s",
            indent=0,
        )
    )
    lines.append(
        _kv(
            "Concurrency-4 Efficiency",
            f"{float(aggregate.get('client_observed_concurrency_4_efficiency', 0.0)):.2f}",
            indent=0,
        )
    )

    first_request = aggregate.get("first_request")
    if isinstance(first_request, dict):
        lines.append("")
        lines.append("First Benchmark Request After Ready Check:")
        lines.append(
            _kv(
                "Wall Time",
                _format_seconds(
                    first_request.get("client_observed_request_wall_time_seconds", 0.0)
                ),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "First Stream Event",
                _format_seconds(
                    first_request.get(
                        "client_observed_time_to_first_stream_event_seconds",
                        0.0,
                    )
                ),
                indent=2,
            )
        )

    after_first = aggregate.get("after_first_request")
    if isinstance(after_first, dict):
        lines.append("")
        lines.append("Average After First Request:")
        lines.append(
            _kv(
                "Wall Time",
                _format_seconds(
                    after_first.get("client_observed_avg_request_wall_time_seconds", 0.0)
                ),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "First Stream Event",
                _format_seconds(
                    after_first.get(
                        "client_observed_avg_time_to_first_stream_event_seconds",
                        0.0,
                    )
                ),
                indent=2,
            )
        )

    by_concurrency = serving.get("by_concurrency") if isinstance(serving, dict) else None
    if isinstance(by_concurrency, dict):
        lines.append("")
        lines.append("By Concurrency:")
        for key in sorted(by_concurrency, key=int):
            item = by_concurrency[key]
            if not isinstance(item, dict):
                continue
            wall = _format_seconds(item.get("avg_request_wall_time_seconds", 0.0))
            first_event = _format_seconds(item.get("avg_time_to_first_stream_event_seconds", 0.0))
            output_rate = float(item.get("avg_output_tokens_per_second", 0.0))
            detail = (
                f"wall {wall}, first event {first_event}, client output {output_rate:.2f} tok/s"
            )
            lines.append(_kv(f"{key} request(s)", detail, indent=2))


def _append_declared_config(lines: list[str], result: dict[str, Any]) -> None:
    declared = result.get("declared_config")
    if not isinstance(declared, dict):
        return
    lines.extend(["", _rule("declared config")])
    labels = {
        "engine": "Engine",
        "model": "Model Path",
        "served_model_name": "Served Model Name",
        "runtime_bin_dir": "Runtime Bin Dir",
    }
    for key, label in labels.items():
        value = declared.get(key)
        if value not in (None, "", {}):
            lines.append(_kv(label, str(value), indent=0))
    args = declared.get("args")
    if isinstance(args, dict):
        arg_labels = {
            "dtype": "DType",
            "kv_cache_dtype": "KV Cache DType",
            "gpu_memory_utilization": "GPU Memory Utilization",
            "max_model_len": "Max Model Length",
            "max_num_seqs": "Max Concurrent Sequences",
            "enable_prefix_caching": "Prefix Caching",
            "reasoning_parser": "Reasoning Parser",
            "tool_call_parser": "Tool Call Parser",
        }
        for key, label in arg_labels.items():
            if key in args:
                lines.append(_kv(label, str(args[key]), indent=0))


def _append_observed_startup(lines: list[str], result: dict[str, Any]) -> None:
    startup = result.get("observed_startup")
    if not isinstance(startup, dict):
        return
    lines.extend(["", _rule("vllm startup")])
    if not startup.get("available"):
        lines.append(_kv("Status", str(startup.get("reason", "unavailable")), indent=0))
        return

    field_map = [
        ("vllm_version", "vLLM Version", str),
        ("resolved_architecture", "Model Architecture", str),
        ("model_path", "Model Path", str),
        ("model_load_gpu_memory_gib", "Model Weights on GPU", _format_gib),
        ("model_load_seconds", "Model Load Time", _format_seconds),
        ("torch_compile_seconds", "Torch Compile Time", _format_seconds),
        ("compile_cache_hit", "Compile Cache", _format_bool_status),
        ("available_kv_cache_memory_gib", "KV Cache Memory Available", _format_gib),
        ("gpu_kv_cache_tokens", "GPU KV Cache Capacity", lambda value: f"{int(value):,} tokens"),
        (
            "max_concurrency_estimate",
            "Estimated Max Concurrency",
            lambda value: f"{float(value):.2f}x",
        ),
        ("multimodal_warmup_seconds", "Multimodal Warmup", _format_seconds),
    ]
    for key, label, formatter in field_map:
        value = startup.get(key)
        if value not in (None, "", []):
            lines.append(_kv(label, formatter(value), indent=0))

    max_tokens = startup.get("max_concurrency_tokens_per_request")
    if max_tokens not in (None, ""):
        lines.append(_kv("Concurrency Basis", f"{int(max_tokens):,} tokens per request", indent=0))

    requested_args = {}
    declared = result.get("declared_config")
    if isinstance(declared, dict) and isinstance(declared.get("args"), dict):
        requested_args = declared["args"]

    verification_rows: list[tuple[str, str, str]] = []
    for label, requested_key, resolved_key in (
        ("DType", "dtype", "resolved_dtype"),
        ("KV Cache DType", "kv_cache_dtype", "resolved_kv_cache_dtype"),
        ("Max Model Length", "max_model_len", "resolved_max_seq_len"),
        ("Chunked Prefill", "enable_chunked_prefill", "resolved_enable_chunked_prefill"),
    ):
        requested = requested_args.get(requested_key, "auto")
        resolved = startup.get(resolved_key)
        if resolved not in (None, ""):
            verification_rows.append((label, str(requested), str(resolved)))
    resolved_quantization = startup.get("resolved_quantization")
    if resolved_quantization not in (None, ""):
        verification_rows.append(("Quantization", "manifest/model", str(resolved_quantization)))
    if verification_rows:
        lines.append("")
        lines.append("Verification:")
        for label, requested, resolved in verification_rows:
            lines.append(_kv(label, f"requested {requested}  ->  resolved {resolved}", indent=2))

    backends = startup.get("attention_backends") or []
    if backends:
        latest = backends[-1]
        if isinstance(latest, dict):
            lines.append(_kv("Attention Backend", str(latest.get("chosen", "unknown")), indent=0))
            potential = latest.get("potential")
            if isinstance(potential, list) and potential:
                lines.append(
                    _kv(
                        "Potential Backends",
                        ", ".join(str(item) for item in potential),
                        indent=0,
                    )
                )
        else:
            lines.append(_kv("Attention Backend", str(latest), indent=0))

    warnings = startup.get("fp8_kernel_warnings") or []
    if warnings:
        lines.append("")
        lines.append("FP8 Kernel Notes:")
        lines.append(_kv("Status", _clean_warning_text(warnings[-1]), indent=2))


def _format_judge_verdict(value: str) -> str:
    return value.replace("_", " ").title()


def _append_observed_runtime(lines: list[str], result: dict[str, Any]) -> None:
    runtime = result.get("observed_runtime")
    if not isinstance(runtime, dict):
        return
    lines.extend(["", _rule("vllm runtime")])
    runtime_log = runtime.get("vllm_log_runtime")
    if isinstance(runtime_log, dict) and runtime_log.get("available"):
        aggregate = runtime_log.get("aggregate", {})
        if isinstance(aggregate, dict):
            lines.append("Generation Throughput:")
            generation_mean = float(
                aggregate.get("generation_throughput_tokens_per_second_mean", 0.0)
            )
            generation_max = float(
                aggregate.get("generation_throughput_tokens_per_second_max", 0.0)
            )
            lines.append(_kv("Mean Active Sample", f"{generation_mean:.2f} tok/s", indent=2))
            lines.append(_kv("Peak Active Sample", f"{generation_max:.2f} tok/s", indent=2))
            if aggregate.get("generation_throughput_tokens_per_second_min") is not None:
                generation_min = float(
                    aggregate.get("generation_throughput_tokens_per_second_min", 0.0)
                )
                lines.append(_kv("Lowest Active Sample", f"{generation_min:.2f} tok/s", indent=2))
            lines.append("")
            lines.append("Prompt Throughput:")
            prompt_mean = float(aggregate.get("prompt_throughput_tokens_per_second_mean", 0.0))
            prompt_max = float(aggregate.get("prompt_throughput_tokens_per_second_max", 0.0))
            lines.append(_kv("Mean Active Sample", f"{prompt_mean:.2f} tok/s", indent=2))
            lines.append(_kv("Peak Active Sample", f"{prompt_max:.2f} tok/s", indent=2))
            if aggregate.get("prompt_throughput_tokens_per_second_min") is not None:
                prompt_min = float(aggregate.get("prompt_throughput_tokens_per_second_min", 0.0))
                lines.append(_kv("Lowest Active Sample", f"{prompt_min:.2f} tok/s", indent=2))
            lines.append("")
            lines.append("Scheduler / Cache:")
            lines.append(
                _kv(
                    "Peak Running Requests",
                    str(aggregate.get("running_requests_max", 0)),
                    indent=2,
                )
            )
            lines.append(
                _kv(
                    "Peak Waiting Requests",
                    str(aggregate.get("waiting_requests_max", 0)),
                    indent=2,
                )
            )
            lines.append(
                _kv(
                    "Max GPU KV Cache Usage",
                    _format_percent(aggregate.get("gpu_kv_cache_usage_percent_max", 0.0)),
                    indent=2,
                )
            )
            if aggregate.get("prefix_cache_hit_rate_percent_max") is not None:
                lines.append(
                    _kv(
                        "Peak Prefix Cache Hit Rate",
                        _format_percent(aggregate.get("prefix_cache_hit_rate_percent_max", 0.0)),
                        indent=2,
                    )
                )
        sample_count = runtime_log.get("sample_count")
        active_count = runtime_log.get("active_sample_count")
        if sample_count is not None:
            lines.append("")
            lines.append(
                _kv(
                    "Runtime Sampling Window",
                    f"{active_count} active samples out of {sample_count} total log samples",
                    indent=0,
                )
            )
            if int(active_count or 0) <= 1:
                lines.append(
                    _kv(
                        "Note",
                        (
                            "Only one active runtime sample was seen, so mean / peak / "
                            "lowest throughput will match."
                        ),
                        indent=0,
                    )
                )
    metrics_gauges = runtime.get("vllm_metrics_serving_gauges")
    if isinstance(metrics_gauges, dict) and metrics_gauges.get("available"):
        lines.append("")
        lines.append("vLLM Prometheus Gauge Samples (Serving Phase):")
        lines.append(
            _kv(
                "Sampling Window",
                (
                    f"{metrics_gauges.get('active_sample_count', 0)} active samples out of "
                    f"{metrics_gauges.get('sample_count', 0)} total scrapes"
                ),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "Peak Requests Running",
                str(metrics_gauges.get("requests_running_max", 0)),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "Peak Requests Waiting",
                str(metrics_gauges.get("requests_waiting_max", 0)),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "Peak KV Cache Usage",
                _format_percent(metrics_gauges.get("kv_cache_usage_percent_max", 0.0)),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "Mean KV Cache Usage",
                _format_percent(metrics_gauges.get("kv_cache_usage_percent_mean", 0.0)),
                indent=2,
            )
        )
        if metrics_gauges.get("kv_cache_usage_metric_unreliable"):
            lines.append(
                _kv(
                    "KV Cache Gauge Check",
                    (
                        "stayed at 0% during active scrapes; this Prometheus gauge "
                        "does not appear trustworthy in this build"
                    ),
                    indent=2,
                )
            )
    metrics_delta = runtime.get("vllm_metrics_serving_delta")
    if isinstance(metrics_delta, dict) and metrics_delta.get("available"):
        lines.append("")
        lines.append("vLLM Prometheus Metrics (Serving Phase):")
        lines.append(
            _kv(
                "Requests Completed",
                str(metrics_delta.get("requests", 0)),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "Prompt Tokens",
                str(metrics_delta.get("prompt_tokens", 0)),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "Generation Tokens",
                str(metrics_delta.get("generation_tokens", 0)),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "Prefix Cache Queries",
                str(metrics_delta.get("prefix_cache_queries", 0)),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "Prefix Cache Hits",
                str(metrics_delta.get("prefix_cache_hits", 0)),
                indent=2,
            )
        )
        lines.append(
            _kv(
                "Prompt Tokens Cached",
                str(metrics_delta.get("prompt_tokens_cached", 0)),
                indent=2,
            )
        )
        for key, label in (
            ("mean_time_to_first_token_seconds", "Mean Time To First Token"),
            ("mean_end_to_end_latency_seconds", "Mean End-To-End Latency"),
            ("mean_queue_time_seconds", "Mean Queue Time"),
            ("mean_inference_time_seconds", "Mean Inference Time"),
            ("mean_prefill_time_seconds", "Mean Prefill Time"),
            ("mean_decode_time_seconds", "Mean Decode Time"),
            (
                "mean_request_time_per_output_token_seconds",
                "Mean Request Time Per Output Token",
            ),
            ("mean_inter_token_latency_seconds", "Mean Inter-Token Latency"),
        ):
            value = metrics_delta.get(key)
            if value is not None:
                lines.append(_kv(label, _format_seconds(value), indent=2))
        for key, label in (
            ("mean_prompt_tokens_per_request", "Mean Prompt Tokens / Request"),
            ("mean_output_tokens_per_request", "Mean Output Tokens / Request"),
        ):
            value = metrics_delta.get(key)
            if value is not None:
                lines.append(_kv(label, f"{float(value):.2f}", indent=2))
        success_parts = []
        for key, label in (
            ("success_stop", "stop"),
            ("success_length", "length"),
            ("success_error", "error"),
            ("success_abort", "abort"),
            ("success_repetition", "repetition"),
        ):
            value = int(metrics_delta.get(key, 0) or 0)
            if value:
                success_parts.append(f"{label}={value}")
        if success_parts:
            lines.append(_kv("Finish Reasons", ", ".join(success_parts), indent=2))


def _append_launch_observation(lines: list[str], result: dict[str, Any]) -> None:
    run = result.get("run")
    if not isinstance(run, dict):
        return
    launch = run.get("launch_observation")
    if not isinstance(launch, dict):
        return
    lines.extend(["", _rule("launch observation")])
    lines.append(_kv("Target Mode", str(run.get("target_mode", "unknown")), indent=0))
    ready_seconds = launch.get("ready_after_seconds")
    if ready_seconds is not None:
        lines.append(_kv("Launch To Ready", _format_seconds(ready_seconds), indent=0))
    kept_running = launch.get("kept_running")
    if kept_running is not None:
        lines.append(_kv("Kept Running After Bench", "yes" if kept_running else "no", indent=0))


def _append_request_accounting(lines: list[str], result: dict[str, Any]) -> None:
    accounting = result.get("request_accounting")
    if not isinstance(accounting, dict):
        return
    lines.extend(["", _rule("request accounting")])
    local_serving_requests = accounting.get("local_serving_requests", 0)
    local_serving_cells = accounting.get("local_serving_cells", 0)
    lines.append(
        _kv(
            "Local Serving Requests",
            f"{local_serving_requests} over {local_serving_cells} serving cells",
            indent=0,
        )
    )
    lines.append(
        _kv(
            "Local Quality Requests",
            str(accounting.get("local_quality_requests", 0)),
            indent=0,
        )
    )
    if "local_workspace_requests" in accounting:
        lines.append(
            _kv(
                "Local Workspace Requests",
                str(accounting.get("local_workspace_requests", 0)),
                indent=0,
            )
        )
    if "local_workspace_tool_calls" in accounting:
        lines.append(
            _kv(
                "Local Workspace Tool Calls",
                str(accounting.get("local_workspace_tool_calls", 0)),
                indent=0,
            )
        )
    if "failed_cases" in accounting:
        lines.append(
            _kv(
                "Failed Cases",
                str(accounting.get("failed_cases", 0)),
                indent=0,
            )
        )
    lines.append(
        _kv(
            "External Judge Requests",
            str(accounting.get("external_judge_requests", 0)),
            indent=0,
        )
    )


def render_detailed_report(
    result: dict[str, Any],
    result_path: Path,
    *,
    failures_only: bool = False,
    judge_flagged_only: bool = False,
    case_filter: str | None = None,
    full: bool = False,
) -> str:
    WIDTH = 80
    max_chars = None if full else 1200
    summary = render_summary(result, result_path)
    cases = list(result.get("cases", []))
    by_id = {str(case.get("id")): case for case in cases}

    judge_flags: dict[str, dict[str, Any]] = {}
    audit = result.get("audit")
    if isinstance(audit, dict):
        review = audit.get("judge_review")
        if isinstance(review, list):
            for item in review:
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("case_id", ""))
                if cid and bool(item.get("flag")):
                    judge_flags[cid] = item
    for case in cases:
        cid = str(case.get("id", ""))
        judge = case.get("judge")
        if isinstance(judge, dict) and judge.get("deterministic_score_fit") not in (None, "fair"):
            judge_flags.setdefault(
                cid,
                {
                    "case_id": cid,
                    "flag": True,
                    "note": judge.get("quality_note") or "judge flagged deterministic fit",
                    "quote": "",
                },
            )

    failure_cases = [c for c in cases if (not bool(c.get("passed"))) or c.get("status") == "failed"]
    flagged_cases = [by_id[cid] for cid in judge_flags if cid in by_id and by_id[cid] not in failure_cases]

    if case_filter:
        needle = case_filter.lower()
        failure_cases = [c for c in failure_cases if needle in str(c.get("id", "")).lower()]
        flagged_cases = [c for c in flagged_cases if needle in str(c.get("id", "")).lower()]
    if failures_only:
        flagged_cases = []
    if judge_flagged_only:
        failure_cases = []

    lines = ["", "", summary, "", _rule("FAILURES", width=WIDTH), _kv("count", str(len(failure_cases)), indent=0, width=WIDTH)]

    def _truncate(text: str) -> tuple[str, bool]:
        if max_chars is None or len(text) <= max_chars:
            return text, False
        return text[:max_chars], True

    def _wrap_block(text: str, indent: str = "    ") -> str:
        parts = []
        for para in text.splitlines() or [text]:
            if not para.strip():
                parts.append("")
                continue
            parts.append(textwrap.fill(para, width=WIDTH, initial_indent=indent, subsequent_indent=indent))
        return "\n".join(parts)

    for case in failure_cases:
        cid = str(case.get("id", "?"))
        prompt, prompt_trunc = _truncate(str(case.get("prompt", "")))
        response, resp_trunc = _truncate(str(case.get("response", "")))
        lines.extend(
            [
                "",
                f"[FAIL] {cid} | {case.get('group', '-')} | score {float(case.get('score', 0.0)):.3f}",
                _kv("deterministic failures", ", ".join(case.get("deterministic_failures") or []) or "none", width=WIDTH),
                "  prompt:",
                _wrap_block(prompt),
                "  response:",
                _wrap_block(response),
            ]
        )
        if prompt_trunc or resp_trunc:
            lines.append("  [truncated; use --full]")
        workspace = case.get("workspace")
        if isinstance(workspace, dict):
            changed = ", ".join(workspace.get("changed_files") or []) or "none"
            lines.append(_kv("changed files", changed, indent=2, width=WIDTH))
            failing_checks = [
                f"{entry.get('path', 'workspace')}: {entry.get('check', '')}"
                for entry in (workspace.get("file_checks") or [])
                if str(entry.get("status", "")).lower() != "pass"
            ]
            if failing_checks:
                lines.append(_kv("failing file checks", " | ".join(failing_checks), indent=2, width=WIDTH))

    lines.extend(["", _rule("JUDGE-FLAGGED", width=WIDTH), _kv("count", str(len(flagged_cases)), indent=0, width=WIDTH)])
    for case in flagged_cases:
        cid = str(case.get("id", "?"))
        flag = judge_flags.get(cid, {})
        prompt, prompt_trunc = _truncate(str(case.get("prompt", "")))
        response, resp_trunc = _truncate(str(case.get("response", "")))
        lines.extend(
            [
                "",
                f"[FLAG] {cid} | {case.get('group', '-')} | score {float(case.get('score', 0.0)):.3f}",
                _kv("judge flag", str(flag.get("note") or "flagged"), width=WIDTH),
                _kv("quote", str(flag.get("quote") or ""), indent=2, width=WIDTH),
                "  prompt:",
                _wrap_block(prompt),
                "  response:",
                _wrap_block(response),
            ]
        )
        if prompt_trunc or resp_trunc:
            lines.append("  [truncated; use --full]")

    if not failure_cases and not flagged_cases:
        lines.extend(["", _kv("result", "no cases matched the current filters", indent=0, width=WIDTH)])
    return "\n".join(lines).rstrip()
