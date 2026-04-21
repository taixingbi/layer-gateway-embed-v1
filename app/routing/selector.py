from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
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
    last_selected_at: float = field(default_factory=time.time)

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
        rng: random.Random | None = None,
    ) -> None:
        self.backends = backends
        self.routing = routing
        self.circuit_breaker = circuit_breaker
        self.rng = rng or random.Random()
        self.state: Dict[str, BackendState] = {b.name: BackendState() for b in backends}
        self.last_pick_reason = "score"

    def _score(self, backend_name: str) -> float:
        state = self.state[backend_name]
        return (
            (state.inflight * self.routing.inflight_weight)
            + (state.latency_ms * self.routing.latency_weight)
            + (state.error_rate() * self.routing.error_weight)
        )

    def _eligible_backends(self, excluded_names: set[str]) -> list[BackendConfig]:
        eligible: list[BackendConfig] = []
        for backend in self.backends:
            if backend.name in excluded_names:
                continue
            if self.state[backend.name].circuit_open():
                continue
            eligible.append(backend)
        return eligible

    def _pick_idle_backend(self, eligible: list[BackendConfig], now: float) -> BackendConfig | None:
        if self.routing.max_idle_ms <= 0:
            return None
        max_idle_sec = self.routing.max_idle_ms / 1000.0
        stale = [backend for backend in eligible if (now - self.state[backend.name].last_selected_at) >= max_idle_sec]
        if not stale:
            return None
        return max(stale, key=lambda b: now - self.state[b.name].last_selected_at)

    def _pick_best_score(self, eligible: list[BackendConfig]) -> BackendConfig:
        return min(eligible, key=lambda backend: self._score(backend.name))

    def _pick_exploration(self, eligible: list[BackendConfig]) -> BackendConfig:
        return self.rng.choice(eligible)

    def pick(self, excluded: set[str] | None = None) -> BackendConfig | None:
        excluded_names = excluded or set()
        eligible = self._eligible_backends(excluded_names)
        if not eligible:
            self.last_pick_reason = "none"
            return None

        now = time.time()
        idle_pick = self._pick_idle_backend(eligible, now)
        if idle_pick is not None:
            self.state[idle_pick.name].last_selected_at = now
            self.last_pick_reason = "idle_rebalance"
            return idle_pick

        if len(eligible) > 1 and self.routing.exploration_rate > 0 and self.rng.random() < self.routing.exploration_rate:
            backend = self._pick_exploration(eligible)
            self.state[backend.name].last_selected_at = now
            self.last_pick_reason = "exploration"
            return backend

        backend = self._pick_best_score(eligible)
        self.state[backend.name].last_selected_at = now
        self.last_pick_reason = "score"
        return backend

    def mark_start(self, backend_name: str) -> None:
        self.state[backend_name].inflight += 1

    def mark_result(self, backend_name: str, latency_ms: float, success: bool) -> None:
        s = self.state[backend_name]
        s.inflight = max(0, s.inflight - 1)
        s.requests += 1
        if success:
            s.latency_ms = latency_ms if s.latency_ms == 0 else (s.latency_ms * 0.2) + (latency_ms * 0.8)
            s.consecutive_failures = 0
            s.circuit_open_until = 0.0
            return
        s.errors += 1
        s.consecutive_failures += 1
        if s.consecutive_failures >= self.circuit_breaker.failure_threshold:
            s.circuit_open_until = time.time() + self.circuit_breaker.reset_timeout_sec
