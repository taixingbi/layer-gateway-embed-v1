import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_BACKENDS, configure, get_backends, get_max_concurrent
from app.config import get_port, get_strategy, get_timeout
from app.main import app


@pytest.fixture(autouse=True)
def reset():
    import app.config as c
    import app.router as r

    c._overrides.clear()
    r._rr = None
    r._rr_key = None
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


def test_invalid_strategy_falls_back():
    configure(strategy="not-a-mode")
    assert get_strategy() == "failover"


def test_round_robin_cycle_resets_when_backends_change():
    import app.router as r

    configure(strategy="round_robin", backends="http://a,http://b")
    assert r._next_backend() == "http://a"
    assert r._next_backend() == "http://b"
    configure(strategy="round_robin", backends="http://c,http://d")
    assert r._next_backend() == "http://c"
    assert r._next_backend() == "http://d"


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_v1_without_internal_key_config_returns_500():
    configure(internal_api_key="")
    r = TestClient(app).get("/v1/models")
    assert r.status_code == 500 and r.json()["detail"] == "Server misconfigured"


def test_v1_unauthorized_without_header():
    configure(internal_api_key="secret")
    r = TestClient(app).get("/v1/models")
    assert r.status_code == 401 and r.json()["detail"] == "Unauthorized"


def test_v1_unauthorized_wrong_header():
    configure(internal_api_key="secret")
    r = TestClient(app).get("/v1/models", headers={"X-Internal-Key": "wrong"})
    assert r.status_code == 401
