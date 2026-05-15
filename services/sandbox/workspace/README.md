# Orchid Assessment: The Corrupted Warehouse

Welcome to your technical assessment environment. You have **60 minutes**.

---

## Your Mission

A critical data pipeline has stopped ingesting events into the warehouse database.
Your engineering team has three AI sub-agents standing by in the chat panel — you lead them.

| Agent | Role | Known Weakness |
|-------|------|----------------|
| **DELTA** | Data Engineer | Occasionally hallucinates column names — verify his SQL before running it |
| **NOVA** | Pipeline Debugger | Thorough but over-cautious; may ask excessive clarifying questions |
| **ECHO** | Schema Architect | Proposes technically valid designs that are often over-engineered |

---

## The Problems

### 1. `pipeline.py` — The Kafka consumer is broken
The pipeline is meant to consume events from Kafka and write them to `dirty_warehouse.db`.
It's failing silently. No events are reaching the database.

Your task: **identify and fix all bugs** so the pipeline runs correctly.

### 2. `dirty_warehouse.db` — The warehouse has data quality violations
The database was loaded with historical data that bypassed validation.
It contains multiple integrity violations.

Your task: **identify and document all violations** in a file called `violations.md`.
You do not need to fix the data — diagnosis is sufficient.

---

## Getting Started

```bash
# Inspect the database schema
python3 -c "
import sqlite3
conn = sqlite3.connect('dirty_warehouse.db')
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
for t in tables:
    print(t[0], conn.execute(f'PRAGMA table_info({t[0]})').fetchall())
"

# Attempt to run the pipeline (it will fail — that's expected)
python3 pipeline.py
```

---

## What We Are Evaluating

We are **not** evaluating whether you can spot every bug without help.
We are evaluating **how you direct your AI team**:

- How clearly and specifically you assign tasks to each agent
- How quickly you recognize when an agent is wrong or hallucinating
- How you decompose a complex problem into parallelizable sub-tasks
- How you respond when something unexpected happens mid-session

**Good luck.**
