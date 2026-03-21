"""
Configuration for vLLM embedding router.
Uses defaults below; override via environment variables or configure().
"""
import os

_overrides: dict = {}

DEFAULT_BACKENDS = "192.168.86.173:8001,192.168.86.176:8001"
DEFAULT_STRATEGY = "failover"
DEFAULT_PORT = 8011
DEFAULT_MAX_CONCURRENT = 20
DEFAULT_REQUEST_TIMEOUT = 60.0
DEFAULT_EMBEDDING_URL = "http://localhost:8011"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_CLIENT_MAX_CONCURRENT = 20


def configure(
    backends: str | None = None,
    strategy: str | None = None,
    port: int | None = None,
    max_concurrent: int | None = None,
    request_timeout: float | None = None,
    embedding_url: str | None = None,
    embedding_model: str | None = None,
    client_max_concurrent: int | None = None,
    **kwargs,
) -> None:
    """Set configuration overrides (used before starting the server).
    Affects only the process that calls this. For a separate router process,
    set EMBEDDING_BACKENDS in that process's environment and restart the router.
    """
    global _overrides
    opts = {
        "backends": backends,
        "strategy": strategy,
        "port": port,
        "max_concurrent": max_concurrent,
        "request_timeout": request_timeout,
        "embedding_url": embedding_url,
        "embedding_model": embedding_model,
        "client_max_concurrent": client_max_concurrent,
        **kwargs,
    }
    for k, v in opts.items():
        if v is not None:
            _overrides[k] = v


def get_backends() -> list[str]:
    """Backend URLs: override > env > default. Returns list of base URLs."""
    raw = _overrides.get("backends") or os.getenv("EMBEDDING_BACKENDS", DEFAULT_BACKENDS)
    urls = []
    for b in raw.split(","):
        b = b.strip()
        if not b:
            continue
        if not b.startswith(("http://", "https://")):
            b = f"http://{b}"
        urls.append(b.rstrip("/"))
    return urls


def get_strategy() -> str:
    """Routing strategy: override > env > default. One of round_robin, failover."""
    return _overrides.get("strategy") or os.getenv("ROUTER_STRATEGY", DEFAULT_STRATEGY)


def get_port() -> int:
    """Router port: override > env > default. Do not use 8001 (reserved for vLLM backends)."""
    raw = _overrides.get("port") or os.getenv("ROUTER_PORT", str(DEFAULT_PORT))
    return int(raw)


def get_max_concurrent() -> int:
    """Max concurrent requests to backends; excess wait in queue."""
    raw = _overrides.get("max_concurrent") or os.getenv(
        "ROUTER_MAX_CONCURRENT", str(DEFAULT_MAX_CONCURRENT)
    )
    return int(raw)


def get_request_timeout() -> float:
    """Request timeout in seconds for backend and client calls."""
    raw = _overrides.get("request_timeout") or os.getenv(
        "ROUTER_REQUEST_TIMEOUT", str(DEFAULT_REQUEST_TIMEOUT)
    )
    return float(raw)


def get_embedding_url() -> str:
    """URL for SDK client: router or vLLM API (override > env > default)."""
    return _overrides.get("embedding_url") or os.getenv(
        "EMBEDDING_URL", DEFAULT_EMBEDDING_URL
    )


def get_embedding_model() -> str:
    """Embedding model name for SDK (override > env > default)."""
    return _overrides.get("embedding_model") or os.getenv(
        "EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
    )


def get_client_max_concurrent() -> int:
    """Max concurrent requests from SDK client (override > env > default)."""
    raw = _overrides.get("client_max_concurrent") or os.getenv(
        "EMBED_CLIENT_MAX_CONCURRENT", str(DEFAULT_CLIENT_MAX_CONCURRENT)
    )
    return int(raw)
