# Telemetry Event Schemas

Avro schemas for all 8 orchid telemetry event types.
Each schema corresponds to one Kafka topic (one event type per topic).

## Topic → Schema mapping

| Topic | Schema file | Subject (Schema Registry) |
|---|---|---|
| `orchid.sandbox.prompt_sent` | `prompt_sent.avsc` | `orchid.sandbox.prompt_sent-value` |
| `orchid.sandbox.agent_response` | `agent_response.avsc` | `orchid.sandbox.agent_response-value` |
| `orchid.sandbox.correction_issued` | `correction_issued.avsc` | `orchid.sandbox.correction_issued-value` |
| `orchid.sandbox.code_executed` | `code_executed.avsc` | `orchid.sandbox.code_executed-value` |
| `orchid.sandbox.focus_shift` | `focus_shift.avsc` | `orchid.sandbox.focus_shift-value` |
| `orchid.sandbox.chaos_injected` | `chaos_injected.avsc` | `orchid.sandbox.chaos_injected-value` |
| `orchid.sandbox.scenario_started` | `scenario_started.avsc` | `orchid.sandbox.scenario_started-value` |
| `orchid.sandbox.scenario_ended` | `scenario_ended.avsc` | `orchid.sandbox.scenario_ended-value` |

## Compatibility mode

All subjects use **BACKWARD** compatibility (see ADR-004).

Evolution rules:
- New fields **must** have a `"default"` value.
- Field types **must not** change between versions.
- Fields **must not** be removed without a 2-sprint deprecation window.

## Registering schemas

```bash
# Stack must be running first
make up

# Register all schemas against the local Schema Registry
python scripts/register_schemas.py --schema-registry http://localhost:8081
```

## Common envelope fields

All 8 schemas share these four fields:

| Field | Type | Notes |
|---|---|---|
| `event_id` | `string` | UUID v4 |
| `session_id` | `string` | Ties all events to one candidate session |
| `timestamp` | `string` | ISO 8601 UTC |
| `event_type` | `string` | Fixed value per topic (validated at application layer) |
