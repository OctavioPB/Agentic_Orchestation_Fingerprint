"""Ingests processed events into the Qdrant vector store."""

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION = "orchid_interactions"

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ingest_point(event_id: str, session_id: str, payload: dict) -> bool:
    """Upsert a single event into Qdrant. Returns True on success."""
    try:
        client.upsert(
            collection_name=COLLECTION,
            points=[
                PointStruct(
                    id=abs(hash(event_id)) % (2**53),
                    vector=[0.1, 0.2, 0.3],  # BUG: dimension 3, collection expects 1536
                    payload={"session_id": session_id, **payload},
                )
            ],
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Qdrant upsert failed: %s", exc)
        return False


if __name__ == "__main__":
    ok = ingest_point("evt_0001", "sess_demo", {"type": "agent_response"})
    print("Ingest ok" if ok else "Ingest failed (check DEBUG logs)")
