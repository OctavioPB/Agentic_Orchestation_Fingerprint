'use client';
// CandidateCompare requires client-side auth + URL search params

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { decodeTenantId, getTokenFromCookie } from '@/lib/auth';
import type { Fingerprint, Scores } from '@/services/api';
import { getFingerprint } from '@/services/api';
import Eyebrow from '@/components/ui/Eyebrow';
import StyleClusterBadge from '@/components/ui/StyleClusterBadge';
import ScoreRadar from '@/components/charts/ScoreRadar';
import EfficiencyRatioGauge from '@/components/charts/EfficiencyRatioGauge';
import ReasoningTrace from '@/components/charts/ReasoningTrace';
import InteractionGraph from '@/components/charts/InteractionGraph';

const SCORE_META: { key: keyof Scores; label: string }[] = [
  { key: 'efficiency_ratio', label: 'Efficiency Ratio' },
  { key: 'trust_calibration', label: 'Trust Calibration' },
  { key: 'correction_velocity', label: 'Correction Velocity' },
  { key: 'decomposition_score', label: 'Decomposition' },
  { key: 'chaos_resilience', label: 'Chaos Resilience' },
];

function avgScore(scores: Scores): number {
  const vals = Object.values(scores) as number[];
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/** Delta summary row comparing each dimension between A and B. */
function DeltaSummary({
  fpA,
  fpB,
  nameA,
  nameB,
}: {
  fpA: Fingerprint;
  fpB: Fingerprint;
  nameA: string;
  nameB: string;
}) {
  const avgA = avgScore(fpA.scores);
  const avgB = avgScore(fpB.scores);
  const overallWinner = avgA >= avgB ? nameA : nameB;
  const overallDelta = Math.abs(avgA - avgB);

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '28px',
        boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
        borderTop: '3px solid var(--gold)',
        marginBottom: 28,
      }}
    >
      <Eyebrow>Head-to-head delta</Eyebrow>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          marginBottom: 24,
          marginTop: 12,
        }}
      >
        <div>
          <span
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 22,
              fontWeight: 400,
              color: 'var(--primary)',
            }}
          >
            {overallWinner}
          </span>
          <span
            style={{
              fontFamily: 'var(--fb)',
              fontSize: 12,
              color: 'var(--mid)',
              marginLeft: 10,
            }}
          >
            leads overall by {Math.round(overallDelta * 100)} pts avg
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {SCORE_META.map(({ key, label }) => {
          const vA = fpA.scores[key];
          const vB = fpB.scores[key];
          const delta = vA - vB;
          const winner = delta >= 0 ? nameA : nameB;
          const absDelta = Math.abs(delta);
          const pctA = Math.round(vA * 100);
          const pctB = Math.round(vB * 100);

          return (
            <div key={key}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  marginBottom: 5,
                }}
              >
                <span
                  style={{ fontFamily: 'var(--fb)', fontSize: 11, color: '#374151' }}
                >
                  {label}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--fb)',
                    fontSize: 10,
                    fontWeight: 600,
                    color: absDelta < 0.03 ? 'var(--mid)' : 'var(--primary)',
                    letterSpacing: '0.5px',
                  }}
                >
                  {absDelta < 0.03
                    ? 'Tied'
                    : `${winner} +${Math.round(absDelta * 100)} pts`}
                </span>
              </div>
              {/* Dual bar */}
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <span
                  style={{
                    fontFamily: 'var(--fb)',
                    fontSize: 9,
                    color: 'var(--mid)',
                    width: 24,
                    textAlign: 'right',
                    flexShrink: 0,
                  }}
                >
                  {pctA}%
                </span>
                <div
                  style={{
                    flex: 1,
                    height: 8,
                    background: 'var(--light)',
                    borderRadius: 4,
                    overflow: 'hidden',
                    display: 'flex',
                  }}
                >
                  {/* A bar (left-anchored) */}
                  <div
                    style={{
                      width: `${pctA}%`,
                      background: delta >= 0 ? 'var(--primary)' : 'var(--primary-30)',
                      borderRadius: 4,
                      transition: 'width 0.3s',
                    }}
                  />
                </div>
                <div
                  style={{
                    flex: 1,
                    height: 8,
                    background: 'var(--light)',
                    borderRadius: 4,
                    overflow: 'hidden',
                    display: 'flex',
                    justifyContent: 'flex-end',
                  }}
                >
                  {/* B bar (right-anchored) */}
                  <div
                    style={{
                      width: `${pctB}%`,
                      background: delta < 0 ? 'var(--primary)' : 'var(--primary-30)',
                      borderRadius: 4,
                      transition: 'width 0.3s',
                    }}
                  />
                </div>
                <span
                  style={{
                    fontFamily: 'var(--fb)',
                    fontSize: 9,
                    color: 'var(--mid)',
                    width: 24,
                    flexShrink: 0,
                  }}
                >
                  {pctB}%
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div
        style={{
          display: 'flex',
          gap: 20,
          marginTop: 16,
          paddingTop: 14,
          borderTop: '1px solid var(--primary-10)',
        }}
      >
        {[nameA, nameB].map((name, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: 2,
                background: i === 0 ? 'var(--primary)' : 'var(--primary-30)',
              }}
            />
            <span style={{ fontFamily: 'var(--fb)', fontSize: 10, color: 'var(--mid)' }}>
              {name}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Render a single fingerprint column in the comparison layout. */
function FingerprintColumn({ fp, label }: { fp: Fingerprint | null; label: string }) {
  if (!fp) {
    return (
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '32px',
          boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
          textAlign: 'center',
        }}
      >
        <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'var(--mid)' }}>
          Fingerprint not available.
        </p>
      </div>
    );
  }

  const benchmarkLevel =
    fp.benchmark_delta != null ? Math.max(0, 1 - fp.benchmark_delta) : undefined;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '24px 28px',
          boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
          borderTop: '3px solid var(--gold)',
        }}
      >
        <div
          style={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: 20,
            fontWeight: 400,
            color: 'var(--primary)',
            marginBottom: 4,
          }}
        >
          {label}
        </div>
        <p style={{ fontFamily: 'Courier New, monospace', fontSize: 10, color: 'var(--mid)' }}>
          {fp.session_id.slice(0, 16)}… · {fp.scenario_id}
        </p>
        <div style={{ marginTop: 12 }}>
          <StyleClusterBadge cluster={fp.style_cluster ?? null} />
        </div>
      </div>

      {/* Scores bars */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '24px 28px',
          boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
        }}
      >
        <Eyebrow>Scores</Eyebrow>
        {SCORE_META.map(({ key, label: scoreLabel }) => {
          const val = fp.scores[key];
          return (
            <div key={key} style={{ marginBottom: 10 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: 4,
                  fontFamily: 'var(--fb)',
                  fontSize: 11,
                  color: '#374151',
                }}
              >
                <span>{scoreLabel}</span>
                <span style={{ fontWeight: 600, color: 'var(--primary)' }}>
                  {Math.round(val * 100)}%
                </span>
              </div>
              <div
                style={{
                  height: 6,
                  borderRadius: 4,
                  background: 'var(--light)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.round(val * 100)}%`,
                    background: 'var(--primary)',
                    borderRadius: 4,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Radar */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '24px 28px',
          boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
        }}
      >
        <Eyebrow>Score radar</Eyebrow>
        <ScoreRadar scores={fp.scores} benchmarkLevel={benchmarkLevel} />
      </div>

      {/* Gauge */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '24px 28px',
          boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <Eyebrow>Efficiency vs AI solo</Eyebrow>
        <EfficiencyRatioGauge score={fp.scores.efficiency_ratio} />
      </div>

      {/* Interaction graph */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '24px 28px',
          boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
        }}
      >
        <Eyebrow>Candidate–agent network</Eyebrow>
        <InteractionGraph graph={fp.interaction_graph} width={380} height={280} />
      </div>

      {/* Reasoning trace */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '24px 28px',
          boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
        }}
      >
        <Eyebrow>Reasoning trace</Eyebrow>
        <ReasoningTrace trace={fp.reasoning_trace} />
      </div>
    </div>
  );
}

export default function ComparePage() {
  const searchParams = useSearchParams();
  const idA = searchParams.get('a') ?? '';
  const idB = searchParams.get('b') ?? '';
  const nameA = searchParams.get('nameA') ?? 'Candidate A';
  const nameB = searchParams.get('nameB') ?? 'Candidate B';

  const [fpA, setFpA] = useState<Fingerprint | null>(null);
  const [fpB, setFpB] = useState<Fingerprint | null>(null);
  const [loading, setLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [errorA, setErrorA] = useState<string | null>(null);
  const [errorB, setErrorB] = useState<string | null>(null);

  useEffect(() => {
    if (!idA || !idB) return; // no params — stay in empty state, hero guides the user

    const token = getTokenFromCookie();
    const tenantId = token ? decodeTenantId(token) : null;
    if (!token || !tenantId) {
      setAuthError('Not authenticated. Return to the session list to log in.');
      return;
    }

    setLoading(true);
    setErrorA(null);
    setErrorB(null);

    const fetchA = getFingerprint(idA, token, tenantId)
      .then(setFpA)
      .catch((err: unknown) =>
        setErrorA(err instanceof Error ? err.message : 'Could not load fingerprint.'),
      );

    const fetchB = getFingerprint(idB, token, tenantId)
      .then(setFpB)
      .catch((err: unknown) =>
        setErrorB(err instanceof Error ? err.message : 'Could not load fingerprint.'),
      );

    Promise.all([fetchA, fetchB]).finally(() => setLoading(false));
  }, [idA, idB]);

  const hasParams = Boolean(idA && idB);
  const showDelta = fpA !== null && fpB !== null;

  return (
    <>
      {/* Hero */}
      <section
        data-print-hero
        data-print-color
        style={{
          background: 'var(--primary)',
          backgroundImage: `
            linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px)`,
          backgroundSize: '48px 48px',
          padding: '56px 48px',
        }}
      >
        <div style={{ maxWidth: 1300, margin: '0 auto', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
          <div>
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
              {idA && idB ? (
                <>
                  <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>{nameA}</em>
                  {' vs '}
                  <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>{nameB}</em>
                </>
              ) : (
                <>
                  Candidate{' '}
                  <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>comparison</em>
                </>
              )}
            </h1>
            <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'rgba(255,255,255,0.6)' }}>
              Side-by-side orchestration fingerprint analysis.
            </p>
            {(!idA || !idB) && (
              <p
                style={{
                  fontFamily: 'var(--fb)',
                  fontSize: 13,
                  color: 'rgba(255,200,100,0.8)',
                  marginTop: 12,
                }}
              >
                Select two sessions from the{' '}
                <Link href="/sessions" style={{ color: 'var(--gold-light)' }}>
                  session list
                </Link>{' '}
                to begin a comparison.
              </p>
            )}
          </div>

          {/* Export button — only when both fingerprints are loaded */}
          {showDelta && (
            <button
              data-no-print
              onClick={() => window.print()}
              style={{
                flexShrink: 0,
                alignSelf: 'center',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 20px',
                background: 'transparent',
                border: '1.5px solid rgba(255,255,255,0.4)',
                borderRadius: 8,
                color: '#fff',
                fontFamily: 'var(--fb)',
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '2px',
                textTransform: 'uppercase',
                cursor: 'pointer',
                transition: 'border-color 0.15s, background 0.15s',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--gold)';
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(200,152,42,0.12)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.4)';
                (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
              }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <path d="M7 1v8M4 6l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M2 10v1.5A1.5 1.5 0 003.5 13h7A1.5 1.5 0 0012 11.5V10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              Export PDF
            </button>
          )}
        </div>
      </section>

      {/* Delta summary + columns */}
      <section style={{ maxWidth: 1300, margin: '0 auto', padding: '40px 48px' }}>
        {authError && (
          <p
            role="alert"
            style={{ fontFamily: 'var(--fb)', fontSize: 14, color: '#E03448', marginBottom: 24 }}
          >
            {authError}
          </p>
        )}

        {!hasParams && !authError && (
          /* Empty state: user landed here without selecting sessions */
          <div
            style={{
              maxWidth: 480,
              margin: '0 auto',
              textAlign: 'center',
              padding: '40px 0',
            }}
          >
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: '50%',
                background: 'var(--primary-10)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
              }}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="9" cy="12" r="5" stroke="#003366" strokeWidth="1.5" />
                <circle cx="15" cy="12" r="5" stroke="#C8982A" strokeWidth="1.5" />
              </svg>
            </div>
            <p
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontSize: 18,
                fontWeight: 400,
                color: 'var(--dark)',
                marginBottom: 8,
              }}
            >
              No candidates selected
            </p>
            <p
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 13,
                color: 'var(--mid)',
                lineHeight: 1.65,
                marginBottom: 24,
              }}
            >
              Go to the session list, check two completed sessions, then click{' '}
              <strong>Compare →</strong>.
            </p>
            <a
              href="/sessions"
              style={{
                display: 'inline-block',
                padding: '9px 20px',
                background: 'var(--primary)',
                borderRadius: 8,
                color: '#fff',
                fontFamily: 'var(--fb)',
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: '2px',
                textTransform: 'uppercase',
                textDecoration: 'none',
              }}
            >
              ← Session list
            </a>
          </div>
        )}

        {hasParams && loading && (
          <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'var(--mid)' }}>
            Loading fingerprints…
          </p>
        )}

        {hasParams && !loading && (
          <>
            {showDelta && (
              <DeltaSummary fpA={fpA} fpB={fpB} nameA={nameA} nameB={nameB} />
            )}

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 24,
                alignItems: 'start',
              }}
            >
              <div>
                {errorA && (
                  <div
                    style={{
                      background: '#fff',
                      borderRadius: 12,
                      padding: '24px 28px',
                      boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
                      borderLeft: '3px solid #E03448',
                      marginBottom: 0,
                    }}
                  >
                    <p style={{ fontFamily: 'var(--fb)', fontSize: 13, fontWeight: 600, color: '#E03448', marginBottom: 6 }}>
                      {nameA}
                    </p>
                    <p style={{ fontFamily: 'var(--fb)', fontSize: 12, color: 'var(--mid)' }}>
                      {errorA}
                    </p>
                  </div>
                )}
                {!errorA && <FingerprintColumn fp={fpA} label={nameA} />}
              </div>
              <div>
                {errorB && (
                  <div
                    style={{
                      background: '#fff',
                      borderRadius: 12,
                      padding: '24px 28px',
                      boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
                      borderLeft: '3px solid #E03448',
                      marginBottom: 0,
                    }}
                  >
                    <p style={{ fontFamily: 'var(--fb)', fontSize: 13, fontWeight: 600, color: '#E03448', marginBottom: 6 }}>
                      {nameB}
                    </p>
                    <p style={{ fontFamily: 'var(--fb)', fontSize: 12, color: 'var(--mid)' }}>
                      {errorB}
                    </p>
                  </div>
                )}
                {!errorB && <FingerprintColumn fp={fpB} label={nameB} />}
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}
