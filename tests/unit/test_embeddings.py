"""Unit tests for embeddings.py — no OpenAI SDK required."""

from __future__ import annotations

import math

import pytest

from services.evaluator.embeddings import (
    EmbeddingBatch,
    EmbeddingClient,
    compute_benchmark_delta,
    compute_centroid,
    cosine_similarity,
    synthesize_centroid,
)

# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors_return_1(self) -> None:
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_return_0(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors_return_minus_1(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_0(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_both_zero_returns_0(self) -> None:
        assert cosine_similarity([0.0], [0.0]) == 0.0

    def test_known_value(self) -> None:
        a = [3.0, 4.0]  # magnitude = 5
        b = [4.0, 3.0]  # magnitude = 5; dot = 12+12 = 24; sim = 24/25
        assert cosine_similarity(a, b) == pytest.approx(24 / 25)

    def test_result_bounded_minus1_to_1(self) -> None:
        a = [0.1, 0.9, -0.3]
        b = [-0.5, 0.2, 0.8]
        result = cosine_similarity(a, b)
        assert -1.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# compute_centroid
# ---------------------------------------------------------------------------


class TestComputeCentroid:
    def test_single_vector_returns_same(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert compute_centroid([v]) == pytest.approx(v)

    def test_two_vectors_average(self) -> None:
        a = [0.0, 0.0]
        b = [2.0, 4.0]
        expected = [1.0, 2.0]
        assert compute_centroid([a, b]) == pytest.approx(expected)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_centroid([])

    def test_three_vectors(self) -> None:
        vecs = [[3.0, 0.0], [0.0, 3.0], [3.0, 3.0]]
        assert compute_centroid(vecs) == pytest.approx([2.0, 2.0])

    def test_preserves_dimensionality(self) -> None:
        vecs = [[1.0] * 10 for _ in range(5)]
        result = compute_centroid(vecs)
        assert len(result) == 10


# ---------------------------------------------------------------------------
# compute_benchmark_delta
# ---------------------------------------------------------------------------


class TestComputeBenchmarkDelta:
    def test_identical_centroid_returns_0(self) -> None:
        v = [1.0, 0.0, 0.0]
        assert compute_benchmark_delta(v, [v]) == pytest.approx(0.0)

    def test_empty_benchmarks_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_benchmark_delta([1.0, 0.0], [])

    def test_orthogonal_returns_1(self) -> None:
        session = [1.0, 0.0]
        benchmarks = [[0.0, 1.0]]
        assert compute_benchmark_delta(session, benchmarks) == pytest.approx(1.0)

    def test_opposite_returns_2(self) -> None:
        session = [1.0, 0.0]
        benchmarks = [[-1.0, 0.0]]
        assert compute_benchmark_delta(session, benchmarks) == pytest.approx(2.0)

    def test_mean_of_multiple_benchmarks(self) -> None:
        session = [1.0, 0.0]
        b1 = [1.0, 0.0]  # sim=1 → delta contrib=0
        b2 = [0.0, 1.0]  # sim=0 → delta contrib=1
        result = compute_benchmark_delta(session, [b1, b2])
        assert result == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# synthesize_centroid
# ---------------------------------------------------------------------------


class TestSynthesizeCentroid:
    def test_default_dims(self) -> None:
        c = synthesize_centroid("p1", "architect")
        assert len(c) == 1536

    def test_custom_dims(self) -> None:
        c = synthesize_centroid("p1", "executor", dims=32)
        assert len(c) == 32

    def test_deterministic(self) -> None:
        c1 = synthesize_centroid("same_id", "debugger")
        c2 = synthesize_centroid("same_id", "debugger")
        assert c1 == c2

    def test_different_ids_produce_different_vectors(self) -> None:
        c1 = synthesize_centroid("alpha", "architect")
        c2 = synthesize_centroid("beta", "architect")
        assert c1 != c2

    def test_different_clusters_produce_different_vectors(self) -> None:
        c1 = synthesize_centroid("p1", "architect")
        c2 = synthesize_centroid("p1", "delegator")
        assert c1 != c2

    def test_unit_length(self) -> None:
        c = synthesize_centroid("p1", "executor", dims=64)
        mag = math.sqrt(sum(v * v for v in c))
        assert mag == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# EmbeddingClient abstract interface
# ---------------------------------------------------------------------------


class TestEmbeddingClientABC:
    def test_cannot_instantiate_abc_directly(self) -> None:
        with pytest.raises(TypeError):
            EmbeddingClient()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_embed_batch(self) -> None:
        class Incomplete(EmbeddingClient):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        import asyncio

        class FakeClient(EmbeddingClient):
            async def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
                return EmbeddingBatch(
                    embeddings=[[0.1] * 3] * len(texts),
                    model="fake",
                    token_count=len(texts) * 10,
                    latency_ms=1.0,
                )

        client = FakeClient()
        result = asyncio.run(client.embed_batch(["hello", "world"]))
        assert len(result.embeddings) == 2
        assert result.model == "fake"
