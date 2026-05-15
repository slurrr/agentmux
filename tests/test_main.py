import json
from pathlib import Path

from agentmux.main import main
from agentmux.onboard import OnboardResult
from agentmux.runtime import RuntimeService, RuntimeStack


def test_render_outputs_stack_commands(capsys) -> None:
    rc = main(["render", "example_vllm_recipes"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "[generalist] uv run vllm serve" in captured.out


def test_show_json_outputs_generic_args(capsys) -> None:
    rc = main(["show", "example_vllm_recipes", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert rc == 0
    assert payload["services"]["generalist"]["args"]["attention_backend"] == "FLASH_ATTN"


def test_list_outputs_track_prefixed_stacks(capsys) -> None:
    rc = main(["list", "--include-archive"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "examples/example_vllm_recipes" in captured.out
    assert "examples/example_two_service" in captured.out
    assert "examples/example_bench_mux" in captured.out


def test_onboard_cli_dispatch(monkeypatch, capsys) -> None:
    result = OnboardResult(
        requested_source="/cache/model",
        resolved_source="/cache/model/snapshots/abc",
        slug="demo-model",
        stack_name="demo-model",
        track="lab",
        local_model_path="/models/local/hf-snapshots/demo-model/current",
        active_model_path="/models/active/demo-model",
        manifest_path="mux/lab/demo-model.toml",
        model_manifest_path="/models/manifests/demo-model.md",
        onboarding_dir="/runs/agentmux/onboarding/demo-model",
        launch_attempted=True,
        launch_performed=False,
        smoke={"ok": True},
        benchmark=None,
        render={"stack": "demo-model", "services": []},
        notes="note",
        services=[],
        created_at="2026-05-12T00:00:00Z",
    )
    monkeypatch.setattr("agentmux.main.onboard_model", lambda *args, **kwargs: result)
    monkeypatch.setattr("agentmux.main.render_onboard_summary", lambda item: "onboard summary\n")

    rc = main(["onboard", "/cache/model"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "onboard summary" in captured.out


def _serving_payload() -> dict[str, object]:
    return {
        "aggregate": {
            "avg_ttft_seconds": 0.1,
            "avg_output_tokens_per_second": 55.0,
            "concurrency_4_efficiency": 0.9,
            "client_observed_avg_request_wall_time_seconds": 1.2,
            "client_observed_avg_time_to_first_stream_event_seconds": 0.4,
            "client_observed_avg_output_tokens_per_second": 55.0,
            "client_observed_concurrency_4_efficiency": 0.9,
            "first_request": {
                "client_observed_request_wall_time_seconds": 2.1,
                "client_observed_time_to_first_stream_event_seconds": 1.3,
            },
            "after_first_request": {
                "client_observed_avg_request_wall_time_seconds": 1.1,
                "client_observed_avg_time_to_first_stream_event_seconds": 0.3,
            },
        },
        "by_concurrency": {
            "1": {
                "avg_request_wall_time_seconds": 1.0,
                "avg_time_to_first_stream_event_seconds": 0.5,
                "avg_output_tokens_per_second": 60.0,
            },
            "2": {
                "avg_request_wall_time_seconds": 1.2,
                "avg_time_to_first_stream_event_seconds": 0.4,
                "avg_output_tokens_per_second": 56.0,
            },
            "4": {
                "avg_request_wall_time_seconds": 1.4,
                "avg_time_to_first_stream_event_seconds": 0.3,
                "avg_output_tokens_per_second": 49.0,
            },
        },
    }


def test_bench_show_formats_latest_result(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("AGENTMUX_RUN_ROOT", str(tmp_path / "runs" / "agentmux"))
    result_dir = tmp_path / "runs" / "agentmux" / "benchmarks"
    result_dir.mkdir(parents=True)
    payload = {
        "profile": "ghosty-local-agent",
        "stack": {"name": "benchstack"},
        "declared_config": {
            "engine": "vllm",
            "model": "/models/test",
            "served_model_name": "benchstack",
            "args": {"kv_cache_dtype": "fp8_e4m3", "max_model_len": 8192},
        },
        "observed_startup": {
            "available": True,
            "vllm_version": "0.20.0",
            "resolved_architecture": "Qwen3_5ForConditionalGeneration",
            "resolved_dtype": "torch.bfloat16",
            "resolved_kv_cache_dtype": "fp8_e4m3",
            "resolved_quantization": "compressed-tensors",
            "resolved_max_seq_len": "8192",
            "resolved_enable_chunked_prefill": "True",
            "model_load_gpu_memory_gib": 12.72,
            "torch_compile_seconds": 5.29,
            "attention_backends": [
                {
                    "chosen": "FLASH_ATTN",
                    "potential": [
                        "FLASH_ATTN",
                        "FLASHINFER",
                        "TRITON_ATTN",
                        "FLEX_ATTENTION",
                    ],
                }
            ],
        },
        "request_accounting": {
            "local_serving_requests": 21,
            "local_serving_cells": 9,
            "local_quality_requests": 12,
            "external_judge_requests": 12,
        },
        "observed_runtime": {
            "vllm_log_runtime": {
                "available": True,
                "sample_count": 4,
                "active_sample_count": 2,
                "aggregate": {
                    "generation_throughput_tokens_per_second_mean": 61.2,
                    "generation_throughput_tokens_per_second_max": 88.4,
                    "generation_throughput_tokens_per_second_min": 2.5,
                    "prompt_throughput_tokens_per_second_mean": 55.1,
                    "prompt_throughput_tokens_per_second_max": 77.0,
                    "prompt_throughput_tokens_per_second_min": 10.0,
                    "gpu_kv_cache_usage_percent_max": 3.4,
                    "prefix_cache_hit_rate_percent_max": 12.0,
                    "running_requests_max": 4,
                    "waiting_requests_max": 1,
                },
            },
            "vllm_metrics": {
                "available": True,
                "sampled_entries": [
                    {"name": "vllm:gpu_cache_usage_perc", "labels": '{engine="0"}', "value": 12.5},
                ],
                "skipped_created_series": 3,
                "skipped_histogram_buckets": 2,
            },
            "vllm_metrics_serving_gauges": {
                "available": True,
                "sample_count": 6,
                "active_sample_count": 3,
                "requests_running_max": 4,
                "requests_waiting_max": 1,
                "kv_cache_usage_percent_max": 3.4,
                "kv_cache_usage_percent_mean": 2.1,
                "kv_cache_usage_metric_unreliable": False,
            },
            "vllm_metrics_serving_delta": {
                "available": True,
                "requests": 21,
                "prompt_tokens": 1400,
                "generation_tokens": 1200,
                "prefix_cache_queries": 1400,
                "prefix_cache_hits": 0,
                "prompt_tokens_cached": 0,
                "mean_time_to_first_token_seconds": 0.032,
                "mean_end_to_end_latency_seconds": 0.88,
                "mean_queue_time_seconds": 0.001,
                "mean_inference_time_seconds": 0.82,
                "mean_prefill_time_seconds": 0.05,
                "mean_decode_time_seconds": 0.77,
                "mean_request_time_per_output_token_seconds": 0.012,
                "mean_inter_token_latency_seconds": 0.011,
                "mean_prompt_tokens_per_request": 66.7,
                "mean_output_tokens_per_request": 57.1,
                "success_stop": 21,
                "success_length": 0,
                "success_error": 0,
                "success_abort": 0,
                "success_repetition": 0,
            },
        },
        "summary": {
            "serving_score": 0.9,
            "quality_score": 0.8,
            "reliability_score": 0.7,
            "overall_score": 0.8,
            "verdict": "usable_with_tradeoffs",
            "blocking_weaknesses": ["structured_output_failure_rate > 10%"],
            "categories": {
                "serving": _serving_payload(),
                "vram": {
                    "available": True,
                    "used_mib": 1000,
                    "free_mib": 2000,
                    "total_mib": 3000,
                    "percent_used": 33.3,
                },
                "quality_no_tools": {"passed_cases": 1, "total_cases": 2},
                "reliability": {
                    "structured_output_failure_rate": 0.0,
                    "constraint_violation_rate": 0.5,
                    "hallucination_fabrication_rate": 0.0,
                    "empty_evasive_degenerate_rate": 0.0,
                },
            },
        },
        "cases": [
            {
                "id": "case_a",
                "group": "structured_output",
                "score": 1.0,
                "passed": True,
                "deterministic_failures": [],
                "rubric_passes": ["good shape"],
                "rubric_failures": [],
                "judge": {
                    "deterministic_score_fit": "fair",
                    "quality_note": "response was concise and useful",
                    "deterministic_notes": ["machine score looks right"],
                },
                "response": "clarify",
            }
        ],
    }
    (result_dir / "20260503-000000-benchstack-ghosty-local-agent.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    rc = main(["bench-show"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "benchmark: benchstack (ghosty-local-agent)" in captured.out
    assert "perf (endpoint)" in captured.out
    assert "deterministic prompt bench" in captured.out
    assert "kv cache dtype: fp8_e4m3" in captured.out
    assert "failures" in captured.out
    assert "judge-flagged" in captured.out


def test_bench_show_json_outputs_selected_result(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("AGENTMUX_RUN_ROOT", str(tmp_path / "runs" / "agentmux"))
    result_dir = tmp_path / "runs" / "agentmux" / "benchmarks"
    result_dir.mkdir(parents=True)
    payload = {
        "profile": "ghosty-local-agent",
        "stack": {"name": "benchstack"},
        "summary": {
            "serving_score": 0.9,
            "quality_score": 0.8,
            "reliability_score": 0.7,
            "overall_score": 0.8,
            "verdict": "usable_with_tradeoffs",
            "blocking_weaknesses": [],
            "categories": {
                "serving": _serving_payload(),
                "vram": {"available": False, "reason": "nvidia_smi_unavailable"},
                "quality_no_tools": {"passed_cases": 1, "total_cases": 1},
                "reliability": {
                    "structured_output_failure_rate": 0.0,
                    "constraint_violation_rate": 0.0,
                    "hallucination_fabrication_rate": 0.0,
                    "empty_evasive_degenerate_rate": 0.0,
                },
            },
        },
        "cases": [],
    }
    (result_dir / "20260503-111111-picked.json").write_text(json.dumps(payload), encoding="utf-8")

    rc = main(["bench-show", "picked", "--json"])
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert rc == 0
    assert parsed["stack"]["name"] == "benchstack"


def test_bench_show_filters_and_judge_note(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("AGENTMUX_RUN_ROOT", str(tmp_path / "runs" / "agentmux"))
    result_dir = tmp_path / "runs" / "agentmux" / "benchmarks"
    result_dir.mkdir(parents=True)
    payload = {
        "profile": "ghosty-local-agent",
        "stack": {"name": "benchstack"},
        "summary": {
            "serving_score": 0.9,
            "quality_score": 0.8,
            "reliability_score": 0.7,
            "overall_score": 0.8,
            "verdict": "usable_with_tradeoffs",
            "blocking_weaknesses": [],
            "categories": {
                "serving": _serving_payload(),
                "vram": {"available": False, "reason": "nvidia_smi_unavailable"},
                "quality_no_tools": {"passed_cases": 1, "total_cases": 2},
                "reliability": {
                    "structured_output_failure_rate": 0.0,
                    "constraint_violation_rate": 0.0,
                    "hallucination_fabrication_rate": 0.0,
                    "empty_evasive_degenerate_rate": 0.0,
                },
            },
        },
        "cases": [
            {
                "id": "failed_case",
                "group": "clarification",
                "score": 0.3,
                "passed": False,
                "deterministic_failures": ["bad bound"],
                "rubric_passes": [],
                "rubric_failures": ["missed ask"],
                "judge": {
                    "deterministic_score_fit": "too_harsh",
                    "quality_note": "failed deterministically but the answer was otherwise good",
                    "deterministic_notes": ["binary zero was too harsh"],
                },
                "response": "please clarify",
            },
            {
                "id": "passed_case",
                "group": "helpfulness",
                "score": 1.0,
                "passed": True,
                "deterministic_failures": [],
                "rubric_passes": ["good"],
                "rubric_failures": [],
                "judge": {
                    "deterministic_score_fit": "fair",
                    "quality_note": None,
                    "deterministic_notes": ["good"],
                },
                "response": "done",
            },
        ],
    }
    (result_dir / "20260503-222222-picked.json").write_text(json.dumps(payload), encoding="utf-8")

    rc = main(["bench-show", "picked", "--failures-only", "--judge-flagged-only", "--full"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "failed_case" not in captured.out
    assert "passed_case" not in captured.out
    assert "no cases matched the current filters" in captured.out


def test_bench_launch_runs_and_stops_stack(monkeypatch, capsys) -> None:
    launched = RuntimeStack(
        stack="benchstack",
        track="bench",
        path="mux/bench/benchstack.toml",
        services=[
            RuntimeService(
                name="main",
                pid=123,
                port=8100,
                command=["vllm", "serve"],
                log_path="/tmp/fake.log",
                started_at=1.0,
            )
        ],
        started_at=1.0,
    )
    observed_calls: list[str] = []

    monkeypatch.setattr(
        "agentmux.main.launch_stack",
        lambda stack, root, vllm_arg_overrides=None: launched,
    )
    monkeypatch.setattr("agentmux.main.resolve_stack", lambda stack, root: type("S", (), {
        "primary_service": "main",
        "services": {"main": type("Svc", (), {"host": "127.0.0.1", "port": 8100})()},
    })())
    monkeypatch.setattr("agentmux.main._follow_startup_log", lambda path, pid: True)
    monkeypatch.setattr("agentmux.main._wait_for_bench_ready", lambda base_url: 1.25)

    def fake_run_benchmark(
        stack_name,
        root,
        *,
        target_mode="already_running",
        launch_observation=None,
        judge_audit=False,
        enable_perf=True,
    ):
        observed_calls.append(target_mode)
        assert launch_observation is not None
        return {}, Path("/tmp/result.json"), "bench ok"

    monkeypatch.setattr("agentmux.main.run_benchmark", fake_run_benchmark)
    monkeypatch.setattr(
        "agentmux.main.stop_runtime",
        lambda runtime: observed_calls.append("stopped"),
    )

    rc = main(["bench", "benchstack", "--launch"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "bench ok" in captured.out
    assert observed_calls == ["launched", "stopped"]



def test_bench_show_reports_missing_judge_data(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("AGENTMUX_RUN_ROOT", str(tmp_path / "runs" / "agentmux"))
    result_dir = tmp_path / "runs" / "agentmux" / "benchmarks"
    result_dir.mkdir(parents=True)
    payload = {
        "profile": "ghosty-local-agent",
        "stack": {"name": "benchstack"},
        "summary": {
            "serving_score": 0.9,
            "quality_score": 0.8,
            "reliability_score": 0.7,
            "overall_score": 0.8,
            "verdict": "usable_with_tradeoffs",
            "blocking_weaknesses": [],
            "categories": {
                "serving": _serving_payload(),
                "vram": {"available": False, "reason": "nvidia_smi_unavailable"},
                "quality_no_tools": {"passed_cases": 0, "total_cases": 1},
                "reliability": {
                    "structured_output_failure_rate": 0.0,
                    "constraint_violation_rate": 0.0,
                    "hallucination_fabrication_rate": 0.0,
                    "empty_evasive_degenerate_rate": 0.0,
                },
            },
        },
        "cases": [
            {
                "id": "old_case",
                "group": "structured_output",
                "score": 0.0,
                "passed": False,
                "deterministic_failures": ["invalid json"],
                "rubric_passes": [],
                "rubric_failures": [],
                "response": "None",
            }
        ],
    }
    (result_dir / "20260503-333333-old.json").write_text(json.dumps(payload), encoding="utf-8")

    rc = main(["bench-show", "old"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "judge: unavailable in this result file" not in captured.out
