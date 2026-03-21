from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Request as FastAPIRequest, Response

UPSTREAM_BASE_URL = os.environ.get('AGENTMUX_RESPONSES_UPSTREAM', 'http://127.0.0.1:8002/v1').rstrip('/')
app = FastAPI(title='agentmux-codex-responses-proxy')


def _summarize_tool(tool: Any) -> dict[str, Any]:
    if not isinstance(tool, dict):
        return {"raw_type": type(tool).__name__}
    summary = {"type": tool.get("type")}
    if tool.get("type") == "function":
        fn = tool.get("function")
        if isinstance(fn, dict):
            summary["name"] = fn.get("name")
    if tool.get("type") == "custom":
        summary["name"] = tool.get("name")
    return summary


def _log_payload_shape(payload: dict[str, Any]) -> None:
    input_items = payload.get("input")
    item_types: list[str] = []
    if isinstance(input_items, list):
        for item in input_items:
            if isinstance(item, dict):
                item_types.append(f"{item.get('type')}:{item.get('role', '-')}")
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
                "tool_count": len(tools) if isinstance(tools, list) else 0,
                "tools": tool_summaries,
                "input_item_types": item_types,
            },
            indent=2,
        ),
        flush=True,
    )


def _stable_item_id(item: dict[str, Any], index: int) -> str:
    digest = hashlib.sha1(json.dumps(item, sort_keys=True).encode('utf-8')).hexdigest()[:12]
    return f'msg_proxy_{index}_{digest}'


def _normalize_assistant_message_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    if item.get('type') != 'message' or item.get('role') != 'assistant':
        return item
    normalized = dict(item)
    normalized.setdefault('id', _stable_item_id(item, index))
    normalized.setdefault('status', 'completed')
    content = []
    for part in normalized.get('content', []):
        if isinstance(part, dict) and part.get('type') == 'output_text':
            updated = dict(part)
            updated.setdefault('annotations', [])
            updated.setdefault('logprobs', [])
            content.append(updated)
        else:
            content.append(part)
    normalized['content'] = content
    return normalized


def normalize_responses_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    input_items = normalized.get('input')
    if isinstance(input_items, list):
        normalized['input'] = [
            _normalize_assistant_message_item(item, index) if isinstance(item, dict) else item
            for index, item in enumerate(input_items)
        ]
    return normalized


@app.post('/v1/responses')
async def responses_proxy(request: FastAPIRequest) -> Response:
    payload = await request.json()
    _log_payload_shape(payload)
    normalized = normalize_responses_payload(payload)
    data = json.dumps(normalized).encode('utf-8')
    upstream = Request(
        f'{UPSTREAM_BASE_URL}/responses',
        data=data,
        headers={
            'Content-Type': 'application/json',
            'Accept': request.headers.get('accept', 'application/json'),
            **({'Authorization': request.headers['authorization']} if 'authorization' in request.headers else {}),
        },
        method='POST',
    )
    try:
        with urlopen(upstream) as resp:
            return Response(
                content=resp.read(),
                status_code=resp.status,
                media_type=resp.headers.get_content_type(),
            )
    except HTTPError as exc:
        return Response(
            content=exc.read(),
            status_code=exc.code,
            media_type=exc.headers.get_content_type() if exc.headers else 'application/json',
        )
