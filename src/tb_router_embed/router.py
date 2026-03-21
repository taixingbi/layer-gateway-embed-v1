"""Backend selection and proxy logic for vLLM embedding router."""
import itertools

import httpx

from tb_router_embed.config import get_backends, get_request_timeout, get_strategy
_ROUND_ROBIN_INDEX: itertools.cycle | None = None


def _get_round_robin_index() -> itertools.cycle:
    global _ROUND_ROBIN_INDEX
    if _ROUND_ROBIN_INDEX is None:
        backends = get_backends()
        if not backends:
            raise ValueError("No backends configured. Set EMBEDDING_BACKENDS.")
        _ROUND_ROBIN_INDEX = itertools.cycle(range(len(backends)))
    return _ROUND_ROBIN_INDEX


def _select_backend() -> str:
    """Select backend URL based on strategy."""
    backends = get_backends()
    if not backends:
        raise ValueError("No backends configured. Set EMBEDDING_BACKENDS.")

    strategy = get_strategy()
    if strategy == "round_robin":
        idx = next(_get_round_robin_index())
        return backends[idx]
    if strategy == "failover":
        return backends[0]
    raise ValueError(f"Unknown ROUTER_STRATEGY: {strategy}. Use round_robin or failover.")


def _is_retryable(status_code: int) -> bool:
    return status_code == 408 or status_code >= 500


async def proxy_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    content: bytes | None = None,
    headers: dict | None = None,
) -> tuple[httpx.Response, str]:
    """
    Forward request to backend(s). Returns (response, backend_url_used).
    On failover: tries next backend on 5xx or timeout.
    Raises httpx.HTTPStatusError if all backends fail.
    """
    backends = get_backends()
    if not backends:
        raise ValueError("No backends configured. Set EMBEDDING_BACKENDS.")

    strategy = get_strategy()
    candidates = backends if strategy == "failover" else [_select_backend()]

    last_error: Exception | None = None
    last_response: httpx.Response | None = None

    timeout = get_request_timeout()
    for base_url in candidates:
        url = f"{base_url}{path}"
        try:
            resp = await client.request(
                method, url, content=content, headers=headers, timeout=timeout
            )
            if strategy == "failover" and _is_retryable(resp.status_code):
                await resp.aread()  # Consume body to release connection before retry
                last_response = resp
                continue
            return resp, base_url
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_error = e
            continue

    if last_response is not None:
        return last_response, candidates[-1]
    if last_error is not None:
        raise last_error
    raise RuntimeError("No backends available")
