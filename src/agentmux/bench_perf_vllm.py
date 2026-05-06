from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from agentmux.runtime import runtime_root

LANES = {
    "lane_a": {"concurrency": 1, "requests": 12, "max_tokens": 512, "prompt_id": "short_request"},
    "lane_b": {
        "concurrency_levels": [2, 4, 8, 16],
        "requests": 12,
        "max_tokens": 2048,
        "prompt_id": "medium_request",
    },
}


def _perf_root() -> Path:
    path = runtime_root() / "benchmarks" / "perf"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_vllm_module() -> tuple[str | None, str | None, str | None]:
    version = None
    try:
        vllm = importlib.import_module("vllm")
        version = str(getattr(vllm, "__version__", "unknown"))
    except Exception:
        return None, version, None

    # Prefer the module that is actually present in this environment.
    # On this machine/version family, serve.py is the canonical entrypoint.
    for module in ("vllm.benchmarks.serve", "vllm.benchmarks.benchmark_serving"):
        spec = importlib.util.find_spec(module)
        if spec is not None:
            return module, version, str(spec.origin)
    return None, version, None


def _extract_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else payload
    completed_raw = metrics.get("completed", metrics.get("num_completed_requests"))
    failed_raw = metrics.get("failed", metrics.get("failed_requests"))
    completed = int(completed_raw) if completed_raw is not None else None
    failed = int(failed_raw) if failed_raw is not None else None
    return {
        "completed": completed,
        "failed": failed,
        "duration": metrics.get("duration"),
        "request_throughput": metrics.get("request_throughput"),
        "output_throughput": metrics.get("output_throughput"),
        "total_token_throughput": metrics.get("total_token_throughput"),
        "mean_ttft_ms": metrics.get("mean_ttft_ms"),
        "median_ttft_ms": metrics.get("median_ttft_ms"),
        "p99_ttft_ms": metrics.get("p99_ttft_ms"),
        "mean_tpot_ms": metrics.get("mean_tpot_ms"),
        "median_tpot_ms": metrics.get("median_tpot_ms"),
        "p99_tpot_ms": metrics.get("p99_tpot_ms"),
        "mean_itl_ms": metrics.get("mean_itl_ms"),
        "median_itl_ms": metrics.get("median_itl_ms"),
        "p99_itl_ms": metrics.get("p99_itl_ms"),
    }


def _validate_metrics_shape(metrics: dict[str, Any] | None) -> list[str]:
    if not isinstance(metrics, dict):
        return ["metrics missing"]
    problems: list[str] = []
    for scalar in ("completed", "failed", "output_throughput", "mean_ttft_ms"):
        if scalar not in metrics:
            problems.append(f"missing field: {scalar}")
    return problems


def _bench_base_url(base_url: str) -> str:
    stripped = base_url.rstrip("/")
    if stripped.endswith("/v1"):
        return stripped
    return f"{stripped}/v1"


def _run_lane(
    *,
    module: str,
    base_url: str,
    model_name: str,
    tokenizer_path: str | None,
    result_dir: Path,
    result_filename: str,
    concurrency: int,
    requests: int,
    max_tokens: int,
) -> dict[str, Any]:
    result_json_path = result_dir / result_filename

    common_args = [
        "--backend",
        "openai-chat",
        "--base-url",
        _bench_base_url(base_url),
        "--endpoint",
        "/chat/completions",
        "--model",
        model_name,
        "--dataset-name",
        "random",
        "--num-prompts",
        str(requests),
        "--max-concurrency",
        str(concurrency),
        "--input-len",
        "256",
        "--output-len",
        str(max_tokens),
        "--metric-percentiles",
        "50,90,95,99",
        "--percentile-metrics",
        "ttft,tpot,itl,e2el",
        "--save-result",
        "--result-dir",
        str(result_dir),
        "--result-filename",
        result_filename,
    ]
    if tokenizer_path:
        common_args.extend(["--tokenizer", tokenizer_path])

    attempts: list[tuple[str, list[str]]] = [
        ("module", [sys.executable, "-m", module, *common_args]),
        ("cli", [str(Path(sys.executable).with_name("vllm")), "bench", "serve", *common_args]),
    ]

    started = time.time()
    aggregate_stdout: list[str] = []
    aggregate_stderr: list[str] = []
    final_returncode = 1
    final_cmd: list[str] = []
    mode_used = "module"

    for mode, cmd in attempts:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        aggregate_stdout.append(f"$ {' '.join(cmd)}\n{proc.stdout or ''}")
        aggregate_stderr.append(f"$ {' '.join(cmd)}\n{proc.stderr or ''}")
        final_returncode = proc.returncode
        final_cmd = cmd
        mode_used = mode
        if proc.returncode == 0 and result_json_path.exists():
            break

    return {
        "command": final_cmd,
        "mode_used": mode_used,
        "returncode": final_returncode,
        "stdout": "\n\n".join(aggregate_stdout),
        "stderr": "\n\n".join(aggregate_stderr),
        "started_at": started,
        "finished_at": time.time(),
        "result_json": str(result_json_path),
    }


def run_vllm_endpoint_perf(
    *,
    stack_name: str,
    base_url: str,
    model_name: str,
    tokenizer_path: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    run_dir = _perf_root() / f"{stamp}-{stack_name}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / "perf_summary.json"
    module, vllm_version, module_path = _resolve_vllm_module()

    if not enabled:
        summary = {
            "available": False,
            "reason": "disabled_by_flag",
            "vllm_version": vllm_version,
            "module": module,
            "module_path": module_path,
            "lanes": LANES,
        }
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return {"artifacts_dir": str(run_dir), "perf_summary_path": str(summary_path), **summary}

    if module is None:
        summary = {
            "available": False,
            "reason": "vllm benchmark module not found",
            "vllm_version": vllm_version,
            "module": None,
            "module_path": None,
            "lanes": LANES,
        }
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return {"artifacts_dir": str(run_dir), "perf_summary_path": str(summary_path), **summary}

    invocations: dict[str, dict[str, Any]] = {}

    lane_a_raw = _run_lane(
        module=module,
        base_url=base_url,
        model_name=model_name,
        tokenizer_path=tokenizer_path,
        result_dir=run_dir,
        result_filename="lane_a.json",
        concurrency=1,
        requests=12,
        max_tokens=512,
    )
    invocations["lane_a"] = lane_a_raw

    lane_b_raw: dict[str, dict[str, Any]] = {}
    for conc in (2, 4, 8, 16):
        lane_b_raw[str(conc)] = _run_lane(
            module=module,
            base_url=base_url,
            model_name=model_name,
            tokenizer_path=tokenizer_path,
            result_dir=run_dir,
            result_filename=f"lane_b_c{conc}.json",
            concurrency=conc,
            requests=12,
            max_tokens=2048,
        )
    invocations["lane_b"] = lane_b_raw

    # Persist raw stdout/stderr unchanged.
    (run_dir / "stdout.txt").write_text(
        "\n\n".join(
            [
                "# lane_a\n" + lane_a_raw["stdout"],
                *[f"# lane_b_c{k}\n{v['stdout']}" for k, v in lane_b_raw.items()],
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "stderr.txt").write_text(
        "\n\n".join(
            [
                "# lane_a\n" + lane_a_raw["stderr"],
                *[f"# lane_b_c{k}\n{v['stderr']}" for k, v in lane_b_raw.items()],
            ]
        ),
        encoding="utf-8",
    )

    def load_json(path: str) -> dict[str, Any] | None:
        p = Path(path)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    lane_a_json = load_json(lane_a_raw["result_json"])
    lane_b_json = {k: load_json(v["result_json"]) for k, v in lane_b_raw.items()}

    lane_a_metrics = _extract_metrics(lane_a_json or {}) if lane_a_json else None
    lane_b_metrics = {
        k: (_extract_metrics(v or {}) if v is not None else None) for k, v in lane_b_json.items()
    }

    schema_errors: list[str] = []
    schema_errors.extend([f"lane_a: {e}" for e in _validate_metrics_shape(lane_a_metrics)])
    for key, value in lane_b_metrics.items():
        schema_errors.extend([f"lane_b_c{key}: {e}" for e in _validate_metrics_shape(value)])

    completed_counts = [
        (lane_a_metrics or {}).get("completed"),
        *[(m or {}).get("completed") for m in lane_b_metrics.values()],
    ]
    known_completed = [int(x) for x in completed_counts if x is not None]
    all_known_zero = bool(known_completed) and all(x == 0 for x in known_completed)

    available = (
        lane_a_raw["returncode"] == 0
        and all(item["returncode"] == 0 for item in lane_b_raw.values())
        and not schema_errors
        and not all_known_zero
    )


    summary = {
        "available": available,
        "reason": None if available else (
            "all lanes completed=0" if all_known_zero else "perf failed or result schema unavailable"
        ),
        "schema_version": "agentmux-perf-summary-v1",
        "schema_errors": schema_errors,
        "vllm_version": vllm_version,
        "module": module,
        "module_path": module_path,
        "lanes": LANES,
        "lane_metrics": {
            "lane_a": lane_a_metrics,
            "lane_b": lane_b_metrics,
        },
        "invocations": {
            "lane_a": {k: v for k, v in lane_a_raw.items() if k not in {"stdout", "stderr"}},
            "lane_b": {
                k: {ik: iv for ik, iv in v.items() if ik not in {"stdout", "stderr"}}
                for k, v in lane_b_raw.items()
            },
        },
        "artifacts": {
            "stdout": str(run_dir / "stdout.txt"),
            "stderr": str(run_dir / "stderr.txt"),
        },
    }

    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {
        "artifacts_dir": str(run_dir),
        "perf_summary_path": str(summary_path),
        "available": available,
        "reason": summary.get("reason"),
        "vllm_version": vllm_version,
        "module": module,
        "module_path": module_path,
        "lanes": LANES,
    }
