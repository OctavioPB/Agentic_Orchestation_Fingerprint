# Scenario v1: The Corrupted Warehouse

**ID**: `scenario_corrupted_warehouse_v1`
**Duration**: Up to 60 minutes | **Chaos**: KILL_CONSUMER at T+30 min

---

## Overview

A Kafka consumer pipeline (`pipeline.py`) is supposed to read events from the
`orchid.sandbox.prompt_sent` topic and write them to a SQLite data warehouse
(`dirty_warehouse.db`). Neither the pipeline nor the warehouse is in a working state.
The candidate must diagnose both, fix the pipeline, document the data quality violations,
and recover after a chaos event that kills the consumer process.

---

## The Eight Data Quality Violations

### Table: `customers`
| # | Column | Violation | Example Value |
|---|--------|-----------|---------------|
| 1 | `email` | NULL stored in a NOT NULL column (missing constraint allows it) | `NULL` (row 2) |

### Table: `orders`
| # | Column | Violation | Example Value |
|---|--------|-----------|---------------|
| 2 | `customer_id` | FK referential integrity — customer does not exist | `999` |
| 3 | `amount` | Wrong data type: string stored in REAL column | `'REFUND_PENDING'` |
| 4 | `customer_id` | FK null #1 — order has no customer association | `NULL` (row 105) |
| 5 | `customer_id` | FK null #2 — order has no customer association | `NULL` (row 106) |
| 6 | `customer_id` | FK null #3 — order has no customer association | `NULL` (row 107) |

### Table: `raw_events`
| # | Column | Violation | Example Value |
|---|--------|-----------|---------------|
| 7 | `event_id` | Missing PRIMARY KEY constraint — duplicate IDs allowed | `'evt_001'` (twice) |
| 8 | `payload` | Malformed JSON — cannot be deserialized | `'{broken json: missing quotes}'` |

---

## Pipeline Bugs (pipeline.py)

Six bugs the candidate must fix:

| # | Variable | Current (broken) | Correct | Reason |
|---|----------|-----------------|---------|--------|
| 1 | `KAFKA_TOPIC` | `'orchid.sandbox.prompts_sent'` | `'orchid.sandbox.prompt_sent'` | Trailing 's' typo |
| 2 | `KAFKA_BROKERS` | `'localhost:9092'` | `'kafka:9092'` | Docker service name resolution |
| 3 | `CONSUMER_GROUP` | `'data-pipeline-consumer'` | `'orchid-telemetry-warehouse'` | Naming convention |
| 4 | `auto_offset_reset` | `'latest'` | `'earliest'` | Must replay missed events |
| 5 | INSERT column | `event_payload` | `payload` | Hallucinated column name |
| 6 | `conn.commit()` | Missing | Add after INSERT | Changes never persisted |

---

## Canonical Resolution Path

**Step 1 — Audit (T+0 to T+5 min)**
```bash
python3 -c "import sqlite3; conn=sqlite3.connect('dirty_warehouse.db'); \
    print(conn.execute('PRAGMA table_info(raw_events)').fetchall())"
```
Identifies all table schemas. Reveals missing PK on `raw_events.event_id`.

**Step 2 — Diagnose pipeline (T+5 to T+12 min)**
Read `pipeline.py`. List each misconfigured value. Do not fix yet.

**Step 3 — Verify via execution (T+12 to T+15 min)**
```bash
python3 pipeline.py
```
Confirms broker error. Validates the candidate's diagnosis before applying fixes.

**Step 4 — Apply fixes (T+15 to T+25 min)**
Apply all 6 pipeline fixes in a single edit. Re-run to confirm consumer connects and writes.

**Step 5 — Document DB violations (T+25 to T+30 min)**
Query each table systematically. Produce a written list of all 8 violations.

**Step 6 — Chaos recovery (T+30 to T+45 min)**
After KILL_CONSUMER at T+30: add retry loop to `run_pipeline()`. Restart the consumer.
Verify it reconnects and continues consuming without manual intervention.

---

## AI-Solo Baseline (for `efficiency_ratio`)

An AI-solo run (no human orchestration) of this scenario:
- Identified 5/8 violations (missed the 3 FK nulls and the duplicate PK explanation)
- Fixed the pipeline in 14 steps over 30.8 minutes
- Did not add the retry loop before chaos; needed 6 additional steps to recover
- Total: 20 steps, 1847 seconds, pipeline running but DB violations documented incompletely

---

## Scoring Notes

| Signal | What to look for |
|--------|-----------------|
| `decomposition_score` | Does the candidate audit before fixing? Or dive straight into code? |
| `trust_calibration` | Does the candidate verify DELTA's column name claim before using it? |
| `correction_velocity` | How quickly is DELTA corrected when it says `event_payload`? |
| `chaos_resilience` | How long from KILL_CONSUMER to consumer back online? |
| `efficiency_ratio` | Steps taken vs AI-solo baseline (20 steps, 1847 sec) |
