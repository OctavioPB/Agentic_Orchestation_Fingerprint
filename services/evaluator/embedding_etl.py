"""Extract embeddable text from telemetry events, embed, and load into Qdrant."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from services.evaluator.embeddings import EmbeddingClient

if TYPE_CHECKING:
    from services.evaluator.qdrant_store import QdrantStore

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class EmbeddingPoint(BaseModel):
    point_id: int
    session_id: str
    event_id: str
    event_type: str
    text: str
    embedding: list[float]
    timestamp: str


class ETLResult(BaseModel):
    session_id: str
    total_events: int
    embeddable_events: int
    points_upserted: int
    token_count: int
    latency_ms: float
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# EmbeddingETL
# ---------------------------------------------------------------------------


class EmbeddingETL:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        qdrant_store: QdrantStore,
        batch_size: int = 50,
    ) -> None:
        self._client = embedding_client
        self._store = qdrant_store
        self._batch_size = batch_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_session(
        self, session_id: str, events: list[dict]
    ) -> ETLResult:
        import time

        t0 = time.monotonic()
        errors: list[str] = []
        total_token_count = 0
        points_upserted = 0

        embeddable = [e for e in events if self.extract_embeddable_text(e) is not None]

        logger.info(
            "etl_session_start",
            session_id=session_id,
            total_events=len(events),
            embeddable_events=len(embeddable),
        )

        for batch_start in range(0, len(embeddable), self._batch_size):
            batch = embeddable[batch_start : batch_start + self._batch_size]
            texts = [self.extract_embeddable_text(e) for e in batch]  # type: ignore[misc]

            try:
                result = await self._client.embed_batch(texts)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001
                msg = f"embed_batch failed for batch starting at {batch_start}: {exc}"
                logger.warning("etl_batch_error", error=msg, session_id=session_id)
                errors.append(msg)
                continue

            total_token_count += result.token_count

            batch_points: list[EmbeddingPoint] = []
            for event, embedding in zip(batch, result.embeddings):
                batch_points.append(
                    EmbeddingPoint(
                        point_id=self.make_point_id(event["event_id"]),
                        session_id=session_id,
                        event_id=event["event_id"],
                        event_type=event["event_type"],
                        text=self.extract_embeddable_text(event),  # type: ignore[arg-type]
                        embedding=embedding,
                        timestamp=event.get("timestamp", ""),
                    )
                )

            try:
                upserted = await self._store.upsert(batch_points)
                points_upserted += upserted
            except Exception as exc:  # noqa: BLE001
                msg = f"qdrant upsert failed for batch at {batch_start}: {exc}"
                logger.warning("etl_upsert_error", error=msg, session_id=session_id)
                errors.append(msg)

        latency_ms = (time.monotonic() - t0) * 1000.0

        logger.info(
            "etl_session_complete",
            session_id=session_id,
            points_upserted=points_upserted,
            token_count=total_token_count,
            latency_ms=round(latency_ms, 2),
            errors=len(errors),
        )

        return ETLResult(
            session_id=session_id,
            total_events=len(events),
            embeddable_events=len(embeddable),
            points_upserted=points_upserted,
            token_count=total_token_count,
            latency_ms=round(latency_ms, 2),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def extract_embeddable_text(event: dict) -> str | None:
        """Return the text to embed for an event, or None if not embeddable."""
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})

        if event_type == "PROMPT_SENT":
            return payload.get("text") or None
        if event_type == "CORRECTION_ISSUED":
            return payload.get("correction_text") or None
        return None

    @staticmethod
    def make_point_id(event_id: str) -> int:
        """Return a stable integer Qdrant point ID derived from a UUID string."""
        digest = hashlib.sha256(event_id.encode()).digest()
        # Use first 8 bytes as a positive int64
        return int.from_bytes(digest[:8], byteorder="big") & 0x7FFF_FFFF_FFFF_FFFF
