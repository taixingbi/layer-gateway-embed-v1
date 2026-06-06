"""Load gateway settings from YAML (GATEWAY_CONFIG) or environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.gateway_config import GatewayYamlConfig, load_gateway_yaml_config


@dataclass(frozen=True)
class ServerConfig:
    """HTTP bind address for uvicorn."""

    host: str = "0.0.0.0"
    port: int = 30181


@dataclass(frozen=True)
class TimeoutConfig:
    """Upstream `httpx` timeouts (connect + read/write/pool)."""

    connect_ms: int = 1000
    read_ms: int = 15000


@dataclass(frozen=True)
class RetryConfig:
    """Per-client-request retry budget and retryable HTTP status codes."""

    max_attempts: int = 2
    retryable_statuses: tuple[int, ...] = (502, 503, 504)


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Per-backend circuit breaker thresholds and half-open probe limits."""

    failure_threshold: int = 5
    reset_timeout_sec: int = 30
    half_open_max_probes: int = 1
    half_open_success_threshold: int = 1


@dataclass(frozen=True)
class RoutingConfig:
    """Routing score weights plus optional exploration and idle-rebalance tuning."""

    inflight_weight: float = 8.0
    latency_weight: float = 0.5
    error_weight: float = 100.0
    hot_penalty_weight: float = 20.0
    overload_penalty_weight: float = 15.0
    hot_window_sec: float = 2.0
    hot_target_share: float = 0.55
    exploration_rate: float = 0.0
    max_idle_ms: int = 0


@dataclass(frozen=True)
class AdmissionQueueConfig:
    """Admission semaphore: max in-flight work and max wait before HTTP 429."""

    max_concurrent: int = 128
    wait_timeout_ms: int = 500


@dataclass(frozen=True)
class BackendConfig:
    """Named upstream base URL (path `/v1/embeddings` is appended by the handler)."""

    name: str
    url: str
    soft_limit: int = 32
    hard_limit: int = 64
    drained: bool = False


@dataclass(frozen=True)
class LogConfig:
    """Root logger level and JSON vs plain formatting."""

    level: str = "INFO"
    json: bool = True


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of all runtime configuration."""

    server: ServerConfig
    timeouts: TimeoutConfig
    retry: RetryConfig
    circuit_breaker: CircuitBreakerConfig
    routing: RoutingConfig
    admission_queue: AdmissionQueueConfig
    backends: tuple[BackendConfig, ...]
    log: LogConfig


def _to_bool(raw: str | None, default: bool) -> bool:
    """Parse env booleans (`1/true/yes`)."""
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes")


def _to_float_clamped(raw: str | None, default: float, *, minimum: float, maximum: float) -> float:
    """Parse a float env value and clamp it to `[minimum, maximum]`."""
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _get_log_config() -> LogConfig:
    level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        level = "INFO"
    return LogConfig(level=level, json=_to_bool(os.getenv("LOG_JSON"), True))


def _settings_from_yaml(cfg: GatewayYamlConfig, log: LogConfig) -> Settings:
    """Build Settings from validated YAML config."""
    return Settings(
        server=ServerConfig(host=cfg.server.host, port=cfg.server.port),
        timeouts=TimeoutConfig(connect_ms=cfg.timeouts.connect_ms, read_ms=cfg.timeouts.read_ms),
        retry=RetryConfig(
            max_attempts=max(1, cfg.retry.max_attempts),
            retryable_statuses=tuple(cfg.retry.retryable_statuses),
        ),
        circuit_breaker=CircuitBreakerConfig(
            failure_threshold=max(1, cfg.circuit_breaker.failure_threshold),
            reset_timeout_sec=max(1, cfg.circuit_breaker.reset_timeout_sec),
            half_open_max_probes=max(1, cfg.circuit_breaker.half_open_max_probes),
            half_open_success_threshold=max(1, cfg.circuit_breaker.half_open_success_threshold),
        ),
        routing=RoutingConfig(
            inflight_weight=cfg.routing.inflight_weight,
            latency_weight=cfg.routing.latency_weight,
            error_weight=cfg.routing.error_weight,
            hot_penalty_weight=cfg.routing.hot_penalty_weight,
            overload_penalty_weight=cfg.routing.overload_penalty_weight,
            hot_window_sec=cfg.routing.hot_window_sec,
            hot_target_share=cfg.routing.hot_target_share,
            exploration_rate=0.0,
            max_idle_ms=0,
        ),
        admission_queue=AdmissionQueueConfig(
            max_concurrent=max(1, cfg.admission.max_concurrent),
            wait_timeout_ms=max(1, cfg.admission.wait_timeout_ms),
        ),
        backends=tuple(
            BackendConfig(
                name=b.name,
                url=b.url.rstrip("/"),
                soft_limit=b.soft_limit,
                hard_limit=b.hard_limit,
                drained=b.drained,
            )
            for b in cfg.backends
            if not b.drained
        ),
        log=log,
    )


def _get_backend_configs() -> tuple[BackendConfig, ...]:
    """Parse `EMBED_BACKENDS` (`name=url` pairs, comma-separated)."""
    soft_limit = max(1, int(os.getenv("EMBED_BACKEND_SOFT_LIMIT", "32")))
    hard_limit = max(soft_limit, int(os.getenv("EMBED_BACKEND_HARD_LIMIT", "64")))
    raw = os.getenv("EMBED_BACKENDS", "embed-node-1=http://127.0.0.1:8001")
    backends: list[BackendConfig] = []
    for item in raw.split(","):
        entry = item.strip()
        if not entry:
            continue
        if "=" in entry:
            name, url = entry.split("=", 1)
            backends.append(
                BackendConfig(
                    name=name.strip(),
                    url=url.strip().rstrip("/"),
                    soft_limit=soft_limit,
                    hard_limit=hard_limit,
                )
            )
        else:
            url = entry.rstrip("/")
            backends.append(
                BackendConfig(
                    name=f"backend-{len(backends)+1}",
                    url=url,
                    soft_limit=soft_limit,
                    hard_limit=hard_limit,
                )
            )
    return tuple(backends)


def _settings_from_env(log: LogConfig) -> Settings:
    """Build Settings from environment variables (local dev)."""
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
            inflight_weight=float(os.getenv("ROUTING_INFLIGHT_WEIGHT", "8.0")),
            latency_weight=float(os.getenv("ROUTING_LATENCY_WEIGHT", "0.5")),
            error_weight=float(os.getenv("ROUTING_ERROR_WEIGHT", "100.0")),
            hot_penalty_weight=float(os.getenv("ROUTING_HOT_PENALTY_WEIGHT", "20.0")),
            overload_penalty_weight=float(os.getenv("ROUTING_OVERLOAD_PENALTY_WEIGHT", "15.0")),
            hot_window_sec=float(os.getenv("ROUTING_HOT_WINDOW_SEC", "2.0")),
            hot_target_share=float(os.getenv("ROUTING_HOT_TARGET_SHARE", "0.55")),
            exploration_rate=_to_float_clamped(
                os.getenv("ROUTING_EXPLORATION_RATE"),
                0.0,
                minimum=0.0,
                maximum=1.0,
            ),
            max_idle_ms=max(0, int(os.getenv("ROUTING_MAX_IDLE_MS", "0"))),
        ),
        admission_queue=AdmissionQueueConfig(
            max_concurrent=max(1, int(os.getenv("ADMISSION_MAX_CONCURRENT", "128"))),
            wait_timeout_ms=max(1, int(os.getenv("ADMISSION_WAIT_TIMEOUT_MS", "500"))),
        ),
        backends=_get_backend_configs(),
        log=log,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings; restart the process to pick up env/config changes."""
    log = _get_log_config()
    config_path = os.getenv("GATEWAY_CONFIG")
    if config_path and Path(config_path).is_file():
        return _settings_from_yaml(load_gateway_yaml_config(config_path), log)
    return _settings_from_env(log)
