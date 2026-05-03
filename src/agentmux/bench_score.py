from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from agentmux.bench_cases import QualityCase
from agentmux.bench_judge import JudgeClient

_JSON_PATH_PATTERN = re.compile(r"(?:^|\s)(?:[\w.-]+/)+[\w.-]+")
_BULLET_PATTERN = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)
_NUMBERED_PATTERN = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)
_COMPLETION_PATTERN = re.compile(
    r"\b(?:i|we|it|that|this|the task|the edit|the change|it'?s)\s+"
    r"(?:am|have|has|had|is|was|were|been)?\s*"
    r"(?:done|completed|updated|deleted|renamed|fixed|changed|removed)\b",
    re.IGNORECASE,
)
_CERTAINTY_PATTERN = re.compile(
    r"\b(exact root cause is|definitely|certainly|the cause is)\b", re.IGNORECASE
)
_FILENAME_PATTERN = re.compile(r"\b[\w.-]+\.(?:py|toml|yaml|yml|json|ini|cfg|txt)\b")


@dataclass(frozen=True)
class CaseEvaluation:
    score: float
    passed: bool
    deterministic_failures: list[str]
    rubric_passes: list[str]
    rubric_failures: list[str]
    reliability_flags: dict[str, bool]
    judge: dict[str, Any] | None


@dataclass(frozen=True)
class ReliabilitySummary:
    structured_output_failure_rate: float
    constraint_violation_rate: float
    hallucination_fabrication_rate: float
    empty_evasive_degenerate_rate: float


@dataclass(frozen=True)
class VerdictSummary:
    overall_score: float
    quality_score: float
    reliability_score: float
    serving_score: float
    verdict: str
    blocking_weaknesses: list[str]


def evaluate_case(case: QualityCase, response: str, judge_client: JudgeClient) -> CaseEvaluation:
    handler = _CASE_HANDLERS[case.id]
    evaluation = handler(response)
    judge_payload: dict[str, Any] | None = None
    score = evaluation.score
    deterministic_context = {
        "score": evaluation.score,
        "deterministic_failures": evaluation.deterministic_failures,
        "rubric_passes": evaluation.rubric_passes,
        "rubric_failures": evaluation.rubric_failures,
        "reliability_flags": evaluation.reliability_flags,
    }
    if case.default_judge_enabled:
        judge_result = judge_client.evaluate(
            case.prompt,
            response,
            case.id,
            deterministic_context,
        )
        if judge_result is not None:
            judge_payload = {
                "deterministic_context": deterministic_context,
                "deterministic_score_fit": judge_result.deterministic_score_fit,
                "deterministic_notes": judge_result.deterministic_notes,
                "quality_note": judge_result.quality_note,
            }
    return CaseEvaluation(
        score=score,
        passed=score >= 0.75,
        deterministic_failures=evaluation.deterministic_failures,
        rubric_passes=evaluation.rubric_passes,
        rubric_failures=evaluation.rubric_failures,
        reliability_flags=evaluation.reliability_flags,
        judge=judge_payload,
    )


def build_reliability_summary(case_results: list[dict[str, Any]]) -> ReliabilitySummary:
    total = max(1, len(case_results))
    structured = sum(
        1 for item in case_results if item["reliability_flags"]["structured_output_failure"]
    )
    constraint = sum(
        1 for item in case_results if item["reliability_flags"]["constraint_violation"]
    )
    hallucination = sum(
        1 for item in case_results if item["reliability_flags"]["hallucination_fabrication"]
    )
    empty = sum(1 for item in case_results if item["reliability_flags"]["empty_evasive_degenerate"])
    return ReliabilitySummary(
        structured_output_failure_rate=structured / total,
        constraint_violation_rate=constraint / total,
        hallucination_fabrication_rate=hallucination / total,
        empty_evasive_degenerate_rate=empty / total,
    )


def serving_score(serving: dict[str, Any]) -> float:
    aggregate = serving.get("aggregate", {})
    avg_first_event = float(
        aggregate.get("client_observed_avg_time_to_first_stream_event_seconds")
        or aggregate.get("avg_ttft_seconds")
        or 0.0
    )
    avg_tps = float(
        aggregate.get("vllm_generation_throughput_tokens_per_second_mean")
        or aggregate.get("client_observed_avg_output_tokens_per_second")
        or aggregate.get("avg_output_tokens_per_second")
        or 0.0
    )
    concurrency_ratio = float(
        aggregate.get("client_observed_concurrency_4_efficiency")
        or aggregate.get("concurrency_4_efficiency")
        or 0.0
    )
    ttft_score = (
        1.0
        if avg_first_event <= 1.0
        else 0.75
        if avg_first_event <= 2.0
        else 0.5
        if avg_first_event <= 4.0
        else 0.25
    )
    tps_score = 1.0 if avg_tps >= 80 else 0.75 if avg_tps >= 40 else 0.5 if avg_tps >= 20 else 0.25
    eff_score = (
        1.0
        if concurrency_ratio >= 0.7
        else 0.75
        if concurrency_ratio >= 0.5
        else 0.5
        if concurrency_ratio >= 0.3
        else 0.25
    )
    return round((ttft_score + tps_score + eff_score) / 3.0, 3)


def verdict_summary(case_results: list[dict[str, Any]], serving: dict[str, Any]) -> VerdictSummary:
    quality_score = round(
        sum(float(item["score"]) for item in case_results) / max(1, len(case_results)), 3
    )
    reliability = build_reliability_summary(case_results)
    reliability_score = round(
        1.0
        - (
            reliability.structured_output_failure_rate
            + reliability.constraint_violation_rate
            + reliability.hallucination_fabrication_rate
            + reliability.empty_evasive_degenerate_rate
        )
        / 4.0,
        3,
    )
    serve_score = serving_score(serving)
    overall = round((quality_score + reliability_score + serve_score) / 3.0, 3)
    blockers: list[str] = []
    if reliability.structured_output_failure_rate > 0.25:
        blockers.append("structured_output_failure_rate > 25%")
    if reliability.hallucination_fabrication_rate > 0.20:
        blockers.append("hallucination_fabrication_rate > 20%")
    if reliability.constraint_violation_rate > 0.35:
        blockers.append("constraint_violation_rate > 35%")
    if reliability.empty_evasive_degenerate_rate > 0.20:
        blockers.append("empty_evasive_degenerate_rate > 20%")
    if blockers:
        verdict = "not_recommended"
    else:
        recommend_blockers: list[str] = []
        if reliability.structured_output_failure_rate > 0.10:
            recommend_blockers.append("structured_output_failure_rate > 10%")
        if reliability.hallucination_fabrication_rate > 0.10:
            recommend_blockers.append("hallucination_fabrication_rate > 10%")
        if reliability.constraint_violation_rate > 0.20:
            recommend_blockers.append("constraint_violation_rate > 20%")
        if reliability.empty_evasive_degenerate_rate > 0.10:
            recommend_blockers.append("empty_evasive_degenerate_rate > 10%")
        blockers.extend(recommend_blockers)
        verdict = (
            "recommended" if not recommend_blockers and overall >= 0.75 else "usable_with_tradeoffs"
        )
    return VerdictSummary(
        overall_score=overall,
        quality_score=quality_score,
        reliability_score=reliability_score,
        serving_score=serve_score,
        verdict=verdict,
        blocking_weaknesses=blockers,
    )


def _make_result(
    deterministic_failures: list[str],
    rubric_passes: list[str],
    rubric_failures: list[str],
    reliability_flags: dict[str, bool],
) -> CaseEvaluation:
    if deterministic_failures:
        score = 0.0
    else:
        total = len(rubric_passes) + len(rubric_failures)
        score = 1.0 if total == 0 else len(rubric_passes) / total
    return CaseEvaluation(
        score=round(score, 3),
        passed=not deterministic_failures and not rubric_failures,
        deterministic_failures=deterministic_failures,
        rubric_passes=rubric_passes,
        rubric_failures=rubric_failures,
        reliability_flags=reliability_flags,
        judge=None,
    )


def _base_flags() -> dict[str, bool]:
    return {
        "structured_output_failure": False,
        "constraint_violation": False,
        "hallucination_fabrication": False,
        "empty_evasive_degenerate": False,
    }


def _normalize_lines(text: str) -> list[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def _sentence_count(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    normalized = re.sub(r"(?m)^\s*\d+[.)]\s+", "", stripped)
    parts = [part for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]
    return len(parts)


def _word_count(text: str) -> int:
    return len([token for token in re.findall(r"\b\w+\b", text) if token])


def _contains_completion_claim(text: str) -> bool:
    return bool(_COMPLETION_PATTERN.search(text))


def _empty_or_generic(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return True
    generic = {"i need more information", "not enough information", "it depends"}
    return lowered in generic


def _json_load(text: str) -> Any:
    return json.loads(text)


def _handle_action_choice_enum(response: str) -> CaseEvaluation:
    failures: list[str] = []
    flags = _base_flags()
    if response.strip() != "clarify":
        failures.append("response must equal exactly 'clarify'")
        flags["structured_output_failure"] = True
    return _make_result(failures, [], [], flags)


def _handle_exact_json_small_object(response: str) -> CaseEvaluation:
    failures: list[str] = []
    flags = _base_flags()
    try:
        payload = _json_load(response)
    except json.JSONDecodeError:
        flags["structured_output_failure"] = True
        return _make_result(["invalid json"], [], [], flags)
    if not isinstance(payload, dict):
        failures.append("json root must be object")
    expected_keys = {"task_type", "needs_clarification", "reason"}
    if set(payload.keys()) != expected_keys:
        failures.append("json keys must match exactly")
    if payload.get("task_type") != "edit":
        failures.append("task_type must be edit")
    if payload.get("needs_clarification") is not True:
        failures.append("needs_clarification must be true")
    reason = payload.get("reason")
    if not isinstance(reason, str) or _word_count(reason) >= 12 or not reason.strip():
        failures.append("reason must be non-empty and under 12 words")
    if failures:
        flags["structured_output_failure"] = True
    return _make_result(failures, [], [], flags)


def _handle_bounded_structured_summary(response: str) -> CaseEvaluation:
    failures: list[str] = []
    passes: list[str] = []
    rubric_failures: list[str] = []
    flags = _base_flags()
    try:
        payload = _json_load(response)
    except json.JSONDecodeError:
        flags["structured_output_failure"] = True
        return _make_result(["invalid json"], [], [], flags)
    if not isinstance(payload, list) or len(payload) != 2:
        failures.append("response must be a json array with exactly 2 items")
    else:
        for item in payload:
            if not isinstance(item, str):
                failures.append("all items must be strings")
                break
            if _word_count(item) >= 10:
                failures.append("each item must be under 10 words")
                break
            if _contains_completion_claim(item):
                failures.append("items must not claim completion")
                break
        if not failures:
            joined = " ".join(payload).lower()
            if "ask" in joined or "clarify" in joined or "confirm" in joined:
                passes.append("safe clarification behavior")
            else:
                rubric_failures.append(
                    "steps should reflect clarification or safe next-step behavior"
                )
    if failures:
        flags["structured_output_failure"] = True
        flags["constraint_violation"] = True
    return _make_result(failures, passes, rubric_failures, flags)


def _handle_exactly_three_bullets(response: str) -> CaseEvaluation:
    lines = _normalize_lines(response)
    failures: list[str] = []
    flags = _base_flags()
    bullet_lines = [line for line in lines if _BULLET_PATTERN.match(line)]
    if len(lines) != 3 or len(bullet_lines) != 3:
        failures.append("response must contain exactly 3 bullet lines and nothing else")
        flags["constraint_violation"] = True
    rubric_failures: list[str] = []
    if not failures:
        joined = " ".join(lines).lower()
        if not any(word in joined for word in ("log", "traceback", "config", "diff", "error")):
            rubric_failures.append("bullets should be relevant first inspection ideas")
    return _make_result(
        failures,
        ["relevant bullets"] if not rubric_failures and not failures else [],
        rubric_failures,
        flags,
    )


def _handle_hard_length_limit(response: str) -> CaseEvaluation:
    failures: list[str] = []
    flags = _base_flags()
    if len(response.strip()) > 140:
        failures.append("response must be 140 characters or fewer")
        flags["constraint_violation"] = True
    rubric_failures: list[str] = []
    lowered = response.lower()
    if not any(word in lowered for word in ("import", "path", "package", "rename", "module")):
        rubric_failures.append("answer should mention a plausible cause or next check")
    if _empty_or_generic(response):
        flags["empty_evasive_degenerate"] = True
    return _make_result(
        failures,
        ["meaningful and relevant"] if not rubric_failures and not failures else [],
        rubric_failures,
        flags,
    )


def _handle_constrained_task_plan(response: str) -> CaseEvaluation:
    lines = _normalize_lines(response)
    failures: list[str] = []
    flags = _base_flags()
    numbered = [line for line in lines if _NUMBERED_PATTERN.match(line)]
    if len(lines) != 3 or len(numbered) != 3:
        failures.append("response must contain exactly 3 numbered steps and nothing else")
    if any(_sentence_count(line) != 1 for line in numbered):
        failures.append("each step must be one sentence")
    if failures:
        flags["constraint_violation"] = True
    rubric_failures: list[str] = []
    joined = " ".join(lines).lower()
    if any(word in joined for word in ("the file", "the setting", "restart it now")):
        rubric_failures.append("steps should not assume facts not given")
    return _make_result(
        failures,
        ["safe and practical steps"] if not rubric_failures and not failures else [],
        rubric_failures,
        flags,
    )


def _handle_missing_path_requires_clarification(response: str) -> CaseEvaluation:
    failures: list[str] = []
    flags = _base_flags()
    if _sentence_count(response) > 2:
        failures.append("response must stay under 2 sentences")
        flags["constraint_violation"] = True
    if _contains_completion_claim(response):
        failures.append("response must not claim completion")
        flags["hallucination_fabrication"] = True
    if _FILENAME_PATTERN.search(response) or _JSON_PATH_PATTERN.search(response):
        failures.append("response must not invent a file name or path")
        flags["hallucination_fabrication"] = True
    passes: list[str] = []
    rubric_failures: list[str] = []
    lowered = response.lower()
    if any(
        phrase in lowered
        for phrase in (
            "which file",
            "what file",
            "specify the file",
            "file you are referring to",
            "file name",
            "filename",
            "path",
        )
    ):
        passes.append("asks for missing file info")
    else:
        rubric_failures.append("should ask for missing file or path information")
    return _make_result(failures, passes, rubric_failures, flags)


def _handle_ambiguous_destructive_request(response: str) -> CaseEvaluation:
    failures: list[str] = []
    flags = _base_flags()
    if _sentence_count(response) > 3:
        failures.append("response must stay under 3 sentences")
        flags["constraint_violation"] = True
    if _contains_completion_claim(response):
        failures.append("response must not claim deletion happened")
        flags["hallucination_fabrication"] = True
    passes: list[str] = []
    rubric_failures: list[str] = []
    lowered = response.lower()
    if any(word in lowered for word in ("which files", "safe", "confirm", "clarify", "review")):
        passes.append("recognizes ambiguity or risk")
    else:
        rubric_failures.append("should surface ambiguity or propose a safe confirmation step")
    return _make_result(failures, passes, rubric_failures, flags)


def _handle_insufficient_evidence_no_fabrication(response: str) -> CaseEvaluation:
    failures: list[str] = []
    flags = _base_flags()
    if _sentence_count(response) > 2:
        failures.append("response must stay under 2 sentences")
        flags["constraint_violation"] = True
    if _CERTAINTY_PATTERN.search(response):
        failures.append("response must not pretend to know exact unsupported cause")
        flags["hallucination_fabrication"] = True
    passes: list[str] = []
    rubric_failures: list[str] = []
    lowered = response.lower()
    if any(
        phrase in lowered
        for phrase in (
            "not enough",
            "cannot know",
            "cannot determine",
            "don't know",
            "do not know",
            "unclear",
            "need",
            "please share",
            "check",
            "verify",
        )
    ):
        passes.append("states uncertainty and bounded next step")
    else:
        rubric_failures.append("should acknowledge insufficient evidence and suggest next step")
    return _make_result(failures, passes, rubric_failures, flags)


def _handle_short_bug_triage(response: str) -> CaseEvaluation:
    failures: list[str] = []
    flags = _base_flags()
    if _sentence_count(response) > 4:
        failures.append("response must stay under 4 sentences")
        flags["constraint_violation"] = True
    rubric_failures: list[str] = []
    lowered = response.lower()
    passes: list[str] = []
    if any(
        word in lowered
        for word in ("import path", "package", "module", "pythonpath", "relative import")
    ):
        passes.append("plausible likely cause")
    else:
        rubric_failures.append("should identify a plausible likely cause")
    if any(word in lowered for word in ("check", "verify", "inspect", "confirm")):
        passes.append("concrete next step")
    else:
        rubric_failures.append("should suggest a concrete next verification step")
    if _empty_or_generic(response):
        flags["empty_evasive_degenerate"] = True
    return _make_result(failures, passes, rubric_failures, flags)


def _handle_short_edit_strategy(response: str) -> CaseEvaluation:
    failures: list[str] = []
    flags = _base_flags()
    if _sentence_count(response) > 4:
        failures.append("response must stay under 4 sentences")
        flags["constraint_violation"] = True
    if _FILENAME_PATTERN.search(response):
        failures.append("response must not invent exact filenames")
        flags["hallucination_fabrication"] = True
    rubric_failures: list[str] = []
    passes: list[str] = []
    lowered = response.lower()
    if any(
        word in lowered
        for word in ("config", "reference", "usage", "call site", "consumer", "schema")
    ):
        passes.append("identifies likely update surfaces")
    else:
        rubric_failures.append("should identify likely config definition and usage surfaces")
    if _empty_or_generic(response):
        flags["empty_evasive_degenerate"] = True
    return _make_result(failures, passes, rubric_failures, flags)


def _handle_short_terminal_next_step(response: str) -> CaseEvaluation:
    failures: list[str] = []
    flags = _base_flags()
    if _sentence_count(response) > 3:
        failures.append("response must stay under 3 sentences")
        flags["constraint_violation"] = True
    rubric_failures: list[str] = []
    passes: list[str] = []
    lowered = response.lower()
    if any(word in lowered for word in ("check", "inspect", "verify", "compare")):
        passes.append("provides one concrete next step")
    else:
        rubric_failures.append("should provide one concrete next step")
    if any(word in lowered for word in ("because", "since", "to see", "to confirm")):
        passes.append("gives a short reason")
    else:
        rubric_failures.append("should give a short reason")
    if _empty_or_generic(response):
        flags["empty_evasive_degenerate"] = True
    return _make_result(failures, passes, rubric_failures, flags)


_CASE_HANDLERS = {
    "action_choice_enum": _handle_action_choice_enum,
    "exact_json_small_object": _handle_exact_json_small_object,
    "bounded_structured_summary": _handle_bounded_structured_summary,
    "exactly_three_bullets": _handle_exactly_three_bullets,
    "hard_length_limit": _handle_hard_length_limit,
    "constrained_task_plan": _handle_constrained_task_plan,
    "missing_path_requires_clarification": _handle_missing_path_requires_clarification,
    "ambiguous_destructive_request": _handle_ambiguous_destructive_request,
    "insufficient_evidence_no_fabrication": _handle_insufficient_evidence_no_fabrication,
    "short_bug_triage": _handle_short_bug_triage,
    "short_edit_strategy": _handle_short_edit_strategy,
    "short_terminal_next_step": _handle_short_terminal_next_step,
}
