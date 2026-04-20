from app.core.config import BackendConfig, CircuitBreakerConfig, RoutingConfig
from app.routing.selector import BackendSelector


def test_routing_prefers_lower_score():
    selector = BackendSelector(
        backends=(
            BackendConfig(name="a", url="http://a"),
            BackendConfig(name="b", url="http://b"),
        ),
        routing=RoutingConfig(inflight_weight=10.0, latency_weight=1.0, error_weight=100.0),
        circuit_breaker=CircuitBreakerConfig(failure_threshold=2, reset_timeout_sec=30),
    )

    selector.mark_result("a", latency_ms=200, success=True)
    selector.mark_result("b", latency_ms=30, success=True)
    assert selector.pick().name == "b"


def test_failures_do_not_poison_latency_ewma():
    selector = BackendSelector(
        backends=(
            BackendConfig(name="a", url="http://a"),
            BackendConfig(name="b", url="http://b"),
        ),
        routing=RoutingConfig(inflight_weight=10.0, latency_weight=1.0, error_weight=100.0),
        circuit_breaker=CircuitBreakerConfig(failure_threshold=100, reset_timeout_sec=30),
    )
    for _ in range(5):
        selector.mark_result("a", latency_ms=30.0, success=True)
    selector.mark_result("a", latency_ms=15000.0, success=False)
    assert selector.state["a"].latency_ms == 30.0


def test_circuit_breaker_opens_after_threshold():
    selector = BackendSelector(
        backends=(BackendConfig(name="a", url="http://a"),),
        routing=RoutingConfig(),
        circuit_breaker=CircuitBreakerConfig(failure_threshold=2, reset_timeout_sec=30),
    )

    selector.mark_start("a")
    selector.mark_result("a", latency_ms=100, success=False)
    selector.mark_start("a")
    selector.mark_result("a", latency_ms=100, success=False)
    assert selector.pick() is None
