# ADR-001: Qdrant over pgvector for Embedding Storage

**Status**: Accepted
**Date**: 2026-05-14

## Context

`orchid` requires vector storage for two distinct use cases:

1. **Session interactions** — embeddings of `PROMPT_SENT` and `CORRECTION_ISSUED` events for each candidate session (write-heavy during session, read-heavy during evaluation).
2. **Benchmark profiles** — 10+ pre-computed senior engineer session embeddings used as a reference corpus for cosine similarity comparison (`benchmark_delta`).

The two main candidates were:

- **Qdrant** — a purpose-built vector database with a native HTTP/gRPC API and Python client.
- **pgvector** — a PostgreSQL extension that adds vector column types and approximate nearest-neighbor (ANN) search operators (e.g., `<=>` for cosine distance).

We already require PostgreSQL for Airflow metadata and session state (Sprint 8 multi-tenant API). Adding pgvector to that instance was considered as a simplification.

## Decision

Use **Qdrant** as the vector store.

## Reasoning

| Criterion | Qdrant | pgvector |
|---|---|---|
| ANN indexing | HNSW (built-in, configurable) | IVFFlat or HNSW (manual `CREATE INDEX`) |
| Payload filtering | Native — filter by JSON metadata during search | Requires SQL JOIN or WHERE before vector ops |
| Operational isolation | Separate container — vector workload doesn't compete with relational ops | Shared Postgres — VACUUM, WAL, and vector indexing contend for I/O |
| Python SDK | `qdrant-client` with async support | `psycopg2`/`asyncpg` with raw SQL or `sqlalchemy-pgvector` |
| Schema evolution | Collection schema updated per sprint | `ALTER TABLE` on live data with index rebuild |
| Local dev overhead | One additional Docker service | Zero (reuses existing Postgres) |

The critical factor is **payload filtering**: when computing `benchmark_delta` or running the style classifier, we need to filter vectors by `session_id` and `event_type` simultaneously with the similarity search. Qdrant handles this in a single API call; pgvector requires a subquery or application-level pre-filtering that defeats the purpose of ANN indexing.

At 1000 concurrent candidates (Sprint 10 scale target), Qdrant's workload isolation also prevents vector HNSW index build operations from degrading the relational query latency of the multi-tenant API.

## Consequences

**Enables:**
- Sub-millisecond filtered similarity search by `session_id` + `event_type` at sprint 6 scale.
- Independent scaling of the vector workload from the relational DB.
- Native support for collection snapshots (useful for reproducible benchmark uploads).

**Forecloses:**
- Single-DB simplicity — engineers must operate two database services locally.
- Direct SQL JOINs between vector data and relational session records; application code must join by `session_id`.

**Accepted trade-off:** The operational cost of an additional Docker service is low and bounded. The performance and filtering benefits are permanent.
