"""Tests for backend health probes and `/ready` payload."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
from fastapi.testclient import TestClient

from app.core.config import BackendConfig
from app.health.backends import probe_backends, ready_payload
from app.main import app


def test_probe_backends_all_healthy():
    client = AsyncMock(spec=httpx.AsyncClient)
    ok = MagicMock(status_code=200)
    client.get = AsyncMock(return_value=ok)
    backends = (
        BackendConfig(name="embed-node-1", url="http://a:8001"),
        BackendConfig(name="embed-node-2", url="http://b:8001"),
    )
    status = asyncio.run(probe_backends(backends, client))
    assert status == {
        "embed-node-1": "healthy",
        "embed-node-2": "healthy",
    }
    assert client.get.await_count == 2


def test_probe_backends_one_fails():
    client = AsyncMock(spec=httpx.AsyncClient)

    async def get(url: str):
        if "a:" in url:
            return MagicMock(status_code=200)
        raise httpx.ConnectError("down")

    client.get = get
    backends = (
        BackendConfig(name="embed-node-1", url="http://a:8001"),
        BackendConfig(name="embed-node-2", url="http://b:8001"),
    )
    status = asyncio.run(probe_backends(backends, client))
    assert status["embed-node-1"] == "healthy"
    assert status["embed-node-2"] == "unhealthy"


def test_ready_payload_all_healthy():
    body, code = ready_payload(
        {"embed-node-1": "healthy", "embed-node-2": "healthy"},
    )
    assert code == 200
    assert body["status"] == "ready"
    assert body["healthy_backends"] == 2


def test_ready_endpoint_mocked(monkeypatch):
    async def fake_probe(*_args, **_kwargs):
        return {"embed-node-1": "healthy", "embed-node-2": "healthy"}

    monkeypatch.setattr("app.main.probe_backends", fake_probe)
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "healthy_backends": 2,
        "total_backends": 2,
        "backends": {
            "embed-node-1": "healthy",
            "embed-node-2": "healthy",
        },
    }
