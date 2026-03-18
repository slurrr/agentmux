import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

from agentmux.config import resolve_stack
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


def test_smoke_stack_safe_round_trips(monkeypatch) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        stack = resolve_stack("qwen2_5_7b")
        service = stack.services[stack.primary_service]
        patched = stack.services.copy()
        patched[stack.primary_service] = service.__class__(
            **{**service.__dict__, "host": "127.0.0.1", "port": server.server_port}
        )
        stack = stack.__class__(**{**stack.__dict__, "services": patched})
        result = smoke_stack_safe(stack)
        assert result["ok"] is True
        chat = cast(dict[str, object], result["chat"])
        choices = cast(list[dict[str, object]], chat["choices"])
        message = cast(dict[str, object], choices[0]["message"])
        assert message["content"] == "ok"
    finally:
        server.shutdown()
        server.server_close()
