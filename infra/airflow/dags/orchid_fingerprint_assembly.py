"""Airflow DAG: orchid_fingerprint_assembly

Triggered after orchid_embedding_etl completes (or manually after SCENARIO_ENDED).
Runs assemble_fingerprint() and persists the result to Neo4j.

DAG definition only — all logic lives in services/evaluator/.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime

from airflow.decorators import dag, task
from airflow.models.param import Param


@dag(
    dag_id="orchid_fingerprint_assembly",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
    tags=["orchid", "fingerprint", "evaluation"],
    params={
        "session_id": Param("", type="string", description="Candidate session UUID"),
        "session_data": Param(
            {},
            type="object",
            description="Full session dict (events + metadata)",
        ),
        "skip_etl": Param(
            False,
            type="boolean",
            description="Skip embedding ETL if already run",
        ),
    },
)
def orchid_fingerprint_assembly() -> None:
    @task
    def assemble(*, params: dict | None = None) -> dict:
        from services.evaluator.agents.llm_client import AnthropicLLMClient
        from services.evaluator.embeddings import OpenAIEmbeddingClient
        from services.evaluator.fingerprint_assembler import assemble_fingerprint
        from services.evaluator.qdrant_store import QdrantStore

        p = params or {}
        session_data: dict = p["session_data"]
        skip_etl: bool = p.get("skip_etl", False)

        llm_client = AnthropicLLMClient(
            api_key=os.environ["ANTHROPIC_API_KEY"]
        )
        embedding_client = OpenAIEmbeddingClient(
            api_key=os.environ.get("OPENAI_API_KEY")
        )
        qdrant = QdrantStore(
            host=os.environ.get("QDRANT_HOST", "localhost"),
            port=int(os.environ.get("QDRANT_PORT", 6333)),
            api_key=os.environ.get("QDRANT_API_KEY"),
        )

        fingerprint = asyncio.run(
            assemble_fingerprint(
                session_data=session_data,
                llm_client=llm_client,
                embedding_client=embedding_client,
                qdrant_store=qdrant,
                skip_etl=skip_etl,
            )
        )

        return json.loads(fingerprint.model_dump_json())

    @task
    def persist_to_neo4j(fingerprint_dict: dict) -> dict:
        from services.evaluator.fingerprint import OrchestraFingerprint
        from services.evaluator.neo4j_store import Neo4jStore

        fingerprint = OrchestraFingerprint(**fingerprint_dict)
        store = Neo4jStore(
            uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            user=os.environ.get("NEO4J_USER", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", "password"),
        )
        store.persist_fingerprint(fingerprint)
        store.close()
        return {
            "session_id": fingerprint.session_id,
            "is_complete": fingerprint.is_complete,
            "style_cluster": fingerprint.style_cluster,
        }

    fingerprint_dict = assemble()
    persist_to_neo4j(fingerprint_dict)


orchid_fingerprint_assembly()
