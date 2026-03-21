"""vLLM embedding router: HTTP proxy with round-robin and failover."""

from tb_router_embed.client import EmbedClient

__all__ = ["EmbedClient", "__version__"]
__version__ = "1.0.0"
