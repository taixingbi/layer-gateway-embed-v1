"""Proxy to vLLM backends with failover or round-robin."""
import itertools

import httpx

from router_embed.config import get_backends, get_strategy, get_timeout

_rr: itertools.cycle | None = None


def _next_backend() -> str:
    backends = get_backends()
    if not backends:
        raise ValueError("No backends. Set EMBEDDING_BACKENDS.")
    if get_strategy() == "failover":
        return backends[0]
    global _rr
    if _rr is None:
        _rr = itertools.cycle(backends)
    return next(_rr)


async def proxy(client: httpx.AsyncClient, method: str, path: str, body: bytes, headers: dict):
    backends = get_backends()
    if not backends:
        raise ValueError("No backends. Set EMBEDDING_BACKENDS.")

    strategy = get_strategy()
    candidates = backends if strategy == "failover" else [_next_backend()]
    timeout = get_timeout()
    err, last_resp = None, None

    for url in candidates:
        try:
            r = await client.request(method, f"{url}{path}", content=body, headers=headers, timeout=timeout)
            if strategy == "failover" and (r.status_code == 408 or r.status_code >= 500):
                await r.aread()
                last_resp, err = r, None
                continue
            return r
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            err = e
            continue

    if last_resp:
        return last_resp
    raise err or RuntimeError("No backends")
