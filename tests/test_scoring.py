"""Tests for backend scoring and pick selection."""

import random

from app.core.config import BackendConfig, CircuitBreakerConfig, RoutingConfig
from app.routing.selector import BackendSelector


def _selector(
    *,
    routing: RoutingConfig | None = None,
    backends: tuple[BackendConfig, ...] | None = None,
    rng: random.Random | None = None,
) -> BackendSelector:
    return BackendSelector(
        backends=backends
        or (
            BackendConfig(name="a", url="http://a", soft_limit=32, hard_limit=64),
            BackendConfig(name="b", url="http://b", soft_limit=32, hard_limit=64),
        ),
        routing=routing or RoutingConfig(inflight_weight=8.0, exploration_rate=0.0, max_idle_ms=0),
        circuit_breaker=CircuitBreakerConfig(failure_threshold=100, reset_timeout_sec=30),
        rng=rng,
    )


def test_pick_prefers_lower_inflight():
    selector = _selector()
    selector.state["a"].inflight = 2
    selector.state["b"].inflight = 10
    assert selector.pick().name == "a"


def test_hard_limit_excludes_overloaded_backend():
    selector = _selector()
    selector.state["a"].inflight = 64
    selector.state["b"].inflight = 2
    assert selector.pick().name == "b"


def test_hard_limit_blocks_all_when_saturated():
    selector = _selector()
    selector.state["a"].inflight = 64
    selector.state["b"].inflight = 64
    assert selector.pick() is None


def test_hot_penalty_flips_choice():
    routing = RoutingConfig(
        hot_penalty_weight=500.0,
        hot_window_sec=2.0,
        hot_target_share=0.5,
        exploration_rate=0.0,
        max_idle_ms=0,
    )
    selector = _selector(routing=routing)
    selector.state["a"].inflight = 2
    selector.state["b"].inflight = 2
    for _ in range(20):
        selector.state["a"].record_dispatch()
    assert selector.pick().name == "b"


def test_overload_penalty():
    routing = RoutingConfig(
        overload_penalty_weight=50.0,
        exploration_rate=0.0,
        max_idle_ms=0,
    )
    selector = BackendSelector(
        backends=(
            BackendConfig(name="light", url="http://l", soft_limit=4, hard_limit=64),
            BackendConfig(name="heavy", url="http://h", soft_limit=2, hard_limit=64),
        ),
        routing=routing,
        circuit_breaker=CircuitBreakerConfig(failure_threshold=100, reset_timeout_sec=30),
    )
    selector.state["light"].inflight = 3
    selector.state["heavy"].inflight = 4
    assert selector.pick().name == "light"


def test_equal_score_tie_break_is_not_always_first():
    selector = _selector(rng=random.Random(0))
    picks = {selector.pick().name for _ in range(30)}
    assert picks == {"a", "b"}
