"""Tests for YAML config loading."""

import os
from pathlib import Path

from app.core.config import get_settings


def test_load_settings_from_yaml(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
server:
  host: 127.0.0.1
  port: 9000
routing:
  inflight_weight: 8.0
  hot_penalty_weight: 20.0
admission:
  max_concurrent: 128
backends:
  - name: embed-node-1
    url: http://a:8001
    soft_limit: 32
    hard_limit: 64
  - name: embed-node-2
    url: http://b:8001
    soft_limit: 32
    hard_limit: 64
""".strip()
    )
    os.environ["GATEWAY_CONFIG"] = str(config)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.server.port == 9000
    assert settings.routing.exploration_rate == 0.0
    assert settings.admission_queue.max_concurrent == 128
    assert len(settings.backends) == 2
    assert settings.backends[0].soft_limit == 32
    assert settings.backends[0].hard_limit == 64
    get_settings.cache_clear()
    os.environ.pop("GATEWAY_CONFIG", None)
