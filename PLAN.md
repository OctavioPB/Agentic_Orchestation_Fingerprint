# PLAN.md — Sprint Roadmap
## Project: Agentic Orchestration Fingerprinting (`orchid`)

> 10 sprints · 20 weeks · Target: 3 paying enterprise clients at beta launch
> Each sprint is 2 weeks. Definition of Done (DoD) is listed per sprint.
> UI decisions are tracked separately in [`BRAND.md`](./BRAND.md).

---

## Milestone Map

```
Sprint 1-2  ──▶  Infrastructure & Sandbox Foundation
Sprint 3-4  ──▶  Telemetry Pipeline (Kafka)
Sprint 5-6  ──▶  Scenario Engine & Chaos Orchestration (Airflow)
Sprint 7    ──▶  Shadow Agent & Embedding Evaluator
Sprint 8    ──▶  Orchestration Fingerprint & Multi-Tenant API
Sprint 9    ──▶  Cognitive Blueprint Dashboard
Sprint 10   ──▶  Beta Hardening & First Paying Customers
```

---

## Sprint 1 — Infrastructure Bootstrap & Sandbox Environment
**Duration**: Weeks 1–2
**Theme**: Zero-to-running. Every engineer can spin up the full stack locally in under 10 minutes.

### Goals
- Monorepo initialized, CI pipeline green, all services runnable via Docker Compose
- Candidate sandbox (code-server) boots and is accessible via browser

### Tasks
- [ ] Initialize monorepo structure per `CLAUDE.md §2`
- [ ] Create root `docker-compose.yml` with: Kafka, Zookeeper, Schema Registry, Qdrant, Neo4j, Airflow (webserver + scheduler), code-server
- [ ] Write `Makefile` targets: `make up`, `make down`, `make logs`, `make test`
- [ ] Configure GitHub Actions CI: lint (`ruff`, `tsc`), unit tests, Docker build check
- [ ] Scaffold `services/sandbox/`: Dockerfile extending `codercom/code-server` with Python 3.11, pre-installed deps, and a seeded workspace
- [ ] Sandbox workspace includes: a broken `pipeline.py`, a dirty SQLite DB (`dirty_warehouse.db`), a `README.md` that introduces the scenario to the candidate
- [ ] Write `ADR-001` through `ADR-004`
- [ ] Set up `.env.example` with all variables from `CLAUDE.md §6`
- [ ] Create `data/synthetic/` with 2 fully-formed synthetic session JSON fixtures

### Definition of Done
- `make up` starts all services with no manual intervention
- Sandbox accessible at `localhost:8080` with scenario workspace loaded
- CI passes on `main` branch
- All ADRs written and merged

---

## Sprint 2 — Kafka Telemetry Bus & Event Schema
**Duration**: Weeks 3–4
**Theme**: Every candidate action becomes a structured, queryable event.

### Goals
- Kafka topics created and schema-registered
- Sandbox emits real telemetry events on every meaningful action

### Tasks
- [ ] Define Avro schemas for all 8 event types from `CLAUDE.md §4.1` in `docs/schema/`
- [ ] Register schemas with Schema Registry; enforce compatibility mode `BACKWARD`
- [ ] Create Kafka topics: `orchid.sandbox.prompt_sent`, `orchid.sandbox.agent_response`, `orchid.sandbox.correction_issued`, `orchid.sandbox.code_executed`, `orchid.sandbox.chaos_injected`, `orchid.sandbox.scenario_started`, `orchid.sandbox.scenario_ended`, `orchid.sandbox.focus_shift`
- [ ] Build `services/telemetry/producer.py`: async Kafka producer with schema validation, retry logic (3 attempts, exponential backoff), and structured logging of every emit
- [ ] Integrate producer into sandbox: instrument the code-server extension to capture keystrokes-to-prompt, terminal executions, and sub-agent API calls
- [ ] Build `services/telemetry/consumer.py`: base consumer class with auto-offset-commit disabled (manual ack), dead-letter topic (`orchid.dlq`) for malformed events
- [ ] Write integration tests using `testcontainers` for Kafka: produce 50 events, assert all consumed in order with correct schemas
- [ ] Build a local CLI tool `tools/session_replay.py` that replays a synthetic fixture into Kafka for dev testing

### Definition of Done
- All 8 topics exist, schemas registered
- Sandbox emits valid events; consumer reads them with zero DLQ entries on happy path
- Integration test suite passes
- Session replay tool works end-to-end with both synthetic fixtures

---

## Sprint 3 — Sub-Agent Infrastructure & Session Lifecycle
**Duration**: Weeks 5–6
**Theme**: The candidate's team is alive. DELTA, NOVA, and ECHO respond to instructions.

### Goals
- Three sub-agents (GPT-4o) running with stable personas
- A candidate can start a session, interact with agents, and have all interactions logged

### Tasks
- [ ] Write system prompts for DELTA, NOVA, and ECHO per `CLAUDE.md §4.5`; version them as `data/scenarios/agents/v1/{delta,nova,echo}_system.md`
- [ ] Build `services/evaluator/agents/sub_agent.py`: `SubAgent` class wrapping the `LLMClient` abstraction, injecting persona system prompt, logging every call (latency_ms, token_count, model_version)
- [ ] Expose sub-agents via internal WebSocket endpoint (`/ws/session/{session_id}/agent/{agent_name}`) — the sandbox terminal connects here
- [ ] Build `services/api/sessions.py`: `POST /sessions` (creates session, emits `SCENARIO_STARTED`), `DELETE /sessions/{id}` (ends session, emits `SCENARIO_ENDED`), `GET /sessions/{id}/events` (paginated event stream)
- [ ] Session state machine: `CREATED → ACTIVE → CHAOS → RESOLVING → COMPLETED`
- [ ] Persist session metadata to Postgres (`session_id`, `candidate_id`, `scenario_id`, `state`, `started_at`, `ended_at`)
- [ ] Add `SANDBOX_MAX_DURATION_SEC` enforced timeout: session auto-terminates and emits `SCENARIO_ENDED` at timeout
- [ ] Update synthetic fixtures to include sub-agent exchange payloads
- [ ] Unit tests: session state transitions, SubAgent prompt construction, timeout logic

### Definition of Done
- Candidate can open sandbox, send a message to DELTA, and receive a persona-consistent response
- Session events flow into Kafka in correct order
- All state transitions tested with >90% coverage
- Synthetic fixtures updated and replay tool works with agent exchanges

---

## Sprint 4 — Scenario Engine & Dirty Data Seeds
**Duration**: Weeks 7–8
**Theme**: The problem the candidate must solve is real, messy, and deliberately broken.

### Goals
- Two complete scenarios with dirty DB seeds, broken pipeline configs, and defined resolution paths
- Airflow can provision and tear down a scenario environment on demand

### Tasks
- [ ] Design Scenario v1: `"The Corrupted Warehouse"` — dirty SQLite DB (8 schema violations, 3 FK nulls, duplicate primary keys), broken Kafka consumer (wrong group ID, topic typo), resolution path documented in `data/scenarios/v1/scenario_corrupted_warehouse.md`
- [ ] Design Scenario v2: `"The Silent Pipeline"` — Kafka producer sending to wrong topic, Qdrant collection missing required payload field, Airflow DAG with a broken task dependency, resolution path documented
- [ ] Build Airflow DAG `orchid_scenario_provision`: pulls scenario config, spins up Docker container with dirty DB + broken pipeline, registers session in API, emits `SCENARIO_STARTED` to Kafka
- [ ] Build Airflow DAG `orchid_scenario_teardown`: stops container, archives logs to S3/local, updates session state to `COMPLETED`
- [ ] Create `data/scenarios/agents/baseline/` — pre-run results of an "AI-solo" run of each scenario (used for `efficiency_ratio` computation)
- [ ] Write seed scripts `data/scenarios/v1/seeds/` for each scenario's dirty DB and broken configs
- [ ] Update sandbox Dockerfile to mount the correct scenario seed on session start
- [ ] Integration test: provision Scenario v1, assert session is `ACTIVE`, teardown, assert session is `COMPLETED`

### Definition of Done
- Both scenarios fully documented with resolution paths and AI-solo baselines
- Airflow can provision and teardown each scenario idempotently
- Sandbox mounts the correct broken environment on session start
- Integration test suite covers full provision → interact → teardown lifecycle

---

## Sprint 5 — Chaos Injection Engine
**Duration**: Weeks 9–10
**Theme**: Midway through the test, something breaks. How does the candidate respond?

### Goals
- Airflow injects a fault at a configurable time during the session
- Fault is logged as a `CHAOS_INJECTED` event before it lands
- Three chaos modes supported

### Tasks
- [ ] Define `ChaosConfig` schema: `{ "type": str, "trigger_at_sec": int, "target": str, "params": dict }`
- [ ] Implement three chaos types: `KILL_CONSUMER` (stops Kafka consumer process), `CORRUPT_SCHEMA` (drops a column from the live DB), `FLOOD_TOPIC` (publishes 500 malformed events to `orchid.sandbox.prompt_sent`)
- [ ] Build Airflow DAG `orchid_chaos_inject`: reads `ChaosConfig` from scenario definition, waits `trigger_at_sec` seconds after `SCENARIO_STARTED`, emits `CHAOS_INJECTED` event to Kafka, executes fault via Docker exec into the sandbox container
- [ ] Chaos injection is per-scenario configurable (not global) — Scenario v1 uses `KILL_CONSUMER` at 15 min, Scenario v2 uses `CORRUPT_SCHEMA` at 20 min
- [ ] Add `chaos_resilience` score scaffold to `OrchestraFingerprint` (scoring logic in Sprint 7)
- [ ] Add chaos event display to sandbox UI — a red banner appears when chaos is injected (see BRAND.md for styling)
- [ ] Unit tests: ChaosConfig validation, DAG trigger timing, event emit before fault execution
- [ ] Update synthetic fixtures with `CHAOS_INJECTED` events and post-chaos interaction sequences

### Definition of Done
- Chaos injects at the configured time, Kafka event emitted before fault lands (verified via timestamp comparison)
- All three chaos types execute without crashing the session container
- Synthetic fixtures include chaos sequences
- CI passes including chaos unit tests

---

## Sprint 6 — Vector ETL & Embedding Pipeline
**Duration**: Weeks 11–12
**Theme**: Candidate interactions become vectors. Comparison against senior engineer profiles becomes possible.

### Goals
- All `PROMPT_SENT` and `CORRECTION_ISSUED` events are embedded and stored in Qdrant
- Senior Engineer benchmark profiles loaded and queryable

### Tasks
- [ ] Build Airflow DAG `orchid_embedding_etl`: triggered on `SCENARIO_ENDED`, consumes all `PROMPT_SENT` and `CORRECTION_ISSUED` events for the session from Kafka, calls OpenAI `text-embedding-3-large`, upserts vectors to Qdrant collection `orchid_interactions`
- [ ] Qdrant collection schema: `{ session_id, event_id, event_type, text, embedding, timestamp }`
- [ ] Create `data/benchmarks/senior_engineer_profiles/`: 10 synthetic senior engineer sessions embedded and pre-loaded into Qdrant collection `orchid_benchmarks`
- [ ] Build `services/evaluator/embeddings.py`: `compute_benchmark_delta(session_id)` — cosine similarity between session centroid and benchmark collection centroid
- [ ] Build `services/evaluator/style_classifier.py`: K-nearest neighbors against benchmark profiles to assign style cluster (`architect`, `executor`, `debugger`, `delegator`)
- [ ] Instrument all OpenAI embedding calls: log `latency_ms`, `token_count`, `model_version` per `CLAUDE.md §7.7`
- [ ] Integration test: run embedding ETL on a synthetic fixture, assert Qdrant upsert, assert `benchmark_delta` is a float in [0, 1]

### Definition of Done
- ETL DAG runs end-to-end on both synthetic fixtures
- Qdrant collections `orchid_interactions` and `orchid_benchmarks` populated correctly
- `benchmark_delta` and `style_cluster` produce deterministic results on synthetic data
- All embedding calls instrumented

---

## Sprint 7 — Shadow Agent & Orchestration Fingerprint Assembly
**Duration**: Weeks 13–14
**Theme**: The evaluator watches, scores, and writes the narrative.

### Goals
- Shadow Agent analyzes session transcript and produces reasoning trace + style narrative
- All five scores computed; full `OrchestraFingerprint` assembled

### Tasks
- [ ] Build `services/evaluator/shadow_agent.py`: `ShadowAgent` class — receives structured transcript (prompt + correction events only, **no agent responses**), calls Claude with a detailed evaluation system prompt, returns `{ prompt_scores: list, reasoning_trace: list[str], style_narrative: str }`
- [ ] Write Shadow Agent system prompt: instructs Claude to score each prompt on clarity (0-10), specificity (0-10), and context-richness (0-10); reconstruct candidate's thought process; classify style cluster; never comment on code correctness
- [ ] Implement all five scoring functions in `services/evaluator/scoring.py`:
  - `efficiency_ratio`: (candidate session solve time) / (AI-solo baseline time) normalized to [0, 1]
  - `trust_calibration`: correction rate weighted by severity of agent error being corrected
  - `correction_velocity`: median time-to-correction after a detectable hallucination event
  - `decomposition_score`: mean Shadow Agent prompt quality score
  - `chaos_resilience`: time-to-recovery after `CHAOS_INJECTED` vs. scenario median
- [ ] Build `services/evaluator/fingerprint.py`: `assemble_fingerprint(session_id)` — orchestrates embedding ETL (if not run), style classifier, Shadow Agent, all five scorers → produces `OrchestraFingerprint`
- [ ] Generate `report_markdown` via a second Claude call: narrative summary of fingerprint for human hiring reviewers
- [ ] Build Airflow DAG `orchid_fingerprint_assembly`: triggered after `orchid_embedding_etl` completes, runs `assemble_fingerprint`, persists result to Postgres + Neo4j
- [ ] Neo4j schema: `(Candidate)-[:INTERACTED_WITH {count, avg_latency_ms}]->(Agent)`, `(Session)-[:PRODUCED]->(Fingerprint)`, `(Candidate)-[:BENCHMARKS_AGAINST]->(SeniorProfile)`
- [ ] Persist interaction graph to Neo4j at fingerprint assembly time
- [ ] Unit tests: each scorer on synthetic fixtures with known expected outputs; Shadow Agent prompt construction

### Definition of Done
- `assemble_fingerprint` runs end-to-end on both synthetic fixtures without errors
- All five scores produce values in their expected ranges
- `report_markdown` is coherent and references actual session data
- Neo4j graph populated with correct nodes and relationships
- Airflow DAG `orchid_fingerprint_assembly` completes successfully in integration test

---

## Sprint 8 — Multi-Tenant API & Hiring Platform Integration
**Duration**: Weeks 15–16
**Theme**: Enterprise hiring teams can integrate `orchid` into their existing workflows via API.

### Goals
- REST API with JWT auth, tenant isolation, and webhook delivery of fingerprint results
- Postman collection + OpenAPI spec published

### Tasks
- [ ] Build `services/api/` with FastAPI: JWT authentication (`python-jose`), tenant isolation via `X-Tenant-ID` header, rate limiting (100 req/min per tenant)
- [ ] Endpoints:
  - `POST /candidates` — register a candidate for assessment
  - `POST /sessions` — provision a new session (triggers `orchid_scenario_provision` DAG)
  - `GET /sessions/{id}` — session status + state
  - `GET /sessions/{id}/fingerprint` — returns `OrchestraFingerprint` (404 if not yet assembled)
  - `POST /webhooks` — register a webhook URL for fingerprint delivery
  - `GET /scenarios` — list available scenarios
- [ ] Webhook delivery: on fingerprint assembly, POST `OrchestraFingerprint` JSON to registered URL; retry 3x with exponential backoff; log delivery status
- [ ] Tenant data isolation: each tenant's candidates, sessions, and fingerprints are row-level isolated in Postgres via `tenant_id` foreign key
- [ ] Generate OpenAPI spec via FastAPI's `/docs` and `/openapi.json`; export to `docs/api/openapi.yaml`
- [ ] Write Postman collection covering all endpoints with example requests/responses
- [ ] Security: API keys hashed (bcrypt) in DB; no plaintext secrets stored
- [ ] Load test: 50 concurrent session creation requests, assert p99 < 2s

### Definition of Done
- All 6 endpoints functional with auth enforced
- Webhook delivers fingerprint within 30s of assembly completing
- OpenAPI spec exported and accurate
- Load test passes
- Tenant isolation verified: Tenant A cannot access Tenant B's data

---

## Sprint 9 — Cognitive Blueprint Dashboard
**Duration**: Weeks 17–18
**Theme**: The fingerprint becomes a visual story that a CMO or Head of Engineering can read in 60 seconds.

> All design decisions (colors, typography, component library, motion, dark/light mode) are defined in [`BRAND.md`](./BRAND.md). This sprint implements what BRAND.md specifies.

### Goals
- Dashboard renders all components of the `OrchestraFingerprint` visually
- Hiring manager can compare two candidates side-by-side

### Tasks
- [ ] Scaffold `services/dashboard/` as Next.js 14 App Router project
- [ ] Implement design tokens, typography, and component primitives per `BRAND.md`
- [ ] Build `InteractionGraph` component: D3-force directed graph, nodes = Human + 3 Agents, edge weight = message count, edge color = correction rate (see BRAND.md for palette)
- [ ] Build `ScoreRadar` component: radar/spider chart of the 5 scores, benchmark overlay shown as a second polygon
- [ ] Build `ReasoningTrace` component: timeline visualization of the candidate's reconstructed thought tree from Shadow Agent output
- [ ] Build `StyleClusterBadge` component: visual classification (Architect / Executor / Debugger / Delegator) with description
- [ ] Build `EfficiencyRatioGauge` component: gauge chart comparing candidate to AI-solo baseline
- [ ] Build `CandidateCompare` page: two `OrchestraFingerprint` objects rendered side-by-side
- [ ] Build `SessionList` page: table of sessions per tenant with status, scores summary, date
- [ ] API integration: use `services/` layer + `zod` validation for all fingerprint data fetching
- [ ] Implement auth: Tenant JWT from `services/api` used to gate dashboard access
- [ ] Responsive layout per BRAND.md breakpoint specifications
- [ ] Accessibility: all charts have aria-labels and keyboard navigation

### Definition of Done
- All 5 chart/visualization components render correctly with synthetic fixture data
- CandidateCompare page loads two fingerprints without layout breakage
- Auth gate works: unauthenticated users redirected to login
- All components meet BRAND.md specifications (visual review sign-off required)
- Lighthouse score ≥ 85 on Performance, Accessibility, Best Practices

---

## Sprint 10 — Beta Hardening, Observability & First Paying Customers
**Duration**: Weeks 19–20
**Theme**: Production-ready. Three enterprise clients onboarded. The system does not fall over.

### Goals
- 3 paying enterprise clients onboarded with real candidate assessments run
- Observability stack live; cost per session tracked
- SLA: 99.5% session completion rate, p99 API latency < 1.5s

### Tasks

**Observability**
- [ ] Add OpenTelemetry instrumentation to `services/evaluator` and `services/api`
- [ ] Deploy Grafana + Prometheus: dashboards for Kafka consumer lag, Airflow DAG success rate, API latency, Qdrant query latency, LLM call cost per session
- [ ] LLM cost tracking: aggregate `token_count` × price per token per session; expose as `GET /sessions/{id}/cost` endpoint (internal only)
- [ ] Alert rules: Kafka consumer lag > 1000, DAG failure rate > 5%, API error rate > 2%

**Performance & Cost**
- [ ] Profile and optimize `assemble_fingerprint`: target < 90s end-to-end from `SCENARIO_ENDED` to fingerprint available
- [ ] Batch OpenAI embedding calls: group events into batches of 50 to reduce API round trips
- [ ] Add Redis caching for `GET /sessions/{id}/fingerprint` (TTL: 1 hour)
- [ ] Load test full session lifecycle: 20 concurrent sessions, assert zero `SCENARIO_ENDED` events missed

**Security & Compliance**
- [ ] GDPR: implement `DELETE /candidates/{id}` that purges all PII from Postgres, Kafka (tombstone), Qdrant, and Neo4j
- [ ] Data retention: sessions auto-purge after 90 days via Airflow `orchid_data_retention` DAG
- [ ] Penetration test checklist: SQL injection, JWT tampering, tenant isolation bypass

**Beta Onboarding**
- [ ] Onboarding documentation: `docs/onboarding/README.md` covering API key setup, webhook configuration, first session walkthrough
- [ ] Client 1 onboarded: first real assessment session run, fingerprint delivered via webhook
- [ ] Client 2 onboarded: CandidateCompare page used for side-by-side evaluation
- [ ] Client 3 onboarded: post-session feedback collected, top 3 product gaps logged as GitHub issues
- [ ] Retrospective: document lessons learned in `docs/adr/ADR-005-beta-lessons.md`

### Definition of Done
- Grafana dashboards live with no critical alerts firing
- 3 paying clients have run at least 1 real session each
- LLM cost per session ≤ $0.80 (tracked, not estimated)
- `DELETE /candidates/{id}` purge verified across all data stores
- Lighthouse score maintained ≥ 85 after performance optimizations
- No open P0/P1 bugs at sprint close

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OpenAI API cost overrun (embeddings + sub-agents) | High | High | Batch embedding calls; cache fingerprints; set hard `max_tokens` on sub-agents |
| Sandbox container isolation failure (candidate escapes env) | Medium | High | Run code-server in rootless Docker; network-isolated; no host mounts |
| Shadow Agent hallucinating scores | Medium | High | Cross-validate with deterministic scorers; flag if Shadow Agent score diverges >30% from rule-based scores |
| Kafka consumer lag under concurrent sessions | Medium | Medium | Partition by `session_id`; autoscale consumers via KEDA |
| Candidate data breach (PII in telemetry events) | Low | Critical | PII scrubber on Kafka consumer before persistence; no names in event payloads |
| "Assessment theater" perception risk | Medium | High | Dashboard always shows methodology explanation; scores are advisory, not decisive |
