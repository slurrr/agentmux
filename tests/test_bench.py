import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agentmux.bench import _chat_completion, _chat_completion_parts, _stream_request
from agentmux.bench_cases import QUALITY_CASES
from agentmux.bench_judge import JudgeClient, JudgeResult, load_judge_client
from agentmux.bench_score import evaluate_case
from agentmux.bench_workspace import _assistant_message_parts, _message_text, _score_rename_timeout_key_everywhere_needed
from agentmux.main import main


class _BenchHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "bench-model"}]}).encode("utf-8"))
            return
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(
                b'# HELP vllm:num_requests_running running requests\n'
                b'vllm:num_requests_running 1\n'
                b'vllm:gpu_cache_usage_perc{engine="0"} 12.5\n'
            )
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        prompt = next(
            message["content"]
            for message in reversed(payload["messages"])
            if message.get("role") == "user"
        )
        if payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            body = (
                'data: {"choices":[{"delta":{"reasoning":"check logs first"}}],'
                '"usage":{"completion_tokens":3}}\n\n'
                "data: [DONE]\n\n"
            )
            self.wfile.write(body.encode("utf-8"))
            return
        message = (
            _workspace_response_for_payload(payload)
            if payload.get("tools")
            else {"role": "assistant", "content": _response_for_prompt(prompt)}
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"choices": [{"message": message}]}).encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A003
        return


def _response_for_prompt(prompt: str) -> str:
    if "Return exactly one word from this list only" in prompt:
        return "clarify"
    if "Return valid JSON only with exactly these keys" in prompt:
        return json.dumps(
            {
                "task_type": "edit",
                "needs_clarification": True,
                "reason": "Missing config file path",
            }
        )
    if "Return a JSON array with exactly 2 strings" in prompt:
        return json.dumps(["Ask which file to change", "Confirm current setting name"])
    if "Reply with exactly 3 bullets and nothing else" in prompt:
        return "- Check the error logs\n- Compare the config diff\n- Reproduce with debug enabled"
    if "Answer in 140 characters or fewer" in prompt:
        return (
            "Renaming the package likely changed the import path. "
            "Check whether imports still reference the old package name."
        )
    if "Give a plan with exactly 3 numbered steps" in prompt:
        return (
            "1. Review the recent config diff.\n"
            "2. Compare it to the last working version.\n"
            "3. Revert the risky change and retest startup."
        )
    if "Edit the file and update the base URL" in prompt:
        return "Which file or path should I update for the base URL?"
    if "Delete the old files so the project is clean again" in prompt:
        return (
            "Which files do you consider safe to delete? "
            "I do not want to remove the wrong project files."
        )
    if "The service times out after my changes" in prompt:
        return (
            "I cannot know the exact root cause from that alone. "
            "Check the changed config and the service logs first."
        )
    if "After I moved some modules" in prompt:
        return (
            "The import paths or package layout likely no longer match the moved modules. "
            "Check the failing import and verify it points to the new module location."
        )
    if "I need to rename a config key everywhere it matters" in prompt:
        return (
            "Update the config definition and every code path that reads or validates that key. "
            "Also check docs or tests that reference the old name."
        )
    if "My local API now returns 404 after a restart" in prompt:
        return (
            "Inspect the routing config that changed and compare it to the last working version, "
            "because the restart likely loaded a mismatched route definition."
        )
    raise AssertionError(f"unhandled prompt: {prompt}")


def _tool_call(call_id: str, name: str, arguments: dict[str, object]) -> dict[str, object]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _workspace_response_for_payload(payload: dict[str, object]) -> dict[str, object]:
    messages = payload["messages"]
    user_prompt = next(
        message["content"] for message in messages if message.get("role") == "user"
    )
    tool_messages = [message for message in messages if message.get("role") == "tool"]
    if "production endpoint" in user_prompt:
        if not tool_messages:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [_tool_call("call_read_app", "read", {"path": "config/app.toml"})],
            }
        if len(tool_messages) == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    _tool_call(
                        "call_edit_app",
                        "edit",
                        {
                            "path": "config/app.toml",
                            "old_text": 'api_base_url = "https://staging-api.example.com/v1"',
                            "new_text": 'api_base_url = "https://api.example.com/v1"',
                        },
                    )
                ],
            }
        return {
            "role": "assistant",
            "content": "Updated config/app.toml to use the production API base URL.",
        }
    if "timeout setting name" in user_prompt:
        if not tool_messages:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [_tool_call("call_read_cfg", "read", {"path": "config/app.toml"})],
            }
        if len(tool_messages) == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [_tool_call("call_read_docs", "read", {"path": "docs/config.md"})],
            }
        if len(tool_messages) == 2:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    _tool_call(
                        "call_edit_cfg",
                        "edit",
                        {
                            "path": "config/app.toml",
                            "old_text": "timeout_secs = 45",
                            "new_text": "request_timeout_secs = 45",
                        },
                    )
                ],
            }
        if len(tool_messages) == 3:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    _tool_call(
                        "call_edit_docs",
                        "edit",
                        {
                            "path": "docs/config.md",
                            "old_text": "`timeout_secs`",
                            "new_text": "`request_timeout_secs`",
                        },
                    )
                ],
            }
        return {
            "role": "assistant",
            "content": "Updated config/app.toml and docs/config.md to use request_timeout_secs.",
        }
    if "required env vars" in user_prompt:
        if not tool_messages:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [_tool_call("call_read_env", "read", {"path": "config/sample.env"})],
            }
        if len(tool_messages) == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [_tool_call("call_read_readme", "read", {"path": "README.md"})],
            }
        if len(tool_messages) == 2:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    _tool_call(
                        "call_write_readme",
                        "write",
                        {
                            "path": "README.md",
                            "content": (
                                "# Tiny API Service\n\n"
                                "Run the service locally after setting the required environment variables.\n\n"
                                "## Environment\n\n"
                                "Set these variables before starting the service.\n\n"
                                "- API_BASE_URL\n"
                                "- API_TOKEN\n"
                                "- REQUEST_TIMEOUT_SECS\n"
                            ),
                        },
                    )
                ],
            }
        return {
            "role": "assistant",
            "content": "Added an Environment section to README.md listing API_BASE_URL, API_TOKEN, and REQUEST_TIMEOUT_SECS.",
        }
    if "switch the API base URL to production in the config" in user_prompt:
        return {
            "role": "assistant",
            "content": "Which config should I update: config/app.toml or config/worker.toml?",
        }
    raise AssertionError(f"unhandled workspace prompt: {user_prompt}")


def test_bench_command_writes_result_file(tmp_path: Path, monkeypatch, capsys) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BenchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("AGENTMUX_RUN_ROOT", str(tmp_path / "runs" / "agentmux"))
        monkeypatch.setenv("AGENTMUX_BENCH_JUDGE_AUTH_FILE", str(tmp_path / "missing-auth.json"))
        mux_root = tmp_path / "mux" / "lab"
        mux_root.mkdir(parents=True)
        (mux_root / "benchstack.toml").write_text(
            f"""
[stack]
name = "benchstack"
track = "lab"
primary_service = "main"

[services.main]
engine = "vllm"
model = "bench-model"
host = "127.0.0.1"
port = {server.server_port}
            """.strip()
            + "\n",
            encoding="utf-8",
        )

        rc = main(["--root", str(tmp_path / "mux"), "bench", "benchstack"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "benchmark: benchstack (ghosty-local-agent)" in captured.out
        result_dir = tmp_path / "runs" / "agentmux" / "benchmarks"
        files = list(result_dir.glob("*.json"))
        assert len(files) == 1
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        assert payload["profile"] == "ghosty-local-agent"
        assert payload["summary"]["categories"]["quality_no_tools"]["total_cases"] == 12
        assert payload["summary"]["categories"]["quality_with_tools"]["total_cases"] == 4
        assert payload["request_accounting"]["local_workspace_tool_calls"] >= 1
        assert "vram" in payload["summary"]["categories"]
        assert payload["judge"]["enabled"] is False
        assert payload["declared_config"]["model"] == "bench-model"
        assert payload["observed_runtime"]["vllm_metrics"]["available"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_stream_request_ignores_reasoning_stream_output() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BenchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        metrics = _stream_request(
            f"http://127.0.0.1:{server.server_port}/v1",
            "bench-model",
            "Say hi",
            0,
            20,
        )
        assert metrics.client_observed_time_to_first_stream_event_seconds >= 0.0
        assert metrics.output_tokens == 3
        assert metrics.response_text == ""
        assert metrics.stream_fields_seen == ()
    finally:
        server.shutdown()
        server.server_close()



def test_workspace_message_text_uses_raw_content_and_reasoning_fields() -> None:
    assert _message_text({"content": "done"}) == "done"
    assert _message_text({"content": None, "reasoning_content": "thinking aloud"}) == ""
    assert _assistant_message_parts(
        {"content": "answer", "reasoning_content": "thinking aloud"}
    ) == ("answer", "thinking aloud")
    assert _assistant_message_parts(
        {"content": None, "reasoning_content": "thinking aloud"}
    ) == ("", "thinking aloud")


def test_chat_completion_uses_reasoning_when_content_is_empty(monkeypatch) -> None:
    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "reasoning_content": "final answer",
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        return _FakeResponse()

    monkeypatch.setattr("agentmux.bench.requests.post", fake_post)

    assert _chat_completion("http://example/v1", "model", "prompt", 20) == ""
    response, thinking = _chat_completion_parts("http://example/v1", "model", "prompt", 20)
    assert response == ""
    assert thinking == "final answer"


def test_rename_timeout_score_ignores_request_substring() -> None:
    before = {
        "config/app.toml": '[service]\nname = "web-api"\ntimeout_secs = 45\napi_base_url = "https://api.example.com/v1"\n',
        "docs/config.md": '# Config\n\n- `timeout_secs`: request timeout in seconds.\n- `api_base_url`: upstream API base URL.\n',
    }
    after = {
        "config/app.toml": '[service]\nname = "web-api"\nrequest_timeout_secs = 45\napi_base_url = "https://api.example.com/v1"\n',
        "docs/config.md": '# Config\n\n- `request_timeout_secs`: request timeout in seconds.\n- `api_base_url`: upstream API base URL.\n',
    }
    result = _score_rename_timeout_key_everywhere_needed(before, after, "updated both files", [], "final_answer")
    assert result["deterministic_failures"] == []
    assert result["file_checks"][0]["status"] == "pass"
    assert result["file_checks"][1]["status"] == "pass"


def test_load_judge_client_uses_pi_cli_provider(tmp_path: Path, monkeypatch) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("AGENTMUX_BENCH_JUDGE_AUTH_FILE", str(auth_path))
    monkeypatch.setenv("AGENTMUX_BENCH_JUDGE_PI_COMMAND", "pi")
    monkeypatch.setenv("AGENTMUX_BENCH_JUDGE_ENABLED", "1")

    judge = load_judge_client()

    assert judge.enabled is True
    assert judge.provider == "pi-cli"
    assert judge.base_url == "pi"


class _FakeCompletedProcess:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr



def test_judge_client_uses_single_batched_pi_cli_call(monkeypatch) -> None:
    calls = []

    def fake_run(args, capture_output, text, timeout, check):
        calls.append(args)
        assert "--provider" in args
        assert "openai-codex" in args
        assert "--model" in args
        payload = {
            "cases": [
                {
                    "case_id": "case",
                    "deterministic_score_fit": "fair",
                    "deterministic_notes": [],
                    "quality_note": "response was concise and useful",
                }
            ]
        }
        return _FakeCompletedProcess(
            '\n'.join(
                [
                    '{"type":"session"}',
                    '{"type":"message_end","message":{"role":"assistant","content":['
                    '{"type":"text","text":' + json.dumps(json.dumps(payload)) + '}]}}',
                ]
            )
        )

    monkeypatch.setenv("AGENTMUX_BENCH_JUDGE_PI_COMMAND", "pi")
    monkeypatch.setattr("agentmux.bench_judge.subprocess.run", fake_run)

    judge = JudgeClient(
        enabled=True,
        provider="pi-cli",
        model="gpt-5.4-mini",
        auth_source="/tmp/auth.json",
        base_url="pi",
    )

    result = judge.evaluate_many(
        [
            {
                "case_id": "case",
                "prompt": "prompt",
                "response": "response",
                "deterministic_context": {"score": 1.0},
            }
        ]
    )

    assert len(calls) == 1
    assert result["case"].deterministic_score_fit == "fair"
    assert result["case"].quality_note == "response was concise and useful"



def test_all_quality_cases_are_judge_enabled() -> None:
    assert QUALITY_CASES
    assert all(case.judge_eligible for case in QUALITY_CASES)
    assert all(case.default_judge_enabled for case in QUALITY_CASES)


def test_bench_score_avoids_false_deterministic_failures() -> None:
    judge = JudgeClient(
        enabled=False,
        provider="none",
        model="none",
        auth_source="/dev/null",
        base_url="http://localhost",
        reason="test",
    )

    prompt_to_case = {case.id: case for case in QUALITY_CASES}

    deterministic_cases = {
        "constrained_task_plan": (
            "1. Review the recent config diff.\n"
            "2. Compare it to the last working version.\n"
            "3. Revert the risky change and retest startup."
        ),
        "missing_path_requires_clarification": (
            "I can help update the base URL, but please specify which file you mean. "
            "Once you provide it, I can prepare the edit for review."
        ),
        "short_edit_strategy": (
            "Update the configuration file, environment variables, and docs that expose the key. "
            "Also review deployment scripts and logs that still reference the old name."
        ),
    }

    for case_id, response in deterministic_cases.items():
        result = evaluate_case(prompt_to_case[case_id], response, judge)
        assert result.deterministic_failures == []

    clarification = evaluate_case(
        prompt_to_case["missing_path_requires_clarification"],
        "I can help you update the base URL, but please specify the file you are referring to. "
        "Once you provide the file name, I can prepare the edit for review.",
        judge,
    )
    assert clarification.score == 1.0

    uncertainty = evaluate_case(
        prompt_to_case["insufficient_evidence_no_fabrication"],
        "I cannot determine the exact root cause from that alone. "
        "Please share the changed config and relevant logs so I can verify it.",
        judge,
    )
    assert uncertainty.score == 1.0


def test_judge_receives_deterministic_context_without_owning_score() -> None:
    class FakeJudge:
        enabled = True

        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str, dict[str, object]]] = []

        def evaluate(self, prompt: str, response: str, case_id: str, deterministic_context):
            self.calls.append((prompt, response, case_id, deterministic_context))
            return JudgeResult(
                deterministic_score_fit="too_harsh",
                deterministic_notes=["one length miss should not zero the case"],
                quality_note="failed deterministically but response was otherwise good",
            )

    judge = FakeJudge()
    case = next(item for item in QUALITY_CASES if item.id == "bounded_structured_summary")
    response = json.dumps(
        [
            "Request the user to specify the exact configuration file name.",
            "Ask the user to provide the current setting name to rename.",
        ]
    )

    result = evaluate_case(case, response, judge)

    assert result.score == 0.0
    assert result.judge is not None
    assert result.judge["deterministic_score_fit"] == "too_harsh"
    assert result.judge["deterministic_notes"] == ["one length miss should not zero the case"]
    assert (
        result.judge["quality_note"]
        == "failed deterministically but response was otherwise good"
    )
    assert judge.calls[0][2] == "bounded_structured_summary"
    assert judge.calls[0][3]["score"] == 0.0
    assert judge.calls[0][3]["deterministic_failures"] == ["each item must be under 10 words"]
