"""Gateway YAML configuration models and loader."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ServerYamlConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class TimeoutYamlConfig(BaseModel):
    connect_ms: int = 1000
    read_ms: int = 15000


class RetryYamlConfig(BaseModel):
    max_attempts: int = 2
    retryable_statuses: list[int] = Field(default_factory=lambda: [502, 503, 504])


class CircuitBreakerYamlConfig(BaseModel):
    failure_threshold: int = 5
    reset_timeout_sec: int = 30
    half_open_max_probes: int = 1
    half_open_success_threshold: int = 1


class RoutingYamlConfig(BaseModel):
    inflight_weight: float = 8.0
    latency_weight: float = 0.5
    error_weight: float = 100.0
    hot_penalty_weight: float = 20.0
    overload_penalty_weight: float = 15.0
    hot_window_sec: float = 2.0
    hot_target_share: float = 0.55


class AdmissionYamlConfig(BaseModel):
    max_concurrent: int = 128
    wait_timeout_ms: int = 500


class BackendYamlEntry(BaseModel):
    name: str
    url: str
    soft_limit: int = 32
    hard_limit: int = 64
    drained: bool = False


class GatewayYamlConfig(BaseModel):
    server: ServerYamlConfig = Field(default_factory=ServerYamlConfig)
    timeouts: TimeoutYamlConfig = Field(default_factory=TimeoutYamlConfig)
    retry: RetryYamlConfig = Field(default_factory=RetryYamlConfig)
    circuit_breaker: CircuitBreakerYamlConfig = Field(default_factory=CircuitBreakerYamlConfig)
    routing: RoutingYamlConfig = Field(default_factory=RoutingYamlConfig)
    admission: AdmissionYamlConfig = Field(default_factory=AdmissionYamlConfig)
    backends: list[BackendYamlEntry] = Field(default_factory=list)


def load_gateway_yaml_config(path: str | Path | None = None) -> GatewayYamlConfig:
    """Load and validate ``config.yaml`` (or ``path`` / ``GATEWAY_CONFIG``)."""
    p = Path(path or os.environ.get("GATEWAY_CONFIG", "config.yaml"))
    raw = yaml.safe_load(p.read_text())
    return GatewayYamlConfig.model_validate(raw)
