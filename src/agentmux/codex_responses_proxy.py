from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
from http.client import IncompleteRead
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import httpx
import requests
from fastapi import FastAPI, Response
from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse


def _to_bytes(body: bytes | memoryview[int]) -> bytes:
    return bytes(body) if isinstance(body, memoryview) else body


UPSTREAM_BASE_URL = os.environ.get(
    "AGENTMUX_RESPONSES_UPSTREAM", "http://127.0.0.1:8002/v1"
).rstrip("/")
LOG_INPUT_PREVIEW = os.environ.get("AGENTMUX_PROXY_LOG_INPUT_PREVIEW", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LOG_INPUT_PREVIEW_CHARS = int(os.environ.get("AGENTMUX_PROXY_LOG_INPUT_PREVIEW_CHARS", "240"))
FORCE_REQUIRED_TOOL_CHOICE = os.environ.get(
    "AGENTMUX_PROXY_FORCE_REQUIRED_TOOL_CHOICE", ""
).lower() in {"1", "true", "yes", "on"}
DISABLE_PARALLEL_TOOL_CALLS = os.environ.get(
    "AGENTMUX_PROXY_DISABLE_PARALLEL_TOOL_CALLS", "1"
).lower() in {"1", "true", "yes", "on"}
CLEAR_PREVIOUS_RESPONSE_ID = os.environ.get(
    "AGENTMUX_PROXY_CLEAR_PREVIOUS_RESPONSE_ID", ""
).lower() in {"1", "true", "yes", "on"}
ENABLE_COMPAT_RETRY = os.environ.get(
    "AGENTMUX_PROXY_ENABLE_COMPAT_RETRY", "1"
).lower() in {"1", "true", "yes", "on"}
ENABLE_TOOL_CHOICE_RETRY = os.environ.get(
    "AGENTMUX_PROXY_ENABLE_TOOL_CHOICE_RETRY", "1"
).lower() in {"1", "true", "yes", "on"}
SANITIZE_XML_TOOL_TEXT = os.environ.get(
    "AGENTMUX_PROXY_SANITIZE_XML_TOOL_TEXT", "1"
).lower() in {"1", "true", "yes", "on"}
SANITIZE_MODE = os.environ.get(
    "AGENTMUX_PROXY_SANITIZE_MODE", "completed_only"
).strip().lower()
app = FastAPI(title="agentmux-codex-responses-proxy")


def _summarize_tool(tool: Any) -> dict[str, Any]:
    if not isinstance(tool, dict):
        return {"raw_type": type(tool).__name__}
    summary = {"type": tool.get("type")}
    if tool.get("type") == "function":
        if isinstance(tool.get("name"), str):
            summary["name"] = tool.get("name")
        fn = tool.get("function")
        if isinstance(fn, dict):
            summary["name"] = fn.get("name")
    elif isinstance(tool.get("name"), str):
        summary["name"] = tool.get("name")
    if tool.get("type") == "custom":
        summary["name"] = tool.get("name")
    return summary


def _log_payload_shape(payload: dict[str, Any], normalized: dict[str, Any] | None = None) -> None:
    input_items = payload.get("input")
    item_types: list[str] = []
    input_previews: list[dict[str, Any]] = []
    if isinstance(input_items, list):
        for index, item in enumerate(input_items):
            if isinstance(item, dict):
                item_types.append(f"{item.get('type')}:{item.get('role', '-')}")
                if LOG_INPUT_PREVIEW:
                    preview = ""
                    content = item.get("content")
                    if isinstance(content, str):
                        preview = content
                    elif isinstance(content, list):
                        parts: list[str] = []
                        for part in content:
                            if isinstance(part, dict):
                                text = part.get("text")
                                if isinstance(text, str) and text:
                                    parts.append(text)
                        preview = "\n".join(parts)
                    if len(preview) > LOG_INPUT_PREVIEW_CHARS:
                        preview = f"{preview[:LOG_INPUT_PREVIEW_CHARS]}...(truncated)"
                    input_previews.append(
                        {
                            "index": index,
                            "type": item.get("type"),
                            "role": item.get("role"),
                            "preview": preview,
                        }
                    )
            else:
                item_types.append(type(item).__name__)
    tools = payload.get("tools")
    tool_summaries = []
    if isinstance(tools, list):
        tool_summaries = [_summarize_tool(tool) for tool in tools[:10]]
    print(
        json.dumps(
            {
                "kind": "responses_proxy_request",
                "model": payload.get("model"),
                "tool_choice": payload.get("tool_choice"),
                "normalized_tool_choice": (
                    normalized.get("tool_choice") if isinstance(normalized, dict) else None
                ),
                "previous_response_id": payload.get("previous_response_id"),
                "normalized_previous_response_id": (
                    normalized.get("previous_response_id") if isinstance(normalized, dict) else None
                ),
                "tool_count": len(tools) if isinstance(tools, list) else 0,
                "tools": tool_summaries,
                "input_item_types": item_types,
                **({"input_previews": input_previews} if LOG_INPUT_PREVIEW else {}),
            },
            indent=2,
        ),
        flush=True,
    )


def _stable_item_id(item: dict[str, Any], index: int) -> str:
    digest = hashlib.sha1(json.dumps(item, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"msg_proxy_{index}_{digest}"


def _normalize_assistant_message_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    if item.get("type") != "message" or item.get("role") != "assistant":
        return item
    normalized = dict(item)
    normalized.setdefault("id", _stable_item_id(item, index))
    normalized.setdefault("status", "completed")
    content = []
    for part in normalized.get("content", []):
        if isinstance(part, dict) and part.get("type") == "output_text":
            updated = dict(part)
            updated.setdefault("annotations", [])
            updated.setdefault("logprobs", [])
            content.append(updated)
        else:
            content.append(part)
    normalized["content"] = content
    return normalized


def _coerce_message_item(item: dict[str, Any]) -> dict[str, Any]:
    # OpenCode may send message objects without explicit type.
    if item.get("type") == "message":
        return item
    if isinstance(item.get("role"), str):
        normalized = dict(item)
        normalized["type"] = "message"
        return normalized
    return item


def _normalize_message_role(item: dict[str, Any]) -> dict[str, Any]:
    # Some HF chat templates used by vLLM reject "developer" and expect "system".
    if item.get("type") == "message" and item.get("role") == "developer":
        normalized = dict(item)
        normalized["role"] = "system"
        return normalized
    return item


def normalize_responses_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    input_items = normalized.get("input")
    if isinstance(input_items, list):
        converted: list[Any] = []
        for index, item in enumerate(input_items):
            if not isinstance(item, dict):
                converted.append(item)
                continue
            normalized_item = _coerce_message_item(item)
            normalized_item = _normalize_message_role(normalized_item)
            normalized_item = _normalize_assistant_message_item(normalized_item, index)
            converted.append(normalized_item)
        system_items: list[Any] = []
        other_items: list[Any] = []
        for item in converted:
            if (
                isinstance(item, dict)
                and item.get("type") == "message"
                and item.get("role") == "system"
            ):
                system_items.append(item)
            else:
                other_items.append(item)
        normalized["input"] = [*system_items, *other_items]
    tools = normalized.get("tools")
    tool_choice = normalized.get("tool_choice")
    if isinstance(tools, list) and tools:
        if DISABLE_PARALLEL_TOOL_CALLS:
            normalized["parallel_tool_calls"] = False
        if FORCE_REQUIRED_TOOL_CHOICE and tool_choice in (None, "auto"):
            normalized["tool_choice"] = "required"
    if CLEAR_PREVIOUS_RESPONSE_ID and "previous_response_id" in normalized:
        normalized["previous_response_id"] = None
    return normalized


def _extract_error_message(raw_body: bytes | memoryview[int]) -> str | None:
    body = _to_bytes(raw_body)
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return None

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
    return None


def _sse_counts(raw_body: bytes) -> dict[str, int]:
    decoded = raw_body.decode("utf-8", errors="replace")
    return {
        "function_call_mentions": decoded.count('"type":"function_call"'),
        "tool_call_tag_mentions": decoded.count("<tool_call>"),
        "output_text_mentions": decoded.count('"type":"output_text"'),
    }


def _remove_xml_tool_messages(output: Any) -> Any:
    if not isinstance(output, list):
        return output
    has_function_call = any(
        isinstance(item, dict) and item.get("type") == "function_call" for item in output
    )
    if not has_function_call:
        return output

    sanitized: list[Any] = []
    for item in output:
        if not isinstance(item, dict):
            sanitized.append(item)
            continue
        if item.get("type") != "message":
            sanitized.append(item)
            continue
        content = item.get("content")
        if not isinstance(content, list):
            sanitized.append(item)
            continue
        text_blob = "\n".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
        if (
            "<tool_call>" in text_blob
            or "<function=" in text_blob
            or "</think>" in text_blob
            or "<think>" in text_blob
        ):
            # Prefer the structured function_call object when mixed text includes
            # tool-call XML or thought tags.
            continue
        sanitized.append(item)
    return sanitized


def _strip_assistant_text_from_output(output: Any) -> Any:
    if not isinstance(output, list):
        return output
    has_function_call = any(
        isinstance(item, dict) and item.get("type") == "function_call" for item in output
    )
    if not has_function_call:
        return output

    stripped: list[Any] = []
    for item in output:
        if not isinstance(item, dict):
            stripped.append(item)
            continue
        if item.get("type") != "message":
            stripped.append(item)
            continue
        if item.get("role") != "assistant":
            stripped.append(item)
            continue
        updated = dict(item)
        content = updated.get("content")
        if not isinstance(content, list):
            stripped.append(updated)
            continue
        new_content: list[Any] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text":
                part_copy = dict(part)
                part_copy["text"] = ""
                new_content.append(part_copy)
            else:
                new_content.append(part)
        updated["content"] = new_content
        stripped.append(updated)
    return stripped


def _sanitize_upstream_body_for_tool_calls(
    raw_body: bytes,
    content_type: str | None,
) -> bytes:
    media_type = content_type or ""
    if media_type.startswith("application/json"):
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return raw_body
        if isinstance(payload, dict):
            mode = SANITIZE_MODE
            if mode == "drop_xml_messages":
                payload["output"] = _remove_xml_tool_messages(payload.get("output"))
            elif mode in {"strip_assistant_text", "function_call_wins"}:
                payload["output"] = _strip_assistant_text_from_output(payload.get("output"))
            return json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return raw_body

    if not media_type.startswith("text/event-stream"):
        return raw_body

    decoded = raw_body.decode("utf-8", errors="replace")
    has_fc_stream = '"type":"function_call"' in decoded
    blocks = decoded.split("\n\n")
    rewritten_blocks: list[str] = []
    for block in blocks:
        if not block:
            continue
        block_lines = block.splitlines()
        data_index = next((i for i, ln in enumerate(block_lines) if ln.startswith("data: ")), None)
        if data_index is None:
            rewritten_blocks.append(block)
            continue
        data_line = block_lines[data_index]
        body = data_line[6:]
        if body.strip() == "[DONE]":
            rewritten_blocks.append(block)
            continue
        try:
            event_payload = json.loads(body)
        except Exception:
            rewritten_blocks.append(block)
            continue

        if isinstance(event_payload, dict):
            # Keep stream shape stable while suppressing assistant text payload
            # on function-call turns.
            if SANITIZE_MODE in {"strip_assistant_text", "function_call_wins"} and has_fc_stream:
                event_type = event_payload.get("type")
                if SANITIZE_MODE == "function_call_wins":
                    if event_type in {
                        "response.output_text.delta",
                        "response.output_text.done",
                    }:
                        continue
                    if event_type in {
                        "response.content_part.added",
                        "response.content_part.done",
                    }:
                        part = event_payload.get("part")
                        if isinstance(part, dict) and part.get("type") == "output_text":
                            continue
                    if event_type in {
                        "response.output_item.added",
                        "response.output_item.done",
                    }:
                        item = event_payload.get("item")
                        if (
                            isinstance(item, dict)
                            and item.get("type") == "message"
                            and item.get("role") == "assistant"
                        ):
                            continue
                if SANITIZE_MODE in {"strip_assistant_text", "function_call_wins"}:
                    if event_type == "response.output_text.delta" and isinstance(
                        event_payload.get("delta"), str
                    ):
                        event_payload = dict(event_payload)
                        event_payload["delta"] = ""
                    elif event_type == "response.output_text.done" and isinstance(
                        event_payload.get("text"), str
                    ):
                        event_payload = dict(event_payload)
                        event_payload["text"] = ""
                    elif event_type in {
                        "response.content_part.added",
                        "response.content_part.done",
                    }:
                        part = event_payload.get("part")
                        if isinstance(part, dict) and part.get("type") == "output_text":
                            updated_part = dict(part)
                            updated_part["text"] = ""
                            event_payload = dict(event_payload)
                            event_payload["part"] = updated_part
                    elif event_type in {
                        "response.output_item.added",
                        "response.output_item.done",
                    }:
                        item = event_payload.get("item")
                        if (
                            isinstance(item, dict)
                            and item.get("type") == "message"
                            and item.get("role") == "assistant"
                        ):
                            updated_item = dict(item)
                            content = updated_item.get("content")
                            if isinstance(content, list):
                                new_content: list[Any] = []
                                for part in content:
                                    if (
                                        isinstance(part, dict)
                                        and part.get("type") == "output_text"
                                    ):
                                        part_copy = dict(part)
                                        part_copy["text"] = ""
                                        new_content.append(part_copy)
                                    else:
                                        new_content.append(part)
                                updated_item["content"] = new_content
                            event_payload = dict(event_payload)
                            event_payload["item"] = updated_item
            if isinstance(event_payload.get("response"), dict):
                event_type = event_payload.get("type")
                response_obj = dict(event_payload["response"])
                should_sanitize = (
                    SANITIZE_MODE != "completed_only" or event_type == "response.completed"
                )
                if should_sanitize:
                    if SANITIZE_MODE == "drop_xml_messages":
                        response_obj["output"] = _remove_xml_tool_messages(
                            response_obj.get("output")
                        )
                    elif SANITIZE_MODE in {"strip_assistant_text", "function_call_wins"}:
                        response_obj["output"] = _strip_assistant_text_from_output(
                            response_obj.get("output")
                        )
                    else:
                        response_obj["output"] = _remove_xml_tool_messages(
                            response_obj.get("output")
                        )
                event_payload = dict(event_payload)
                event_payload["response"] = response_obj
                block_lines[data_index] = (
                    f"data: {json.dumps(event_payload, separators=(',', ':'))}"
                )
                rewritten_blocks.append("\n".join(block_lines))
                continue
            block_lines[data_index] = f"data: {json.dumps(event_payload, separators=(',', ':'))}"
            rewritten_blocks.append("\n".join(block_lines))
            continue
        rewritten_blocks.append(block)
    if not rewritten_blocks:
        return b""
    return ("\n\n".join(rewritten_blocks) + "\n\n").encode("utf-8")


def _sanitize_sse_block_for_tool_calls(block: str, has_fc_stream: bool) -> str | None:
    if not block:
        return None
    sanitized = _sanitize_upstream_body_for_tool_calls(
        (block + "\n\n").encode("utf-8"),
        "text/event-stream",
    ).decode("utf-8", errors="replace")
    if not sanitized:
        return None
    if sanitized.endswith("\n\n"):
        sanitized = sanitized[:-2]
    return sanitized


def _build_compat_retry_payload(payload: dict[str, Any]) -> dict[str, Any]:
    # Aggressive compatibility pass for chat templates that are strict about
    # role set and system-message placement.
    normalized = normalize_responses_payload(payload)
    input_items = normalized.get("input")
    if not isinstance(input_items, list):
        return normalized

    cleaned: list[dict[str, Any]] = []
    for item in input_items:
        if not isinstance(item, dict):
            continue
        msg = _coerce_message_item(item)
        if msg.get("type") != "message":
            continue
        msg = dict(msg)
        role = msg.get("role")
        role_str = role.lower() if isinstance(role, str) else "user"
        if role_str in {"developer", "system"}:
            role_str = "system"
        elif role_str not in {"user", "assistant", "tool"}:
            role_str = "user"
        msg["role"] = role_str
        cleaned.append(msg)

    has_instructions = isinstance(normalized.get("instructions"), str) and bool(
        normalized.get("instructions", "").strip()
    )
    if has_instructions:
        # If instructions are present, avoid additional system-role messages to
        # prevent "System message must be at the beginning" in strict templates.
        for msg in cleaned:
            if msg.get("role") == "system":
                msg["role"] = "user"
        normalized["input"] = cleaned
        return normalized

    first_system_seen = False
    ordered: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for msg in cleaned:
        if msg.get("role") == "system":
            if not first_system_seen:
                first_system_seen = True
                ordered.append(msg)
            else:
                # Demote extra system messages to user role to satisfy strict
                # templates while retaining content.
                demoted = dict(msg)
                demoted["role"] = "user"
                deferred.append(demoted)
        else:
            deferred.append(msg)
    normalized["input"] = [*ordered, *deferred]
    return normalized


def _forward_upstream(
    *,
    path: str,
    method: str,
    accept: str,
    authorization: str | None = None,
    data: bytes | None = None,
) -> Response:
    headers: dict[str, str] = {"Accept": accept}
    if authorization:
        headers["Authorization"] = authorization
    if data is not None:
        headers["Content-Type"] = "application/json"
    upstream = Request(
        f"{UPSTREAM_BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(upstream) as resp:
            try:
                body = resp.read()
            except IncompleteRead as exc:
                body = exc.partial
            return Response(
                content=body,
                status_code=resp.status,
                media_type=resp.headers.get_content_type(),
            )
    except HTTPError as exc:
        return Response(
            content=exc.read(),
            status_code=exc.code,
            media_type=exc.headers.get_content_type() if exc.headers else "application/json",
        )


def _log_upstream_response_shape(
    raw_body: bytes, content_type: str | None, status_code: int
) -> None:
    base: dict[str, Any] = {
        "kind": "responses_proxy_upstream_response",
        "status_code": status_code,
        "content_type": content_type or "unknown",
        "body_bytes": len(raw_body),
    }
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        if raw_body:
            decoded = raw_body.decode("utf-8", errors="replace")
            snippet = decoded[:240]
            base["body_preview"] = f"{snippet}...(truncated)" if len(raw_body) > 240 else snippet
            if (content_type or "").startswith("text/event-stream"):
                base["sse_event_count"] = decoded.count("\nevent: ") + (
                    1 if decoded.startswith("event: ") else 0
                )
                base["sse_data_count"] = decoded.count("\ndata: ") + (
                    1 if decoded.startswith("data: ") else 0
                )
                base["sse_function_call_mentions"] = decoded.count('"type":"function_call"')
                base["sse_tool_call_tag_mentions"] = decoded.count("<tool_call>")
                base["sse_output_text_mentions"] = decoded.count('"type":"output_text"')
                first_fc_name = re.search(
                    r'"type":"function_call".{0,600}?"name":"([^"]+)"',
                    decoded,
                )
                first_fc_args = re.search(
                    r'"type":"function_call".{0,1200}?"arguments":"([^"]*)"',
                    decoded,
                )
                if first_fc_name:
                    base["sse_first_function_call_name"] = first_fc_name.group(1)
                if first_fc_args:
                    arg_preview = first_fc_args.group(1)
                    if len(arg_preview) > 200:
                        arg_preview = f"{arg_preview[:200]}...(truncated)"
                    base["sse_first_function_call_arguments"] = arg_preview

                # Parse SSE data lines to extract the final completed response payload.
                final_response = None
                for line in decoded.splitlines():
                    if not line.startswith("data: "):
                        continue
                    payload_text = line[6:]
                    if payload_text.strip() == "[DONE]":
                        continue
                    try:
                        event_payload = json.loads(payload_text)
                    except Exception:
                        continue
                    if isinstance(event_payload, dict):
                        if "response" in event_payload and isinstance(
                            event_payload["response"], dict
                        ):
                            final_response = event_payload["response"]

                if isinstance(final_response, dict):
                    output = final_response.get("output")
                    if isinstance(output, list):
                        first_fc = next(
                            (
                                item
                                for item in output
                                if isinstance(item, dict) and item.get("type") == "function_call"
                            ),
                            None,
                        )
                        if isinstance(first_fc, dict):
                            base["sse_final_function_call_name"] = first_fc.get("name")
                            args = first_fc.get("arguments")
                            if isinstance(args, str):
                                if len(args) > 300:
                                    args = f"{args[:300]}...(truncated)"
                                base["sse_final_function_call_arguments"] = args
        print(json.dumps(base, indent=2), flush=True)
        return
    output = payload.get("output")
    output_types: list[str] = []
    function_calls = 0
    assistant_preview = ""
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                output_types.append(type(item).__name__)
                continue
            item_type = item.get("type")
            output_types.append(str(item_type))
            if item_type == "function_call":
                function_calls += 1
            if item_type == "message" and not assistant_preview:
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            assistant_preview = part["text"]
                            break
    if len(assistant_preview) > 240:
        assistant_preview = f"{assistant_preview[:240]}...(truncated)"
    base.update(
        {
            "status": payload.get("status"),
            "error_type": (
                payload.get("error", {}).get("type")
                if isinstance(payload.get("error"), dict)
                else None
            ),
            "error_message": (
                payload.get("error", {}).get("message")
                if isinstance(payload.get("error"), dict)
                else None
            ),
            "output_types": output_types,
            "function_call_count": function_calls,
            "assistant_preview": assistant_preview,
        }
    )
    print(json.dumps(base, indent=2), flush=True)


@app.get("/v1/models")
async def models_proxy(request: FastAPIRequest) -> Response:
    return _forward_upstream(
        path="/models",
        method="GET",
        accept=request.headers.get("accept", "application/json"),
        authorization=request.headers.get("authorization"),
    )


@app.get("/v1/models/{model_id:path}")
async def model_detail_proxy(model_id: str, request: FastAPIRequest) -> Response:
    response = _forward_upstream(
        path=f"/models/{model_id}",
        method="GET",
        accept=request.headers.get("accept", "application/json"),
        authorization=request.headers.get("authorization"),
    )
    if response.status_code != 404:
        return response

    list_response = _forward_upstream(
        path="/models",
        method="GET",
        accept=request.headers.get("accept", "application/json"),
        authorization=request.headers.get("authorization"),
    )
    if list_response.status_code != 200:
        return response

    try:
        payload = json.loads(_to_bytes(list_response.body).decode("utf-8"))
    except Exception:
        return response

    models = payload.get("data")
    if not isinstance(models, list):
        return response

    match = next(
        (
            model
            for model in models
            if isinstance(model, dict) and str(model.get("id", "")).lower() == model_id.lower()
        ),
        None,
    )
    if match is None:
        return response

    return Response(
        content=json.dumps(match).encode("utf-8"),
        status_code=200,
        media_type="application/json",
    )


@app.post("/v1/responses")
async def responses_proxy(request: FastAPIRequest) -> Response:
    payload = await request.json()
    normalized = normalize_responses_payload(payload)
    _log_payload_shape(payload, normalized)
    accept = request.headers.get("accept", "application/json")
    authorization = request.headers.get("authorization")
    headers: dict[str, str] = {"Accept": accept, "Content-Type": "application/json"}
    if authorization:
        headers["Authorization"] = authorization

    upstream = requests.post(
        f"{UPSTREAM_BASE_URL}/responses",
        headers=headers,
        data=json.dumps(normalized).encode("utf-8"),
        stream=True,
        timeout=None,
    )
    media_type = upstream.headers.get("content-type", "application/json").split(";")[0]

    if not media_type.startswith("text/event-stream"):
        try:
            raw_body = upstream.content
        finally:
            upstream.close()
        response = Response(content=raw_body, status_code=upstream.status_code, media_type=media_type)
        error_message = _extract_error_message(raw_body)
        retry_trigger = (
            response.status_code == 400
            and isinstance(error_message, str)
            and ENABLE_COMPAT_RETRY
            and (
                "Unexpected message role" in error_message
                or "System message must be at the beginning" in error_message
            )
        )
        if retry_trigger:
            compat = _build_compat_retry_payload(payload)
            print(
                json.dumps(
                    {
                        "kind": "responses_proxy_retry",
                        "reason": error_message,
                        "strategy": "compat_input_roles_and_order",
                    },
                    indent=2,
                ),
                flush=True,
            )
            return _forward_upstream(
                path="/responses",
                method="POST",
                accept=accept,
                authorization=authorization,
                data=json.dumps(compat).encode("utf-8"),
            )
        _log_upstream_response_shape(raw_body, media_type, response.status_code)
        return response

    async def generate() -> Any:
        decoder = codecs.getincrementaldecoder("utf-8")()
        buffered = ""
        collected = bytearray()
        has_fc_stream = False
        try:
            try:
                for chunk in upstream.iter_content(chunk_size=None):
                    if not chunk:
                        continue
                    buffered += decoder.decode(chunk)
                    buffered = buffered.replace("\r\n", "\n")
                    while "\n\n" in buffered:
                        block, buffered = buffered.split("\n\n", 1)
                        if not block:
                            continue
                        if '"type":"function_call"' in block:
                            has_fc_stream = True
                        rewritten = (
                            _sanitize_sse_block_for_tool_calls(block, has_fc_stream)
                            if SANITIZE_XML_TOOL_TEXT
                            else block
                        )
                        if rewritten is None:
                            continue
                        payload_bytes = (rewritten + "\n\n").encode("utf-8")
                        collected.extend(payload_bytes)
                        yield payload_bytes
            except requests.exceptions.ChunkedEncodingError:
                pass
            buffered += decoder.decode(b"", final=True)
            buffered = buffered.replace("\r\n", "\n")
            if buffered.strip():
                if '"type":"function_call"' in buffered:
                    has_fc_stream = True
                rewritten = (
                    _sanitize_sse_block_for_tool_calls(buffered, has_fc_stream)
                    if SANITIZE_XML_TOOL_TEXT
                    else buffered
                )
                if rewritten is not None:
                    payload_bytes = (rewritten + "\n\n").encode("utf-8")
                    collected.extend(payload_bytes)
                    yield payload_bytes
            _log_upstream_response_shape(bytes(collected), media_type, upstream.status_code)
        except requests.exceptions.ChunkedEncodingError:
            _log_upstream_response_shape(bytes(collected), media_type, upstream.status_code)
        finally:
            upstream.close()

    return StreamingResponse(generate(), status_code=upstream.status_code, media_type=media_type)
