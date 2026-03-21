"""SDK client for embedding via router or vLLM API."""
import threading

import httpx

from router_embed.config import (
    get_client_max_concurrent,
    get_embedding_model,
    get_embedding_url,
)


class EmbedClient:
    """Client for embedding text via router or vLLM /v1/embeddings API."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        max_concurrent: int | None = None,
    ):
        """base_url: router or vLLM URL (default from EMBEDDING_URL env).
        max_concurrent: max concurrent requests (default from EMBED_CLIENT_MAX_CONCURRENT env or 20).
        """
        self._base_url = (base_url or get_embedding_url()).rstrip("/")
        self._model = model or get_embedding_model()
        self._max_concurrent = max_concurrent if max_concurrent is not None else get_client_max_concurrent()
        self._semaphore = threading.Semaphore(self._max_concurrent)
        self._client = httpx.Client(timeout=60.0)

    def embed(self, text: str) -> list[float]:
        """Embed single text. Returns vector."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Returns list of vectors."""
        if not texts:
            return []

        url = f"{self._base_url}/v1/embeddings"
        payload = {"model": self._model, "input": texts if len(texts) > 1 else texts[0]}

        with self._semaphore:
            resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return [e["embedding"] for e in sorted(data["data"], key=lambda x: x["index"])]
