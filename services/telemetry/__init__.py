"""orchid telemetry service — Kafka producer, consumer, and event models."""
from .consumer import LoggingConsumer, TelemetryConsumer
from .models import (
    AgentName,
    AgentResponsePayload,
    ChaosInjectedPayload,
    CodeExecutedPayload,
    CorrectionIssuedPayload,
    EventType,
    FocusShiftPayload,
    PromptSentPayload,
    ScenarioEndedPayload,
    ScenarioStartedPayload,
    TelemetryEvent,
)
from .producer import DLQProducer, TelemetryProducer
from .topics import ALL_ORCHID_TOPICS, DLQ_TOPIC, TOPIC_MAP

__all__ = [
    # Models
    "AgentName",
    "AgentResponsePayload",
    "ChaosInjectedPayload",
    "CodeExecutedPayload",
    "CorrectionIssuedPayload",
    "EventType",
    "FocusShiftPayload",
    "PromptSentPayload",
    "ScenarioEndedPayload",
    "ScenarioStartedPayload",
    "TelemetryEvent",
    # Producer
    "DLQProducer",
    "TelemetryProducer",
    # Consumer
    "LoggingConsumer",
    "TelemetryConsumer",
    # Topics
    "ALL_ORCHID_TOPICS",
    "DLQ_TOPIC",
    "TOPIC_MAP",
]
