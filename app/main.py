"""Proxy /v1/embeddings and /v1/models to vLLM."""
import asyncio
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from .config import (
    get_backends,
    get_gpu_trace_header,
    get_internal_api_key,
    get_max_concurrent,
    get_port,
    get_retry_attempts,
    get_strategy,
    get_timeout,
    validate_config,
)
from .logging_config import logger, setup_logging, shutdown_logging
from .request_context import RequestContextMiddleware, get_request_id, get_session_id
from .router import TRANSIENT_UPSTREAM_ERRORS, proxy

client: httpx.AsyncClient | None = None
queue: asyncio.Semaphore | None = None

# Hop-by-hop and headers httpx will replace from message body.
_SKIP_REQUEST_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "connection",
        "keep-alive",
        "proxy-connection",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "x-internal-key",
    }
)

# httpx may decompress the body; strip encodings the client must not apply again.
_SKIP_RESPONSE_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "content-encoding",
        "transfer-encoding",
        "content-length",
    }
)


@asynccontextmanager
async def lifespan(_):
    global client, queue
    validate_config()
    setup_logging()
    client = httpx.AsyncClient(timeout=get_timeout())
    queue = asyncio.Semaphore(get_max_concurrent())
    logger.info(
        "gateway started (backends=%s strategy=%s timeout=%ss max_concurrent=%s retry_attempts=%s)",
        len(get_backends()),
        get_strategy(),
        get_timeout(),
        get_max_concurrent(),
        get_retry_attempts(),
    )
    yield
    logger.info("gateway stopping")
    await client.aclose()
    client = queue = None
    shutdown_logging()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)


@app.get("/health")
def health():
    logger.info("layer-gateway-embed-v1 health ok")
    return {"status": "ok"}


def verify_internal_key(x_internal_key: str | None) -> None:
    expected = get_internal_api_key()
    if not expected:
        raise HTTPException(status_code=500, detail="Server misconfigured")
    if x_internal_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _response_headers(upstream: httpx.Response) -> dict[str, str]:
    return {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in _SKIP_RESPONSE_HEADERS
    }


def _gpu_trace_for_log(headers: httpx.Headers, header_name: str) -> str | None:
    name = header_name.strip()
    if not name:
        return None
    v = headers.get(name)
    return v if v is not None else "-"


def _service_unavailable_json(reason: str, error_body: str) -> JSONResponse:
    logger.warning("service unavailable", extra={"status": 503, "reason": reason})
    return JSONResponse(status_code=503, content={"error": error_body})


def _ensure_ready() -> JSONResponse | None:
    if not client or not queue:
        return _service_unavailable_json("not_ready", "Not ready")
    if not get_backends():
        return _service_unavailable_json("no_backends", "No backends. Set EMBEDDING_BACKENDS.")
    return None


def _upstream_headers(request: Request) -> dict[str, str]:
    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _SKIP_REQUEST_HEADERS
    }
    headers["x-request-id"] = get_request_id()
    sid = get_session_id()
    if sid != "-":
        headers["x-session-id"] = sid
    return headers


@app.api_route("/v1/embeddings", methods=["POST"])
@app.api_route("/v1/models", methods=["GET"])
async def route(
    request: Request,
    x_internal_key: str | None = Header(default=None),
):
    verify_internal_key(x_internal_key)
    not_ready = _ensure_ready()
    if not_ready:
        return not_ready

    headers = _upstream_headers(request)
    body = await request.body()
    try:
        t0 = time.perf_counter()
        async with queue:
            result = await proxy(client, request.method, request.url.path, body, headers)
        r = result.response
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        extra: dict[str, object] = {
            "status": r.status_code,
            "duration_ms": elapsed_ms,
            "backend": result.backend_url,
        }
        gpu_log = _gpu_trace_for_log(r.headers, get_gpu_trace_header())
        if gpu_log is not None:
            extra["gpu"] = gpu_log
        logger.info("proxied upstream response", extra=extra)
        return Response(r.content, r.status_code, _response_headers(r))
    except TRANSIENT_UPSTREAM_ERRORS as e:
        logger.warning(
            "backends unavailable",
            extra={
                "status": 503,
                "reason": "upstream_unreachable",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )
        return JSONResponse(status_code=503, content={"error": "Backends unavailable"})


def run():
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=get_port())


if __name__ == "__main__":
    run()
