"""Embedding client abstraction, math utilities, and centroid synthesis."""

from __future__ import annotations

import hashlib
import math
import time
from abc import ABC, abstractmethod

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

_MODEL = "text-embedding-3-large"
_DIMS = 1536


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class EmbeddingBatch(BaseModel):
    embeddings: list[list[float]]
    model: str
    token_count: int
    latency_ms: float


# ---------------------------------------------------------------------------
# Abstract client
# ---------------------------------------------------------------------------


class EmbeddingClient(ABC):
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> EmbeddingBatch: ...


# ---------------------------------------------------------------------------
# OpenAI implementation
# ---------------------------------------------------------------------------


class OpenAIEmbeddingClient(EmbeddingClient):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    async def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
        import openai  # lazy import — SDK not required in test suite

        client = openai.AsyncOpenAI(api_key=self._api_key)
        t0 = time.monotonic()
        response = await client.embeddings.create(model=_MODEL, input=texts)
        latency_ms = (time.monotonic() - t0) * 1000.0

        embeddings = [item.embedding for item in response.data]
        token_count = response.usage.total_tokens

        logger.info(
            "embedding_batch_complete",
            model_version=_MODEL,
            token_count=token_count,
            latency_ms=round(latency_ms, 2),
            batch_size=len(texts),
        )

        return EmbeddingBatch(
            embeddings=embeddings,
            model=_MODEL,
            token_count=token_count,
            latency_ms=round(latency_ms, 2),
        )


# ---------------------------------------------------------------------------
# Pure math utilities
# ---------------------------------------------------------------------------


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity in [-1, 1]. Returns 0.0 for zero vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def compute_centroid(vectors: list[list[float]]) -> list[float]:
    """Return element-wise mean of a non-empty list of equal-length vectors."""
    if not vectors:
        raise ValueError("Cannot compute centroid of empty list")
    dims = len(vectors[0])
    centroid = [0.0] * dims
    for vec in vectors:
        for i, v in enumerate(vec):
            centroid[i] += v
    n = len(vectors)
    return [c / n for c in centroid]


def compute_benchmark_delta(
    session_centroid: list[float],
    benchmark_centroids: list[list[float]],
) -> float:
    """Return mean cosine *distance* (1 - similarity) vs benchmark centroids.

    Result is in [0.0, 2.0] but practically in [0.0, 1.0] for non-negative
    embedding spaces. Lower means closer to senior-engineer reference profiles.
    """
    if not benchmark_centroids:
        raise ValueError("benchmark_centroids must not be empty")
    similarities = [cosine_similarity(session_centroid, b) for b in benchmark_centroids]
    mean_sim = sum(similarities) / len(similarities)
    return 1.0 - mean_sim


# ---------------------------------------------------------------------------
# Deterministic centroid synthesis (tests + benchmark seed files)
# ---------------------------------------------------------------------------

_CLUSTER_SEED: dict[str, int] = {
    "architect": 0,
    "executor": 1,
    "debugger": 2,
    "delegator": 3,
}


def synthesize_centroid(
    profile_id: str,
    style_cluster: str,
    dims: int = _DIMS,
) -> list[float]:
    """Return a deterministic unit-length centroid seeded from profile_id + cluster.

    Uses SHA-256 to generate reproducible pseudo-random floats so tests never
    need a live OpenAI connection.
    """
    cluster_offset = _CLUSTER_SEED.get(style_cluster, 99)
    seed_str = f"{profile_id}:{style_cluster}:{cluster_offset}"
    digest = hashlib.sha256(seed_str.encode()).digest()

    # Expand digest via repeated hashing to fill dims floats
    raw: list[float] = []
    block = digest
    while len(raw) < dims:
        for i in range(0, len(block) - 1, 2):
            val = (block[i] * 256 + block[i + 1]) / 65535.0  # in [0, 1)
            raw.append(val * 2.0 - 1.0)  # shift to [-1, 1)
        block = hashlib.sha256(block).digest()

    vec = raw[:dims]

    # Normalise to unit length so cosine similarity is well-behaved
    mag = math.sqrt(sum(v * v for v in vec))
    if mag == 0.0:
        vec[0] = 1.0
        mag = 1.0
    return [v / mag for v in vec]
