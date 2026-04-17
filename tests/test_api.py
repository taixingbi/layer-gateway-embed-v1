import os
import asyncio

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _headers():
    return {
        "X-Request-Id": "req-1",
        "X-Trace-Id": "trace-1",
        "X-Session-Id": "sess-1",
    }


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200


def test_missing_request_or_session_id():
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post("/v1/embeddings", headers={"X-Request-Id": "req-1"}, json={"model": "m", "input": "hi"})
    assert response.status_code == 400


def test_admission_queue_timeout_rejects_request():
    os.environ["ADMISSION_WAIT_TIMEOUT_MS"] = "1"
    get_settings.cache_clear()
    with TestClient(app) as client:
        client.app.state.gateway_context.queue = asyncio.Semaphore(0)
        response = client.post("/v1/embeddings", headers=_headers(), json={"model": "m", "input": "hi"})
    assert response.status_code == 429
