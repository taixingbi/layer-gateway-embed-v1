# tb-router-embed

HTTP proxy router for vLLM embedding API. Routes `/v1/embeddings` and `/v1/models` requests to multiple vLLM backends with configurable round-robin or failover strategies.

## Install

```bash
pip install tb-router-embed
```

## SDK

```python
from tb_router_embed import EmbedClient

client = EmbedClient()
vec = client.embed("hello world")

# Batch
vecs = client.embed_batch(["a", "b", "c"])
```

Set `EMBEDDING_URL`, `EMBEDDING_MODEL`, or `EMBED_CLIENT_MAX_CONCURRENT` (default 20) via env, or pass to constructor: `EmbedClient(base_url="...", model="...", max_concurrent=20)`.

See [DOCS.md](DOCS.md) for router setup, configuration, API, and deployment.
