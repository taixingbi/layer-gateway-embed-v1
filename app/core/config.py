from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 30181


@dataclass(frozen=True)
class TimeoutConfig:
    connect_ms: int = 1000
    read_ms: int = 15000


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 2
    retryable_statuses: tuple[int, ...] = (502, 503, 504)


@dataclass(frozen=True)
class CircuitBreakerConfig:
    failure_threshold: int = 5
    reset_timeout_sec: int = 30
    half_open_max_probes: int = 1
    half_open_success_threshold: int = 1


@dataclass(frozen=True)
class RoutingConfig:
    inflight_weight: float = 20.0
    latency_weight: float = 0.5
    error_weight: float = 100.0
    exploration_rate: float = 0.15
    max_idle_ms: int = 500


@dataclass(frozen=True)
class AdmissionQueueConfig:
    max_concurrent: int = 20
    wait_timeout_ms: int = 100


@dataclass(frozen=True)
class BackendConfig:
    name: str
    url: str


@dataclass(frozen=True)
class LogConfig:
    level: str = "INFO"
    json: bool = True


@dataclass(frozen=True)
class Settings:
    server: ServerConfig
    timeouts: TimeoutConfig
    retry: RetryConfig
    circuit_breaker: CircuitBreakerConfig
    routing: RoutingConfig
    admission_queue: AdmissionQueueConfig
    backends: tuple[BackendConfig, ...]
    log: LogConfig


def _to_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes")


def _to_float_clamped(raw: str | None, default: float, *, minimum: float, maximum: float) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _get_backend_configs() -> tuple[BackendConfig, ...]:
    raw = os.getenv("EMBED_BACKENDS", "embed-node-1=http://127.0.0.1:8001")
    backends: list[BackendConfig] = []
    for item in raw.split(","):
        entry = item.strip()
        if not entry:
            continue
        if "=" in entry:
            name, url = entry.split("=", 1)
            backends.append(BackendConfig(name=name.strip(), url=url.strip().rstrip("/")))
        else:
            url = entry.rstrip("/")
            backends.append(BackendConfig(name=f"backend-{len(backends)+1}", url=url))
    return tuple(backends)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        level = "INFO"
    return Settings(
        server=ServerConfig(
            host=os.getenv("GATEWAY_HOST", "0.0.0.0"),
            port=int(os.getenv("GATEWAY_PORT", "30181")),
        ),
        timeouts=TimeoutConfig(
            connect_ms=int(os.getenv("TIMEOUT_CONNECT_MS", "1000")),
            read_ms=int(os.getenv("TIMEOUT_READ_MS", "15000")),
        ),
        retry=RetryConfig(
            max_attempts=max(1, int(os.getenv("RETRY_MAX_ATTEMPTS", "2"))),
            retryable_statuses=(502, 503, 504),
        ),
        circuit_breaker=CircuitBreakerConfig(
            failure_threshold=max(1, int(os.getenv("CB_FAILURE_THRESHOLD", "5"))),
            reset_timeout_sec=max(1, int(os.getenv("CB_RESET_TIMEOUT_SEC", "30"))),
            half_open_max_probes=max(1, int(os.getenv("CB_HALF_OPEN_MAX_PROBES", "1"))),
            half_open_success_threshold=max(1, int(os.getenv("CB_HALF_OPEN_SUCCESS_THRESHOLD", "1"))),
        ),
        routing=RoutingConfig(
            inflight_weight=float(os.getenv("ROUTING_INFLIGHT_WEIGHT", "20.0")),
            latency_weight=float(os.getenv("ROUTING_LATENCY_WEIGHT", "0.5")),
            error_weight=float(os.getenv("ROUTING_ERROR_WEIGHT", "100.0")),
            exploration_rate=_to_float_clamped(
                os.getenv("ROUTING_EXPLORATION_RATE"),
                0.15,
                minimum=0.0,
                maximum=1.0,
            ),
            max_idle_ms=max(0, int(os.getenv("ROUTING_MAX_IDLE_MS", "500"))),
        ),
        admission_queue=AdmissionQueueConfig(
            max_concurrent=max(1, int(os.getenv("ADMISSION_MAX_CONCURRENT", "20"))),
            wait_timeout_ms=max(1, int(os.getenv("ADMISSION_WAIT_TIMEOUT_MS", "100"))),
        ),
        backends=_get_backend_configs(),
        log=LogConfig(level=level, json=_to_bool(os.getenv("LOG_JSON"), True)),
    )
