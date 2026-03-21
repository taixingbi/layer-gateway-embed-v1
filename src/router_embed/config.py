"""
Configuration for vLLM embedding router.
Loads .env if present; values can be overridden by environment variables or configure().
"""
import os

from dotenv import load_dotenv

load_dotenv()

_overrides: dict = {}

DEFAULT_BACKENDS = "192.168.86.173:8001,192.168.86.176:8001"
DEFAULT_STRATEGY = "failover"
DEFAULT_PORT = 8011
DEFAULT_MAX_CONCURRENT = 20


def configure(
    backends: str | None = None,
    strategy: str | None = None,
    port: int | None = None,
    max_concurrent: int | None = None,
    **kwargs,
) -> None:
    """Set configuration overrides (used before starting the server)."""
    global _overrides
    if backends is not None:
        _overrides["backends"] = backends
    if strategy is not None:
        _overrides["strategy"] = strategy
    if port is not None:
        _overrides["port"] = port
    if max_concurrent is not None:
        _overrides["max_concurrent"] = max_concurrent
    for k, v in kwargs.items():
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
