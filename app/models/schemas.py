from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class RequestClass(str, Enum):
    SMALL_EMBED = "SMALL_EMBED"
    MEDIUM_EMBED = "MEDIUM_EMBED"
    LARGE_EMBED = "LARGE_EMBED"


class EmbeddingRequest(BaseModel):
    model: str
    input: Any

    def classify(self) -> RequestClass:
        items = self.input if isinstance(self.input, list) else [self.input]
        count = len(items)
        total_chars = sum(len(str(i)) for i in items)
        if count <= 2 and total_chars <= 512:
            return RequestClass.SMALL_EMBED
        if count <= 16 and total_chars <= 8192:
            return RequestClass.MEDIUM_EMBED
        return RequestClass.LARGE_EMBED
