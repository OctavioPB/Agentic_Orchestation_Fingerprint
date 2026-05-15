"""Publishes processed events to the orchid agent response topic."""

import json

from kafka import KafkaProducer

KAFKA_TOPIC = "orchid.sandbox.agent.responses"  # BUG: should be 'orchid.sandbox.agent_response'
KAFKA_BROKERS = ["kafka:9092"]

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)


def publish_events(events: list[dict]) -> int:
    """Publish events to Kafka. Returns number of messages sent."""
    for event in events:
        producer.send(KAFKA_TOPIC, value=event)
    producer.flush()
    return len(events)


if __name__ == "__main__":
    sample_events = [
        {"event_id": f"evt_{i:04d}", "type": "agent_response"} for i in range(1000)
    ]
    sent = publish_events(sample_events)
    print(f"Published {sent} events to {KAFKA_TOPIC}")
