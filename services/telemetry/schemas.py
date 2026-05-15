"""Schema Registry client helpers for Avro schema registration and serialization."""
from __future__ import annotations

import json
from pathlib import Path

import structlog
from confluent_kafka.schema_registry import Schema, SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer

logger = structlog.get_logger(__name__)

# Path to .avsc files — relative to the repo root
_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "docs" / "schema"

# Subjects follow Confluent naming convention: {topic-name}-value
_SUBJECT_MAP: dict[str, str] = {
    "orchid.sandbox.prompt_sent": "orchid.sandbox.prompt_sent-value",
    "orchid.sandbox.agent_response": "orchid.sandbox.agent_response-value",
    "orchid.sandbox.correction_issued": "orchid.sandbox.correction_issued-value",
    "orchid.sandbox.code_executed": "orchid.sandbox.code_executed-value",
    "orchid.sandbox.focus_shift": "orchid.sandbox.focus_shift-value",
    "orchid.sandbox.chaos_injected": "orchid.sandbox.chaos_injected-value",
    "orchid.sandbox.scenario_started": "orchid.sandbox.scenario_started-value",
    "orchid.sandbox.scenario_ended": "orchid.sandbox.scenario_ended-value",
}


class SchemaRegistryHelper:
    """Wraps the Confluent Schema Registry client for orchid schema operations."""

    def __init__(self, schema_registry_url: str) -> None:
        self._client = SchemaRegistryClient({"url": schema_registry_url})
        self._log = logger.bind(component="SchemaRegistryHelper", url=schema_registry_url)

    # ── Registration ────────────────────────────────────────────────────────────

    def register_all(self, compatibility: str = "BACKWARD") -> dict[str, int]:
        """Register all Avro schemas from docs/schema/ and return subject → schema_id map."""
        results: dict[str, int] = {}
        for avsc_file in sorted(_SCHEMA_DIR.glob("*.avsc")):
            topic_name = f"orchid.sandbox.{avsc_file.stem}"
            subject = _SUBJECT_MAP.get(topic_name)
            if subject is None:
                self._log.warning("unknown_schema_file", file=avsc_file.name)
                continue
            schema_id = self._register_one(subject, avsc_file.read_text(), compatibility)
            results[subject] = schema_id
        return results

    def _register_one(self, subject: str, schema_str: str, compatibility: str) -> int:
        # Set compatibility before registering
        try:
            self._client.set_compatibility(subject_name=subject, level=compatibility)
        except Exception:
            pass  # Subject may not exist yet; registry sets default on first registration

        schema = Schema(schema_str, "AVRO")
        schema_id = self._client.register_schema(subject, schema)
        self._log.info("schema_registered", subject=subject, schema_id=schema_id)
        return schema_id

    # ── Serializer/Deserializer factories ───────────────────────────────────────

    def get_serializer(self, avsc_file: Path) -> AvroSerializer:
        schema_str = avsc_file.read_text()
        return AvroSerializer(self._client, schema_str, lambda obj, _: obj)

    def get_deserializer(self, avsc_file: Path) -> AvroDeserializer:
        schema_str = avsc_file.read_text()
        return AvroDeserializer(self._client, schema_str, lambda obj, _: obj)

    # ── Schema introspection ────────────────────────────────────────────────────

    def list_subjects(self) -> list[str]:
        return self._client.get_subjects()

    def get_schema(self, subject: str) -> dict:
        registered = self._client.get_latest_version(subject)
        return json.loads(registered.schema.schema_str)
