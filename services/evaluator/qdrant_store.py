"""Qdrant vector store wrapper — injectable client for testability."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from services.evaluator.embedding_etl import EmbeddingPoint

logger = structlog.get_logger(__name__)

_COLLECTION = "orchid_embeddings"
_VECTOR_SIZE = 1536


class QdrantStore:
    """Thin wrapper around the Qdrant client.

    The qdrant-client SDK is imported lazily so the test suite runs without it.
    Pass a pre-built client to the constructor to inject a mock or test double.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        api_key: str | None = None,
        collection: str = _COLLECTION,
        *,
        client: Any | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._api_key = api_key
        self._collection = collection
        self._client = client  # injected in tests; built lazily in production

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        from qdrant_client import QdrantClient  # lazy import

        self._client = QdrantClient(
            host=self._host,
            port=self._port,
            api_key=self._api_key,
        )
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_collection_if_not_exists(self) -> None:
        """Idempotent: create the collection if it does not already exist."""
        from qdrant_client.http.models import Distance, VectorParams  # lazy import

        client = self._get_client()
        existing = {c.name for c in client.get_collections().collections}
        if self._collection in existing:
            logger.info("qdrant_collection_exists", collection=self._collection)
            return

        client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("qdrant_collection_created", collection=self._collection)

    async def upsert(self, points: list[EmbeddingPoint]) -> int:
        """Upsert a batch of EmbeddingPoints. Returns the number of points stored."""
        from qdrant_client.http.models import PointStruct  # lazy import

        if not points:
            return 0

        client = self._get_client()
        structs = [
            PointStruct(
                id=p.point_id,
                vector=p.embedding,
                payload={
                    "session_id": p.session_id,
                    "event_id": p.event_id,
                    "event_type": p.event_type,
                    "text": p.text,
                    "timestamp": p.timestamp,
                },
            )
            for p in points
        ]

        client.upsert(collection_name=self._collection, points=structs)
        logger.info(
            "qdrant_upsert",
            collection=self._collection,
            count=len(structs),
        )
        return len(structs)

    async def get_session_vectors(self, session_id: str) -> list[list[float]]:
        """Return all embedding vectors stored for a session."""
        client = self._get_client()
        result, _ = client.scroll(
            collection_name=self._collection,
            scroll_filter={
                "must": [{"key": "session_id", "match": {"value": session_id}}]
            },
            with_vectors=True,
            limit=10_000,
        )
        vectors: list[list[float]] = []
        for record in result:
            if record.vector is not None:
                vectors.append(record.vector)  # type: ignore[arg-type]
        return vectors
