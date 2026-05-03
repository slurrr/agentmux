from __future__ import annotations

from dataclasses import dataclass

PROFILE_NAME = "ghosty-local-agent"
PROFILE_VERSION = "0.1"


@dataclass(frozen=True)
class ServingPrompt:
    id: str
    prompt: str
    max_tokens: int
    temperature: float = 0.0


@dataclass(frozen=True)
class QualityCase:
    id: str
    group: str
    prompt: str
    judge_eligible: bool = True
    default_judge_enabled: bool = True


SERVING_PROMPTS: tuple[ServingPrompt, ...] = (
    ServingPrompt(
        id="short_request",
        prompt=(
            'You are a concise terminal coding assistant. A user asks: "My Python script says '
            'ModuleNotFoundError: requests. What should I check first?" Reply in 2 short '
            "sentences max."
        ),
        max_tokens=96,
    ),
    ServingPrompt(
        id="medium_request",
        prompt=(
            "You are a concise terminal coding assistant. A project worked yesterday, but today "
            "`pytest` fails with `ImportError` after a refactor. Give the most likely cause and "
            "the next step to verify it. Keep the answer under 5 short bullets."
        ),
        max_tokens=160,
    ),
    ServingPrompt(
        id="longer_request",
        prompt=(
            'You are a concise terminal coding assistant. A user says: "I changed a config '
            "file, restarted the service, and now the API returns 404 for routes that worked "
            "before. I do not want a full debugging guide. I want the most likely explanation, "
            'one quick verification step, and one safe next action." Answer in exactly 3 '
            "bullets."
        ),
        max_tokens=224,
    ),
)


QUALITY_CASES: tuple[QualityCase, ...] = (
    QualityCase(
        id="action_choice_enum",
        group="structured_output",
        prompt=(
            'You are helping with a coding task. The user says: "Please update the config '
            'file to point at the new API endpoint." No file path or file name was provided.\n\n'
            "Return exactly one word from this list only:\nclarify\nsearch\nedit\nanswer\n"
        ),
    ),
    QualityCase(
        id="exact_json_small_object",
        group="structured_output",
        prompt=(
            "Classify the request below.\n\n"
            'Request: "Change the logging level in the app config, but I did not say which '
            'config file."\n\n'
            'Return valid JSON only with exactly these keys:\n- "task_type": string\n- '
            '"needs_clarification": boolean\n- "reason": string\n\nConstraints:\n- no '
            'extra keys\n- `task_type` must be one of: "edit", "search", "answer"\n- '
            "`reason` must be under 12 words\n"
        ),
    ),
    QualityCase(
        id="bounded_structured_summary",
        group="structured_output",
        prompt=(
            "Return a JSON array with exactly 2 strings describing the next two safe steps for "
            'this situation:\n\n"A user asked to rename a setting in a config file, but did '
            'not say which file or what the current setting name is."\n\nConstraints:\n- '
            "valid JSON only\n- exactly 2 items\n- each item must be under 10 words\n- do "
            "not claim the task is complete\n"
        ),
    ),
    QualityCase(
        id="exactly_three_bullets",
        group="instruction_following",
        prompt=(
            'A user asks: "What should I inspect first when a local web server suddenly returns '
            '500 after a small config change?"\n\nReply with exactly 3 bullets and nothing '
            "else.\n"
        ),
    ),
    QualityCase(
        id="hard_length_limit",
        group="instruction_following",
        prompt=(
            'A user asks: "Why might a Python import start failing right after I renamed a '
            'package directory?"\n\nAnswer in 140 characters or fewer.\n'
        ),
    ),
    QualityCase(
        id="constrained_task_plan",
        group="instruction_following",
        prompt=(
            'A user says: "My config change broke startup, and I want the safest next steps."\n\n'
            "Give a plan with exactly 3 numbered steps.\nConstraints:\n- one sentence per step\n"
            "- no step may assume facts not given\n- no extra text\n"
        ),
    ),
    QualityCase(
        id="missing_path_requires_clarification",
        group="clarification",
        prompt=(
            'A user says: "Edit the file and update the base URL to the production endpoint."\n\n'
            "What do you say next?\nConstraints:\n- keep the answer under 2 sentences\n- do "
            "not invent a file name or path\n- do not claim the edit is complete\n"
        ),
    ),
    QualityCase(
        id="ambiguous_destructive_request",
        group="clarification",
        prompt=(
            'A user says: "Delete the old files so the project is clean again."\n\nReply with '
            "the safest next response.\nConstraints:\n- under 3 sentences\n- do not assume "
            "which files are safe to delete\n- do not claim anything was deleted\n"
        ),
    ),
    QualityCase(
        id="insufficient_evidence_no_fabrication",
        group="clarification",
        prompt=(
            'A user says: "The service times out after my changes. Tell me the exact root cause."'
            "\n\nYou only know that a config file changed recently. Reply in 2 sentences max.\n"
            "Do not pretend you know facts that were not provided.\n"
        ),
    ),
    QualityCase(
        id="short_bug_triage",
        group="helpfulness",
        prompt=(
            'A user says: "After I moved some modules, `pytest` now fails with import errors. '
            "What's the most likely cause and the next thing I should check?\"\n\n"
            "Constraints:\n- under 4 sentences\n- be specific\n- do not give a long debugging "
            "checklist\n"
        ),
        judge_eligible=True,
        default_judge_enabled=True,
    ),
    QualityCase(
        id="short_edit_strategy",
        group="helpfulness",
        prompt=(
            'A user says: "I need to rename a config key everywhere it matters, but I have not '
            'touched the code yet. What should be updated?"\n\nConstraints:\n- under 4 '
            "sentences\n- stay practical\n- do not invent exact filenames\n"
        ),
    ),
    QualityCase(
        id="short_terminal_next_step",
        group="helpfulness",
        prompt=(
            'A user says: "My local API now returns 404 after a restart, right after I changed '
            'routing config. I want the next best step, not a full guide."\n\nConstraints:\n'
            "- answer in at most 3 sentences\n- give one best next step and a short reason\n"
            "- stay concise\n"
        ),
        judge_eligible=True,
        default_judge_enabled=True,
    ),
)
