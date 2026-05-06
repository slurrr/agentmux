import json
from pathlib import Path

from agentmux.bench_perf_vllm import run_vllm_endpoint_perf


class _Done:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_perf_runner_disabled_by_flag(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTMUX_RUN_ROOT", str(tmp_path / "runs" / "agentmux"))
    result = run_vllm_endpoint_perf(
        stack_name="s", base_url="http://x", model_name="m", enabled=False
    )
    assert result["available"] is False
    assert "perf_summary_path" in result


def test_perf_runner_writes_summary_and_raw_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTMUX_RUN_ROOT", str(tmp_path / "runs" / "agentmux"))
    monkeypatch.setattr(
        "agentmux.bench_perf_vllm._resolve_vllm_module",
        lambda: ("vllm.benchmarks.benchmark_serving", "0.8.0", "/x.py"),
    )

    def fake_run(cmd, capture_output, text, check):
        out_json = Path(cmd[cmd.index("--result-dir") + 1]) / str(cmd[cmd.index("--result-filename") + 1])
        payload = {
            "metrics": {
                "ttft_p50": 0.5,
                "ttft_p90": 0.7,
                "ttft_p95": 0.8,
                "ttft_p99": 0.9,
                "ttft_mean": 0.6,
                "latency_p50": 1.0,
                "latency_p90": 1.2,
                "latency_p95": 1.3,
                "latency_p99": 1.4,
                "latency_mean": 1.1,
                "output_tps_p50": 50,
                "output_tps_p90": 45,
                "output_tps_p95": 40,
                "output_tps_p99": 35,
                "output_tps_mean": 48,
                "failed_requests": 0,
                "error_rate": 0.0,
            }
        }
        out_json.write_text(json.dumps(payload), encoding="utf-8")
        return _Done(0, "ok", "")

    monkeypatch.setattr("agentmux.bench_perf_vllm.subprocess.run", fake_run)

    result = run_vllm_endpoint_perf(stack_name="s", base_url="http://x", model_name="m")
    assert result["available"] is True
    summary = Path(result["perf_summary_path"])
    assert summary.exists()
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["available"] is True
    assert Path(data["artifacts"]["stdout"]).exists()
