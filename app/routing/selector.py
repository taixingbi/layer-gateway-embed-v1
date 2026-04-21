from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

from app.core.config import BackendConfig, CircuitBreakerConfig, RoutingConfig


@dataclass
class BackendState:
    inflight: int = 0
    latency_ms: float = 0.0
    errors: int = 0
    requests: int = 0
    consecutive_failures: int = 0
    circuit_open_until: float = 0.0

    def error_rate(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.errors / self.requests

    def circuit_open(self) -> bool:
        return time.time() < self.circuit_open_until


class BackendSelector:
    def __init__(
        self,
        backends: tuple[BackendConfig, ...],
        routing: RoutingConfig,
        circuit_breaker: CircuitBreakerConfig,
    ) -> None:
        self.backends = backends
        self.routing = routing
        self.circuit_breaker = circuit_breaker
        self.state: Dict[str, BackendState] = {b.name: BackendState() for b in backends}

    def pick(self, excluded: set[str] | None = None) -> BackendConfig | None:
        excluded_names = excluded or set()
        best_backend: BackendConfig | None = None
        best_score = float("inf")
        for backend in self.backends:
            if backend.name in excluded_names:
                continue
            state = self.state[backend.name]
            if state.circuit_open():
                continue
            score = (
                (state.inflight * self.routing.inflight_weight)
                + (state.latency_ms * self.routing.latency_weight)
                + (state.error_rate() * self.routing.error_weight)
            )
            if score < best_score:
                best_score = score
                best_backend = backend
        return best_backend

    def mark_start(self, backend_name: str) -> None:
        self.state[backend_name].inflight += 1

    def mark_result(self, backend_name: str, latency_ms: float, success: bool) -> None:
        s = self.state[backend_name]
        s.inflight = max(0, s.inflight - 1)
        s.requests += 1
        if success:
            s.latency_ms = latency_ms if s.latency_ms == 0 else (s.latency_ms * 0.01) + (latency_ms * 0.99)
            s.consecutive_failures = 0
            s.circuit_open_until = 0.0
            return
        s.errors += 1
        s.consecutive_failures += 1
        if s.consecutive_failures >= self.circuit_breaker.failure_threshold:
            s.circuit_open_until = time.time() + self.circuit_breaker.reset_timeout_sec
