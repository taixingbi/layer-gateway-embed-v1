"""Embedding request model and `request_class` bucketing for metrics labels."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class RequestClass(str, Enum):
    """Low-cardinality `request_class` label values (SMALL / MEDIUM / LARGE)."""

    SMALL_EMBED = "SMALL_EMBED"
    MEDIUM_EMBED = "MEDIUM_EMBED"
    LARGE_EMBED = "LARGE_EMBED"


class EmbeddingRequest(BaseModel):
    """Minimal OpenAI-style embedding request (`model` + `input`)."""

    model: str
    input: Any

    def classify(self) -> RequestClass:
        """Map input size to `RequestClass` using item count and total character length."""
        items = self.input if isinstance(self.input, list) else [self.input]
        count = len(items)
        total_chars = sum(len(str(i)) for i in items)
        if count <= 2 and total_chars <= 512:
            return RequestClass.SMALL_EMBED
        if count <= 16 and total_chars <= 8192:
            return RequestClass.MEDIUM_EMBED
        return RequestClass.LARGE_EMBED
