"""Resolve thread id from request body; strip gateway-only fields before upstream."""

from __future__ import annotations

import json
import secrets
from typing import Any


def strip_conversation_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy without gateway thread fields (not forwarded to OpenAI-compatible backends)."""
    return {k: v for k, v in data.items() if k not in ("conversation_id", "is_new_conversation")}


def resolve_conversation_id(data: dict[str, Any]) -> tuple[str, bool]:
    """
    Effective thread id and whether this request started a new conversation.

    Missing or blank ``conversation_id`` → ``conv_`` + 32 hex chars, ``is_new=True``.
    Non-blank string → that value (stripped), ``is_new=False``.
    """
    raw = data.get("conversation_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), False
    return f"conv_{secrets.token_hex(16)}", True


def merge_conversation_into_response_json(
    content: bytes, *, conversation_id: str, is_new_conversation: bool
) -> bytes | None:
    """If ``content`` is a UTF-8 JSON object, return a copy with thread fields merged; else ``None``."""
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    merged = dict(data)
    merged["conversation_id"] = conversation_id
    merged["is_new_conversation"] = is_new_conversation
    return json.dumps(merged, ensure_ascii=False).encode("utf-8")
