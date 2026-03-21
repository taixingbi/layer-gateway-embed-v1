"""Tests for router_embed."""
import pytest

from router_embed.config import configure, get_backends, get_max_concurrent, get_port, get_strategy


@pytest.fixture(autouse=True)
def reset_config():
    import router_embed.config as cfg
    cfg._overrides.clear()
    yield


def test_get_backends_default():
    backends = get_backends()
    assert len(backends) == 2
    assert "192.168.86.173" in backends[0]
    assert "192.168.86.176" in backends[1]


def test_get_backends_override():
    configure(backends="http://a:8001,http://b:8002")
    assert get_backends() == ["http://a:8001", "http://b:8002"]


def test_get_strategy_default():
    assert get_strategy() == "failover"


def test_get_port_default():
    assert get_port() == 8011


def test_get_max_concurrent_default():
    assert get_max_concurrent() == 20


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from router_embed.main import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
