"""Proxy to vLLM backends with failover or round-robin."""
import threading

import httpx

from .config import get_backends, get_retry_attempts, get_strategy, get_timeout
from .logging_config import logger

_rr_lock = threading.Lock()
_rr_key: tuple[str, ...] | None = None
_rr_idx = 0


def _next_round_robin_backend(backends: list[str]) -> str:
    global _rr_key, _rr_idx
    key = tuple(backends)
    with _rr_lock:
        if _rr_key != key:
            _rr_key = key
            _rr_idx = 0
        backend = backends[_rr_idx % len(backends)]
        _rr_idx = (_rr_idx + 1) % len(backends)
        return backend


def _candidate_backends(strategy: str, backends: list[str]) -> list[str]:
    if strategy == "round_robin":
        return [_next_round_robin_backend(backends)]
    return backends


async def _request_once(
    client: httpx.AsyncClient,
    url: str,
    method: str,
    path: str,
    body: bytes,
    headers: dict,
    timeout: float,
) -> httpx.Response:
    return await client.request(
        method, f"{url}{path}", content=body, headers=headers, timeout=timeout
    )


async def proxy(client: httpx.AsyncClient, method: str, path: str, body: bytes, headers: dict):
    backends = get_backends()
    if not backends:
        raise ValueError("No backends. Set EMBEDDING_BACKENDS.")

    strategy = get_strategy()
    candidates = _candidate_backends(strategy, backends)
    timeout = get_timeout()
    # attempts=1 is intentional: one request per backend candidate unless configured otherwise.
    attempts = get_retry_attempts()
    err, last_resp = None, None

    logger.info(
        "proxy %s %s strategy=%s candidates=%d timeout=%s body_bytes=%d",
        method,
        path,
        strategy,
        len(candidates),
        timeout,
        len(body),
    )

    for idx, url in enumerate(candidates):
        if idx > 0:
            logger.info("failover: try backend %s for %s", url, path)
        for attempt in range(attempts):
            try:
                r = await _request_once(client, url, method, path, body, headers, timeout)
                if strategy == "failover" and (r.status_code == 408 or r.status_code >= 500):
                    await r.aread()
                    logger.warning("backend %s returned %s for %s", url, r.status_code, path)
                    last_resp, err = r, None
                    if attempt < attempts - 1:
                        continue
                    break
                return r
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                err = e
                logger.warning("backend %s failed for %s: %s", url, path, e)
                if attempt < attempts - 1:
                    continue
                break

    if last_resp:
        return last_resp
    raise err or RuntimeError("No backends")
