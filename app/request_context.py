"""Per-request correlation IDs (contextvars + ASGI middleware).

Pure ASGI middleware (not BaseHTTPMiddleware) so ContextVar updates are visible
inside route handlers — Starlette runs the inner app in a separate task for
BaseHTTPMiddleware, which does not inherit middleware contextvars.
"""
from __future__ import annotations

import contextvars
import json
import logging

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send

_REQUEST_ID = contextvars.ContextVar[str]("request_id", default="-")
_SESSION_ID = contextvars.ContextVar[str]("session_id", default="-")

_mw_log = logging.getLogger("layer_gateway.embed")


def get_request_id() -> str:
    return _REQUEST_ID.get()


def get_session_id() -> str:
    return _SESSION_ID.get()


def _norm_header(value: str | None) -> str:
    if not value:
        return "-"
    s = value.strip()
    return s if s else "-"


def _headers_dict(scope: Scope) -> dict[str, str]:
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}


def _post_embeddings_requires_correlation(scope: Scope) -> bool:
    return scope.get("method") == "POST" and scope.get("path") == "/v1/embeddings"


def _missing_required_headers(request_id: str, session_id: str) -> list[str]:
    missing: list[str] = []
    if request_id == "-":
        missing.append("X-Request-Id")
    if session_id == "-":
        missing.append("X-Session-Id")
    return missing


async def _send_400_missing_headers(send: Send, missing: list[str]) -> None:
    body = json.dumps(
        {
            "error": "X-Request-Id and X-Session-Id are required for POST /v1/embeddings",
            "missing": missing,
        }
    ).encode("utf-8")
    resp_headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    _mw_log.warning("POST /v1/embeddings rejected: missing correlation headers %s", missing)
    await send({"type": "http.response.start", "status": 400, "headers": resp_headers})
    await send({"type": "http.response.body", "body": body, "more_body": False})


class RequestContextMiddleware:
    """Correlation headers: required for POST /v1/embeddings; optional for /health and GET /v1/models."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        hdr = _headers_dict(scope)
        rid_raw = _norm_header(hdr.get("x-request-id"))
        sid_raw = _norm_header(hdr.get("x-session-id"))

        if _post_embeddings_requires_correlation(scope):
            missing = _missing_required_headers(rid_raw, sid_raw)
            if missing:
                await _send_400_missing_headers(send, missing)
                return
        rid, sid = rid_raw, sid_raw

        t_rid = _REQUEST_ID.set(rid)
        t_sid = _SESSION_ID.set(sid)

        async def send_with_correlation_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                h = MutableHeaders(raw=list(message["headers"]))
                h["x-request-id"] = rid
                if sid != "-":
                    h["x-session-id"] = sid
                message = {**message, "headers": h.raw}
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation_headers)
        finally:
            _REQUEST_ID.reset(t_rid)
            _SESSION_ID.reset(t_sid)
