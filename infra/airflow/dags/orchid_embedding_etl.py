"""Airflow DAG: orchid_embedding_etl

Triggered on SCENARIO_ENDED. Reads all telemetry events for a session,
embeds PROMPT_SENT and CORRECTION_ISSUED events, and upserts them into Qdrant.

DAG definition only — all logic lives in services/evaluator/.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from airflow.decorators import dag, task
from airflow.models.param import Param


@dag(
    dag_id="orchid_embedding_etl",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
    tags=["orchid", "embeddings", "etl"],
    params={
        "session_id": Param("", type="string", description="Candidate session UUID"),
        "scenario_id": Param("", type="string", description="Scenario identifier"),
        "events": Param(
            [],
            type="array",
            description="List of telemetry event dicts (serialised from Kafka)",
        ),
    },
)
def orchid_embedding_etl() -> None:
    @task
    def embed_and_store(*, params: dict | None = None) -> dict:
        from services.evaluator.embedding_etl import EmbeddingETL
        from services.evaluator.embeddings import OpenAIEmbeddingClient
        from services.evaluator.qdrant_store import QdrantStore

        p = params or {}
        session_id: str = p["session_id"]
        events: list[dict] = p["events"]

        client = OpenAIEmbeddingClient(api_key=os.environ.get("OPENAI_API_KEY"))
        store = QdrantStore(
            host=os.environ.get("QDRANT_HOST", "localhost"),
            port=int(os.environ.get("QDRANT_PORT", 6333)),
            api_key=os.environ.get("QDRANT_API_KEY"),
        )
        etl = EmbeddingETL(embedding_client=client, qdrant_store=store)

        result = asyncio.run(etl.process_session(session_id, events))

        return {
            "session_id": result.session_id,
            "total_events": result.total_events,
            "embeddable_events": result.embeddable_events,
            "points_upserted": result.points_upserted,
            "token_count": result.token_count,
            "latency_ms": result.latency_ms,
            "errors": result.errors,
        }

    embed_and_store()


orchid_embedding_etl()
