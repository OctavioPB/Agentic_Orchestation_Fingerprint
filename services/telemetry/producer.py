"""Async Kafka producer with retry logic and structured logging."""
from __future__ import annotations

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog
from confluent_kafka import KafkaException, Producer
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .models import TelemetryEvent
from .topics import DLQ_TOPIC, TOPIC_MAP

logger = structlog.get_logger(__name__)

_PRODUCER_CONFIG_DEFAULTS: dict[str, Any] = {
    "acks": "all",
    "retries": 0,  # tenacity handles retries at application level
    "linger.ms": 5,
    "compression.type": "snappy",
}


class TelemetryProducer:
    """Async Kafka producer for orchid telemetry events.

    Uses confluent-kafka (synchronous C extension) wrapped via asyncio.to_thread
    so callers can await emit() without blocking the event loop.

    Retry policy: 3 attempts with exponential backoff (1s, 2s, 4s) on BufferError
    (internal queue full). Other errors are re-raised immediately.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        extra_config: dict[str, Any] | None = None,
    ) -> None:
        cfg: dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers,
            **_PRODUCER_CONFIG_DEFAULTS,
            **(extra_config or {}),
        }
        self._producer = Producer(cfg)
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="orchid-producer")
        self._log = logger.bind(component="TelemetryProducer", brokers=bootstrap_servers)

    # ── Public API ──────────────────────────────────────────────────────────────

    async def emit(self, event: TelemetryEvent) -> None:
        """Serialize and produce one event. Awaitable; does not block the event loop."""
        await asyncio.to_thread(self._sync_emit, event)

    def flush(self, timeout: float = 10.0) -> None:
        """Block until all queued messages are delivered (or timeout)."""
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            self._log.warning("flush_incomplete", remaining_messages=remaining)

    def close(self) -> None:
        self.flush()
        self._executor.shutdown(wait=False)

    # ── Internal sync path (runs in thread) ────────────────────────────────────

    def _sync_emit(self, event: TelemetryEvent) -> None:
        topic = TOPIC_MAP[event.event_type]
        value = json.dumps(event.model_dump()).encode()
        key = event.session_id.encode()

        start = time.monotonic()
        self._produce_with_retry(topic, key, value, event.event_id)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        self._log.info(
            "event_queued",
            event_id=event.event_id,
            event_type=event.event_type,
            topic=topic,
            elapsed_ms=elapsed_ms,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(BufferError),
        reraise=True,
    )
    def _produce_with_retry(
        self, topic: str, key: bytes, value: bytes, event_id: str
    ) -> None:
        self._producer.produce(
            topic=topic,
            key=key,
            value=value,
            callback=self._delivery_callback,
        )
        # Poll triggers delivery callbacks for already-sent messages without blocking
        self._producer.poll(0)

    def _delivery_callback(self, err: Any, msg: Any) -> None:
        if err:
            self._log.error(
                "delivery_failed",
                error=str(err),
                topic=msg.topic() if msg else "unknown",
            )
        else:
            self._log.debug(
                "delivered",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )


class DLQProducer:
    """Minimal synchronous producer for sending malformed messages to the DLQ."""

    def __init__(self, bootstrap_servers: str) -> None:
        self._producer = Producer({"bootstrap.servers": bootstrap_servers})
        self._log = logger.bind(component="DLQProducer")

    def send(self, original_value: bytes, error: str, original_topic: str) -> None:
        envelope = json.dumps(
            {
                "original_topic": original_topic,
                "error": error,
                "original_value": original_value.decode(errors="replace"),
            }
        ).encode()
        try:
            self._producer.produce(topic=DLQ_TOPIC, value=envelope)
            self._producer.poll(0)
            self._log.warning(
                "sent_to_dlq", original_topic=original_topic, error=error[:200]
            )
        except KafkaException as exc:
            self._log.error("dlq_produce_failed", exc=str(exc))

    def flush(self) -> None:
        self._producer.flush(5.0)
