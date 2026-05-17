from __future__ import annotations

import json
from urllib import error, request

from agentmux.config import ServiceSpec, StackSpec


def _base_url(service: ServiceSpec) -> str:
    return f"http://{service.host}:{service.port}"


def smoke_stack(stack: StackSpec) -> dict[str, object]:
    service = stack.services[stack.primary_service]
    base_url = _base_url(service)
    model_name = service.served_model_name or service.model

    health_status = 0
    health_body = ""
    try:
        health = request.urlopen(f"{base_url}/health", timeout=5)
        health_status = getattr(health, "status", 200)
        health_body = health.read().decode("utf-8", errors="ignore")
    except error.URLError:
        # Some OpenAI-compatible servers do not implement /health.
        pass

    models = request.urlopen(f"{base_url}/v1/models", timeout=5)
    models_payload = json.loads(models.read().decode("utf-8"))

    if health_status == 0:
        health_status = getattr(models, "status", 200)

    payload = json.dumps(
        {
            "model": model_name,
            "messages": [{"role": "user", "content": "Reply with the single word ok."}],
            "temperature": 0,
            "max_tokens": 8,
        }
    ).encode("utf-8")
    chat_request = request.Request(
        f"{base_url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chat = request.urlopen(chat_request, timeout=30)
    chat_payload = json.loads(chat.read().decode("utf-8"))

    return {
        "service": service.name,
        "base_url": base_url,
        "health_status": health_status,
        "health_body": health_body,
        "models": models_payload,
        "chat": chat_payload,
    }


def smoke_stack_safe(stack: StackSpec) -> dict[str, object]:
    try:
        result = smoke_stack(stack)
        result["ok"] = True
        return result
    except error.URLError as exc:
        return {"ok": False, "error": str(exc)}
