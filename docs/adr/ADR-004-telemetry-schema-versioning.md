# ADR-004: Telemetry Event Schema Versioning Strategy

**Status**: Accepted
**Date**: 2026-05-14

## Context

`orchid` emits 8 types of telemetry events to Kafka. These schemas will evolve as sprints progress: new fields will be added, optional fields may become required, and new event types will be introduced. Consumers (the evaluator, the fingerprint assembler, the embedding ETL DAG) must be able to read messages produced by both old and new schema versions.

We evaluated three approaches:

1. **Avro schemas + Confluent Schema Registry (BACKWARD compatibility mode)**
2. **JSON Schema + Schema Registry (FORWARD compatibility mode)**
3. **Raw JSON with no schema enforcement (schemaless)**

## Decision

Use **Avro schemas + Confluent Schema Registry with BACKWARD compatibility mode**.

## Reasoning

### Schema enforcement at produce time
Schemaless JSON producers can emit malformed or incomplete events that only fail when consumed — potentially hours after production, when debugging is harder. Avro serialization with Schema Registry enforces the schema at the producer before the message hits Kafka. Invalid messages fail fast at source.

### BACKWARD vs FORWARD vs FULL_TRANSITIVE

| Mode | Allows | Prohibits |
|---|---|---|
| BACKWARD | Add optional fields; remove fields with defaults | Add required fields; change field types |
| FORWARD | Add required fields | Remove fields |
| FULL_TRANSITIVE | Only add optional fields with defaults | Everything else |

**BACKWARD** is the correct choice for our consumer topology: consumers may lag behind producers during rolling deploys. A consumer running schema version N must be able to read messages produced with schema version N+1. BACKWARD guarantees this as long as new fields are optional with defaults. This is consistent with our sprint cadence — we add fields sprint by sprint, rarely remove them.

**FULL_TRANSITIVE** would be more conservative but prohibits removing fields, which blocks cleanup of deprecated fields added during early sprints. We expect to prune 2–3 experimental fields by Sprint 7.

### Avro over JSON Schema
Avro is more compact on the wire (binary encoding vs UTF-8 JSON) — a meaningful difference at 1000 concurrent sessions emitting events every few seconds. More importantly, Confluent's `confluent-kafka` Python client has first-class Avro serializer support that integrates with the Schema Registry client. JSON Schema validation in the Python ecosystem requires a separate validator and custom producer middleware.

### Schema ID in message header
Every Avro message produced via the Confluent serializer embeds the Schema Registry schema ID in the first 5 bytes of the message value. Consumers use this ID to fetch the correct schema version from the registry. This is transparent to application code — the `AvroDeserializer` handles it automatically.

## Schema evolution rules (enforced by CI)

1. New fields **must** have a default value (e.g., `"default": null` for optional fields).
2. Field types **must not** change between versions.
3. Fields **must not** be removed without a deprecation period of at least 2 sprint versions.
4. New event types (new schemas) are registered as new subjects, not appended to existing schemas.

Subject naming convention: `orchid.{service}.{event_type}-value`
Example: `orchid.sandbox.prompt_sent-value`

## Consequences

**Enables:**
- Producers validated at emit time — malformed events never reach Kafka.
- Zero-downtime schema migrations via BACKWARD compatibility.
- Automatic schema documentation via Schema Registry UI.
- Compact binary encoding reduces Kafka storage and consumer throughput costs.

**Forecloses:**
- Ad-hoc JSON producers without a schema (all producers must use the Avro serializer).
- Schema Registry becomes a hard availability dependency — if the registry is down, no events can be produced. Mitigation: enable `schema.registry.cache.enabled=true` so producers can operate for a configurable TTL using cached schemas.

**Accepted trade-off:** The registry dependency is acceptable. The alternative — schemaless JSON — would shift schema validation errors to downstream consumers, where they are significantly more expensive to diagnose and recover from.
