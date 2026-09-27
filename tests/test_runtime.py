from __future__ import annotations

from unittest import mock

from agentmux.runtime import RuntimeService, RuntimeStack, runtime_status


def stack() -> RuntimeStack:
    return RuntimeStack(
        mux="demo",
        track="lab",
        path="mux/lab/demo/mux.toml",
        services=[
            RuntimeService(
                name="main",
                container_name="agentmux-demo-main",
                container_id="abc123",
                image="localhost/demo:latest",
                host="127.0.0.1",
                port=8002,
                command=["podman", "run"],
                health_url="http://127.0.0.1:8002/v1/models",
                started_at=1.0,
            )
        ],
        started_at=1.0,
    )


@mock.patch("agentmux.runtime.container_is_running", return_value=True)
@mock.patch(
    "agentmux.runtime._endpoint_probe",
    return_value={"reachable": False, "serving": False, "http_status": None, "models": []},
)
def test_running_container_with_missing_endpoint_is_not_reported_running(
    _probe: mock.Mock, _container: mock.Mock
) -> None:
    payload = runtime_status(stack())

    assert payload["active"] is False
    assert payload["services"][0]["container_running"] is True
    assert payload["services"][0]["running"] is False
    assert payload["services"][0]["status"] == "unreachable"


@mock.patch("agentmux.runtime.container_is_running", return_value=True)
@mock.patch(
    "agentmux.runtime._endpoint_probe",
    return_value={
        "reachable": True,
        "serving": True,
        "http_status": 200,
        "models": ["served-model"],
    },
)
def test_reachable_served_model_is_reported_running(
    _probe: mock.Mock, _container: mock.Mock
) -> None:
    payload = runtime_status(stack())

    assert payload["active"] is True
    assert payload["services"][0]["running"] is True
    assert payload["services"][0]["status"] == "running"
    assert payload["services"][0]["models"] == ["served-model"]
