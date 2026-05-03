from __future__ import annotations

import ast
import json
import re
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

from agentmux import __version__
from agentmux.bench_cases import PROFILE_NAME, PROFILE_VERSION, QUALITY_CASES, SERVING_PROMPTS
from agentmux.bench_judge import load_judge_client
from agentmux.bench_report import render_summary, write_result
from agentmux.bench_score import build_reliability_summary, evaluate_case, verdict_summary
from agentmux.config import ServiceSpec, resolve_stack
from agentmux.runner import build_stack_plan
from agentmux.runtime import read_active

REQUEST_TIMEOUT_SECONDS = 60
SERVING_CONCURRENCY_LEVELS = (1, 2, 4)
_METRIC_LINE_PATTERN = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?P<labels>\{[^}]*\})?\s+(?P<value>[-+0-9.eE]+)$"
)
_LOGGER_PATTERN = re.compile(
    r"Avg prompt throughput: (?P<prompt>[0-9.]+) tokens/s, "
    r"Avg generation throughput: (?P<generation>[0-9.]+) tokens/s, "
    r"Running: (?P<running>\d+) reqs, Waiting: (?P<waiting>\d+) reqs, "
    r"GPU KV cache usage: (?P<kv>[0-9.]+)%, Prefix cache hit rate: (?P<prefix>[0-9.]+)%"
)


@dataclass(frozen=True)
class RequestMetrics:
    client_observed_request_wall_time_seconds: float
    client_observed_time_to_first_stream_event_seconds: float
    output_tokens: int
    client_observed_output_tokens_per_second: float
    response_text: str
    stream_fields_seen: tuple[str, ...]


class BenchmarkError(RuntimeError):
    pass


class _PrometheusSampler:
    def __init__(self, base_url: str, interval_seconds: float = 0.5) -> None:
        self.base_url = base_url
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.snapshots: list[dict[str, Any]] = []

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 1.0)
        return _summarize_metrics_gauges(self.snapshots)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.snapshots.append(_capture_metrics_snapshot(self.base_url))
            self._stop.wait(self.interval_seconds)


def run_benchmark(
    stack_name: str,
    root: Path,
    *,
    target_mode: str = "already_running",
    launch_observation: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path, str]:
    stack = resolve_stack(stack_name, root=root)
    service = stack.services[stack.primary_service]
    model_name = service.served_model_name or service.model
    if model_name is None:
        raise BenchmarkError(f"Primary service {service.name} has no model configured")
    base_url = _service_base_url(service)
    _ensure_reachable(base_url)

    judge_client = load_judge_client()
    started_at = time.time()
    runtime_log_path = _runtime_log_path(stack.name, stack.primary_service)
    declared_config = _capture_declared_config(stack_name, root, service)
    metrics_before_serving = _capture_metrics_snapshot(base_url)
    sampler = _PrometheusSampler(base_url)
    sampler.start()
    try:
        serving = _run_serving_benchmark(base_url, model_name)
    finally:
        metrics_during_serving = sampler.stop()
    metrics_after_serving = _capture_metrics_snapshot(base_url)
    vram = _capture_vram_stats()
    case_results = _run_quality_benchmark(base_url, model_name, judge_client)
    metrics_after_quality = _capture_metrics_snapshot(base_url)
    reliability = build_reliability_summary(case_results)
    observed_startup = _parse_startup_log(runtime_log_path)
    observed_runtime = _capture_observed_runtime(
        base_url,
        runtime_log_path,
        metrics_before_serving=metrics_before_serving,
        metrics_after_serving=metrics_after_serving,
        metrics_after_quality=metrics_after_quality,
        metrics_during_serving=metrics_during_serving,
    )
    _merge_observed_runtime_into_serving(serving, observed_runtime)
    verdict = verdict_summary(case_results, serving)
    quality_summary = {
        "score": verdict.quality_score,
        "total_cases": len(case_results),
        "passed_cases": sum(1 for item in case_results if item["passed"]),
    }
    result = {
        "benchmark_version": PROFILE_VERSION,
        "profile": PROFILE_NAME,
        "stack": {
            "name": stack.name,
            "path": str(stack.path),
            "track": stack.track,
            "primary_service": stack.primary_service,
        },
        "run": {
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at)),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "target_mode": target_mode,
            "base_url": base_url,
            "model": model_name,
            "launch_observation": launch_observation,
        },
        "environment": {
            "python": sys.executable,
            "agentmux_version": __version__,
        },
        "judge": {
            "enabled": judge_client.enabled,
            "provider": judge_client.provider,
            "model": judge_client.model,
            "auth_source": judge_client.auth_source,
            "reason": judge_client.reason,
        },
        "declared_config": declared_config,
        "observed_startup": observed_startup,
        "observed_runtime": observed_runtime,
        "summary": {
            "overall_score": verdict.overall_score,
            "serving_score": verdict.serving_score,
            "quality_score": verdict.quality_score,
            "reliability_score": verdict.reliability_score,
            "verdict": verdict.verdict,
            "blocking_weaknesses": verdict.blocking_weaknesses,
            "categories": {
                "serving": serving,
                "vram": vram,
                "quality_no_tools": quality_summary,
                "reliability": asdict(reliability),
            },
        },
        "cases": case_results,
        "request_accounting": {
            "local_serving_requests": serving["aggregate"]["request_counts"]["serving_requests"],
            "local_serving_cells": serving["aggregate"]["request_counts"]["serving_cells"],
            "local_quality_requests": len(case_results),
            "external_judge_requests": sum(
                1 for item in case_results if isinstance(item.get("judge"), dict)
            ),
        },
    }
    result_path = write_result(result)
    summary_text = render_summary(result, result_path)
    return result, result_path, summary_text


def _ensure_reachable(base_url: str) -> None:
    response = requests.get(f"{base_url}/models", timeout=10)
    response.raise_for_status()


def _capture_declared_config(
    stack_name: str,
    root: Path,
    service: ServiceSpec,
) -> dict[str, Any]:
    command: list[str] | None = None
    rendered_env: dict[str, str] | None = None
    try:
        plan = build_stack_plan(stack_name, root=root)
        launch = next(item for item in plan.services if item.service == plan.stack.primary_service)
        command = launch.command
        rendered_env = launch.env
    except Exception:
        pass

    return {
        "source": "manifest_and_rendered_command",
        "engine": service.engine,
        "runtime_bin_dir": service.runtime_bin_dir,
        "model": service.model,
        "served_model_name": service.served_model_name,
        "host": service.host,
        "port": service.port,
        "args": dict(service.args or {}),
        "extra_args": list(service.extra_args or []),
        "env": dict(service.env or {}),
        "assets": dict(service.assets.values if service.assets is not None else {}),
        "rendered_command": command,
        "rendered_command_shell": subprocess.list2cmdline(command) if command else None,
        "rendered_env": rendered_env,
    }


def _runtime_log_path(stack_name: str, primary_service: str) -> str | None:
    active = read_active(prune_stale=False)
    if active is None or active.stack != stack_name:
        return None
    for service in active.services:
        if service.name == primary_service:
            return service.log_path
    return None


def _run_serving_benchmark(base_url: str, model_name: str) -> dict[str, Any]:
    prompt_results: list[dict[str, Any]] = []
    summary_by_concurrency: dict[str, dict[str, float]] = {}
    all_metrics: list[RequestMetrics] = []
    first_request_metric: RequestMetrics | None = None
    for concurrency in SERVING_CONCURRENCY_LEVELS:
        metrics: list[RequestMetrics] = []
        for prompt in SERVING_PROMPTS:
            prompt_metrics = _run_concurrent_streams(
                base_url=base_url,
                model_name=model_name,
                prompt=prompt.prompt,
                temperature=prompt.temperature,
                max_tokens=prompt.max_tokens,
                concurrency=concurrency,
            )
            if first_request_metric is None and prompt_metrics:
                first_request_metric = prompt_metrics[0]
            metrics.extend(prompt_metrics)
            all_metrics.extend(prompt_metrics)
            prompt_results.append(
                {
                    "prompt_id": prompt.id,
                    "concurrency": concurrency,
                    "source": "client_observed",
                    "avg_request_wall_time_seconds": round(
                        statistics.mean(
                            item.client_observed_request_wall_time_seconds
                            for item in prompt_metrics
                        ),
                        4,
                    ),
                    "avg_time_to_first_stream_event_seconds": round(
                        statistics.mean(
                            item.client_observed_time_to_first_stream_event_seconds
                            for item in prompt_metrics
                        ),
                        4,
                    ),
                    "avg_output_tokens_per_second": round(
                        statistics.mean(
                            item.client_observed_output_tokens_per_second for item in prompt_metrics
                        ),
                        4,
                    ),
                    "stream_field_counts": _stream_field_counts(prompt_metrics),
                }
            )
        avg_first = statistics.mean(
            item.client_observed_time_to_first_stream_event_seconds for item in metrics
        )
        avg_wall = statistics.mean(
            item.client_observed_request_wall_time_seconds for item in metrics
        )
        avg_tps = statistics.mean(item.client_observed_output_tokens_per_second for item in metrics)
        summary_by_concurrency[str(concurrency)] = {
            "source": "client_observed",
            "avg_request_wall_time_seconds": round(avg_wall, 4),
            "avg_time_to_first_stream_event_seconds": round(avg_first, 4),
            "avg_output_tokens_per_second": round(avg_tps, 4),
        }
    efficiency = 0.0
    one_tps = summary_by_concurrency["1"]["avg_output_tokens_per_second"]
    four_tps = summary_by_concurrency["4"]["avg_output_tokens_per_second"]
    if one_tps > 0:
        efficiency = min(1.0, max(0.0, four_tps / one_tps))
    all_first = [
        entry["avg_time_to_first_stream_event_seconds"] for entry in summary_by_concurrency.values()
    ]
    all_tps = [entry["avg_output_tokens_per_second"] for entry in summary_by_concurrency.values()]
    remaining_metrics = all_metrics[1:] if len(all_metrics) > 1 else []
    aggregate = {
        "source": "client_observed",
        "client_observed_avg_time_to_first_stream_event_seconds": round(
            statistics.mean(all_first), 4
        ),
        "client_observed_avg_request_wall_time_seconds": round(
            statistics.mean(
                item.client_observed_request_wall_time_seconds for item in all_metrics
            ),
            4,
        ),
        "client_observed_avg_output_tokens_per_second": round(statistics.mean(all_tps), 4),
        "client_observed_concurrency_4_efficiency": round(efficiency, 4),
        "request_counts": {
            "serving_requests": len(all_metrics),
            "serving_cells": len(prompt_results),
        },
    }
    if first_request_metric is not None:
        aggregate["first_request"] = {
            "client_observed_request_wall_time_seconds": round(
                first_request_metric.client_observed_request_wall_time_seconds,
                4,
            ),
            "client_observed_time_to_first_stream_event_seconds": round(
                first_request_metric.client_observed_time_to_first_stream_event_seconds,
                4,
            ),
            "client_observed_output_tokens_per_second": round(
                first_request_metric.client_observed_output_tokens_per_second,
                4,
            ),
            "stream_fields_seen": list(first_request_metric.stream_fields_seen),
        }
    if remaining_metrics:
        aggregate["after_first_request"] = {
            "client_observed_avg_request_wall_time_seconds": round(
                statistics.mean(
                    item.client_observed_request_wall_time_seconds
                    for item in remaining_metrics
                ),
                4,
            ),
            "client_observed_avg_time_to_first_stream_event_seconds": round(
                statistics.mean(
                    item.client_observed_time_to_first_stream_event_seconds
                    for item in remaining_metrics
                ),
                4,
            ),
            "client_observed_avg_output_tokens_per_second": round(
                statistics.mean(
                    item.client_observed_output_tokens_per_second for item in remaining_metrics
                ),
                4,
            ),
        }
    return {
        "prompt_results": prompt_results,
        "by_concurrency": summary_by_concurrency,
        "aggregate": aggregate,
    }


def _stream_field_counts(metrics: list[RequestMetrics]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for metric in metrics:
        for field in metric.stream_fields_seen:
            counts[field] = counts.get(field, 0) + 1
    return counts


def _run_concurrent_streams(
    *,
    base_url: str,
    model_name: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    concurrency: int,
) -> list[RequestMetrics]:
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                _stream_request,
                base_url,
                model_name,
                prompt,
                temperature,
                max_tokens,
            )
            for _ in range(concurrency)
        ]
        return [future.result() for future in futures]


def _stream_request(
    base_url: str,
    model_name: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
) -> RequestMetrics:
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    started_at = time.perf_counter()
    first_event_at: float | None = None
    content_parts: list[str] = []
    output_tokens = 0
    stream_fields_seen: set[str] = set()
    with requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        stream=True,
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as response:
        response.raise_for_status()
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            payload_obj = json.loads(data)
            choices = payload_obj.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                for field in ("content", "reasoning"):
                    text = delta.get(field)
                    if isinstance(text, str) and text:
                        if first_event_at is None:
                            first_event_at = time.perf_counter()
                        content_parts.append(text)
                        stream_fields_seen.add(field)
            usage = payload_obj.get("usage")
            if isinstance(usage, dict):
                completion = usage.get("completion_tokens")
                if isinstance(completion, int) and completion > 0:
                    output_tokens = completion
    finished_at = time.perf_counter()
    if first_event_at is None:
        first_event_at = finished_at
    response_text = "".join(content_parts)
    if output_tokens <= 0:
        output_tokens = max(1, len(response_text.split()))
    wall_time = finished_at - started_at
    generate_seconds = max(finished_at - first_event_at, 1e-6)
    return RequestMetrics(
        client_observed_request_wall_time_seconds=wall_time,
        client_observed_time_to_first_stream_event_seconds=first_event_at - started_at,
        output_tokens=output_tokens,
        client_observed_output_tokens_per_second=output_tokens / generate_seconds,
        response_text=response_text,
        stream_fields_seen=tuple(sorted(stream_fields_seen)),
    )


def _run_quality_benchmark(base_url: str, model_name: str, judge_client) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    judge_cases: list[dict[str, Any]] = []

    class _DisabledJudge:
        enabled = False

        def evaluate(self, prompt, response, case_id, deterministic_context=None):
            return None

    disabled_judge = _DisabledJudge()
    for case in QUALITY_CASES:
        response_text = _chat_completion(base_url, model_name, case.prompt, max_tokens=220)
        evaluation = evaluate_case(case, response_text, disabled_judge)
        result = {
            "id": case.id,
            "group": case.group,
            "judge_eligible": case.judge_eligible,
            "default_judge_enabled": case.default_judge_enabled,
            "prompt": case.prompt,
            "response": response_text,
            "score": evaluation.score,
            "passed": evaluation.passed,
            "deterministic_failures": evaluation.deterministic_failures,
            "rubric_passes": evaluation.rubric_passes,
            "rubric_failures": evaluation.rubric_failures,
            "reliability_flags": evaluation.reliability_flags,
            "judge": None,
        }
        results.append(result)
        if case.default_judge_enabled:
            judge_cases.append(
                {
                    "case_id": case.id,
                    "prompt": case.prompt,
                    "response": response_text,
                    "deterministic_context": {
                        "score": evaluation.score,
                        "deterministic_failures": evaluation.deterministic_failures,
                        "rubric_passes": evaluation.rubric_passes,
                        "rubric_failures": evaluation.rubric_failures,
                        "reliability_flags": evaluation.reliability_flags,
                    },
                }
            )
    judge_results = judge_client.evaluate_many(judge_cases)
    judge_context_by_case = {
        item["case_id"]: item["deterministic_context"] for item in judge_cases
    }
    for result in results:
        judge_result = judge_results.get(result["id"])
        if judge_result is None:
            continue
        result["judge"] = {
            "deterministic_context": judge_context_by_case[result["id"]],
            "deterministic_score_fit": judge_result.deterministic_score_fit,
            "deterministic_notes": judge_result.deterministic_notes,
            "quality_note": judge_result.quality_note,
        }
    return results


def _chat_completion(base_url: str, model_name: str, prompt: str, max_tokens: int) -> str:
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    response = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    return str(data["choices"][0]["message"]["content"])


def _service_base_url(service: ServiceSpec) -> str:
    host = "127.0.0.1" if service.host == "0.0.0.0" else service.host
    return f"http://{host}:{service.port}/v1"


def _capture_vram_stats() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.used,memory.free,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"available": False, "reason": "nvidia_smi_unavailable"}
    rows: list[dict[str, int]] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            index, used, free, total = (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
        except ValueError:
            continue
        rows.append({"index": index, "used": used, "free": free, "total": total})
    if not rows:
        return {"available": False, "reason": "no_gpu_rows"}
    selected = max(rows, key=lambda item: item["used"])
    percent_used = (selected["used"] / selected["total"] * 100.0) if selected["total"] else 0.0
    return {
        "available": True,
        "gpu_index": selected["index"],
        "used_mib": selected["used"],
        "free_mib": selected["free"],
        "total_mib": selected["total"],
        "percent_used": round(percent_used, 2),
        "source": "nvidia-smi",
    }


def _parse_startup_log(log_path: str | None) -> dict[str, Any]:
    if not log_path:
        return {"available": False, "reason": "runtime_log_unavailable"}
    path = Path(log_path)
    if not path.exists():
        return {"available": False, "reason": "runtime_log_missing", "log_path": log_path}

    summary: dict[str, Any] = {
        "available": True,
        "source": "vllm_log",
        "log_path": str(path),
        "warnings": [],
        "fp8_kernel_warnings": [],
    }
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if "version" in line and "model" in line and "vllm" not in summary:
            version_match = re.search(r"version\s+([0-9.]+)", line)
            model_match = re.search(r"model\s+(.+)$", line)
            if version_match:
                summary["vllm_version"] = version_match.group(1)
            if model_match:
                summary["model_path"] = model_match.group(1).strip()
        if "non-default args:" in line:
            payload = line.split("non-default args:", 1)[1].strip()
            try:
                summary["non_default_args"] = ast.literal_eval(payload)
            except (SyntaxError, ValueError):
                summary["non_default_args_raw"] = payload
        if "Initializing a V1 LLM engine" in line:
            summary["engine_init_line"] = line
            for source_key, target_key in (
                ("dtype", "resolved_dtype"),
                ("kv_cache_dtype", "resolved_kv_cache_dtype"),
                ("quantization", "resolved_quantization"),
                ("max_seq_len", "resolved_max_seq_len"),
                ("enable_chunked_prefill", "resolved_enable_chunked_prefill"),
            ):
                value = _extract_engine_config_value(line, source_key)
                if value is not None:
                    summary[target_key] = value
        if "Resolved architecture:" in line:
            summary["resolved_architecture"] = line.rsplit(":", 1)[1].strip()
        if "Asynchronous scheduling is enabled." in line:
            summary["asynchronous_scheduling"] = True
        if "Selected TritonFp8BlockScaledMMKernel" in line:
            summary["fp8_weight_kernel"] = line
        if "Using FLASH" in line and "attention backend" in line:
            parsed_backend = _parse_attention_backend(line)
            if parsed_backend is not None:
                summary.setdefault("attention_backends", []).append(parsed_backend)
            else:
                summary.setdefault("attention_backends", []).append({"raw": line})
        if "Loading weights took" in line:
            match = re.search(r"Loading weights took ([0-9.]+) seconds", line)
            if match:
                summary["weights_load_seconds"] = float(match.group(1))
        if "Model loading took" in line:
            match = re.search(
                r"Model loading took ([0-9.]+) GiB memory and ([0-9.]+) seconds",
                line,
            )
            if match:
                summary["model_load_gpu_memory_gib"] = float(match.group(1))
                summary["model_load_seconds"] = float(match.group(2))
        if "torch.compile took" in line and "s in total" in line:
            match = re.search(r"torch\.compile took ([0-9.]+) s in total", line)
            if match:
                summary["torch_compile_seconds"] = float(match.group(1))
        if "Directly load the compiled graph" in line:
            summary["compile_cache_hit"] = True
        if "Compiling a graph for compile range" in line:
            summary["compile_cache_hit"] = False
        if "Estimated CUDA graph memory:" in line:
            match = re.search(r"Estimated CUDA graph memory: ([0-9.]+) GiB total", line)
            if match:
                summary["estimated_cuda_graph_memory_gib"] = float(match.group(1))
        if "CUDA graph pool memory:" in line:
            match = re.search(
                r"CUDA graph pool memory: ([0-9.]+) GiB \(actual\), ([0-9.]+) GiB \(estimated\)",
                line,
            )
            if match:
                summary["cuda_graph_pool_memory_gib_actual"] = float(match.group(1))
                summary["cuda_graph_pool_memory_gib_estimated"] = float(match.group(2))
        if "Available KV cache memory:" in line:
            match = re.search(r"Available KV cache memory: ([0-9.]+) GiB", line)
            if match:
                summary["available_kv_cache_memory_gib"] = float(match.group(1))
        if "GPU KV cache size:" in line:
            match = re.search(r"GPU KV cache size: ([0-9,]+) tokens", line)
            if match:
                summary["gpu_kv_cache_tokens"] = int(match.group(1).replace(",", ""))
        if "Maximum concurrency for" in line:
            match = re.search(
                r"Maximum concurrency for ([0-9,]+) tokens per request: ([0-9.]+)x", line
            )
            if match:
                summary["max_concurrency_tokens_per_request"] = int(match.group(1).replace(",", ""))
                summary["max_concurrency_estimate"] = float(match.group(2))
        if "Multi-modal warmup completed in" in line:
            match = re.search(r"Multi-modal warmup completed in ([0-9.]+)s", line)
            if match:
                summary["multimodal_warmup_seconds"] = float(match.group(1))
        if "Readonly multi-modal warmup completed in" in line:
            match = re.search(r"Readonly multi-modal warmup completed in ([0-9.]+)s", line)
            if match:
                summary["readonly_multimodal_warmup_seconds"] = float(match.group(1))
        if "init engine (profile, create kv cache, warmup model) took" in line:
            match = re.search(
                r"init engine \(profile, create kv cache, warmup model\) took "
                r"([0-9.]+) s \(compilation: ([0-9.]+) s\)",
                line,
            )
            if match:
                summary["engine_init_seconds"] = float(match.group(1))
                summary.setdefault("torch_compile_seconds", float(match.group(2)))
        if "Using default W8A8 Block FP8 kernel config" in line:
            summary["fp8_kernel_warnings"].append(line)
        if "WARNING" in line:
            summary["warnings"].append(line)

    return summary


def _extract_engine_config_value(line: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}=([^,]+)", line)
    if not match:
        return None
    return match.group(1).strip()


def _capture_observed_runtime(
    base_url: str,
    log_path: str | None,
    *,
    metrics_before_serving: dict[str, Any] | None = None,
    metrics_after_serving: dict[str, Any] | None = None,
    metrics_after_quality: dict[str, Any] | None = None,
    metrics_during_serving: dict[str, Any] | None = None,
) -> dict[str, Any]:
    after_serving = metrics_after_serving or _capture_metrics_snapshot(base_url)
    before_serving = metrics_before_serving or _capture_metrics_snapshot(base_url)
    after_quality = metrics_after_quality or after_serving
    return {
        "vllm_log_runtime": _parse_runtime_logger_lines(log_path),
        "vllm_metrics": after_serving,
        "vllm_metrics_serving_delta": _summarize_metrics_delta(
            before_serving,
            after_serving,
            phase="serving",
        ),
        "vllm_metrics_serving_gauges": metrics_during_serving
        or {"available": False, "reason": "no_serving_samples"},
        "vllm_metrics_quality_delta": _summarize_metrics_delta(
            after_serving,
            after_quality,
            phase="quality",
        ),
    }


def _parse_attention_backend(line: str) -> dict[str, Any] | None:
    chosen_match = re.search(r"Using\s+([A-Z_]+) attention backend", line)
    if not chosen_match:
        return None
    result: dict[str, Any] = {"chosen": chosen_match.group(1), "raw": line}
    potentials_match = re.search(r"potential backends:\s*(\[.*\])", line)
    if potentials_match:
        try:
            result["potential"] = ast.literal_eval(potentials_match.group(1))
        except (SyntaxError, ValueError):
            result["potential_raw"] = potentials_match.group(1)
    return result


def _merge_observed_runtime_into_serving(
    serving: dict[str, Any], observed_runtime: dict[str, Any]
) -> None:
    aggregate = serving.setdefault("aggregate", {})
    runtime_log = observed_runtime.get("vllm_log_runtime", {})
    if not isinstance(runtime_log, dict) or not runtime_log.get("available"):
        return
    runtime_aggregate = runtime_log.get("aggregate", {})
    if not isinstance(runtime_aggregate, dict):
        return
    for source_key, target_key in (
        (
            "generation_throughput_tokens_per_second_mean",
            "vllm_generation_throughput_tokens_per_second_mean",
        ),
        (
            "generation_throughput_tokens_per_second_max",
            "vllm_generation_throughput_tokens_per_second_max",
        ),
        (
            "prompt_throughput_tokens_per_second_mean",
            "vllm_prompt_throughput_tokens_per_second_mean",
        ),
        (
            "prompt_throughput_tokens_per_second_max",
            "vllm_prompt_throughput_tokens_per_second_max",
        ),
    ):
        value = runtime_aggregate.get(source_key)
        if isinstance(value, (int, float)):
            aggregate[target_key] = float(value)


def _parse_runtime_logger_lines(log_path: str | None) -> dict[str, Any]:
    if not log_path:
        return {"available": False, "reason": "runtime_log_unavailable"}
    path = Path(log_path)
    if not path.exists():
        return {"available": False, "reason": "runtime_log_missing", "log_path": log_path}

    samples: list[dict[str, float | int]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _LOGGER_PATTERN.search(raw_line)
        if not match:
            continue
        samples.append(
            {
                "prompt_throughput_tokens_per_second": float(match.group("prompt")),
                "generation_throughput_tokens_per_second": float(match.group("generation")),
                "running_requests": int(match.group("running")),
                "waiting_requests": int(match.group("waiting")),
                "gpu_kv_cache_usage_percent": float(match.group("kv")),
                "prefix_cache_hit_rate_percent": float(match.group("prefix")),
            }
        )
    if not samples:
        return {"available": False, "reason": "no_runtime_samples", "log_path": log_path}

    active = [
        sample
        for sample in samples
        if sample["running_requests"] > 0 or sample["waiting_requests"] > 0
    ]
    basis = active or samples
    return {
        "available": True,
        "source": "vllm_log",
        "log_path": log_path,
        "sample_count": len(samples),
        "active_sample_count": len(active),
        "samples": samples[-10:],
        "aggregate": {
            "prompt_throughput_tokens_per_second_mean": round(
                statistics.mean(
                    sample["prompt_throughput_tokens_per_second"] for sample in basis
                ),
                3,
            ),
            "generation_throughput_tokens_per_second_mean": round(
                statistics.mean(
                    sample["generation_throughput_tokens_per_second"] for sample in basis
                ),
                3,
            ),
            "prompt_throughput_tokens_per_second_max": round(
                max(sample["prompt_throughput_tokens_per_second"] for sample in basis), 3
            ),
            "generation_throughput_tokens_per_second_max": round(
                max(sample["generation_throughput_tokens_per_second"] for sample in basis), 3
            ),
            "prompt_throughput_tokens_per_second_min": round(
                min(sample["prompt_throughput_tokens_per_second"] for sample in basis), 3
            ),
            "generation_throughput_tokens_per_second_min": round(
                min(sample["generation_throughput_tokens_per_second"] for sample in basis), 3
            ),
            "gpu_kv_cache_usage_percent_max": round(
                max(sample["gpu_kv_cache_usage_percent"] for sample in basis), 3
            ),
            "prefix_cache_hit_rate_percent_max": round(
                max(sample["prefix_cache_hit_rate_percent"] for sample in basis), 3
            ),
            "running_requests_max": max(sample["running_requests"] for sample in basis),
            "waiting_requests_max": max(sample["waiting_requests"] for sample in basis),
        },
    }


def _metric_key(entry: dict[str, Any]) -> tuple[str, str | None]:
    return str(entry.get("name", "")), entry.get("labels")


def _metrics_to_map(snapshot: dict[str, Any]) -> dict[tuple[str, str | None], float]:
    entries = snapshot.get("sampled_entries") if isinstance(snapshot, dict) else None
    result: dict[tuple[str, str | None], float] = {}
    if not isinstance(entries, list):
        return result
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        result[_metric_key(entry)] = float(entry.get("value", 0.0))
    return result


def _sum_metric_values(metric_map: dict[tuple[str, str | None], float], prefix: str) -> float:
    total = 0.0
    for (name, _labels), value in metric_map.items():
        if name == prefix:
            total += value
    return total


def _sum_metric_values_with_label(
    metric_map: dict[tuple[str, str | None], float],
    prefix: str,
    label_fragment: str,
) -> float:
    total = 0.0
    for (name, labels), value in metric_map.items():
        if name == prefix and isinstance(labels, str) and label_fragment in labels:
            total += value
    return total


def _summarize_metrics_gauges(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [snapshot for snapshot in snapshots if snapshot.get("available")]
    if not valid:
        return {"available": False, "reason": "no_valid_samples"}
    series: list[dict[str, float]] = []
    for snapshot in valid:
        metric_map = _metrics_to_map(snapshot)
        series.append(
            {
                "requests_running": _sum_metric_values(metric_map, "vllm:num_requests_running"),
                "requests_waiting": _sum_metric_values(metric_map, "vllm:num_requests_waiting"),
                "kv_cache_usage_perc": _sum_metric_values(metric_map, "vllm:kv_cache_usage_perc"),
            }
        )
    active = [
        sample
        for sample in series
        if sample["requests_running"] > 0
        or sample["requests_waiting"] > 0
        or sample["kv_cache_usage_perc"] > 0
    ]
    basis = active or series
    kv_max = round(max(sample["kv_cache_usage_perc"] for sample in basis), 3)
    return {
        "available": True,
        "sample_count": len(series),
        "active_sample_count": len(active),
        "requests_running_max": round(max(sample["requests_running"] for sample in basis), 3),
        "requests_waiting_max": round(max(sample["requests_waiting"] for sample in basis), 3),
        "kv_cache_usage_percent_max": kv_max,
        "kv_cache_usage_percent_mean": round(
            statistics.mean(sample["kv_cache_usage_perc"] for sample in basis),
            3,
        ),
        "kv_cache_usage_metric_unreliable": bool(active and kv_max == 0.0),
    }


def _summarize_metrics_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    if not before.get("available") or not after.get("available"):
        return {"available": False, "reason": "metrics_unavailable", "phase": phase}
    before_map = _metrics_to_map(before)
    after_map = _metrics_to_map(after)

    def delta(name: str, label_fragment: str | None = None) -> float:
        if label_fragment is None:
            return _sum_metric_values(after_map, name) - _sum_metric_values(before_map, name)
        after_value = _sum_metric_values_with_label(after_map, name, label_fragment)
        before_value = _sum_metric_values_with_label(before_map, name, label_fragment)
        return after_value - before_value

    request_count = delta("vllm:request_success_total")
    ttft_count = delta("vllm:time_to_first_token_seconds_count")
    ttft_sum = delta("vllm:time_to_first_token_seconds_sum")
    e2e_count = delta("vllm:e2e_request_latency_seconds_count")
    e2e_sum = delta("vllm:e2e_request_latency_seconds_sum")
    queue_count = delta("vllm:request_queue_time_seconds_count")
    queue_sum = delta("vllm:request_queue_time_seconds_sum")
    inference_count = delta("vllm:request_inference_time_seconds_count")
    inference_sum = delta("vllm:request_inference_time_seconds_sum")
    prefill_count = delta("vllm:request_prefill_time_seconds_count")
    prefill_sum = delta("vllm:request_prefill_time_seconds_sum")
    decode_count = delta("vllm:request_decode_time_seconds_count")
    decode_sum = delta("vllm:request_decode_time_seconds_sum")
    output_token_count = delta("vllm:generation_tokens_total")
    prompt_token_count = delta("vllm:prompt_tokens_total")

    prefix_queries = delta("vllm:prefix_cache_queries_total")
    prefix_hits = delta("vllm:prefix_cache_hits_total")
    prompt_tokens_cached = delta("vllm:prompt_tokens_cached_total")
    result = {
        "available": True,
        "phase": phase,
        "requests": int(round(request_count)),
        "prompt_tokens": int(round(prompt_token_count)),
        "generation_tokens": int(round(output_token_count)),
        "prefix_cache_queries": int(round(prefix_queries)),
        "prefix_cache_hits": int(round(prefix_hits)),
        "prompt_tokens_cached": int(round(prompt_tokens_cached)),
        "success_stop": int(round(delta("vllm:request_success_total", 'finished_reason="stop"'))),
        "success_length": int(
            round(delta("vllm:request_success_total", 'finished_reason="length"'))
        ),
        "success_error": int(round(delta("vllm:request_success_total", 'finished_reason="error"'))),
        "success_abort": int(round(delta("vllm:request_success_total", 'finished_reason="abort"'))),
        "success_repetition": int(
            round(delta("vllm:request_success_total", 'finished_reason="repetition"'))
        ),
        "mean_time_to_first_token_seconds": (
            round(ttft_sum / ttft_count, 6) if ttft_count > 0 else None
        ),
        "mean_end_to_end_latency_seconds": (
            round(e2e_sum / e2e_count, 6) if e2e_count > 0 else None
        ),
        "mean_queue_time_seconds": (
            round(queue_sum / queue_count, 6) if queue_count > 0 else None
        ),
        "mean_inference_time_seconds": (
            round(inference_sum / inference_count, 6) if inference_count > 0 else None
        ),
        "mean_prefill_time_seconds": (
            round(prefill_sum / prefill_count, 6) if prefill_count > 0 else None
        ),
        "mean_decode_time_seconds": (
            round(decode_sum / decode_count, 6) if decode_count > 0 else None
        ),
        "mean_output_tokens_per_request": (
            round(output_token_count / request_count, 6) if request_count > 0 else None
        ),
        "mean_prompt_tokens_per_request": (
            round(prompt_token_count / request_count, 6) if request_count > 0 else None
        ),
    }
    request_time_per_output_token_count = delta("vllm:request_time_per_output_token_seconds_count")
    request_time_per_output_token_sum = delta("vllm:request_time_per_output_token_seconds_sum")
    if request_time_per_output_token_count > 0:
        result["mean_request_time_per_output_token_seconds"] = round(
            request_time_per_output_token_sum / request_time_per_output_token_count,
            6,
        )
    inter_token_latency_count = delta("vllm:inter_token_latency_seconds_count")
    inter_token_latency_sum = delta("vllm:inter_token_latency_seconds_sum")
    if inter_token_latency_count > 0:
        result["mean_inter_token_latency_seconds"] = round(
            inter_token_latency_sum / inter_token_latency_count,
            6,
        )
    return result


def _capture_metrics_snapshot(base_url: str) -> dict[str, Any]:
    metrics_url = base_url[:-3] + "/metrics" if base_url.endswith("/v1") else f"{base_url}/metrics"
    try:
        response = requests.get(metrics_url, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"available": False, "reason": f"metrics_unavailable: {exc.__class__.__name__}"}

    interesting: list[dict[str, Any]] = []
    names: set[str] = set()
    skipped_created = 0
    skipped_histogram = 0
    for raw_line in response.text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _METRIC_LINE_PATTERN.match(line)
        if not match:
            continue
        name = match.group("name")
        if not name.startswith("vllm:"):
            continue
        if name.endswith("_created"):
            skipped_created += 1
            continue
        if name.endswith("_bucket"):
            skipped_histogram += 1
            continue
        names.add(name)
        if len(interesting) < 80:
            interesting.append(
                {
                    "name": name,
                    "labels": match.group("labels"),
                    "value": float(match.group("value")),
                }
            )
    return {
        "available": True,
        "source": "vllm_metrics",
        "metric_names": sorted(names),
        "sampled_entries": interesting,
        "skipped_created_series": skipped_created,
        "skipped_histogram_buckets": skipped_histogram,
    }
