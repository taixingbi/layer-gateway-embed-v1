"""FastAPI app: proxy /v1/embeddings and /v1/models to vLLM backends."""
import sys
from pathlib import Path

if __name__ == "__main__":
    _src = Path(__file__).resolve().parent.parent
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from tb_router_embed.config import get_backends, get_max_concurrent, get_port
from tb_router_embed.router import proxy_request

_http_client: httpx.AsyncClient | None = None
_queue: asyncio.Semaphore | None = None

_SKIP_HEADERS = frozenset({"host", "content-length"})


def _err(code: int, msg: str) -> JSONResponse:
    return JSONResponse(status_code=code, content={"error": msg})


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client, _queue
    _http_client = httpx.AsyncClient(timeout=60.0)
    _queue = asyncio.Semaphore(get_max_concurrent())
    yield
    await _http_client.aclose()
    _http_client = None
    _queue = None


app = FastAPI(title="vLLM Embedding Router", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check: router is up."""
    return {"status": "ok"}


@app.api_route("/v1/embeddings", methods=["POST"])
@app.api_route("/v1/models", methods=["GET"])
async def proxy(request: Request):
    """Forward /v1/embeddings and /v1/models to backend(s)."""
    if _http_client is None or _queue is None:
        return _err(503, "Router not initialized")

    backends = get_backends()
    if not backends:
        return _err(503, "No backends configured. Set EMBEDDING_BACKENDS.")

    headers = {k: v for k, v in request.headers.items() if k.lower() not in _SKIP_HEADERS}

    try:
        async with _queue:
            resp, _ = await proxy_request(
                _http_client,
                request.method,
                request.url.path,
                content=await request.body(),
                headers=headers,
            )
        return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        return _err(503, f"All backends unavailable: {e!s}")


def run():
    """CLI entry point: run uvicorn server."""
    import uvicorn

    port = get_port()
    uvicorn.run(
        "tb_router_embed.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    run()
