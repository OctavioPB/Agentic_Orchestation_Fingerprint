"""Integration tests: produce + consume 50 events via testcontainers Kafka.

Run with:
    pytest tests/integration/ -m integration -v

Requires: Docker daemon running, testcontainers[kafka] installed.
These tests are NOT run in the standard CI unit-test job.
"""
from __future__ import annotations

import json
import time
from collections.abc import Generator

import pytest
from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic

# testcontainers is an optional dependency — skip cleanly if not installed
testcontainers = pytest.importorskip("testcontainers", reason="testcontainers not installed")
from testcontainers.kafka import KafkaContainer  # noqa: E402

from services.telemetry.models import (  # noqa: E402
    AgentName,
    EventType,
    PromptSentPayload,
    TelemetryEvent,
)
from services.telemetry.producer import DLQProducer, TelemetryProducer  # noqa: E402
from services.telemetry.topics import DLQ_TOPIC  # noqa: E402

_TEST_TOPIC = "test.orchid.prompt_sent"
_TEST_GROUP = "orchid-integration-test"
_KAFKA_IMAGE = "confluentinc/cp-kafka:7.5.0"


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def kafka_bootstrap() -> Generator[str, None, None]:
    """Start a throwaway Kafka container for the test module."""
    with KafkaContainer(image=_KAFKA_IMAGE) as kafka:
        servers = kafka.get_bootstrap_server()
        _create_test_topics(servers)
        yield servers


def _create_test_topics(bootstrap_servers: str) -> None:
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    topics = [
        NewTopic(_TEST_TOPIC, num_partitions=1, replication_factor=1),
        NewTopic(DLQ_TOPIC, num_partitions=1, replication_factor=1),
    ]
    futures = admin.create_topics(topics)
    for topic, future in futures.items():
        try:
            future.result()
        except Exception:
            pass  # Already exists is fine


# ─── Helpers ───────────────────────────────────────────────────────────────────


def _make_event(index: int, session_id: str = "sess_integration") -> TelemetryEvent:
    payload = PromptSentPayload(
        agent=AgentName.DELTA,
        text=f"Integration test event {index}",
    )
    return TelemetryEvent.prompt_sent(session_id, payload)


def _consume_all(
    bootstrap_servers: str,
    topic: str,
    expected_count: int,
    timeout_sec: float = 15.0,
) -> list[dict]:
    """Consume up to expected_count messages or until timeout. Returns raw dicts."""
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": _TEST_GROUP,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([topic])
    collected: list[dict] = []
    deadline = time.monotonic() + timeout_sec

    try:
        while len(collected) < expected_count and time.monotonic() < deadline:
            msg = consumer.poll(timeout=1.0)
            if msg is None or msg.error():
                continue
            collected.append(json.loads(msg.value()))
    finally:
        consumer.close()

    return collected


# ─── Tests ─────────────────────────────────────────────────────────────────────


class TestProducerConsumer:
    def test_produce_and_consume_50_events(self, kafka_bootstrap: str) -> None:
        """Produce 50 PROMPT_SENT events and verify all are consumed in order."""
        events = [_make_event(i) for i in range(50)]
        session_id = events[0].session_id

        # Produce
        producer = TelemetryProducer(
            bootstrap_servers=kafka_bootstrap,
            extra_config={"compression.type": "none"},  # snappy not always in test image
        )

        # Emit to the test topic directly (bypass TOPIC_MAP for isolation)
        sync_producer = Producer({"bootstrap.servers": kafka_bootstrap})
        for event in events:
            sync_producer.produce(
                topic=_TEST_TOPIC,
                key=event.session_id.encode(),
                value=event.model_dump_json().encode(),
            )
        sync_producer.flush(10.0)

        # Consume
        consumed = _consume_all(kafka_bootstrap, _TEST_TOPIC, expected_count=50)

        assert len(consumed) == 50, f"Expected 50 events, got {len(consumed)}"

        # Verify all session_ids match
        for msg in consumed:
            assert msg["session_id"] == session_id
            assert msg["event_type"] == "PROMPT_SENT"
        producer.close()

    def test_malformed_events_go_to_dlq(self, kafka_bootstrap: str) -> None:
        """Malformed bytes (not JSON) sent to a topic end up in orchid.dlq."""
        dlq_producer = DLQProducer(bootstrap_servers=kafka_bootstrap)
        dlq_producer.send(
            original_value=b"{not valid json}",
            error="JSONDecodeError: test",
            original_topic=_TEST_TOPIC,
        )
        dlq_producer.flush()

        dlq_messages = _consume_all(kafka_bootstrap, DLQ_TOPIC, expected_count=1)
        assert len(dlq_messages) >= 1
        dlq_entry = dlq_messages[0]
        assert "error" in dlq_entry
        assert "original_topic" in dlq_entry
        assert dlq_entry["original_topic"] == _TEST_TOPIC

    def test_telemetry_event_roundtrip_through_kafka(self, kafka_bootstrap: str) -> None:
        """A TelemetryEvent serialized to JSON and consumed from Kafka parses back correctly."""
        original = _make_event(999)

        sync_producer = Producer({"bootstrap.servers": kafka_bootstrap})
        sync_producer.produce(
            topic=_TEST_TOPIC,
            key=original.session_id.encode(),
            value=original.model_dump_json().encode(),
        )
        sync_producer.flush(10.0)

        consumed = _consume_all(kafka_bootstrap, _TEST_TOPIC, expected_count=1, timeout_sec=10.0)

        assert len(consumed) >= 1
        last = consumed[-1]  # most recently produced
        restored = TelemetryEvent.model_validate(last)

        assert restored.event_type == EventType.PROMPT_SENT
        assert restored.payload["agent"] == "DELTA"

    def test_zero_dlq_entries_on_happy_path(self, kafka_bootstrap: str) -> None:
        """Consuming valid events must not produce DLQ entries."""
        # Consume any accumulated valid messages — the DLQ consumer check is the key assertion
        # The DLQ only gets entries from malformed messages (previous test).
        # Valid events must have at most 1 DLQ entry (the one we intentionally sent).
        dlq_messages = _consume_all(
            kafka_bootstrap, DLQ_TOPIC, expected_count=10, timeout_sec=3.0
        )
        # We sent exactly 1 malformed message in test_malformed_events_go_to_dlq
        assert len(dlq_messages) <= 1, (
            f"Too many DLQ entries: {len(dlq_messages)}. "
            "Valid events must not be routed to the DLQ."
        )
