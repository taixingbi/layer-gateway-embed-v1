"""`POST /v1/embeddings`: admission queue, routing, upstream proxy, metrics."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.core.config import Settings
from app.core.logging import log_gateway_event
from app.metrics.prometheus import (
    ADMISSION_INQUEUE,
    ADMISSION_REJECTED,
    ADMISSION_WAIT,
    BACKEND_SELECTED,
    FAILURES,
    INFLIGHT,
    LATENCY,
    REQUESTS,
    RETRIES,
)
from app.models.schemas import EmbeddingRequest
from app.routing.selector import BackendSelector

logger = logging.getLogger(__name__)
router = APIRouter()
_BLOCKED_HEADERS = frozenset({"host", "content-length"})
_EMBEDDINGS_PATH = "/v1/embeddings"


def _routing_debug(selector: BackendSelector, excluded: set[str]) -> dict[str, object]:
    """
    Build `gateway_meta` for routing logs: per-backend score, inflight, latency EWMA,
    error rate, circuit fields, and routing weights.
    """
    r = selector.routing
    rows: dict[str, object] = {}
    for b in selector.backends:
        st = selector.state[b.name]
        err = st.error_rate()
        score = (st.inflight * r.inflight_weight) + (st.latency_ms * r.latency_weight) + (err * r.error_weight)
        rows[b.name] = {
            "score": score,
            "inflight": st.inflight,
            "latency_ms": st.latency_ms,
            "error_rate": err,
            "requests": st.requests,
            "errors": st.errors,
            "circuit_open": st.circuit_open(),
            "circuit_half_open": st.circuit_half_open,
            "half_open_inflight": st.half_open_inflight,
            "half_open_successes": st.half_open_successes,
            "excluded": b.name in excluded,
            "eligible": (b.name not in excluded) and (not st.circuit_open()),
        }
    return {
        "backends": rows,
        "weights": {
            "inflight": r.inflight_weight,
            "latency": r.latency_weight,
            "error": r.error_weight,
        },
    }


@dataclass
class GatewayContext:
    """Shared process state: settings, selector, HTTP client, admission semaphore."""

    settings: Settings
    selector: BackendSelector
    client: httpx.AsyncClient
    queue: asyncio.Semaphore


def _safe_headers(req: Request) -> dict[str, str]:
    """Copy incoming headers except hop-by-hop fields (`host`, `content-length`)."""
    return {k: v for k, v in req.headers.items() if k.lower() not in _BLOCKED_HEADERS}


def _validate_headers(request: Request) -> tuple[str, str, str]:
    """Require `X-Request-Id`, `X-Trace-Id`, and `X-Session-Id` (400 if missing)."""
    request_id = request.headers.get("x-request-id")
    trace_id = request.headers.get("x-trace-id")
    session_id = request.headers.get("x-session-id")
    if not request_id or not trace_id or not session_id:
        raise HTTPException(status_code=400, detail="Missing X-Request-Id, X-Trace-Id, or X-Session-Id")
    return request_id, trace_id, session_id


@router.post("/v1/embeddings")
async def embeddings(request: Request) -> Response:
    """
    Proxy an embedding request to a selected backend.

    Flow: admission → parse JSON → retry loop (pick backend → POST upstream → metrics/logs).
    Retries exclude failed backends; `5xx` counts as selector failure for the breaker.
    """
    context: GatewayContext = request.app.state.gateway_context
    request_id, trace_id, session_id = _validate_headers(request)
    safe_headers = _safe_headers(request)
    retryable_statuses = context.settings.retry.retryable_statuses
    queue_wait_start = time.perf_counter()
    ADMISSION_INQUEUE.inc()
    acquired = False
    try:
        await asyncio.wait_for(
            context.queue.acquire(),
            timeout=context.settings.admission_queue.wait_timeout_ms / 1000.0,
        )
        acquired = True
    except asyncio.TimeoutError:
        ADMISSION_REJECTED.inc()
        log_gateway_event(
            logger,
            logging.WARNING,
            "admission_rejected",
            request_id=request_id,
            trace_id=trace_id,
            session_id=session_id,
            path=_EMBEDDINGS_PATH,
            status_code=429,
            error={"kind": "AdmissionQueueTimeout"},
            gateway_meta={"wait_timeout_ms": context.settings.admission_queue.wait_timeout_ms},
        )
        return JSONResponse(status_code=429, content={"error": "Gateway busy, try again"})
    finally:
        ADMISSION_INQUEUE.dec()

    queue_wait_ms = (time.perf_counter() - queue_wait_start) * 1000
    ADMISSION_WAIT.observe(queue_wait_ms)
    payload = await request.json()
    parsed = EmbeddingRequest.model_validate(payload)
    req_class = parsed.classify().value

    log_gateway_event(
        logger,
        logging.INFO,
        "gateway_started",
        request_id=request_id,
        trace_id=trace_id,
        session_id=session_id,
        path=_EMBEDDINGS_PATH,
        queue_wait_ms=queue_wait_ms,
        gateway_meta={
            "backends_count": len(context.settings.backends),
            "admission_max_concurrent": context.settings.admission_queue.max_concurrent,
            "admission_wait_timeout_ms": context.settings.admission_queue.wait_timeout_ms,
            "model": parsed.model,
            "request_class": req_class,
            "client_host": getattr(request.client, "host", None),
        },
    )

    try:
        excluded: set[str] = set()
        last_exc: Exception | None = None

        for attempt in range(1, context.settings.retry.max_attempts + 1):
            backend = context.selector.pick(excluded=excluded)
            if backend is None:
                FAILURES.labels(backend="none", reason="no_backend").inc()
                log_gateway_event(
                    logger,
                    logging.WARNING,
                    "routing_no_backend",
                    request_id=request_id,
                    trace_id=trace_id,
                    session_id=session_id,
                    path=_EMBEDDINGS_PATH,
                    queue_wait_ms=queue_wait_ms,
                    gateway_meta={"attempt": attempt, "excluded": sorted(excluded), **_routing_debug(context.selector, excluded)},
                )
                raise HTTPException(status_code=503, detail="No healthy backend available")

            log_gateway_event(
                logger,
                logging.INFO,
                "routing_pick",
                request_id=request_id,
                trace_id=trace_id,
                session_id=session_id,
                path=_EMBEDDINGS_PATH,
                backend=backend.name,
                queue_wait_ms=queue_wait_ms,
                gateway_meta={
                    "attempt": attempt,
                    "excluded": sorted(excluded),
                    "decision_reason": context.selector.last_pick_reason,
                    **_routing_debug(context.selector, excluded),
                },
            )

            start = time.perf_counter()
            context.selector.mark_start(backend.name)
            INFLIGHT.labels(backend=backend.name).inc()
            BACKEND_SELECTED.labels(backend=backend.name).inc()

            try:
                upstream = await context.client.post(
                    f"{backend.url}{_EMBEDDINGS_PATH}",
                    json=payload,
                    headers=safe_headers,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                success = upstream.status_code < 500
                context.selector.mark_result(backend.name, latency_ms, success=success)
                LATENCY.labels(backend=backend.name).observe(latency_ms)
                if upstream.status_code in retryable_statuses and attempt < context.settings.retry.max_attempts:
                    RETRIES.labels(backend=backend.name).inc()
                    INFLIGHT.labels(backend=backend.name).dec()
                    excluded.add(backend.name)
                    log_gateway_event(
                        logger,
                        logging.WARNING,
                        "backend_retry",
                        request_id=request_id,
                        trace_id=trace_id,
                        session_id=session_id,
                        path=_EMBEDDINGS_PATH,
                        backend=backend.name,
                        latency_ms=latency_ms,
                        queue_wait_ms=queue_wait_ms,
                        status_code=upstream.status_code,
                        gateway_meta={"attempt": attempt},
                    )
                    continue

                REQUESTS.labels(backend=backend.name, status=str(upstream.status_code), request_class=req_class).inc()
                INFLIGHT.labels(backend=backend.name).dec()
                log_gateway_event(
                    logger,
                    logging.INFO,
                    "request_finished",
                    request_id=request_id,
                    trace_id=trace_id,
                    session_id=session_id,
                    path=_EMBEDDINGS_PATH,
                    backend=backend.name,
                    latency_ms=latency_ms,
                    queue_wait_ms=queue_wait_ms,
                    status_code=upstream.status_code,
                    gateway_meta={
                        "model": parsed.model,
                        "request_class": req_class,
                        "attempt": attempt,
                    },
                )
                return Response(
                    content=upstream.content,
                    status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type"),
                )
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                latency_ms = (time.perf_counter() - start) * 1000
                context.selector.mark_result(backend.name, latency_ms, success=False)
                FAILURES.labels(backend=backend.name, reason=type(exc).__name__).inc()
                INFLIGHT.labels(backend=backend.name).dec()
                last_exc = exc
                if attempt < context.settings.retry.max_attempts:
                    RETRIES.labels(backend=backend.name).inc()
                    excluded.add(backend.name)
                    log_gateway_event(
                        logger,
                        logging.WARNING,
                        "backend_retry",
                        request_id=request_id,
                        trace_id=trace_id,
                        session_id=session_id,
                        path=_EMBEDDINGS_PATH,
                        backend=backend.name,
                        latency_ms=latency_ms,
                        queue_wait_ms=queue_wait_ms,
                        error={"kind": type(exc).__name__},
                        gateway_meta={"attempt": attempt},
                    )
                    continue
                break

        log_gateway_event(
            logger,
            logging.WARNING,
            "request_failed",
            request_id=request_id,
            trace_id=trace_id,
            session_id=session_id,
            path=_EMBEDDINGS_PATH,
            queue_wait_ms=queue_wait_ms,
            error={"kind": type(last_exc).__name__ if last_exc else "unknown"},
        )
        return JSONResponse(status_code=503, content={"error": "Backends unavailable"})
    finally:
        if acquired:
            context.queue.release()
