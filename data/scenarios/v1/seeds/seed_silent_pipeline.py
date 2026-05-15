"""Reference seed script for Scenario v2: The Silent Pipeline.

Writes the broken workspace files and a realistic pipeline_run.log that
candidates read at T+0. No external dependencies — pure stdlib.

Run from the workspace_v2 directory:
    python3 seed_silent_pipeline.py [target_dir]
"""

import json
import sys
from pathlib import Path

TARGET_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

# ---------------------------------------------------------------------------
# Violation catalogue (3 total)
# ---------------------------------------------------------------------------
# V1 — producer.py: KAFKA_TOPIC = 'orchid.sandbox.agent.responses'
#       Should be 'orchid.sandbox.agent_response'. No exception is raised;
#       messages accumulate in a dead topic.
#
# V2 — qdrant_ingest.py: vector=[0.1, 0.2, 0.3] (dimension 3)
#       Collection orchid_interactions expects 1536-dimensional vectors
#       (text-embedding-3-large). HTTP 400 is logged at DEBUG level only.
#
# V3 — etl_dag.py: load_task >> extract_task creates extract→transform→load→extract cycle.
#       Airflow raises AirflowDagCycleException; DAG never loads.
# ---------------------------------------------------------------------------

PRODUCER_PY = '''\
"""Publishes processed events to the orchid agent response topic."""
from kafka import KafkaProducer
import json

KAFKA_TOPIC = 'orchid.sandbox.agent.responses'   # BUG: should be 'orchid.sandbox.agent_response'
KAFKA_BROKERS = ['kafka:9092']

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
)


def publish_events(events: list[dict]) -> int:
    """Publish events to Kafka. Returns number of messages sent."""
    for event in events:
        producer.send(KAFKA_TOPIC, value=event)
    producer.flush()
    return len(events)


if __name__ == '__main__':
    sample_events = [{"event_id": f"evt_{i:04d}", "type": "agent_response"} for i in range(1000)]
    sent = publish_events(sample_events)
    print(f"Published {sent} events to {KAFKA_TOPIC}")
'''

QDRANT_INGEST_PY = '''\
"""Ingests processed events into the Qdrant vector store."""
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import logging

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
                    vector=[0.1, 0.2, 0.3],   # BUG: dimension 3, collection expects 1536
                    payload={"session_id": session_id, **payload},
                )
            ],
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Qdrant upsert failed: %s", exc)
        return False


if __name__ == '__main__':
    ok = ingest_point("evt_0001", "sess_demo", {"type": "agent_response"})
    print("Ingest ok" if ok else "Ingest failed (check DEBUG logs)")
'''

ETL_DAG_PY = '''\
"""Airflow DAG: orchid_etl — extract → transform → load pipeline."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

with DAG(
    dag_id="orchid_etl",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
) as dag:

    extract_task = PythonOperator(
        task_id="extract",
        python_callable=lambda: print("extracting"),
    )
    transform_task = PythonOperator(
        task_id="transform",
        python_callable=lambda: print("transforming"),
    )
    load_task = PythonOperator(
        task_id="load",
        python_callable=lambda: print("loading"),
    )

    extract_task >> transform_task >> load_task
    load_task >> extract_task   # BUG: creates cycle extract→transform→load→extract
'''

PIPELINE_RUN_LOG = """\
[2024-04-15 09:00:00] INFO  scenario=silent_pipeline run_id=run_001 started
[2024-04-15 09:00:01] INFO  producer: connecting to kafka:9092
[2024-04-15 09:00:02] INFO  producer: connected. publishing 1000 events to orchid.sandbox.agent.responses
[2024-04-15 09:00:08] INFO  producer: 1000 events published. flush complete.
[2024-04-15 09:00:08] INFO  consumer: connecting to kafka:9092 group=orchid-evaluator-ingest
[2024-04-15 09:00:09] INFO  consumer: subscribed to [orchid.sandbox.agent_response]
[2024-04-15 09:00:09] INFO  consumer: polling for messages (timeout=10s)...
[2024-04-15 09:00:19] INFO  consumer: 0 messages received.
[2024-04-15 09:00:19] INFO  consumer: 0 messages received.
[2024-04-15 09:00:29] INFO  consumer: 0 messages received.
[2024-04-15 09:00:39] INFO  qdrant_ingest: starting ingest for 0 events
[2024-04-15 09:00:39] INFO  qdrant_ingest: 0 points upserted to orchid_interactions
[2024-04-15 09:00:39] INFO  airflow: triggering DAG orchid_etl
[2024-04-15 09:00:40] ERROR airflow: DAG orchid_etl failed to load — check import errors
[2024-04-15 09:00:40] INFO  run complete. events_published=1000 events_indexed=0 events_in_correct_topic=0
"""

REQUIREMENTS_TXT = """\
kafka-python>=2.0.0
qdrant-client>=1.9.0
apache-airflow>=2.9.0
"""

README_MD = """\
# The Silent Pipeline — Workspace

**Scenario ID**: `scenario_silent_pipeline_v1`

## Overview

Something is wrong. The pipeline ran without errors, but no events reached the index.

- `pipeline_run.log` — output from the last pipeline run
- `producer.py` — publishes events to Kafka
- `qdrant_ingest.py` — ingests events into the Qdrant vector store
- `etl_dag.py` — Airflow DAG for the extract-transform-load pipeline
- `requirements.txt` — Python dependencies

## Your Task

1. Read `pipeline_run.log` to understand the failure signature.
2. Trace the failure through each component: producer → consumer → index → DAG.
3. Fix each root cause. Document what you found and how you diagnosed it.
4. Re-run to verify events flow end-to-end.

The pipeline should eventually show `events_indexed > 0` and the DAG should load cleanly.

**Hint**: No component raises an unhandled exception. All failures are silent.
"""


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path}")


def main() -> None:
    print(f"Seeding workspace_v2 into {TARGET_DIR.resolve()}/")
    write_file(TARGET_DIR / "producer.py", PRODUCER_PY)
    write_file(TARGET_DIR / "qdrant_ingest.py", QDRANT_INGEST_PY)
    write_file(TARGET_DIR / "etl_dag.py", ETL_DAG_PY)
    write_file(TARGET_DIR / "pipeline_run.log", PIPELINE_RUN_LOG)
    write_file(TARGET_DIR / "requirements.txt", REQUIREMENTS_TXT)
    write_file(TARGET_DIR / "README.md", README_MD)

    # Also write a snapshot of what the config looks like
    config = {
        "scenario_id": "scenario_silent_pipeline_v1",
        "violations": [
            {"id": "V1", "file": "producer.py",     "description": "Wrong Kafka topic"},
            {"id": "V2", "file": "qdrant_ingest.py", "description": "Wrong vector dimension"},
            {"id": "V3", "file": "etl_dag.py",       "description": "Circular DAG dependency"},
        ],
    }
    config_path = TARGET_DIR / "pipeline_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"  wrote {config_path}")
    print("Done — 3 violations seeded.")


if __name__ == "__main__":
    main()
