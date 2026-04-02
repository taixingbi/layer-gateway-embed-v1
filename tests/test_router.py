import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_BACKENDS, configure, get_backends, get_max_concurrent
from app.config import get_port, get_strategy, get_timeout, validate_config
from app.main import app


@pytest.fixture(autouse=True)
def reset():
    import app.config as c
    import app.router as r

    c._overrides.clear()
    configure(internal_api_key="secret")
    r._rr_idx = 0
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

    assert r._next_round_robin_backend(["http://a", "http://b"]) == "http://a"
    assert r._next_round_robin_backend(["http://a", "http://b"]) == "http://b"
    assert r._next_round_robin_backend(["http://c", "http://d"]) == "http://c"
    assert r._next_round_robin_backend(["http://c", "http://d"]) == "http://d"


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_validate_config_requires_internal_key():
    configure(internal_api_key="")
    with pytest.raises(ValueError, match="INTERNAL_API_KEY"):
        validate_config()


def test_v1_unauthorized_without_header():
    configure(internal_api_key="secret")
    r = TestClient(app).get("/v1/models")
    assert r.status_code == 401 and r.json()["detail"] == "Unauthorized"


def test_v1_unauthorized_wrong_header():
    configure(internal_api_key="secret")
    r = TestClient(app).get("/v1/models", headers={"X-Internal-Key": "wrong"})
    assert r.status_code == 401


def test_embeddings_requires_correlation_headers():
    configure(internal_api_key="secret")
    c = TestClient(app)
    r = c.post(
        "/v1/embeddings",
        headers={
            "X-Internal-Key": "secret",
            "Content-Type": "application/json",
            "X-Session-Id": "session-1",
        },
        content=b'{"model":"m","input":"x"}',
    )
    assert r.status_code == 400
    body = r.json()
    assert "missing" in body and "X-Request-Id" in body["missing"]

    r2 = c.post(
        "/v1/embeddings",
        headers={
            "X-Internal-Key": "secret",
            "Content-Type": "application/json",
            "X-Request-Id": "req-1",
        },
        content=b'{"model":"m","input":"x"}',
    )
    assert r2.status_code == 400
    assert "X-Session-Id" in r2.json()["missing"]
