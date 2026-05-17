import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast

from agentmux.config import ServiceSpec, StackSpec
from agentmux.smoke import smoke_stack_safe


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if self.path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "qwen2.5-7b"}]}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):  # noqa: N802
        if self.path == "/v1/chat/completions":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {
                "choices": [
                    {"message": {"role": "assistant", "content": "ok"}},
                ],
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        return


class _NoHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "qwen2.5-7b"}]}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):  # noqa: N802
        if self.path == "/v1/chat/completions":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {
                "choices": [
                    {"message": {"role": "assistant", "content": "ok"}},
                ],
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        return


def _test_stack_for_port(port: int) -> StackSpec:
    service = ServiceSpec(
        name="main",
        engine="vllm",
        host="127.0.0.1",
        port=port,
        env={},
        notes=None,
        model="demo-model",
        served_model_name="demo-model",
    )
    return StackSpec(
        name="smoke_test",
        track="lab",
        path=Path("mux/lab/smoke_test.toml"),
        primary_service="main",
        notes=None,
        env={},
        services={"main": service},
    )


def test_smoke_stack_safe_round_trips(monkeypatch) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = smoke_stack_safe(_test_stack_for_port(server.server_port))
        assert result["ok"] is True
        chat = cast(dict[str, object], result["chat"])
        choices = cast(list[dict[str, object]], chat["choices"])
        message = cast(dict[str, object], choices[0]["message"])
        assert message["content"] == "ok"
    finally:
        server.shutdown()
        server.server_close()


def test_smoke_stack_safe_without_health_endpoint(monkeypatch) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _NoHealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = smoke_stack_safe(_test_stack_for_port(server.server_port))
        assert result["ok"] is True
        assert result["health_status"] == 200
    finally:
        server.shutdown()
        server.server_close()
