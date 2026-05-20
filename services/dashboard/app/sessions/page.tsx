'use client';
// Session list requires client-side auth cookie access + interactive table

import Link from 'next/link';
import { useRouter } from 'next/navigation';
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
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string[]>([]);

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

  function toggleSelect(sessionId: string) {
    setSelected((prev) => {
      if (prev.includes(sessionId)) return prev.filter((id) => id !== sessionId);
      if (prev.length >= 2) return prev; // cap at 2
      return [...prev, sessionId];
    });
  }

  function handleCompare() {
    if (selected.length !== 2) return;
    const [a, b] = selected;
    const sA = sessions.find((s) => s.session_id === a);
    const sB = sessions.find((s) => s.session_id === b);
    const params = new URLSearchParams({ a, b });
    if (sA?.candidate_name) params.set('nameA', sA.candidate_name);
    if (sB?.candidate_name) params.set('nameB', sB.candidate_name);
    router.push(`/sessions/compare?${params.toString()}`);
  }

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
            All sessions for your tenant — view fingerprints or select two candidates to compare.
          </p>
        </div>
      </section>

      {/* Compare CTA bar — visible when 1 or 2 sessions are checked */}
      {selected.length > 0 && (
        <div
          style={{
            position: 'sticky',
            top: 52,
            zIndex: 50,
            background: 'var(--dark)',
            borderBottom: '2px solid var(--gold)',
            padding: '12px 48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          <p
            style={{
              fontFamily: 'var(--fb)',
              fontSize: 13,
              color: 'rgba(255,255,255,0.75)',
            }}
          >
            {selected.length === 1
              ? 'Select one more candidate to compare.'
              : `${selected.length} candidates selected.`}
          </p>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              onClick={() => setSelected([])}
              style={{
                background: 'none',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 6,
                color: 'rgba(255,255,255,0.5)',
                cursor: 'pointer',
                fontFamily: 'var(--fb)',
                fontSize: 9,
                letterSpacing: '2px',
                textTransform: 'uppercase',
                padding: '5px 10px',
              }}
            >
              Clear
            </button>
            <button
              onClick={handleCompare}
              disabled={selected.length !== 2}
              style={{
                background: selected.length === 2 ? 'var(--gold)' : 'rgba(200,152,42,0.35)',
                border: 'none',
                borderRadius: 6,
                color: selected.length === 2 ? '#1C1C2E' : 'rgba(255,255,255,0.4)',
                cursor: selected.length === 2 ? 'pointer' : 'not-allowed',
                fontFamily: 'var(--fb)',
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: '2px',
                textTransform: 'uppercase',
                padding: '7px 16px',
                transition: 'background 0.15s',
              }}
            >
              Compare →
            </button>
          </div>
        </div>
      )}

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
                  {['', 'Candidate', 'Session', 'Scenario', 'State', 'Started', 'Actions'].map(
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
                          textAlign: h === '' ? 'center' : 'left',
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
                      colSpan={7}
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
                  sessions.map((s, idx) => {
                    const isSelected = selected.includes(s.session_id);
                    const isDisabled = !isSelected && selected.length >= 2;
                    return (
                      <tr
                        key={s.session_id}
                        style={{
                          background: isSelected
                            ? 'rgba(200,152,42,0.07)'
                            : idx % 2 === 0
                              ? '#fff'
                              : 'var(--primary-10)',
                          borderBottom: isSelected
                            ? '1px solid rgba(200,152,42,0.3)'
                            : '1px solid var(--primary-10)',
                          opacity: isDisabled ? 0.45 : 1,
                          transition: 'background 0.1s, opacity 0.1s',
                        }}
                      >
                        {/* Checkbox */}
                        <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={isDisabled}
                            onChange={() => toggleSelect(s.session_id)}
                            aria-label={`Select session for ${s.candidate_name ?? s.candidate_id.slice(0, 8)}`}
                            style={{ accentColor: 'var(--gold)', width: 15, height: 15, cursor: isDisabled ? 'not-allowed' : 'pointer' }}
                          />
                        </td>
                        {/* Candidate name */}
                        <td
                          style={{
                            padding: '12px 16px',
                            fontFamily: 'var(--fb)',
                            fontSize: 13,
                            fontWeight: s.candidate_name ? 500 : 400,
                            color: s.candidate_name ? '#0a1628' : 'var(--mid)',
                          }}
                        >
                          {s.candidate_name ?? `${s.candidate_id.slice(0, 8)}…`}
                        </td>
                        {/* Session ID */}
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
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && sessions.length > 0 && (
          <p
            style={{
              fontFamily: 'var(--fb)',
              fontSize: 11,
              color: 'var(--mid)',
              marginTop: 16,
              letterSpacing: '0.5px',
            }}
          >
            Tip: check any two rows to compare their orchestration profiles side by side.
          </p>
        )}
      </section>
    </>
  );
}
