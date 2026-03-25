"""Proxy /v1/embeddings and /v1/models to vLLM."""
import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from .config import get_backends, get_internal_api_key, get_max_concurrent, get_port, get_timeout
from .router import proxy

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
    client = httpx.AsyncClient(timeout=get_timeout())
    queue = asyncio.Semaphore(get_max_concurrent())
    yield
    await client.aclose()
    client = queue = None


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
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


@app.api_route("/v1/embeddings", methods=["POST"])
@app.api_route("/v1/models", methods=["GET"])
async def route(
    request: Request,
    x_internal_key: str | None = Header(default=None),
):
    verify_internal_key(x_internal_key)
    if not client or not queue:
        return JSONResponse(status_code=503, content={"error": "Not ready"})
    if not get_backends():
        return JSONResponse(status_code=503, content={"error": "No backends. Set EMBEDDING_BACKENDS."})

    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _SKIP_REQUEST_HEADERS
    }
    try:
        async with queue:
            r = await proxy(client, request.method, request.url.path, await request.body(), headers)
        return Response(r.content, r.status_code, _response_headers(r))
    except (httpx.TimeoutException, httpx.ConnectError):
        return JSONResponse(status_code=503, content={"error": "Backends unavailable"})


def run():
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=get_port())


if __name__ == "__main__":
    run()
