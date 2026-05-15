# The Silent Pipeline — Workspace

**Scenario ID**: `scenario_silent_pipeline_v1`

## Overview

Something is wrong. The pipeline ran without errors, but no events reached the index.

- `pipeline_run.log` — output from the last pipeline run
- `producer.py` — publishes events to Kafka
- `qdrant_ingest.py` — ingests events into the Qdrant vector store
- `etl_dag.py` — Airflow DAG for the extract-transform-load pipeline
- `requirements.txt` — Python dependencies

## Your Task

1. Read `pipeline_run.log` to understand the failure signature.
2. Trace the failure through each component: producer → consumer → index → DAG.
3. Fix each root cause. Document what you found and how you diagnosed it.
4. Re-run to verify events flow end-to-end.

The pipeline should eventually show `events_indexed > 0` and the DAG should load cleanly.

**Hint**: No component raises an unhandled exception. All failures are silent.
