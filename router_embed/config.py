"""Config: override > env > default."""
import os

_overrides: dict = {}

DEFAULT_BACKENDS = "192.168.86.173:8001,192.168.86.176:8001"
DEFAULT_STRATEGY = "failover"
DEFAULT_PORT = 8011
DEFAULT_MAX_CONCURRENT = 20
DEFAULT_TIMEOUT = 60.0


def _v(key: str, env: str, default: str) -> str:
    return _overrides.get(key) or os.getenv(env, default)


def configure(**kwargs) -> None:
    for k, v in kwargs.items():
        if v is not None:
            _overrides[k] = v


def get_backends() -> list[str]:
    raw = _v("backends", "EMBEDDING_BACKENDS", DEFAULT_BACKENDS)
    return [
        (b if "://" in b else f"http://{b}").rstrip("/")
        for b in raw.split(",")
        if (b := b.strip())
    ]


def get_strategy() -> str:
    return _v("strategy", "ROUTER_STRATEGY", DEFAULT_STRATEGY)


def get_port() -> int:
    return int(_v("port", "ROUTER_PORT", str(DEFAULT_PORT)))


def get_max_concurrent() -> int:
    return int(_v("max_concurrent", "ROUTER_MAX_CONCURRENT", str(DEFAULT_MAX_CONCURRENT)))


def get_timeout() -> float:
    return float(_v("request_timeout", "ROUTER_REQUEST_TIMEOUT", str(DEFAULT_TIMEOUT)))
