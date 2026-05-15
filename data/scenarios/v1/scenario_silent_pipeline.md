# Scenario v2: The Silent Pipeline

**ID**: `scenario_silent_pipeline_v1`
**Duration**: Up to 60 minutes | **Chaos**: CORRUPT_SCHEMA at T+20 min

---

## Overview

An event processing pipeline appears to be running normally — no exceptions, no errors in the
logs. But events are disappearing. The Kafka producer is publishing to the wrong topic. The
Qdrant vector store rejects upserts silently because the vector dimension is wrong. And an
Airflow DAG cannot load because of a circular task dependency. The candidate must trace each
silent failure to its root cause.

This scenario rewards systematic thinkers who check the full pipeline path (produce → consume
→ index) rather than focusing only on the layer that "looks wrong."

---

## The Three Violations

### Violation 1 — Wrong Kafka Topic (producer.py)

```python
KAFKA_TOPIC = 'orchid.sandbox.agent.responses'   # BUG
# Should be:
KAFKA_TOPIC = 'orchid.sandbox.agent_response'    # correct (underscore, no dot-separated subpath)
```

**Impact**: Producer publishes 1,000 events per run. Zero are consumed. No exception is raised
because producing to a non-subscribed topic is not an error — the messages simply accumulate
in a dead topic until retention expires.

### Violation 2 — Wrong Vector Dimension (qdrant_ingest.py)

```python
vector=[0.1, 0.2, 0.3],  # BUG: dimension 3
# Should be: vector of 1536 floats (text-embedding-3-large output dimension)
```

**Impact**: `QdrantClient.upsert()` raises `UnexpectedResponse` (HTTP 400) because the
collection `orchid_interactions` is configured for 1536-dimensional vectors. The error is
raised as a generic exception and logged at DEBUG level, making it easy to miss.

### Violation 3 — Circular DAG Dependency (etl_dag.py)

```python
extract_task >> transform_task >> load_task
load_task >> extract_task  # creates cycle: extract → transform → load → extract
```

**Impact**: Airflow raises `AirflowDagCycleException` during DAG parsing. The DAG never
loads into the scheduler. Any run triggered via the UI appears to do nothing.

---

## Canonical Resolution Path

**Step 1 — Read the run log (T+0 to T+3 min)**
```bash
cat pipeline_run.log
```
Observe: 1000 events published, 0 indexed, 0 found in the correct topic. This is the
key signal that the producer and consumer are not on the same topic.

**Step 2 — Compare topic names (T+3 to T+8 min)**
```bash
grep -n "KAFKA_TOPIC" producer.py
# Compare against the orchid topic convention: orchid.sandbox.{event_type}
```
Identifies `agent.responses` vs `agent_response` (dot vs underscore delimiter).

**Step 3 — Fix producer.py (T+8 to T+10 min)**
Change `KAFKA_TOPIC` to `'orchid.sandbox.agent_response'`. Re-run and verify 0 published
to old topic, N published to correct topic.

**Step 4 — Diagnose Qdrant failure (T+10 to T+18 min)**
Run `qdrant_ingest.py` and capture full exception. Read the response body: dimension mismatch.
```bash
python3 qdrant_ingest.py 2>&1
```
Fix: replace `vector=[0.1, 0.2, 0.3]` with a properly sized embedding call.

**Step 5 — Diagnose DAG (T+18 to T+20 min)**
```bash
python3 -c "import ast; ast.parse(open('etl_dag.py').read()); print('syntax ok')"
# Then try: airflow dags list-import-errors
```
Identify the `load_task >> extract_task` line creating the cycle. Remove it.

**Step 6 — Chaos recovery (T+20 to T+35 min)**
CORRUPT_SCHEMA drops `session_id` from Qdrant payload. The ingest script now produces
points without a required field. Candidate must add `session_id` back to the payload
dict before upserting.

**Steps 7–8 — Verify and document (T+35 to T+45 min)**
End-to-end test: produce events → verify consumed → verify indexed with correct dimensions
and required payload fields.

---

## AI-Solo Baseline (for `efficiency_ratio`)

An AI-solo run of this scenario:
- Fixed the topic typo (step 2–3) and the DAG cycle (step 5)
- Did not diagnose the Qdrant dimension mismatch — the AI solo passed `None` as a placeholder
  and moved on, leaving the ingest broken
- Total: 19 steps, 2341 seconds, 2/3 violations fixed

---

## Scoring Notes

| Signal | What to look for |
|--------|-----------------|
| `decomposition_score` | Does the candidate check all three components (Kafka, Qdrant, Airflow)? |
| `trust_calibration` | Does the candidate verify DELTA's topic name suggestion before applying? |
| `correction_velocity` | NOVA will ask 3 clarifying questions before diagnosing. How quickly managed? |
| `chaos_resilience` | Time from CORRUPT_SCHEMA to Qdrant payload fixed and ingest re-running |
| `efficiency_ratio` | Steps taken vs AI-solo baseline (19 steps, 2341 sec) |
