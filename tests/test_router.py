"""Tests for tb_router_embed."""
import pytest

from tb_router_embed.config import (
    DEFAULT_BACKENDS,
    configure,
    get_backends,
    get_max_concurrent,
    get_port,
    get_request_timeout,
    get_strategy,
)


@pytest.fixture(autouse=True)
def reset_config():
    import tb_router_embed.config as cfg
    cfg._overrides.clear()
    yield


def test_get_backends_default():
    configure(backends=DEFAULT_BACKENDS)
    backends = get_backends()
    assert len(backends) == 2
    assert all(b.startswith("http://") for b in backends)
    assert "8001" in backends[0] and "8001" in backends[1]


def test_get_backends_override():
    configure(backends="http://a:8001,http://b:8002")
    assert get_backends() == ["http://a:8001", "http://b:8002"]


def test_get_strategy_default():
    assert get_strategy() == "failover"


def test_get_port_default():
    assert get_port() == 8011


def test_get_max_concurrent_default():
    assert get_max_concurrent() == 20


def test_get_request_timeout_default():
    assert get_request_timeout() == 60.0


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from tb_router_embed.server import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
