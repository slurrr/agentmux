from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_AUTH_PATH = Path("/home/poop/.pi/agent/auth.json")
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_PI_COMMAND = "pi"
_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class JudgeResult:
    deterministic_score_fit: str
    deterministic_notes: list[str]
    quality_note: str | None


@dataclass(frozen=True)
class JudgeClient:
    enabled: bool
    provider: str
    model: str
    auth_source: str
    base_url: str
    reason: str | None = None

    def evaluate(
        self,
        prompt: str,
        response: str,
        case_id: str,
        deterministic_context: dict[str, Any] | None = None,
    ) -> JudgeResult | None:
        results = self.evaluate_many(
            [
                {
                    "case_id": case_id,
                    "prompt": prompt,
                    "response": response,
                    "deterministic_context": deterministic_context,
                }
            ]
        )
        return results.get(case_id)

    def evaluate_many(self, cases: list[dict[str, Any]]) -> dict[str, JudgeResult]:
        if not self.enabled or not cases:
            return {}
        try:
            content = _run_pi_judge_many(model=self.model, cases=cases)
            parsed = _extract_json_object(content)
            if not isinstance(parsed, dict):
                return {}
            items = parsed.get("cases")
            if not isinstance(items, list):
                return {}
            results: dict[str, JudgeResult] = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                case_id = item.get("case_id")
                if not isinstance(case_id, str) or not case_id:
                    continue
                result = _parse_judge_result(item)
                if result is not None:
                    results[case_id] = result
            return results
        except Exception:
            return {}


def _parse_judge_result(parsed: dict[str, Any]) -> JudgeResult | None:
    deterministic_score_fit = parsed.get("deterministic_score_fit")
    deterministic_notes = parsed.get("deterministic_notes")
    quality_note = parsed.get("quality_note")
    if not isinstance(deterministic_score_fit, str):
        deterministic_score_fit = "mixed"
    if not isinstance(deterministic_notes, list) or not all(
        isinstance(item, str) for item in deterministic_notes
    ):
        deterministic_notes = []
    if not isinstance(quality_note, str) or not quality_note.strip():
        quality_note = None
    return JudgeResult(
        deterministic_score_fit=deterministic_score_fit,
        deterministic_notes=list(deterministic_notes),
        quality_note=quality_note,
    )


def _judge_user_content_many(cases: list[dict[str, Any]]) -> str:
    parts = [
        "Review all cases. Return JSON only with {\"cases\": [...]} where each item has "
        "case_id, deterministic_score_fit, deterministic_notes, quality_note. Only include "
        "cases where you have useful feedback.",
        json.dumps({"cases": cases}, indent=2, sort_keys=True),
    ]
    return "\n\n".join(parts)


def _extract_json_object(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_PATTERN.search(text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _judge_system_prompt() -> str:
    return (
        "You are reviewing a short local-agent benchmark response. Return JSON only "
        "with keys: deterministic_score_fit, deterministic_notes, quality_note. "
        "deterministic_score_fit must be one of: fair, too_harsh, too_lenient, mixed. "
        "deterministic_notes must be a very short array of strings explaining whether the "
        "machine-checked score seems accurate or misleading. quality_note must be either "
        "null or one short sentence with useful human-quality context not already captured "
        "by the deterministic result. Do not assign a score. Do not override the benchmark. "
        "Keep output minimal."
    )


def _run_pi_judge_many(*, model: str, cases: list[dict[str, Any]]) -> str:
    return _run_pi_with_prompt(
        model=model,
        system_prompt=_judge_system_prompt(),
        user_content=_judge_user_content_many(cases),
    )


def _extract_pi_assistant_text(stdout: str) -> str:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        text_parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        merged = "".join(text_parts).strip()
        if merged:
            return merged
    raise ValueError("No assistant text found in pi output")


def run_judge_audit(cases: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    if not cases:
        return []
    prompt = (
        "For each case, restate user intent in 1 line, then say if response actually fulfills it. "
        "Flag if technically correct but unhelpful. Quote the response fragment causing failure. "
        "Return JSON only as an array with keys: case_id, intent, fulfills_intent, "
        "technically_correct_but_unhelpful, flag, quote, note."
    )
    payload = json.dumps({"cases": cases}, indent=2, sort_keys=True)
    content = _run_pi_with_prompt(model=model, system_prompt=prompt, user_content=payload)
    parsed = _extract_json_object(content)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict) and isinstance(parsed.get("cases"), list):
        return [item for item in parsed["cases"] if isinstance(item, dict)]
    return []


def _run_pi_with_prompt(*, model: str, system_prompt: str, user_content: str) -> str:
    pi_command = os.environ.get("AGENTMUX_BENCH_JUDGE_PI_COMMAND", DEFAULT_PI_COMMAND)
    invocation = shlex.split(pi_command)
    if not invocation:
        raise ValueError("Empty AGENTMUX_BENCH_JUDGE_PI_COMMAND")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as handle:
        handle.write(system_prompt)
        system_prompt_path = handle.name
    try:
        args = [
            *invocation,
            "--mode",
            "json",
            "-p",
            "--no-session",
            "--provider",
            "openai-codex",
            "--model",
            model,
            "--append-system-prompt",
            system_prompt_path,
            user_content,
        ]
        result = subprocess.run(args, capture_output=True, text=True, timeout=90, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"pi exited with code {result.returncode}")
        return _extract_pi_assistant_text(result.stdout)
    finally:
        Path(system_prompt_path).unlink(missing_ok=True)


def load_judge_client() -> JudgeClient:
    auth_source = os.environ.get("AGENTMUX_BENCH_JUDGE_AUTH_FILE", str(DEFAULT_AUTH_PATH))
    model = os.environ.get("AGENTMUX_BENCH_JUDGE_MODEL", DEFAULT_MODEL)
    enabled_raw = os.environ.get("AGENTMUX_BENCH_JUDGE_ENABLED", "0").strip().lower()
    auth_path = Path(auth_source)
    if enabled_raw not in {"1", "true", "yes", "on"}:
        return JudgeClient(
            enabled=False,
            provider="pi-cli",
            model=model,
            auth_source=str(auth_path),
            base_url=os.environ.get("AGENTMUX_BENCH_JUDGE_PI_COMMAND", DEFAULT_PI_COMMAND),
            reason="disabled_by_env",
        )
    if not auth_path.exists():
        return JudgeClient(
            enabled=False,
            provider="pi-cli",
            model=model,
            auth_source=str(auth_path),
            base_url=os.environ.get("AGENTMUX_BENCH_JUDGE_PI_COMMAND", DEFAULT_PI_COMMAND),
            reason="auth_missing",
        )
    return JudgeClient(
        enabled=True,
        provider="pi-cli",
        model=model,
        auth_source=str(auth_path),
        base_url=os.environ.get("AGENTMUX_BENCH_JUDGE_PI_COMMAND", DEFAULT_PI_COMMAND),
    )
