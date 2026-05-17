# orchid — Beta Onboarding Guide

> Cognitive Blueprint Platform · Beta v0.1 · Confidential

---

## What you're integrating

orchid runs a structured technical assessment where your engineering candidates solve a real operational problem alongside three AI sub-agents. You receive an **Orchestration Fingerprint** — a scored profile of how the candidate thinks, delegates, and recovers under pressure. Not code output. Leadership signal.

---

## Prerequisites

- orchid API credentials (tenant ID + API key — provided by your account contact)
- Webhook endpoint reachable from the internet (HTTPS)
- 60 minutes of uninterrupted candidate time per session

---

## Step 1 — Obtain your API key

Your account contact provides two values:

```
ORCHID_TENANT_ID=tenant-<your-company>-<6-char-hex>
ORCHID_API_KEY=orchid_<48-char-hex>
```

Exchange your API key for a JWT:

```bash
curl -X POST https://api.orchid.example.com/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "orchid_<your-key>"}'
```

Response:

```json
{ "access_token": "eyJ...", "expires_in": 604800 }
```

Store the `access_token` — all subsequent requests use it as `Authorization: Bearer <token>` plus `X-Tenant-ID: <your-tenant-id>`.

---

## Step 2 — Register a candidate

```bash
curl -X POST https://api.orchid.example.com/candidates \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "name": "Alice Chen"}'
```

Response:

```json
{
  "candidate_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "tenant_id": "tenant-apex-capital-beta",
  "email": "alice@example.com",
  "name": "Alice Chen",
  "created_at": "2024-01-15T10:00:00+00:00"
}
```

---

## Step 3 — Register a webhook

orchid POSTs the finished fingerprint to your endpoint within ~90 seconds of session completion.

```bash
curl -X POST https://api.orchid.example.com/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-ats.example.com/orchid-webhook"}'
```

Your endpoint receives a POST with this body:

```json
{
  "session_id": "...",
  "candidate_id": "...",
  "scenario_id": "corrupted-warehouse-v1",
  "scores": {
    "efficiency_ratio": 0.82,
    "trust_calibration": 0.75,
    "correction_velocity": 0.91,
    "decomposition_score": 0.68,
    "chaos_resilience": 0.54
  },
  "style_cluster": "architect",
  "reasoning_trace": ["...", "..."],
  "benchmark_delta": 0.12,
  "report_markdown": "## Assessment Report\n\n..."
}
```

Respond with HTTP 200 within 5 seconds. orchid retries 3× with exponential backoff on non-200 responses.

---

## Step 4 — Provision a session

```bash
curl -X POST https://api.orchid.example.com/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "scenario_id": "corrupted-warehouse-v1"
  }'
```

Response:

```json
{
  "session_id": "a1b2c3d4-...",
  "state": "active",
  "started_at": "2024-01-15T10:05:00+00:00"
}
```

Send the candidate the sandbox URL:

```
https://sandbox.orchid.example.com/session/<session_id>
```

The candidate works in an isolated VS Code environment with a broken database, a misconfigured Kafka pipeline, and three AI sub-agents (DELTA, NOVA, ECHO) they can consult. The session auto-terminates after 60 minutes.

---

## Step 5 — Retrieve the fingerprint

After your webhook fires (or after polling), retrieve the full fingerprint:

```bash
curl https://api.orchid.example.com/sessions/$SESSION_ID/fingerprint \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID"
```

Returns 404 until the Airflow assembly DAG completes (~90s post-session).

---

## Step 6 — View in the dashboard

Open `https://dashboard.orchid.example.com` and log in with your JWT. Navigate to **Sessions** to see all sessions for your tenant. Click any row to open the full **Cognitive Blueprint** — radar chart, efficiency gauge, interaction graph, and reasoning trace.

To compare two candidates side-by-side:

```
https://dashboard.orchid.example.com/sessions/compare?a=<session_id_A>&b=<session_id_B>
```

---

## Score interpretation

| Score | What it measures | What high means |
|---|---|---|
| **Efficiency Ratio** | Candidate time vs AI-solo baseline | Candidate added real value beyond what AI would do alone |
| **Trust Calibration** | Frequency + quality of agent corrections | Verifies output without micromanaging |
| **Correction Velocity** | Speed of catching hallucinations | Detects errors quickly; does not let them propagate |
| **Decomposition Score** | Quality of task breakdown to sub-agents | Gives agents context-rich, specific instructions |
| **Chaos Resilience** | Recovery speed after injected fault | Stays methodical under surprise system failures |

No score is pass/fail. orchid surfaces signal — your team makes the hire decision.

---

## GDPR / data deletion

To purge a candidate's data across all orchid stores (Postgres, fingerprint cache):

```bash
curl -X DELETE https://api.orchid.example.com/candidates/$CANDIDATE_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID"
```

Returns 204 on success. All sessions and fingerprints for that candidate are removed.

---

## Rate limits

- 100 requests / 60 seconds per tenant
- HTTP 429 when exceeded — retry after 60 seconds

---

## Available scenarios

```bash
curl https://api.orchid.example.com/scenarios \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID"
```

| Scenario ID | Name | Chaos component |
|---|---|---|
| `corrupted-warehouse-v1` | The Corrupted Warehouse | Kafka consumer killed at 15 min |
| `silent-pipeline-v1` | The Silent Pipeline | Schema column dropped at 20 min |

---

## Support

For integration issues or to request a sandbox demo session, contact your account contact or open an issue at the private client GitHub repository.
