'use client';
// Admin console requires client-side state (admin key, data fetching)

import { useEffect, useState } from 'react';
import Eyebrow from '@/components/ui/Eyebrow';
import type { SeedResponse, TenantSummary } from '@/services/api';
import { deleteAdminTenant, getAdminTenants, seedSyntheticData } from '@/services/api';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function KpiCard({ value, label }: { value: number | string; label: string }) {
  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 12,
        boxShadow: '0 1px 4px rgba(0,51,102,0.08)',
        display: 'flex',
        alignItems: 'stretch',
        overflow: 'hidden',
      }}
    >
      <div style={{ width: 3, background: 'var(--gold)', flexShrink: 0 }} />
      <div style={{ padding: '18px 20px', flex: 1 }}>
        <div
          style={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: 32,
            fontWeight: 300,
            color: 'var(--dark)',
            lineHeight: 1,
          }}
        >
          {value}
        </div>
        <div
          style={{
            fontFamily: 'var(--fb)',
            fontSize: 10,
            letterSpacing: '2px',
            textTransform: 'uppercase',
            color: 'var(--mid)',
            marginTop: 6,
          }}
        >
          {label}
        </div>
      </div>
    </div>
  );
}

function SeedResultCard({ result }: { result: SeedResponse }) {
  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '24px 28px',
        boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
        borderLeft: '3px solid var(--gold)',
        marginTop: 20,
      }}
    >
      <Eyebrow>Seed complete</Eyebrow>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 16,
          marginTop: 12,
          marginBottom: 16,
        }}
      >
        <KpiCard value={result.tenants_created} label="Tenants created" />
        <KpiCard value={result.sessions_created} label="Sessions created" />
        <KpiCard value={result.fingerprints_created} label="Fingerprints created" />
      </div>
      <div>
        <div
          style={{
            fontFamily: 'var(--fb)',
            fontSize: 10,
            letterSpacing: '2px',
            textTransform: 'uppercase',
            color: 'var(--mid)',
            marginBottom: 8,
          }}
        >
          Tenant IDs
        </div>
        {result.tenant_ids.map((id) => (
          <div
            key={id}
            style={{
              fontFamily: 'Courier New, monospace',
              fontSize: 11,
              color: 'var(--primary)',
              marginBottom: 4,
            }}
          >
            {id}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AdminPage() {
  const [adminKey, setAdminKey] = useState('');
  const [inputKey, setInputKey] = useState('');
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Seed form state
  const [tenantCount, setTenantCount] = useState(3);
  const [sessionsPerTenant, setSessionsPerTenant] = useState(2);
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState<SeedResponse | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);

  // Delete state
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function fetchTenants(key: string) {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getAdminTenants(key);
      setTenants(data);
      setAdminKey(key);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Access denied or API unavailable.');
      setAdminKey('');
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    await fetchTenants(inputKey);
  }

  async function handleSeed(e: React.FormEvent) {
    e.preventDefault();
    setSeeding(true);
    setSeedResult(null);
    setSeedError(null);
    try {
      const result = await seedSyntheticData(adminKey, tenantCount, sessionsPerTenant);
      setSeedResult(result);
      await fetchTenants(adminKey);
    } catch (err) {
      setSeedError(err instanceof Error ? err.message : 'Seed failed.');
    } finally {
      setSeeding(false);
    }
  }

  async function handleDelete(tenantId: string) {
    if (!confirm(`Permanently delete all data for tenant "${tenantId}"?`)) return;
    setDeletingId(tenantId);
    try {
      await deleteAdminTenant(adminKey, tenantId);
      setTenants((prev) => prev.filter((t) => t.tenant_id !== tenantId));
      setSeedResult(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setDeletingId(null);
    }
  }

  const totalSessions = tenants.reduce((s, t) => s + t.session_count, 0);
  const totalCandidates = tenants.reduce((s, t) => s + t.candidate_count, 0);

  // ── Key gate ───────────────────────────────────────────────────────────────
  if (!adminKey) {
    return (
      <>
        {/* Hero */}
        <section
          style={{
            background: 'var(--primary)',
            backgroundImage: `
              linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px)`,
            backgroundSize: '48px 48px',
            padding: '56px 48px',
          }}
        >
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <h1
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontSize: 32,
                fontWeight: 400,
                color: '#fff',
                lineHeight: 1.2,
                marginBottom: 8,
              }}
            >
              Admin{' '}
              <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>console</em>
            </h1>
            <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'rgba(255,255,255,0.6)' }}>
              Internal use only — requires admin key.
            </p>
          </div>
        </section>

        {/* Key gate */}
        <section style={{ maxWidth: 480, margin: '64px auto', padding: '0 48px' }}>
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: '36px',
              boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
              borderTop: '3px solid var(--gold)',
            }}
          >
            <Eyebrow>Authentication</Eyebrow>
            <h2
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontSize: 20,
                fontWeight: 400,
                color: '#0a1628',
                marginBottom: 20,
              }}
            >
              Enter admin key
            </h2>
            <form onSubmit={handleConnect}>
              <input
                type="password"
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                placeholder="ADMIN_SECRET_KEY"
                aria-label="Admin secret key"
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '10px 14px',
                  fontFamily: 'Courier New, monospace',
                  fontSize: 13,
                  border: '1px solid var(--primary-30)',
                  borderRadius: 8,
                  outline: 'none',
                  marginBottom: 16,
                  color: '#0a1628',
                }}
              />
              {loadError && (
                <p
                  style={{
                    fontFamily: 'var(--fb)',
                    fontSize: 12,
                    color: '#E03448',
                    marginBottom: 12,
                  }}
                >
                  {loadError}
                </p>
              )}
              <button
                type="submit"
                disabled={loading || !inputKey}
                style={{
                  width: '100%',
                  padding: '10px 0',
                  background: loading || !inputKey ? 'var(--primary-30)' : 'var(--primary)',
                  border: 'none',
                  borderRadius: 8,
                  color: '#fff',
                  fontFamily: 'var(--fb)',
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: '2px',
                  textTransform: 'uppercase',
                  cursor: loading || !inputKey ? 'not-allowed' : 'pointer',
                }}
              >
                {loading ? 'Connecting…' : 'Connect →'}
              </button>
            </form>
          </div>
        </section>
      </>
    );
  }

  // ── Dashboard (authenticated) ──────────────────────────────────────────────
  return (
    <>
      {/* Hero */}
      <section
        style={{
          background: 'var(--primary)',
          backgroundImage: `
            linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px)`,
          backgroundSize: '48px 48px',
          padding: '56px 48px',
        }}
      >
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <h1
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 32,
              fontWeight: 400,
              color: '#fff',
              lineHeight: 1.2,
              marginBottom: 8,
            }}
          >
            Admin{' '}
            <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>console</em>
          </h1>
          <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'rgba(255,255,255,0.6)' }}>
            Synthetic data generation · Tenant management · Cost observability
          </p>
        </div>
      </section>

      {/* KPI row */}
      <section style={{ maxWidth: 1200, margin: '0 auto', padding: '40px 48px 0' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 16,
          }}
        >
          <KpiCard value={tenants.length} label="Active tenants" />
          <KpiCard value={totalSessions} label="Total sessions" />
          <KpiCard value={totalCandidates} label="Total candidates" />
        </div>
      </section>

      <section style={{ maxWidth: 1200, margin: '0 auto', padding: '40px 48px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, alignItems: 'start' }}>

          {/* Generate synthetic data */}
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: '28px',
              boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
            }}
          >
            <Eyebrow>Synthetic data</Eyebrow>
            <h3
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 16,
                fontWeight: 600,
                color: '#0a1628',
                marginBottom: 20,
              }}
            >
              Generate beta fixtures
            </h3>
            <p
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 13,
                color: 'var(--mid)',
                lineHeight: 1.65,
                marginBottom: 20,
              }}
            >
              Creates synthetic enterprise tenants with realistic Faker-generated candidate
              profiles, completed sessions, and assembled fingerprints. Safe to run
              multiple times — each call produces new UUIDs.
            </p>
            <form onSubmit={handleSeed}>
              <label
                style={{
                  display: 'block',
                  fontFamily: 'var(--fb)',
                  fontSize: 10,
                  letterSpacing: '2px',
                  textTransform: 'uppercase',
                  color: 'var(--mid)',
                  marginBottom: 6,
                }}
              >
                Tenants
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={tenantCount}
                onChange={(e) => setTenantCount(Number(e.target.value))}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '8px 12px',
                  fontFamily: 'var(--fb)',
                  fontSize: 13,
                  border: '1px solid var(--primary-30)',
                  borderRadius: 8,
                  marginBottom: 14,
                  color: '#0a1628',
                }}
              />
              <label
                style={{
                  display: 'block',
                  fontFamily: 'var(--fb)',
                  fontSize: 10,
                  letterSpacing: '2px',
                  textTransform: 'uppercase',
                  color: 'var(--mid)',
                  marginBottom: 6,
                }}
              >
                Sessions per tenant
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={sessionsPerTenant}
                onChange={(e) => setSessionsPerTenant(Number(e.target.value))}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '8px 12px',
                  fontFamily: 'var(--fb)',
                  fontSize: 13,
                  border: '1px solid var(--primary-30)',
                  borderRadius: 8,
                  marginBottom: 20,
                  color: '#0a1628',
                }}
              />
              {seedError && (
                <p style={{ fontFamily: 'var(--fb)', fontSize: 12, color: '#E03448', marginBottom: 12 }}>
                  {seedError}
                </p>
              )}
              <button
                type="submit"
                disabled={seeding}
                style={{
                  width: '100%',
                  padding: '10px 0',
                  background: seeding ? 'var(--primary-30)' : 'var(--primary)',
                  border: 'none',
                  borderRadius: 8,
                  color: '#fff',
                  fontFamily: 'var(--fb)',
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: '2px',
                  textTransform: 'uppercase',
                  cursor: seeding ? 'not-allowed' : 'pointer',
                }}
              >
                {seeding ? 'Generating…' : `Generate ${tenantCount * sessionsPerTenant} sessions →`}
              </button>
            </form>
            {seedResult && <SeedResultCard result={seedResult} />}
          </div>

          {/* Tenant registry */}
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: '28px',
              boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
            }}
          >
            <Eyebrow>Tenant registry</Eyebrow>
            <h3
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 16,
                fontWeight: 600,
                color: '#0a1628',
                marginBottom: 20,
              }}
            >
              Active tenants
            </h3>

            {loading ? (
              <p style={{ fontFamily: 'var(--fb)', fontSize: 13, color: 'var(--mid)' }}>
                Loading…
              </p>
            ) : tenants.length === 0 ? (
              <p style={{ fontFamily: 'var(--fb)', fontSize: 13, color: 'var(--mid)' }}>
                No tenants found. Generate synthetic data to populate the registry.
              </p>
            ) : (
              <div style={{ overflowX: 'auto', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,51,102,0.08)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--primary)' }}>
                      {['Tenant ID', 'Sessions', 'Candidates', ''].map((h) => (
                        <th
                          key={h}
                          style={{
                            padding: '10px 12px',
                            fontFamily: 'var(--fb)',
                            fontSize: 9,
                            fontWeight: 500,
                            letterSpacing: '2px',
                            textTransform: 'uppercase',
                            color: 'rgba(255,255,255,0.85)',
                            textAlign: 'left',
                            whiteSpace: 'nowrap',
                            borderBottom: '1px solid var(--primary-10)',
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tenants.map((t, idx) => (
                      <tr
                        key={t.tenant_id}
                        style={{
                          background: idx % 2 === 0 ? '#fff' : 'var(--primary-10)',
                          borderBottom: '1px solid var(--primary-10)',
                        }}
                      >
                        <td
                          style={{
                            padding: '10px 12px',
                            fontFamily: 'Courier New, monospace',
                            fontSize: 10,
                            color: 'var(--primary)',
                            maxWidth: 200,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                          title={t.tenant_id}
                        >
                          {t.tenant_id}
                        </td>
                        <td
                          style={{
                            padding: '10px 12px',
                            fontFamily: 'var(--fb)',
                            fontSize: 13,
                            color: '#374151',
                            textAlign: 'center',
                          }}
                        >
                          {t.session_count}
                        </td>
                        <td
                          style={{
                            padding: '10px 12px',
                            fontFamily: 'var(--fb)',
                            fontSize: 13,
                            color: '#374151',
                            textAlign: 'center',
                          }}
                        >
                          {t.candidate_count}
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <button
                            onClick={() => handleDelete(t.tenant_id)}
                            disabled={deletingId === t.tenant_id}
                            aria-label={`Delete all data for tenant ${t.tenant_id}`}
                            style={{
                              background: 'none',
                              border: '1px solid #E03448',
                              borderRadius: 6,
                              color: '#E03448',
                              cursor: deletingId === t.tenant_id ? 'not-allowed' : 'pointer',
                              fontFamily: 'var(--fb)',
                              fontSize: 9,
                              letterSpacing: '1.5px',
                              textTransform: 'uppercase',
                              padding: '4px 8px',
                              opacity: deletingId === t.tenant_id ? 0.5 : 1,
                            }}
                          >
                            {deletingId === t.tenant_id ? '…' : 'Delete'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </section>
    </>
  );
}
