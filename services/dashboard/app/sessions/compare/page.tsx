'use client';
// CandidateCompare requires client-side auth + URL search params

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { decodeTenantId, getTokenFromCookie } from '@/lib/auth';
import type { Fingerprint } from '@/services/api';
import { getFingerprint } from '@/services/api';
import Eyebrow from '@/components/ui/Eyebrow';
import StyleClusterBadge from '@/components/ui/StyleClusterBadge';
import ScoreRadar from '@/components/charts/ScoreRadar';
import EfficiencyRatioGauge from '@/components/charts/EfficiencyRatioGauge';
import ReasoningTrace from '@/components/charts/ReasoningTrace';
import InteractionGraph from '@/components/charts/InteractionGraph';

/** Render a single fingerprint column in the comparison layout. */
function FingerprintColumn({
  fp,
  label,
}: {
  fp: Fingerprint | null;
  label: string;
}) {
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
            fontFamily: 'var(--fb)',
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '3px',
            textTransform: 'uppercase',
            color: 'var(--gold)',
            marginBottom: 8,
          }}
        >
          {label}
        </div>
        <p style={{ fontFamily: 'Courier New, monospace', fontSize: 11, color: 'var(--mid)' }}>
          {fp.session_id.slice(0, 16)}…
        </p>
        <div style={{ marginTop: 12 }}>
          <StyleClusterBadge cluster={fp.style_cluster ?? null} />
        </div>
      </div>

      {/* Scores KPI */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '24px 28px',
          boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
        }}
      >
        <Eyebrow>Scores</Eyebrow>
        {Object.entries(fp.scores).map(([key, val]) => (
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
              <span style={{ textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}</span>
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
        ))}
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
        <Eyebrow>Radar</Eyebrow>
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
        <Eyebrow>Efficiency</Eyebrow>
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
        <Eyebrow>Interaction</Eyebrow>
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
        <Eyebrow>Reasoning</Eyebrow>
        <ReasoningTrace trace={fp.reasoning_trace} />
      </div>
    </div>
  );
}

export default function ComparePage() {
  const searchParams = useSearchParams();
  const idA = searchParams.get('a') ?? '';
  const idB = searchParams.get('b') ?? '';

  const [fpA, setFpA] = useState<Fingerprint | null>(null);
  const [fpB, setFpB] = useState<Fingerprint | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorA, setErrorA] = useState<string | null>(null);
  const [errorB, setErrorB] = useState<string | null>(null);

  useEffect(() => {
    const token = getTokenFromCookie();
    const tenantId = token ? decodeTenantId(token) : null;
    if (!token || !tenantId) {
      setLoading(false);
      return;
    }

    const fetchA = idA
      ? getFingerprint(idA, token, tenantId)
          .then(setFpA)
          .catch(() => setErrorA('Fingerprint A not available.'))
      : Promise.resolve();

    const fetchB = idB
      ? getFingerprint(idB, token, tenantId)
          .then(setFpB)
          .catch(() => setErrorB('Fingerprint B not available.'))
      : Promise.resolve();

    Promise.all([fetchA, fetchB]).finally(() => setLoading(false));
  }, [idA, idB]);

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
            Candidate{' '}
            <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>comparison</em>
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
              Add <code>?a=&#123;sessionId&#125;&amp;b=&#123;sessionId&#125;</code> to the URL to
              compare two sessions. &nbsp;
              <Link href="/sessions" style={{ color: 'var(--gold-light)' }}>
                ← Back to session list
              </Link>
            </p>
          )}
        </div>
      </section>

      {/* Comparison grid */}
      <section style={{ maxWidth: 1300, margin: '0 auto', padding: '40px 48px' }}>
        {loading ? (
          <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'var(--mid)' }}>
            Loading fingerprints…
          </p>
        ) : (
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
                <p style={{ fontFamily: 'var(--fb)', fontSize: 13, color: '#E03448' }}>
                  {errorA}
                </p>
              )}
              <FingerprintColumn fp={fpA} label="Candidate A" />
            </div>
            <div>
              {errorB && (
                <p style={{ fontFamily: 'var(--fb)', fontSize: 13, color: '#E03448' }}>
                  {errorB}
                </p>
              )}
              <FingerprintColumn fp={fpB} label="Candidate B" />
            </div>
          </div>
        )}
      </section>
    </>
  );
}
