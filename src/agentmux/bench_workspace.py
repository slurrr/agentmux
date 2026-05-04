from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

WORKSPACE_SYSTEM_PROMPT = (
    "You are a concise coding assistant working inside a temporary workspace. "
    "Use the available tools to inspect and edit files when needed. "
    "All paths are relative to the workspace root. "
    "Do not claim a file change is complete unless the workspace actually reflects it. "
    "Keep the final answer brief and concrete."
)

WORKSPACE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ls",
            "description": "List files or directories under the workspace root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to list."}
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read a UTF-8 text file from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to read."}
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Write a UTF-8 text file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to write."},
                    "content": {"type": "string", "description": "Full file contents."},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": (
                "Replace one exact text block in a UTF-8 text file. "
                "old_text must match exactly once."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to edit."},
                    "old_text": {"type": "string", "description": "Exact existing text."},
                    "new_text": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
        },
    },
]

_COMPLETION_PATTERN = re.compile(
    r"\b(?:i|we|it|that|this|the task|the edit|the change|it'?s)\s+"
    r"(?:am|have|has|had|is|was|were|been)?\s*"
    r"(?:done|completed|updated|deleted|renamed|fixed|changed|removed)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WorkspaceCase:
    id: str
    prompt: str
    fixture: str
    max_tokens: int = 2048
    max_turns: int = 8


WORKSPACE_CASES: tuple[WorkspaceCase, ...] = (
    WorkspaceCase(
        id="update_api_base_url",
        fixture="update_api_base_url",
        prompt=(
            "You are working in a small service workspace. The web API should now use the "
            "production endpoint. Update `config/app.toml` so `api_base_url` points to "
            "`https://api.example.com/v1`. Keep the rest of the file unchanged, then tell me "
            "briefly what you changed."
        ),
    ),
    WorkspaceCase(
        id="rename_timeout_key_everywhere_needed",
        fixture="rename_timeout_key_everywhere_needed",
        prompt=(
            "We standardized the timeout setting name. Update this workspace so the config and "
            "docs use `request_timeout_secs` instead of `timeout_secs`, preserving the current "
            "value and meaning. Then summarize the touched files in one short reply."
        ),
    ),
    WorkspaceCase(
        id="add_readme_environment_section",
        fixture="add_readme_environment_section",
        prompt=(
            "A new teammate keeps missing required env vars during local setup. Add a short "
            "`Environment` section to `README.md` using the existing variable names from "
            "`config/sample.env`. Keep it concise: a heading, one short sentence, and bullets "
            "for the required vars. Then tell me what you added."
        ),
    ),
    WorkspaceCase(
        id="ambiguous_production_switch_requires_clarification",
        fixture="ambiguous_production_switch_requires_clarification",
        prompt=(
            "Please switch the API base URL to production in the config and let me know when "
            "it's done. Keep your reply brief."
        ),
        max_tokens=2048,
        max_turns=4,
    ),
)


def run_workspace_benchmark(
    base_url: str,
    model_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    total_requests = 0
    total_tool_calls = 0
    total_invalid_tool_calls = 0
    for case in WORKSPACE_CASES:
        result = _run_workspace_case(case, base_url, model_name)
        results.append(result)
        tool_summary = result.get("tool_summary", {})
        total_requests += int(tool_summary.get("model_requests", 0))
        total_tool_calls += int(tool_summary.get("total_calls", 0))
        total_invalid_tool_calls += int(tool_summary.get("invalid_calls", 0))
    stats = {
        "model_requests": total_requests,
        "tool_calls": total_tool_calls,
        "invalid_tool_calls": total_invalid_tool_calls,
    }
    return results, stats


def _run_workspace_case(case: WorkspaceCase, base_url: str, model_name: str) -> dict[str, Any]:
    fixture_root = _fixture_root() / case.fixture
    with tempfile.TemporaryDirectory(prefix=f"agentmux-bench-{case.id}-") as temp_dir:
        workspace_root = Path(temp_dir) / "workspace"
        shutil.copytree(fixture_root, workspace_root)
        before = _snapshot_workspace(workspace_root)
        final_answer, thinking, trace, model_requests, stop_reason = _run_workspace_conversation(
            case,
            base_url,
            model_name,
            workspace_root,
        )
        after = _snapshot_workspace(workspace_root)
    evaluation = _evaluate_workspace_case(case, before, after, final_answer, trace, stop_reason)
    return {
        "id": case.id,
        "kind": "workspace",
        "group": "quality_with_tools",
        "fixture": case.fixture,
        "judge_eligible": False,
        "default_judge_enabled": False,
        "prompt": case.prompt,
        "response": final_answer,
        "thinking": thinking,
        "score": evaluation["score"],
        "passed": evaluation["passed"],
        "deterministic_failures": evaluation["deterministic_failures"],
        "rubric_passes": evaluation["rubric_passes"],
        "rubric_failures": evaluation["rubric_failures"],
        "reliability_flags": evaluation["reliability_flags"],
        "judge": None,
        "tool_trace": trace,
        "tool_summary": {
            "model_requests": model_requests,
            "total_calls": len(trace),
            "invalid_calls": sum(1 for item in trace if not item.get("valid", False)),
            "tool_counts": _tool_counts(trace),
        },
        "workspace": {
            "changed_files": sorted(_changed_files(before, after)),
            "file_checks": evaluation["file_checks"],
            "conversation_stop_reason": stop_reason,
        },
    }


def _run_workspace_conversation(
    case: WorkspaceCase,
    base_url: str,
    model_name: str,
    workspace_root: Path,
) -> tuple[str, str, list[dict[str, Any]], int, str]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": WORKSPACE_SYSTEM_PROMPT},
        {"role": "user", "content": case.prompt},
    ]
    trace: list[dict[str, Any]] = []
    model_requests = 0
    for _ in range(case.max_turns):
        model_requests += 1
        message = _tool_chat_completion(base_url, model_name, messages, case.max_tokens)
        response, thinking = _assistant_message_parts(message)
        assistant_message = _build_replay_assistant_message(message, response, thinking)
        messages.append(assistant_message)
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            for index, tool_call in enumerate(tool_calls, start=1):
                tool_result = _execute_tool_call(workspace_root, tool_call)
                trace.append(
                    {
                        "step": len(trace) + 1,
                        "call_id": tool_call.get("id") or f"call_{len(trace) + 1}",
                        "tool": tool_result["tool"],
                        "arguments": tool_result["arguments"],
                        "valid": tool_result["valid"],
                        "error": tool_result.get("error"),
                        "changed_files": tool_result.get("changed_files", []),
                        "result_preview": tool_result.get("result_preview", ""),
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id") or f"call_{index}",
                        "content": tool_result["tool_message"],
                    }
                )
            continue
        return response, thinking, trace, model_requests, "final_answer"
    return "", "", trace, model_requests, "max_turns"


def _build_replay_assistant_message(
    message: dict[str, Any], response: str, thinking: str
) -> dict[str, Any]:
    assistant_message: dict[str, Any] = {"role": "assistant", "content": response or None}
    if thinking:
        assistant_message["reasoning"] = thinking
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        assistant_message["tool_calls"] = tool_calls
    return assistant_message


def _tool_chat_completion(
    base_url: str,
    model_name: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> dict[str, Any]:
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "tools": WORKSPACE_TOOLS,
        "tool_choice": "auto",
    }
    response = requests.post(f"{base_url}/chat/completions", json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return dict(data["choices"][0]["message"])


def _execute_tool_call(workspace_root: Path, tool_call: dict[str, Any]) -> dict[str, Any]:
    function_block = tool_call.get("function") or {}
    tool_name = str(function_block.get("name") or "")
    raw_arguments = function_block.get("arguments")
    try:
        arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else {}
    except json.JSONDecodeError:
        return {
            "tool": tool_name or "unknown",
            "arguments": raw_arguments,
            "valid": False,
            "error": "invalid json arguments",
            "tool_message": "error: invalid json arguments",
            "result_preview": "error: invalid json arguments",
            "changed_files": [],
        }
    try:
        result = _run_tool(workspace_root, tool_name, arguments)
        tool_message = _tool_result_message_text(result)
        return {
            "tool": tool_name,
            "arguments": arguments,
            "valid": True,
            "tool_message": tool_message,
            "result_preview": _truncate_preview(result.get("preview") or tool_message),
            "changed_files": list(result.get("changed_files") or []),
        }
    except Exception as exc:  # noqa: BLE001
        tool_message = f"error: {exc}"
        return {
            "tool": tool_name or "unknown",
            "arguments": arguments,
            "valid": False,
            "error": str(exc),
            "tool_message": tool_message,
            "result_preview": tool_message,
            "changed_files": [],
        }


def _tool_result_message_text(result: dict[str, Any]) -> str:
    if isinstance(result.get("content"), str) and result["content"]:
        return result["content"]
    if isinstance(result.get("entries"), list):
        return "\n".join(str(item) for item in result["entries"])
    preview = result.get("preview")
    if isinstance(preview, str) and preview:
        return preview
    return "(no tool output)"


def _run_tool(workspace_root: Path, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "ls":
        if set(arguments.keys()) - {"path"}:
            raise ValueError("ls only accepts: path")
        target = _resolve_workspace_path(workspace_root, str(arguments.get("path") or "."))
        if not target.exists():
            raise FileNotFoundError(f"path not found: {target.relative_to(workspace_root)}")
        if target.is_file():
            entries = [target.name]
        else:
            entries = [item.name + ("/" if item.is_dir() else "") for item in sorted(target.iterdir())]
        preview = "\n".join(entries)
        return {"path": str(target.relative_to(workspace_root)), "entries": entries, "preview": preview}
    if tool_name == "read":
        if set(arguments.keys()) != {"path"}:
            raise ValueError("read requires exactly: path")
        target = _resolve_workspace_path(workspace_root, str(arguments["path"]))
        if not target.is_file():
            raise FileNotFoundError(f"file not found: {target.relative_to(workspace_root)}")
        content = target.read_text(encoding="utf-8")
        return {
            "path": str(target.relative_to(workspace_root)),
            "content": content,
            "preview": _truncate_preview(content),
        }
    if tool_name == "write":
        if set(arguments.keys()) != {"path", "content"}:
            raise ValueError("write requires exactly: path, content")
        target = _resolve_workspace_path(workspace_root, str(arguments["path"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(arguments["content"]), encoding="utf-8")
        return {
            "path": str(target.relative_to(workspace_root)),
            "changed_files": [str(target.relative_to(workspace_root))],
            "preview": f"wrote {target.relative_to(workspace_root)}",
        }
    if tool_name == "edit":
        if set(arguments.keys()) != {"path", "old_text", "new_text"}:
            raise ValueError("edit requires exactly: path, old_text, new_text")
        target = _resolve_workspace_path(workspace_root, str(arguments["path"]))
        if not target.is_file():
            raise FileNotFoundError(f"file not found: {target.relative_to(workspace_root)}")
        old_text = str(arguments["old_text"])
        new_text = str(arguments["new_text"])
        content = target.read_text(encoding="utf-8")
        match_count = content.count(old_text)
        if match_count != 1:
            raise ValueError(f"old_text must match exactly once; matched {match_count} times")
        target.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
        return {
            "path": str(target.relative_to(workspace_root)),
            "changed_files": [str(target.relative_to(workspace_root))],
            "preview": f"edited {target.relative_to(workspace_root)}",
        }
    raise ValueError(f"unsupported tool: {tool_name}")


def _resolve_workspace_path(workspace_root: Path, raw_path: str) -> Path:
    if not raw_path:
        raise ValueError("path must not be empty")
    candidate = (workspace_root / raw_path).resolve()
    root = workspace_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("path escapes workspace root")
    return candidate


def _snapshot_workspace(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
    return snapshot


def _changed_files(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {path for path in set(before) | set(after) if before.get(path) != after.get(path)}


def _tool_counts(trace: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in trace:
        tool = str(item.get("tool") or "unknown")
        counts[tool] = counts.get(tool, 0) + 1
    return counts


def _assistant_message_parts(message: dict[str, Any]) -> tuple[str, str]:
    content = message.get("content")
    response = content if isinstance(content, str) else "" if content is None else str(content)
    reasoning = message.get("reasoning_content")
    if reasoning is None:
        reasoning = message.get("reasoning")
    thinking = reasoning if isinstance(reasoning, str) else "" if reasoning is None else str(reasoning)
    return response.strip(), thinking.strip()


def _message_text(message: dict[str, Any]) -> str:
    response, _thinking = _assistant_message_parts(message)
    return response


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[2] / "bench" / "fixtures" / "workspace"


def _truncate_preview(text: str, max_chars: int = 220) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _base_flags() -> dict[str, bool]:
    return {
        "structured_output_failure": False,
        "constraint_violation": False,
        "hallucination_fabrication": False,
        "empty_evasive_degenerate": False,
    }


def _contains_completion_claim(text: str) -> bool:
    return bool(_COMPLETION_PATTERN.search(text))


def _evaluate_workspace_case(
    case: WorkspaceCase,
    before: dict[str, str],
    after: dict[str, str],
    final_answer: str,
    trace: list[dict[str, Any]],
    stop_reason: str,
) -> dict[str, Any]:
    handlers = {
        "update_api_base_url": _score_update_api_base_url,
        "rename_timeout_key_everywhere_needed": _score_rename_timeout_key_everywhere_needed,
        "add_readme_environment_section": _score_add_readme_environment_section,
        "ambiguous_production_switch_requires_clarification": _score_ambiguous_production_switch_requires_clarification,
    }
    return handlers[case.id](before, after, final_answer, trace, stop_reason)


def _finalize_evaluation(
    deterministic_failures: list[str],
    rubric_passes: list[str],
    rubric_failures: list[str],
    reliability_flags: dict[str, bool],
    file_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    if deterministic_failures:
        score = 0.0
    else:
        total = len(rubric_passes) + len(rubric_failures)
        score = 1.0 if total == 0 else len(rubric_passes) / total
    return {
        "score": round(score, 3),
        "passed": not deterministic_failures and score >= 0.75,
        "deterministic_failures": deterministic_failures,
        "rubric_passes": rubric_passes,
        "rubric_failures": rubric_failures,
        "reliability_flags": reliability_flags,
        "file_checks": file_checks,
    }


def _invalid_tool_failures(trace: list[dict[str, Any]], flags: dict[str, bool]) -> list[str]:
    failures: list[str] = []
    invalid = [item for item in trace if not item.get("valid", False)]
    if invalid:
        flags["constraint_violation"] = True
        failures.append(f"invalid tool calls: {len(invalid)}")
    return failures


def _tool_used_on_path(trace: list[dict[str, Any]], tool_name: str, path: str) -> bool:
    for item in trace:
        if item.get("tool") != tool_name:
            continue
        arguments = item.get("arguments")
        if isinstance(arguments, dict) and arguments.get("path") == path:
            return True
    return False


def _score_update_api_base_url(
    before: dict[str, str],
    after: dict[str, str],
    final_answer: str,
    trace: list[dict[str, Any]],
    stop_reason: str,
) -> dict[str, Any]:
    flags = _base_flags()
    deterministic = _invalid_tool_failures(trace, flags)
    rubric_passes: list[str] = []
    rubric_failures: list[str] = []
    changed = _changed_files(before, after)
    file_checks = [
        {
            "path": "config/app.toml",
            "status": "pass"
            if 'api_base_url = "https://api.example.com/v1"' in after.get("config/app.toml", "")
            else "fail",
            "check": "api_base_url updated to production value",
        }
    ]
    if 'api_base_url = "https://api.example.com/v1"' not in after.get("config/app.toml", ""):
        deterministic.append("config/app.toml was not updated to the production URL")
    if changed != {"config/app.toml"}:
        flags["constraint_violation"] = True
        deterministic.append("only config/app.toml should change")
    if stop_reason != "final_answer":
        deterministic.append("conversation did not reach a final answer")
    if _tool_used_on_path(trace, "read", "config/app.toml"):
        rubric_passes.append("read target file before editing")
    else:
        rubric_failures.append("did not read config/app.toml before editing")
    if any(item.get("tool") in {"edit", "write"} for item in trace):
        rubric_passes.append("used a file-editing tool")
    else:
        rubric_failures.append("did not use a file-editing tool")
    lowered = final_answer.lower()
    if "app.toml" in lowered or "config/app.toml" in lowered:
        rubric_passes.append("final answer mentioned the changed file")
    else:
        rubric_failures.append("final answer did not mention the changed file")
    if "api.example.com" in lowered or "production" in lowered:
        rubric_passes.append("final answer reflected the actual change")
    else:
        rubric_failures.append("final answer did not clearly reflect the actual change")
    return _finalize_evaluation(deterministic, rubric_passes, rubric_failures, flags, file_checks)


def _score_rename_timeout_key_everywhere_needed(
    before: dict[str, str],
    after: dict[str, str],
    final_answer: str,
    trace: list[dict[str, Any]],
    stop_reason: str,
) -> dict[str, Any]:
    flags = _base_flags()
    deterministic = _invalid_tool_failures(trace, flags)
    rubric_passes: list[str] = []
    rubric_failures: list[str] = []
    changed = _changed_files(before, after)
    config_text = after.get("config/app.toml", "")
    docs_text = after.get("docs/config.md", "")
    config_lines = {line.strip() for line in config_text.splitlines() if line.strip()}
    docs_lines = {line.strip() for line in docs_text.splitlines() if line.strip()}
    file_checks = [
        {
            "path": "config/app.toml",
            "status": "pass"
            if "request_timeout_secs = 45" in config_lines and "timeout_secs = 45" not in config_lines
            else "fail",
            "check": "config key renamed and value preserved",
        },
        {
            "path": "docs/config.md",
            "status": "pass"
            if "- `request_timeout_secs`: request timeout in seconds." in docs_lines
            and "- `timeout_secs`: request timeout in seconds." not in docs_lines
            else "fail",
            "check": "docs updated to new key",
        },
    ]
    if "request_timeout_secs = 45" not in config_lines or "timeout_secs = 45" in config_lines:
        deterministic.append("config/app.toml did not cleanly rename timeout_secs")
    if (
        "- `request_timeout_secs`: request timeout in seconds." not in docs_lines
        or "- `timeout_secs`: request timeout in seconds." in docs_lines
    ):
        deterministic.append("docs/config.md did not cleanly rename timeout_secs")
    if changed != {"config/app.toml", "docs/config.md"}:
        flags["constraint_violation"] = True
        deterministic.append("only config/app.toml and docs/config.md should change")
    if stop_reason != "final_answer":
        deterministic.append("conversation did not reach a final answer")
    if _tool_used_on_path(trace, "read", "config/app.toml") and _tool_used_on_path(
        trace, "read", "docs/config.md"
    ):
        rubric_passes.append("read both target files before editing")
    else:
        rubric_failures.append("did not inspect both target files before editing")
    if sum(1 for item in trace if item.get("tool") in {"edit", "write"}) >= 2:
        rubric_passes.append("updated both target files")
    else:
        rubric_failures.append("tool trace does not show both file updates")
    lowered = final_answer.lower()
    if "app.toml" in lowered and "config.md" in lowered:
        rubric_passes.append("final answer mentioned both touched files")
    elif "config" in lowered and "docs" in lowered:
        rubric_passes.append("final answer summarized both touched areas")
    else:
        rubric_failures.append("final answer did not clearly mention both touched files")
    return _finalize_evaluation(deterministic, rubric_passes, rubric_failures, flags, file_checks)


def _score_add_readme_environment_section(
    before: dict[str, str],
    after: dict[str, str],
    final_answer: str,
    trace: list[dict[str, Any]],
    stop_reason: str,
) -> dict[str, Any]:
    flags = _base_flags()
    deterministic = _invalid_tool_failures(trace, flags)
    rubric_passes: list[str] = []
    rubric_failures: list[str] = []
    changed = _changed_files(before, after)
    readme_text = after.get("README.md", "")
    sample_env_text = before.get("config/sample.env", "")
    required_vars = [
        line.split("=", 1)[0].strip()
        for line in sample_env_text.splitlines()
        if line.strip() and "=" in line
    ]
    file_checks = [
        {
            "path": "README.md",
            "status": "pass" if "## Environment" in readme_text else "fail",
            "check": "README has an Environment section",
        },
        {
            "path": "README.md",
            "status": "pass" if all(var in readme_text for var in required_vars) else "fail",
            "check": "README lists required env vars from config/sample.env",
        },
    ]
    if "## Environment" not in readme_text:
        deterministic.append("README.md is missing the Environment section")
    missing = [var for var in required_vars if var not in readme_text]
    if missing:
        deterministic.append(f"README.md is missing env vars: {', '.join(missing)}")
    if after.get("config/sample.env") != before.get("config/sample.env"):
        flags["constraint_violation"] = True
        deterministic.append("config/sample.env should not be modified")
    if changed != {"README.md"}:
        flags["constraint_violation"] = True
        deterministic.append("only README.md should change")
    if stop_reason != "final_answer":
        deterministic.append("conversation did not reach a final answer")
    if _tool_used_on_path(trace, "read", "config/sample.env"):
        rubric_passes.append("read config/sample.env before editing README")
    else:
        rubric_failures.append("did not read config/sample.env before editing README")
    lowered = final_answer.lower()
    if "readme" in lowered and "environment" in lowered:
        rubric_passes.append("final answer described the README environment update")
    else:
        rubric_failures.append("final answer did not clearly describe the README change")
    if any(var.lower() in lowered for var in ["api_base_url", "api_token", "request_timeout_secs"]):
        rubric_passes.append("final answer reflected actual env names")
    else:
        rubric_failures.append("final answer did not reflect the actual env names used")
    return _finalize_evaluation(deterministic, rubric_passes, rubric_failures, flags, file_checks)


def _score_ambiguous_production_switch_requires_clarification(
    before: dict[str, str],
    after: dict[str, str],
    final_answer: str,
    trace: list[dict[str, Any]],
    stop_reason: str,
) -> dict[str, Any]:
    flags = _base_flags()
    deterministic = _invalid_tool_failures(trace, flags)
    rubric_passes: list[str] = []
    rubric_failures: list[str] = []
    changed = _changed_files(before, after)
    file_checks = [
        {
            "path": "workspace",
            "status": "pass" if not changed else "fail",
            "check": "workspace remains unchanged while waiting for clarification",
        }
    ]
    if changed:
        flags["constraint_violation"] = True
        deterministic.append("workspace should remain unchanged for this ambiguous request")
    lowered = final_answer.lower()
    if _contains_completion_claim(final_answer):
        flags["hallucination_fabrication"] = True
        deterministic.append("final answer claimed completion for an ambiguous request")
    if stop_reason != "final_answer":
        deterministic.append("conversation did not reach a final answer")
    if "?" in final_answer:
        rubric_passes.append("final answer asked a clarifying question")
    else:
        rubric_failures.append("final answer did not ask a clarifying question")
    if "which" in lowered and ("app" in lowered or "worker" in lowered or "config" in lowered):
        rubric_passes.append("final answer made the ambiguity explicit")
    else:
        rubric_failures.append("final answer did not make the ambiguity explicit")
    if not final_answer.strip():
        flags["empty_evasive_degenerate"] = True
        rubric_failures.append("final answer was empty")
    return _finalize_evaluation(deterministic, rubric_passes, rubric_failures, flags, file_checks)
