"""Base async Kafka consumer with manual commit and DLQ routing for malformed events."""
from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any

import structlog
from confluent_kafka import Consumer, KafkaError, Message
from pydantic import ValidationError

from .models import TelemetryEvent
from .producer import DLQProducer

logger = structlog.get_logger(__name__)

_CONSUMER_CONFIG_DEFAULTS: dict[str, Any] = {
    "enable.auto.commit": False,  # manual ack — never auto-commit
    "auto.offset.reset": "earliest",
    "fetch.min.bytes": 1,
    "fetch.wait.max.ms": 100,
}


class TelemetryConsumer(ABC):
    """Base class for all orchid Kafka consumers.

    Subclass and implement handle_event(). The base class handles:
    - Manual offset commit after successful handling
    - DLQ routing for JSON parse errors and schema validation failures
    - Graceful shutdown via stop()
    """

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topics: list[str],
        extra_config: dict[str, Any] | None = None,
    ) -> None:
        cfg: dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            **_CONSUMER_CONFIG_DEFAULTS,
            **(extra_config or {}),
        }
        self._consumer = Consumer(cfg)
        self._consumer.subscribe(topics)
        self._dlq = DLQProducer(bootstrap_servers)
        self._stopping = False
        self._log = logger.bind(
            component=self.__class__.__name__,
            group_id=group_id,
            topics=topics,
        )

    # ── Public API ──────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Poll and dispatch events indefinitely. Returns only after stop() is called."""
        self._log.info("consumer_started")
        try:
            while not self._stopping:
                # poll blocks for up to 1 s — run in a thread so the event loop stays free
                msg: Message | None = await asyncio.to_thread(self._consumer.poll, 1.0)

                if msg is None:
                    continue

                if msg.error():
                    self._handle_kafka_error(msg)
                    continue

                await self._dispatch(msg)
        finally:
            self._consumer.close()
            self._dlq.flush()
            self._log.info("consumer_stopped")

    def stop(self) -> None:
        self._stopping = True

    # ── Abstract handler ────────────────────────────────────────────────────────

    @abstractmethod
    async def handle_event(self, event: TelemetryEvent) -> None:
        """Process one validated event. Commit happens after this returns."""

    # ── Internal dispatch ───────────────────────────────────────────────────────

    async def _dispatch(self, msg: Message) -> None:
        raw = msg.value()
        topic = msg.topic()

        event = self._deserialize(raw, topic)
        if event is None:
            # Deserialization failure → DLQ; still commit so we don't re-process
            self._consumer.commit(message=msg, asynchronous=False)
            return

        try:
            await self.handle_event(event)
            self._consumer.commit(message=msg, asynchronous=False)
            self._log.debug(
                "event_handled",
                event_id=event.event_id,
                event_type=event.event_type,
            )
        except Exception as exc:
            self._log.error(
                "handler_error",
                event_id=event.event_id,
                error=str(exc),
            )
            # Do NOT commit — allow re-processing on restart

    def _deserialize(self, raw: bytes, topic: str) -> TelemetryEvent | None:
        try:
            data = json.loads(raw)
            return TelemetryEvent.model_validate(data)
        except json.JSONDecodeError as exc:
            self._log.warning("json_parse_error", topic=topic, error=str(exc))
            self._dlq.send(raw, f"JSONDecodeError: {exc}", topic)
            return None
        except ValidationError as exc:
            self._log.warning("schema_validation_error", topic=topic, errors=exc.error_count())
            self._dlq.send(raw, f"ValidationError: {exc}", topic)
            return None

    def _handle_kafka_error(self, msg: Message) -> None:
        err = msg.error()
        if err.code() == KafkaError._PARTITION_EOF:
            # Normal end of partition — not an error
            self._log.debug("partition_eof", topic=msg.topic(), partition=msg.partition())
        else:
            self._log.error("kafka_error", code=err.code(), reason=err.str())


class LoggingConsumer(TelemetryConsumer):
    """Concrete consumer that logs every received event. Used in dev and for session replay."""

    async def handle_event(self, event: TelemetryEvent) -> None:
        self._log.info(
            "received",
            event_id=event.event_id,
            event_type=event.event_type,
            session_id=event.session_id,
        )
