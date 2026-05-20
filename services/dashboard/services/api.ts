/**
 * Typed API layer for the orchid REST API.
 * All responses validated with Zod before use in components.
 * No fetch() calls allowed directly in components — always use this module.
 */
import { z } from 'zod';

const BASE = process.env.NEXT_PUBLIC_ORCHID_API_URL ?? 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Zod schemas (mirror Pydantic models in services/api/)
// ---------------------------------------------------------------------------

export const ScoresSchema = z.object({
  efficiency_ratio: z.number(),
  trust_calibration: z.number(),
  correction_velocity: z.number(),
  decomposition_score: z.number(),
  chaos_resilience: z.number(),
});
export type Scores = z.infer<typeof ScoresSchema>;

export const GraphNodeSchema = z.object({
  id: z.string(),
  label: z.string(),
  node_type: z.enum(['human', 'agent']),
  agent_name: z.string().optional(),
});
export type GraphNode = z.infer<typeof GraphNodeSchema>;

export const GraphEdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  message_count: z.number(),
  correction_count: z.number(),
  avg_latency_ms: z.number().nullable().optional(),
});
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;

export const InteractionGraphSchema = z.object({
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
});
export type InteractionGraphData = z.infer<typeof InteractionGraphSchema>;

export const FingerprintSchema = z.object({
  session_id: z.string(),
  candidate_id: z.string(),
  scenario_id: z.string(),
  scores: ScoresSchema,
  style_cluster: z.enum(['architect', 'executor', 'debugger', 'delegator']).nullable().optional(),
  reasoning_trace: z.array(z.string()).default([]),
  interaction_graph: InteractionGraphSchema,
  benchmark_delta: z.number().nullable().optional(),
  report_markdown: z.string().default(''),
  assembled_at: z.string().nullable().optional(),
});
export type Fingerprint = z.infer<typeof FingerprintSchema>;

export const SessionSchema = z.object({
  session_id: z.string(),
  candidate_id: z.string(),
  scenario_id: z.string(),
  tenant_id: z.string(),
  state: z.enum(['created', 'active', 'completed']),
  started_at: z.string(),
  ended_at: z.string().nullable().optional(),
  candidate_name: z.string().nullable().optional(),
});
export type Session = z.infer<typeof SessionSchema>;

export const ScoringSignalSchema = z.object({
  dimension: z.string(),
  signal: z.string(),
});

export const ScenarioSchema = z.object({
  scenario_id: z.string(),
  name: z.string(),
  version: z.string().default('v1'),
  difficulty: z.string().default('medium'),
  description: z.string().default(''),
  chaos_component: z.string().nullable().optional(),
  chaos_trigger_min: z.number().nullable().optional(),
  max_duration_min: z.number().nullable().optional(),
  violations_count: z.number().nullable().optional(),
  expected_resolution_steps: z.number().nullable().optional(),
  ai_solo_steps: z.number().nullable().optional(),
  ai_solo_duration_sec: z.number().nullable().optional(),
  ai_solo_violations_found: z.number().nullable().optional(),
  scoring_signals: z.array(ScoringSignalSchema).default([]),
});
export type Scenario = z.infer<typeof ScenarioSchema>;

// ---------------------------------------------------------------------------
// Request helpers
// ---------------------------------------------------------------------------

function authHeaders(token: string, tenantId: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    'X-Tenant-ID': tenantId,
    'Content-Type': 'application/json',
  };
}

async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  token: string,
  tenantId: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { ...authHeaders(token, tenantId), ...options.headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  const json = await res.json();
  return schema.parse(json);
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function getSessions(token: string, tenantId: string): Promise<Session[]> {
  return apiFetch('/sessions', z.array(SessionSchema), token, tenantId);
}

export async function getSession(
  sessionId: string,
  token: string,
  tenantId: string,
): Promise<Session> {
  return apiFetch(`/sessions/${sessionId}`, SessionSchema, token, tenantId);
}

export async function getFingerprint(
  sessionId: string,
  token: string,
  tenantId: string,
): Promise<Fingerprint> {
  return apiFetch(`/sessions/${sessionId}/fingerprint`, FingerprintSchema, token, tenantId);
}

export async function getScenarios(token: string, tenantId: string): Promise<Scenario[]> {
  return apiFetch('/scenarios', z.array(ScenarioSchema), token, tenantId);
}

// ---------------------------------------------------------------------------
// Demo auth (no authentication required)
// ---------------------------------------------------------------------------

export const DemoTokenSchema = z.object({
  token: z.string(),
  tenant_id: z.string(),
  seeded: z.boolean(),
  admin_key: z.string(),
});
export type DemoToken = z.infer<typeof DemoTokenSchema>;

export async function getDemoToken(): Promise<DemoToken> {
  const res = await fetch(`${BASE}/auth/demo-token`);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Demo token error ${res.status}: ${text}`);
  }
  return DemoTokenSchema.parse(await res.json());
}

// ---------------------------------------------------------------------------
// Admin API (X-Admin-Key auth, no tenant JWT required)
// ---------------------------------------------------------------------------

export const TenantSummarySchema = z.object({
  tenant_id: z.string(),
  session_count: z.number(),
  candidate_count: z.number(),
});
export type TenantSummary = z.infer<typeof TenantSummarySchema>;

export const SeedResponseSchema = z.object({
  tenants_created: z.number(),
  sessions_created: z.number(),
  fingerprints_created: z.number(),
  tenant_ids: z.array(z.string()),
});
export type SeedResponse = z.infer<typeof SeedResponseSchema>;

function adminHeaders(adminKey: string): HeadersInit {
  return { 'X-Admin-Key': adminKey, 'Content-Type': 'application/json' };
}

async function adminFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  adminKey: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { ...adminHeaders(adminKey), ...options.headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Admin API ${res.status}: ${text}`);
  }
  const json = await res.json();
  return schema.parse(json);
}

export async function getAdminTenants(adminKey: string): Promise<TenantSummary[]> {
  return adminFetch('/admin/tenants', z.array(TenantSummarySchema), adminKey);
}

export async function seedSyntheticData(
  adminKey: string,
  tenantCount: number,
  sessionsPerTenant: number,
): Promise<SeedResponse> {
  return adminFetch('/admin/seed', SeedResponseSchema, adminKey, {
    method: 'POST',
    body: JSON.stringify({ tenant_count: tenantCount, sessions_per_tenant: sessionsPerTenant }),
  });
}

export async function deleteAdminTenant(adminKey: string, tenantId: string): Promise<void> {
  const res = await fetch(`${BASE}/admin/tenants/${encodeURIComponent(tenantId)}`, {
    method: 'DELETE',
    headers: adminHeaders(adminKey),
  });
  if (!res.ok && res.status !== 204) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Admin API ${res.status}: ${text}`);
  }
}
