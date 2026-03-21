"""Proxy /v1/embeddings and /v1/models to vLLM."""
import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from router_embed.config import get_backends, get_max_concurrent, get_port, get_timeout
from router_embed.router import proxy

client: httpx.AsyncClient | None = None
 queue: asyncio.Semaphore | None = None
SKIP = frozenset({"host", "content-length"})


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


@app.api_route("/v1/embeddings", methods=["POST"])
@app.api_route("/v1/models", methods=["GET"])
async def route(request: Request):
    if not client or not queue:
        return JSONResponse(status_code=503, content={"error": "Not ready"})
    if not get_backends():
        return JSONResponse(status_code=503, content={"error": "No backends. Set EMBEDDING_BACKENDS."})

    headers = {k: v for k, v in request.headers.items() if k.lower() not in SKIP}
    try:
        async with queue:
            r = await proxy(client, request.method, request.url.path, await request.body(), headers)
        return Response(r.content, r.status_code, dict(r.headers))
    except (httpx.TimeoutException, httpx.ConnectError):
        return JSONResponse(status_code=503, content={"error": "Backends unavailable"})


def run():
    import uvicorn
    uvicorn.run("router_embed.server:app", host="0.0.0.0", port=get_port())


if __name__ == "__main__":
    run()
