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
from agentmux.bench_cases import (
    PROFILE_NAME,
    PROFILE_VERSION,
    QUALITY_CASES,
    SERVING_PROMPTS,
)
from agentmux.bench_judge import JudgeClient, load_judge_client, run_judge_audit
from agentmux.bench_perf_vllm import run_vllm_endpoint_perf
from agentmux.bench_report import render_summary, write_result
from agentmux.bench_score import build_reliability_summary, evaluate_case, verdict_summary
from agentmux.bench_tokens import TokenCountResult, count_text_tokens
from agentmux.bench_workspace import _assistant_message_parts, run_workspace_benchmark
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


@dataclass(frozen=True)
class ChatCompletionDetails:
    response_text: str
    thinking_text: str
    usage: dict[str, int]
    tool_calls: tuple[dict[str, Any], ...]
    request_error: dict[str, Any] | None = None
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class RequestOutcome:
    ok: bool
    metrics: RequestMetrics | None = None
    error: dict[str, Any] | None = None
    elapsed_seconds: float = 0.0


class BenchmarkError(RuntimeError):
    pass


def _error_payload(
    exc: Exception,
    *,
    phase: str,
    elapsed_seconds: float,
    timeout_seconds: float | None = None,
    request_index: int | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "phase": phase,
        "error_type": exc.__class__.__name__,
        "message": str(exc),
        "elapsed_seconds": round(elapsed_seconds, 4),
    }
    if timeout_seconds is not None:
        payload["timeout_seconds"] = timeout_seconds
    if request_index is not None:
        payload["request_index"] = request_index
    if case_id is not None:
        payload["case_id"] = case_id
    return payload


def _safe_mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


def _tokenizer_resolution(service: ServiceSpec, model_name: str) -> dict[str, Any]:
    assets = service.assets.values if service.assets is not None else {}
    tokenizer_path = assets.get("tokenizer") or service.model or model_name
    source = "service.assets.tokenizer" if assets.get("tokenizer") else "service.model"
    return {
        "path": tokenizer_path,
        "source": source,
        "safe_local_only": True,
    }


def _tool_calls_text(tool_calls: tuple[dict[str, Any], ...]) -> str:
    if not tool_calls:
        return ""
    return json.dumps(tool_calls, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _count_with_metadata(text: str, tokenizer_path: str) -> TokenCountResult:
    return count_text_tokens(text, tokenizer_path)


def _build_token_accounting(
    *,
    response_text: str,
    tool_calls: tuple[dict[str, Any], ...],
    completion_tokens: int,
    tokenizer_path: str,
) -> dict[str, Any]:
    response_count = _count_with_metadata(response_text, tokenizer_path)
    tool_call_text = _tool_calls_text(tool_calls)
    tool_call_count = (
        _count_with_metadata(tool_call_text, tokenizer_path) if tool_call_text else None
    )
    tool_call_tokens = tool_call_count.tokens if tool_call_count is not None else 0
    thinking_tokens = max(0, completion_tokens - response_count.tokens - tool_call_tokens)
    thinking_exact = response_count.loaded and not response_count.fallback_used and not tool_calls
    tool_call_estimated = bool(tool_calls)
    return {
        "response_tokens": response_count.tokens,
        "visible_response_tokens": response_count.tokens,
        "tool_call_tokens": tool_call_tokens,
        "thinking_tokens": thinking_tokens,
        "derived_thinking_tokens": thinking_tokens,
        "thinking_tokens_exact": thinking_exact,
        "thinking_tokens_source": (
            "completion_tokens_minus_visible_response_tokens"
            if not tool_calls
            else "completion_tokens_minus_visible_response_tokens_minus_estimated_tool_call_tokens"
        ),
        "tool_call_tokens_exact": not tool_calls,
        "tool_call_tokens_source": ("none" if not tool_calls else "canonical_tool_calls_json"),
        "tool_call_tokens_estimated": tool_call_estimated,
        "response_tokenizer": {
            "path": response_count.tokenizer_path,
            "loaded": response_count.loaded,
            "fallback_used": response_count.fallback_used,
            "fallback_reason": response_count.fallback_reason,
        },
        "tool_call_tokenizer": (
            None
            if tool_call_count is None
            else {
                "path": tool_call_count.tokenizer_path,
                "loaded": tool_call_count.loaded,
                "fallback_used": tool_call_count.fallback_used,
                "fallback_reason": tool_call_count.fallback_reason,
            }
        ),
    }


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
    judge_audit: bool = False,
    enable_perf: bool = True,
) -> tuple[dict[str, Any], Path, str]:
    stack = resolve_stack(stack_name, root=root)
    service = stack.services[stack.primary_service]
    model_name = service.served_model_name or service.model
    if model_name is None:
        raise BenchmarkError(f"Primary service {service.name} has no model configured")
    tokenizer_resolution = _tokenizer_resolution(service, model_name)
    tokenizer_source = str(tokenizer_resolution["path"])
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
        perf = run_vllm_endpoint_perf(
            stack_name=stack.name,
            base_url=base_url,
            model_name=(service.served_model_name or model_name),
            tokenizer_path=tokenizer_source,
            enabled=enable_perf,
        )
        serving = {
            "aggregate": {
                "request_counts": {
                    "serving_requests": 0,
                    "serving_cells": 0,
                    "failed_requests": 0,
                }
            }
        }
    finally:
        metrics_during_serving = sampler.stop()
    metrics_after_serving = _capture_metrics_snapshot(base_url)
    vram = _capture_vram_stats()
    no_tool_case_results = _run_quality_benchmark(
        base_url,
        model_name,
        judge_client,
        tokenizer_source,
    )
    workspace_case_results, workspace_stats = run_workspace_benchmark(
        base_url,
        model_name,
        tokenizer_source,
    )
    case_results = [*no_tool_case_results, *workspace_case_results]
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
    quality_no_tools_summary = {
        "score": round(
            sum(float(item["score"]) for item in no_tool_case_results)
            / max(1, len(no_tool_case_results)),
            3,
        ),
        "total_cases": len(no_tool_case_results),
        "passed_cases": sum(1 for item in no_tool_case_results if item["passed"]),
        "failed_cases": sum(1 for item in no_tool_case_results if item.get("status") == "failed"),
    }
    quality_with_tools_summary = {
        "score": round(
            sum(float(item["score"]) for item in workspace_case_results)
            / max(1, len(workspace_case_results)),
            3,
        ),
        "total_cases": len(workspace_case_results),
        "passed_cases": sum(1 for item in workspace_case_results if item["passed"]),
        "failed_cases": sum(1 for item in workspace_case_results if item.get("status") == "failed"),
        "total_tool_calls": workspace_stats["tool_calls"],
        "invalid_tool_calls": workspace_stats["invalid_tool_calls"],
        "model_requests": workspace_stats["model_requests"],
    }
    thinking_summary = _build_thinking_summary(case_results)
    case_failures = sum(1 for item in case_results if item.get("status") == "failed")
    serving_failures = int(
        serving.get("aggregate", {}).get("request_counts", {}).get("failed_requests", 0)
    )

    audit_payload: dict[str, Any] | None = None
    if judge_audit and judge_client.enabled:
        audit_cases = [
            {
                "case_id": str(item.get("id", "")),
                "group": str(item.get("group", "")),
                "prompt": str(item.get("prompt", "")),
                "response": str(item.get("response", "")),
                "passed": bool(item.get("passed", False)),
                "deterministic_failures": list(item.get("deterministic_failures") or []),
            }
            for item in case_results
            if item.get("group") != "quality_with_tools" and item.get("kind") != "workspace"
        ]
        try:
            review = run_judge_audit(audit_cases, judge_client.model)
        except Exception:
            review = []
        audit_payload = {
            "judge_prompt_version": "audit-v1",
            "judge_review": review,
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
            "status": "partial" if (case_failures or serving_failures) else "completed",
            "failed_cases": case_failures,
            "failed_requests": serving_failures,
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
        "tokenizer": tokenizer_resolution,
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
                "quality_no_tools": quality_no_tools_summary,
                "quality_with_tools": quality_with_tools_summary,
                "thinking": thinking_summary,
                "reliability": asdict(reliability),
            },
        },
        "perf": perf,
        "cases": case_results,
        "audit": audit_payload,
        "request_accounting": {
            "local_serving_requests": serving["aggregate"]["request_counts"]["serving_requests"],
            "local_serving_cells": serving["aggregate"]["request_counts"]["serving_cells"],
            "local_quality_requests": len(no_tool_case_results),
            "local_workspace_requests": workspace_stats["model_requests"],
            "local_workspace_tool_calls": workspace_stats["tool_calls"],
            "failed_cases": case_failures,
            "failed_requests": serving_failures,
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


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 4)
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 4)


def _run_stream_batch(
    *,
    base_url: str,
    model_name: str,
    prompt: str,
    max_tokens: int,
    total_requests: int,
    concurrency: int,
) -> list[RequestOutcome]:
    outcomes: list[RequestOutcome] = []
    remaining = total_requests
    while remaining > 0:
        wave = min(concurrency, remaining)
        outcomes.extend(
            _run_concurrent_streams(
                base_url=base_url,
                model_name=model_name,
                prompt=prompt,
                temperature=0.0,
                max_tokens=max_tokens,
                concurrency=wave,
            )
        )
        remaining -= wave
    return outcomes


def _run_serving_benchmark(
    base_url: str,
    model_name: str,
    tokenizer_source: str,
) -> dict[str, Any]:
    lane_a_prompt = SERVING_PROMPTS[0].prompt
    lane_b_prompt = SERVING_PROMPTS[1].prompt

    lane_a_outcomes = _run_stream_batch(
        base_url=base_url,
        model_name=model_name,
        prompt=lane_a_prompt,
        max_tokens=512,
        total_requests=12,
        concurrency=1,
    )
    lane_a_successes = [o.metrics for o in lane_a_outcomes if o.ok and o.metrics]
    lane_a_failures = [o.error for o in lane_a_outcomes if (not o.ok and o.error)]

    lane_b_results: dict[str, Any] = {}
    lane_b_all_successes: list[RequestMetrics] = []
    lane_b_all_failures: list[dict[str, Any]] = []
    for concurrency in (2, 4, 8, 16):
        outcomes = _run_stream_batch(
            base_url=base_url,
            model_name=model_name,
            prompt=lane_b_prompt,
            max_tokens=2048,
            total_requests=12,
            concurrency=concurrency,
        )
        successes = [o.metrics for o in outcomes if o.ok and o.metrics]
        failures = [o.error for o in outcomes if (not o.ok and o.error)]
        lane_b_all_successes.extend(successes)
        lane_b_all_failures.extend(failures)
        throughput = sum(item.output_tokens for item in successes) / max(
            1e-6,
            sum(item.client_observed_request_wall_time_seconds for item in successes),
        )
        ttft = [item.client_observed_time_to_first_stream_event_seconds for item in successes]
        lane_b_results[str(concurrency)] = {
            "concurrency": concurrency,
            "requests": 12,
            "successful_requests": len(successes),
            "failed_requests": len(failures),
            "error_rate": round(len(failures) / 12.0, 4),
            "aggregate_throughput_tokens_per_second": round(throughput, 4),
            "ttft_p95_seconds": _percentile(ttft, 95),
        }

    lane_a_ttft = [item.client_observed_time_to_first_stream_event_seconds for item in lane_a_successes]
    lane_a_latency = [item.client_observed_request_wall_time_seconds for item in lane_a_successes]
    lane_a_tps = [item.client_observed_output_tokens_per_second for item in lane_a_successes]

    ttft_p95_at_1 = _percentile(lane_a_ttft, 95) or 0.0
    ttft_p95_at_16 = float(lane_b_results.get("16", {}).get("ttft_p95_seconds") or 0.0)
    degradation_ratio = round(ttft_p95_at_16 / ttft_p95_at_1, 4) if ttft_p95_at_1 > 0 else None

    one_tps = lane_b_results.get("2", {}).get("aggregate_throughput_tokens_per_second")
    four_tps = lane_b_results.get("4", {}).get("aggregate_throughput_tokens_per_second")
    efficiency = 0.0
    if isinstance(one_tps, (int, float)) and isinstance(four_tps, (int, float)) and float(one_tps) > 0:
        efficiency = min(1.0, max(0.0, float(four_tps) / float(one_tps)))

    all_successes = [*lane_a_successes, *lane_b_all_successes]
    all_failures = [*lane_a_failures, *lane_b_all_failures]

    aggregate = {
        "source": "endpoint_perf_two_lane",
        "client_observed_avg_time_to_first_stream_event_seconds": _safe_mean(
            [item.client_observed_time_to_first_stream_event_seconds for item in all_successes]
        ),
        "client_observed_avg_request_wall_time_seconds": _safe_mean(
            [item.client_observed_request_wall_time_seconds for item in all_successes]
        ),
        "client_observed_avg_output_tokens_per_second": _safe_mean(
            [item.client_observed_output_tokens_per_second for item in all_successes]
        ),
        "client_observed_concurrency_4_efficiency": round(efficiency, 4),
        "request_counts": {
            "serving_requests": len(all_successes),
            "serving_cells": 5,
            "failed_requests": len(all_failures),
        },
    }
    if all_failures:
        aggregate["request_failures"] = all_failures

    return {
        "perf_profile": "endpoint_two_lane_v1",
        "lane_a": {
            "concurrency": 1,
            "requests": 12,
            "max_output_tokens": 512,
            "successful_requests": len(lane_a_successes),
            "failed_requests": len(lane_a_failures),
            "error_rate": round(len(lane_a_failures) / 12.0, 4),
            "ttft_p50_seconds": _percentile(lane_a_ttft, 50),
            "ttft_p95_seconds": _percentile(lane_a_ttft, 95),
            "latency_p50_seconds": _percentile(lane_a_latency, 50),
            "latency_p95_seconds": _percentile(lane_a_latency, 95),
            "output_tokens_per_second_p50": _percentile(lane_a_tps, 50),
            "output_tokens_per_second_p95": _percentile(lane_a_tps, 95),
        },
        "lane_b": {
            "concurrency_levels": [2, 4, 8, 16],
            "requests_per_concurrency": 12,
            "max_output_tokens": 2048,
            "by_concurrency": lane_b_results,
            "degradation": {
                "ttft_p95_ratio_16_over_1": degradation_ratio,
            },
        },
        "artifacts": {
            "kind": "inline",
            "note": "endpoint perf metrics embedded in result JSON",
        },
        "by_concurrency": lane_b_results,
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
) -> list[RequestOutcome]:
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
) -> RequestOutcome:
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "thinking_token_budget": 2048,
    }
    started_at = time.perf_counter()
    first_event_at: float | None = None
    content_parts: list[str] = []
    output_tokens = 0
    reported_completion_tokens = 0
    stream_fields_seen: set[str] = set()
    try:
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
                    text = delta.get("content")
                    if isinstance(text, str) and text:
                        if first_event_at is None:
                            first_event_at = time.perf_counter()
                        content_parts.append(text)
                        stream_fields_seen.add("content")
                usage = payload_obj.get("usage")
                if isinstance(usage, dict):
                    completion = usage.get("completion_tokens")
                    if isinstance(completion, int) and completion > 0:
                        reported_completion_tokens = completion
    except Exception as exc:  # noqa: BLE001
        finished_at = time.perf_counter()
        return RequestOutcome(
            ok=False,
            error=_error_payload(
                exc,
                phase="stream_request",
                elapsed_seconds=finished_at - started_at,
                timeout_seconds=REQUEST_TIMEOUT_SECONDS,
            ),
            elapsed_seconds=finished_at - started_at,
        )
    finished_at = time.perf_counter()
    if first_event_at is None:
        first_event_at = finished_at
    response_text = "".join(content_parts)
    visible_output_tokens = max(1, len(response_text.split()))
    # Keep reported completion tokens for compatibility/diagnostics, but use visible
    # streamed tokens for local perf rate math.
    output_tokens = reported_completion_tokens if reported_completion_tokens > 0 else visible_output_tokens
    wall_time = finished_at - started_at
    generate_seconds = max(finished_at - first_event_at, 1e-6)
    return RequestOutcome(
        ok=True,
        metrics=RequestMetrics(
            client_observed_request_wall_time_seconds=wall_time,
            client_observed_time_to_first_stream_event_seconds=first_event_at - started_at,
            output_tokens=output_tokens,
            client_observed_output_tokens_per_second=visible_output_tokens / generate_seconds,
            response_text=response_text,
            stream_fields_seen=tuple(sorted(stream_fields_seen)),
        ),
        elapsed_seconds=wall_time,
    )


def _run_quality_benchmark(
    base_url: str,
    model_name: str,
    judge_client,
    tokenizer_source: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    judge_cases: list[dict[str, Any]] = []

    disabled_judge = JudgeClient(
        enabled=False,
        provider="disabled",
        model=model_name,
        auth_source="",
        base_url="",
        reason="disabled_for_benchmark_scoring",
    )
    for case in QUALITY_CASES:
        details = _chat_completion_details(
            base_url,
            model_name,
            case.prompt,
            max_tokens=4096,
        )
        completion_tokens = int(details.usage.get("completion_tokens", 0))
        token_accounting = _build_token_accounting(
            response_text=details.response_text,
            tool_calls=details.tool_calls,
            completion_tokens=completion_tokens,
            tokenizer_path=tokenizer_source,
        )
        if details.request_error is not None:
            error_message = str(details.request_error.get("message", "request failed"))
            reliability_flags = {
                "structured_output_failure": False,
                "constraint_violation": False,
                "hallucination_fabrication": False,
                "empty_evasive_degenerate": True,
                "request_failed": True,
            }
            result = {
                "id": case.id,
                "group": case.group,
                "judge_eligible": case.judge_eligible,
                "default_judge_enabled": case.default_judge_enabled,
                "prompt": case.prompt,
                "response": "",
                "thinking": "",
                "score": 0.0,
                "passed": False,
                "deterministic_failures": [error_message],
                "rubric_passes": [],
                "rubric_failures": [],
                "reliability_flags": reliability_flags,
                "judge": None,
                "usage": details.usage,
                "status": "failed",
                "failure": details.request_error,
                "token_accounting": {
                    **token_accounting,
                    "prompt_tokens": int(details.usage.get("prompt_tokens", 0)),
                    "completion_tokens": completion_tokens,
                    "total_tokens": int(details.usage.get("total_tokens", 0)),
                    "token_source": tokenizer_source,
                },
            }
            results.append(result)
            continue
        response_text = details.response_text
        thinking_text = details.thinking_text
        evaluation = evaluate_case(case, response_text, disabled_judge)
        result = {
            "id": case.id,
            "group": case.group,
            "judge_eligible": case.judge_eligible,
            "default_judge_enabled": case.default_judge_enabled,
            "prompt": case.prompt,
            "response": response_text,
            "thinking": thinking_text,
            "score": evaluation.score,
            "passed": evaluation.passed,
            "deterministic_failures": evaluation.deterministic_failures,
            "rubric_passes": evaluation.rubric_passes,
            "rubric_failures": evaluation.rubric_failures,
            "reliability_flags": evaluation.reliability_flags,
            "judge": None,
            "usage": details.usage,
            "status": "ok",
            "token_accounting": {
                **token_accounting,
                "prompt_tokens": int(details.usage.get("prompt_tokens", 0)),
                "completion_tokens": completion_tokens,
                "total_tokens": int(details.usage.get("total_tokens", 0)),
                "token_source": tokenizer_source,
            },
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
    judge_context_by_case = {item["case_id"]: item["deterministic_context"] for item in judge_cases}
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


def _summarize_thinking_cases(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    accounting: list[dict[str, Any]] = []
    for case in case_results:
        token_accounting = case.get("token_accounting")
        if isinstance(token_accounting, dict):
            accounting.append(token_accounting)
    total_cases = len(accounting)
    total_completion = sum(int(item.get("completion_tokens", 0)) for item in accounting)
    total_visible = sum(int(item.get("visible_response_tokens", 0)) for item in accounting)
    total_tool_calls = sum(int(item.get("tool_call_tokens", 0)) for item in accounting)
    total_thinking = sum(
        int(item.get("thinking_tokens", item.get("derived_thinking_tokens", 0)))
        for item in accounting
    )
    exact_cases = sum(1 for item in accounting if bool(item.get("thinking_tokens_exact", False)))
    estimated_cases = total_cases - exact_cases
    return {
        "source": "completion_tokens_minus_visible_response_tokens_minus_tool_call_tokens",
        "total_cases": total_cases,
        "exact_cases": exact_cases,
        "estimated_cases": estimated_cases,
        "total_completion_tokens": total_completion,
        "total_visible_response_tokens": total_visible,
        "total_tool_call_tokens": total_tool_calls,
        "total_thinking_tokens": total_thinking,
        "mean_completion_tokens": round(total_completion / total_cases, 3) if total_cases else 0.0,
        "mean_visible_response_tokens": round(total_visible / total_cases, 3)
        if total_cases
        else 0.0,
        "mean_tool_call_tokens": round(total_tool_calls / total_cases, 3) if total_cases else 0.0,
        "mean_thinking_tokens": round(total_thinking / total_cases, 3) if total_cases else 0.0,
    }


def _build_thinking_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for group_name in ("quality_no_tools", "quality_with_tools"):
        group_cases = [case for case in case_results if case.get("group") == group_name]
        if group_cases:
            groups[group_name] = _summarize_thinking_cases(group_cases)
    return {
        "source": "completion_tokens_minus_visible_response_tokens_minus_tool_call_tokens",
        "overall": _summarize_thinking_cases(case_results),
        "groups": groups,
    }


def _chat_completion_details(
    base_url: str, model_name: str, prompt: str, max_tokens: int
) -> ChatCompletionDetails:
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "thinking_token_budget": 2048,
    }
    started_at = time.perf_counter()
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage")
        usage_payload = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)) if isinstance(usage, dict) else 0,
            "completion_tokens": int(usage.get("completion_tokens", 0))
            if isinstance(usage, dict)
            else 0,
            "total_tokens": int(usage.get("total_tokens", 0)) if isinstance(usage, dict) else 0,
        }
        message = data.get("choices", [{}])[0].get("message", {})
        response_text, thinking_text = _assistant_message_parts(dict(message))
        tool_calls = tuple(
            dict(item) for item in (message.get("tool_calls") or []) if isinstance(item, dict)
        )
        return ChatCompletionDetails(
            response_text=response_text,
            thinking_text=thinking_text,
            usage=usage_payload,
            tool_calls=tool_calls,
            elapsed_seconds=time.perf_counter() - started_at,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started_at
        return ChatCompletionDetails(
            response_text="",
            thinking_text="",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            tool_calls=(),
            request_error=_error_payload(
                exc,
                phase="chat_completion",
                elapsed_seconds=elapsed,
                timeout_seconds=REQUEST_TIMEOUT_SECONDS,
            ),
            elapsed_seconds=elapsed,
        )


def _chat_completion_parts(
    base_url: str, model_name: str, prompt: str, max_tokens: int
) -> tuple[str, str]:
    details = _chat_completion_details(base_url, model_name, prompt, max_tokens)
    return details.response_text, details.thinking_text


def _chat_completion(base_url: str, model_name: str, prompt: str, max_tokens: int) -> str:
    response_text, _thinking_text = _chat_completion_parts(base_url, model_name, prompt, max_tokens)
    return response_text


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
                statistics.mean(sample["prompt_throughput_tokens_per_second"] for sample in basis),
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
        "mean_queue_time_seconds": (round(queue_sum / queue_count, 6) if queue_count > 0 else None),
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
