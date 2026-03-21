import pytest
from fastapi.testclient import TestClient

from router_embed.config import DEFAULT_BACKENDS, configure, get_backends, get_max_concurrent
from router_embed.config import get_port, get_strategy, get_timeout
from router_embed.main import app


@pytest.fixture(autouse=True)
def reset():
    import router_embed.config as c
    c._overrides.clear()
    yield


def test_backends():
    configure(backends=DEFAULT_BACKENDS)
    b = get_backends()
    assert len(b) == 2 and all(x.startswith("http://") for x in b)

    configure(backends="http://a:8001,http://b:8002")
    assert get_backends() == ["http://a:8001", "http://b:8002"]


def test_defaults():
    assert get_strategy() == "failover"
    assert get_port() == 8011
    assert get_max_concurrent() == 20
    assert get_timeout() == 60.0


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
