"""Proxy to vLLM backends with failover or round-robin."""
import threading
from typing import NamedTuple

import httpx

from .config import get_backends, get_retry_attempts, get_strategy, get_timeout
from .logging_config import logger

# Shared with app.main for except clauses (connect/timeout while talking to backends).
TRANSIENT_UPSTREAM_ERRORS: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
)

_rr_lock = threading.Lock()
_rr_key: tuple[str, ...] | None = None
_rr_idx = 0


class ProxyResult(NamedTuple):
    response: httpx.Response
    backend_url: str


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


def _status_triggers_failover(status_code: int) -> bool:
    return status_code == 408 or status_code >= 500


async def _request_once(
    client: httpx.AsyncClient,
    url: str,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> httpx.Response:
    return await client.request(
        method, f"{url}{path}", content=body, headers=headers, timeout=timeout
    )


async def proxy(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
) -> ProxyResult:
    backends = get_backends()
    if not backends:
        raise ValueError("No backends. Set EMBEDDING_BACKENDS.")

    strategy = get_strategy()
    candidates = _candidate_backends(strategy, backends)
    timeout = get_timeout()
    # attempts=1 is intentional: one request per backend candidate unless configured otherwise.
    attempts = get_retry_attempts()
    err, last_resp, last_backend_url = None, None, None

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
                if strategy == "failover" and _status_triggers_failover(r.status_code):
                    await r.aread()
                    logger.warning(
                        "upstream error response",
                        extra={
                            "backend": url,
                            "upstream_status": r.status_code,
                            "reason": "failover_status",
                        },
                    )
                    last_resp, last_backend_url, err = r, url, None
                    if attempt < attempts - 1:
                        continue
                    break
                return ProxyResult(r, url)
            except TRANSIENT_UPSTREAM_ERRORS as e:
                err = e
                logger.warning(
                    "upstream request failed",
                    extra={
                        "backend": url,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "reason": "connect_or_timeout",
                    },
                    exc_info=True,
                )
                if attempt < attempts - 1:
                    continue
                break

    if last_resp is not None and last_backend_url is not None:
        return ProxyResult(last_resp, last_backend_url)
    raise err or RuntimeError("No backends")
