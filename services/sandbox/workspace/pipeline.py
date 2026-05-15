"""
Data pipeline: consumes events from Kafka and writes them to the warehouse DB.

STATUS: BROKEN — see README.md for the assessment task.
"""
import json
import logging
import sqlite3

from kafka import KafkaConsumer

# BUG 1: Wrong topic name — extra 's' in 'prompts_sent'
KAFKA_TOPIC = "orchid.sandbox.prompts_sent"

# BUG 2: Wrong broker address — must reference the Docker service name inside compose
KAFKA_BROKERS = "localhost:9092"

# BUG 3: Consumer group does not follow the orchid-{service}-{purpose} convention
CONSUMER_GROUP = "data-pipeline-consumer"

DB_PATH = "dirty_warehouse.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def process_event(event_data: dict) -> None:
    conn = get_connection()
    # BUG 4: Wrong column name — 'event_payload' does not exist; the column is 'payload'
    conn.execute(
        "INSERT INTO raw_events (event_id, source, event_payload, created_at) VALUES (?, ?, ?, ?)",
        (
            event_data.get("event_id"),
            event_data.get("session_id"),
            json.dumps(event_data.get("payload", {})),
            event_data.get("timestamp"),
        ),
    )
    # BUG 5: Missing conn.commit() — writes are never persisted to disk
    conn.close()


def run_pipeline() -> None:
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKERS,
        group_id=CONSUMER_GROUP,
        # BUG 6: 'latest' means events that arrived before the consumer started are skipped.
        # Should be 'earliest' for reliable replay during debugging / cold starts.
        auto_offset_reset="latest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )

    logger.info("Listening on topic %s ...", KAFKA_TOPIC)
    for message in consumer:
        process_event(message.value)


if __name__ == "__main__":
    run_pipeline()
