"""Unit tests for EmbeddingETL — no OpenAI, no Qdrant required."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from services.evaluator.embedding_etl import EmbeddingETL, EmbeddingPoint, ETLResult
from services.evaluator.embeddings import EmbeddingBatch, EmbeddingClient

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeClient(EmbeddingClient):
    """Returns fixed-size zero embeddings and records calls."""

    def __init__(self, dims: int = 4, fail: bool = False) -> None:
        self.dims = dims
        self.fail = fail
        self.calls: list[list[str]] = []

    async def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
        self.calls.append(list(texts))
        if self.fail:
            raise RuntimeError("fake embed failure")
        return EmbeddingBatch(
            embeddings=[[0.0] * self.dims] * len(texts),
            model="fake",
            token_count=len(texts) * 5,
            latency_ms=1.0,
        )


class _FakeStore:
    """Records upsert calls."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.upserted: list[list[EmbeddingPoint]] = []

    async def upsert(self, points: list[EmbeddingPoint]) -> int:
        if self.fail:
            raise RuntimeError("fake qdrant failure")
        self.upserted.append(list(points))
        return len(points)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(event_type: str, text: str, **payload_extra: object) -> dict:
    payload: dict = {}
    if event_type == "PROMPT_SENT":
        payload["text"] = text
    elif event_type == "CORRECTION_ISSUED":
        payload["correction_text"] = text
    payload.update(payload_extra)
    return {
        "event_id": str(uuid.uuid4()),
        "session_id": "sess_test",
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# extract_embeddable_text
# ---------------------------------------------------------------------------


class TestExtractEmbeddableText:
    def test_prompt_sent_returns_text(self) -> None:
        event = _event("PROMPT_SENT", "Fix the pipeline")
        assert EmbeddingETL.extract_embeddable_text(event) == "Fix the pipeline"

    def test_correction_issued_returns_correction_text(self) -> None:
        event = _event("CORRECTION_ISSUED", "Use SIGTERM not SIGKILL")
        assert EmbeddingETL.extract_embeddable_text(event) == "Use SIGTERM not SIGKILL"

    def test_agent_response_returns_none(self) -> None:
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "AGENT_RESPONSE",
            "payload": {"response": "ok"},
        }
        assert EmbeddingETL.extract_embeddable_text(event) is None

    def test_chaos_injected_returns_none(self) -> None:
        event = {"event_type": "CHAOS_INJECTED", "payload": {}}
        assert EmbeddingETL.extract_embeddable_text(event) is None

    def test_scenario_started_returns_none(self) -> None:
        event = {"event_type": "SCENARIO_STARTED", "payload": {}}
        assert EmbeddingETL.extract_embeddable_text(event) is None

    def test_empty_prompt_text_returns_none(self) -> None:
        event = {"event_type": "PROMPT_SENT", "payload": {"text": ""}}
        assert EmbeddingETL.extract_embeddable_text(event) is None

    def test_missing_payload_returns_none(self) -> None:
        event = {"event_type": "PROMPT_SENT", "payload": {}}
        assert EmbeddingETL.extract_embeddable_text(event) is None


# ---------------------------------------------------------------------------
# make_point_id
# ---------------------------------------------------------------------------


class TestMakePointId:
    def test_returns_int(self) -> None:
        pid = EmbeddingETL.make_point_id("some-uuid")
        assert isinstance(pid, int)

    def test_deterministic(self) -> None:
        assert EmbeddingETL.make_point_id("abc") == EmbeddingETL.make_point_id("abc")

    def test_different_inputs_different_ids(self) -> None:
        assert EmbeddingETL.make_point_id("uuid-1") != EmbeddingETL.make_point_id("uuid-2")

    def test_non_negative(self) -> None:
        for i in range(20):
            assert EmbeddingETL.make_point_id(f"id-{i}") >= 0


# ---------------------------------------------------------------------------
# EmbeddingETL.process_session
# ---------------------------------------------------------------------------


class TestProcessSession:
    def _make_etl(
        self, *, client_fail: bool = False, store_fail: bool = False
    ) -> tuple[EmbeddingETL, _FakeClient, _FakeStore]:
        client = _FakeClient(fail=client_fail)
        store = _FakeStore(fail=store_fail)
        etl = EmbeddingETL(embedding_client=client, qdrant_store=store, batch_size=3)
        return etl, client, store

    def test_only_embeddable_events_are_sent_to_client(self) -> None:
        etl, client, store = self._make_etl()
        events = [
            _event("PROMPT_SENT", "Fix A"),
            _event("AGENT_RESPONSE", "ignored"),
            _event("CORRECTION_ISSUED", "No, use B"),
            _event("CODE_EXECUTED", "ignored"),
        ]
        result = asyncio.run(etl.process_session("sess_1", events))
        assert result.embeddable_events == 2
        assert result.total_events == 4

    def test_points_upserted_count_matches_embeddable(self) -> None:
        etl, _, _ = self._make_etl()
        events = [_event("PROMPT_SENT", f"text {i}") for i in range(5)]
        result = asyncio.run(etl.process_session("sess_2", events))
        assert result.points_upserted == 5

    def test_batching_splits_correctly(self) -> None:
        etl, client, store = self._make_etl()
        events = [_event("PROMPT_SENT", f"msg {i}") for i in range(7)]
        asyncio.run(etl.process_session("sess_3", events))
        # batch_size=3 → batches of [3, 3, 1]
        assert len(client.calls) == 3
        assert len(client.calls[0]) == 3
        assert len(client.calls[1]) == 3
        assert len(client.calls[2]) == 1

    def test_no_embeddable_events_returns_zero_counts(self) -> None:
        etl, client, _ = self._make_etl()
        events = [_event("AGENT_RESPONSE", "ignored")]
        result = asyncio.run(etl.process_session("sess_4", events))
        assert result.embeddable_events == 0
        assert result.points_upserted == 0
        assert client.calls == []

    def test_empty_events_list(self) -> None:
        etl, _, _ = self._make_etl()
        result = asyncio.run(etl.process_session("sess_5", []))
        assert result.total_events == 0
        assert result.embeddable_events == 0
        assert result.points_upserted == 0

    def test_client_failure_logged_as_error_not_exception(self) -> None:
        etl, _, _ = self._make_etl(client_fail=True)
        events = [_event("PROMPT_SENT", "Fix this")]
        result = asyncio.run(etl.process_session("sess_6", events))
        assert result.points_upserted == 0
        assert len(result.errors) == 1
        assert "embed_batch failed" in result.errors[0]

    def test_store_failure_logged_as_error_not_exception(self) -> None:
        etl, _, _ = self._make_etl(store_fail=True)
        events = [_event("PROMPT_SENT", "Fix this")]
        result = asyncio.run(etl.process_session("sess_7", events))
        assert result.points_upserted == 0
        assert len(result.errors) == 1
        assert "upsert failed" in result.errors[0]

    def test_token_count_accumulated_across_batches(self) -> None:
        etl, _, _ = self._make_etl()
        # _FakeClient charges 5 tokens per text; 4 texts in 2 batches of 2
        etl2 = EmbeddingETL(
            embedding_client=_FakeClient(),
            qdrant_store=_FakeStore(),
            batch_size=2,
        )
        events = [_event("PROMPT_SENT", f"msg {i}") for i in range(4)]
        result = asyncio.run(etl2.process_session("sess_8", events))
        assert result.token_count == 20  # 4 texts × 5 tokens

    def test_result_session_id_matches(self) -> None:
        etl, _, _ = self._make_etl()
        result = asyncio.run(etl.process_session("my_session", []))
        assert result.session_id == "my_session"

    def test_etl_result_is_pydantic_model(self) -> None:
        etl, _, _ = self._make_etl()
        result = asyncio.run(etl.process_session("sess_9", []))
        assert isinstance(result, ETLResult)
