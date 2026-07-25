"""Embedding interfaces and deterministic CI implementation."""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Protocol, cast

import numpy as np


class EmbeddingModel(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]: ...


def lexical_tokens(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_/-]+", lowered)
    chinese = re.findall(r"[\u4e00-\u9fff]", lowered)
    chinese_bigrams = [
        "".join(chinese[index : index + 2]) for index in range(max(0, len(chinese) - 1))
    ]
    return latin + chinese + chinese_bigrams


class HashEmbedding:
    """Deterministic lexical hashing for tests; it is not an evaluation substitute."""

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def encode(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            vector = np.zeros(self.dimensions, dtype=np.float64)
            for token in lexical_tokens(text):
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                vector[index] += 1
            norm = float(np.linalg.norm(vector))
            if norm:
                vector /= norm
            results.append(vector.tolist())
        return results


class BGEEmbedding:
    """Lazy local BAAI/bge-small-zh-v1.5 adapter."""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("EMBEDDING_EXTRA_NOT_INSTALLED") from exc
        self.model = SentenceTransformer(
            model_name,
            cache_folder=os.getenv("HF_HOME"),
        )

    def encode(self, texts: list[str]) -> list[list[float]]:
        encoded: Any = self.model.encode(texts, normalize_embeddings=True)
        return cast(list[list[float]], encoded.tolist())
