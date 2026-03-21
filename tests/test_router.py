"""Tests for tb_router_embed."""
import pytest

from tb_router_embed.config import configure, get_backends, get_client_max_concurrent
from tb_router_embed.config import get_embedding_model, get_embedding_url, get_max_concurrent
from tb_router_embed.config import get_port, get_strategy


@pytest.fixture(autouse=True)
def reset_config():
    import tb_router_embed.config as cfg
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


def test_get_embedding_url_default():
    assert get_embedding_url() == "http://localhost:8011"


def test_get_embedding_model_default():
    assert get_embedding_model() == "BAAI/bge-m3"


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from tb_router_embed.main import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_embed_client_init():
    from tb_router_embed import EmbedClient
    configure(embedding_url="http://test:8011", embedding_model="test-model")
    client = EmbedClient()
    assert client._base_url == "http://test:8011"
    assert client._model == "test-model"


def test_get_client_max_concurrent_default():
    assert get_client_max_concurrent() == 20


def test_embed_client_init_explicit():
    from tb_router_embed import EmbedClient
    client = EmbedClient(base_url="http://custom:9000", model="custom-model", max_concurrent=5)
    assert client._base_url == "http://custom:9000"
    assert client._model == "custom-model"
    assert client._max_concurrent == 5


def test_embed_client_embed_batch_empty():
    from tb_router_embed import EmbedClient
    client = EmbedClient(base_url="http://localhost:8011")
    assert client.embed_batch([]) == []
