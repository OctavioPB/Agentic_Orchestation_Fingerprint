'use client';
// Session list requires client-side auth cookie access + interactive table

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { decodeTenantId, getTokenFromCookie } from '@/lib/auth';
import type { Session } from '@/services/api';
import { getSessions } from '@/services/api';
import Eyebrow from '@/components/ui/Eyebrow';

const STATE_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  active: { bg: '#E0F7EF', text: '#0D5C3A', dot: '#27B97C' },
  completed: { bg: '#E0EAF4', text: '#001F4D', dot: '#003366' },
  created: { bg: '#FEF0E6', text: '#7A3800', dot: '#F07020' },
};

function StateBadge({ state }: { state: Session['state'] }) {
  const c = STATE_COLORS[state] ?? { bg: '#F4F6F9', text: '#6B7280', dot: '#6B7280' };
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        borderRadius: 20,
        padding: '3px 10px',
        backgroundColor: c.bg,
        color: c.text,
        fontFamily: 'var(--fb)',
        fontSize: 10,
        fontWeight: 500,
        letterSpacing: '1px',
        textTransform: 'uppercase',
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: c.dot }} />
      {state}
    </span>
  );
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getTokenFromCookie();
    const tenantId = token ? decodeTenantId(token) : null;
    if (!token || !tenantId) {
      setError('Not authenticated.');
      setLoading(false);
      return;
    }
    getSessions(token, tenantId)
      .then(setSessions)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : 'Failed to load sessions.'),
      )
      .finally(() => setLoading(false));
  }, []);

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
            Assessment{' '}
            <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>sessions</em>
          </h1>
          <p
            style={{
              fontFamily: 'var(--fb)',
              fontSize: 14,
              color: 'rgba(255,255,255,0.6)',
              lineHeight: 1.75,
            }}
          >
            All sessions for your tenant — click any row to view the full fingerprint.
          </p>
        </div>
      </section>

      {/* Content */}
      <section style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 48px' }}>
        <Eyebrow>Session registry</Eyebrow>

        {loading && (
          <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'var(--mid)' }}>
            Loading sessions…
          </p>
        )}

        {error && (
          <p
            role="alert"
            style={{ fontFamily: 'var(--fb)', fontSize: 14, color: '#E03448' }}
          >
            {error}
          </p>
        )}

        {!loading && !error && (
          <div style={{ overflowX: 'auto', borderRadius: 12, boxShadow: '0 1px 6px rgba(0,51,102,0.09)' }}>
            <table
              aria-label="Assessment sessions"
              style={{ width: '100%', borderCollapse: 'collapse' }}
            >
              <thead>
                <tr style={{ background: 'var(--primary)' }}>
                  {['Session ID', 'Candidate', 'Scenario', 'State', 'Started', 'Actions'].map(
                    (h) => (
                      <th
                        key={h}
                        scope="col"
                        style={{
                          padding: '12px 16px',
                          fontFamily: 'var(--fb)',
                          fontSize: 10,
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
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {sessions.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      style={{
                        padding: '32px 16px',
                        textAlign: 'center',
                        fontFamily: 'var(--fb)',
                        fontSize: 14,
                        color: 'var(--mid)',
                        background: '#fff',
                      }}
                    >
                      No sessions found for this tenant.
                    </td>
                  </tr>
                ) : (
                  sessions.map((s, idx) => (
                    <tr
                      key={s.session_id}
                      style={{
                        background: idx % 2 === 0 ? '#fff' : 'var(--primary-10)',
                        borderBottom: '1px solid var(--primary-10)',
                      }}
                    >
                      <td
                        style={{
                          padding: '12px 16px',
                          fontFamily: 'Courier New, monospace',
                          fontSize: 11,
                          color: 'var(--primary)',
                        }}
                      >
                        {s.session_id.slice(0, 8)}…
                      </td>
                      <td
                        style={{
                          padding: '12px 16px',
                          fontFamily: 'var(--fb)',
                          fontSize: 13,
                          color: '#374151',
                        }}
                      >
                        {s.candidate_id.slice(0, 8)}…
                      </td>
                      <td
                        style={{
                          padding: '12px 16px',
                          fontFamily: 'var(--fb)',
                          fontSize: 13,
                          color: '#374151',
                        }}
                      >
                        {s.scenario_id}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <StateBadge state={s.state} />
                      </td>
                      <td
                        style={{
                          padding: '12px 16px',
                          fontFamily: 'var(--fb)',
                          fontSize: 12,
                          color: 'var(--mid)',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {new Date(s.started_at).toLocaleString()}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <Link
                          href={`/sessions/${s.session_id}`}
                          style={{
                            fontFamily: 'var(--fb)',
                            fontSize: 10,
                            fontWeight: 600,
                            letterSpacing: '2px',
                            textTransform: 'uppercase',
                            color: 'var(--primary)',
                            borderBottom: '1px solid var(--primary-30)',
                            paddingBottom: 1,
                          }}
                          aria-label={`View fingerprint for session ${s.session_id}`}
                        >
                          Fingerprint →
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
