'use client';
// Fingerprint detail requires client-side token access

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { decodeTenantId, getTokenFromCookie } from '@/lib/auth';
import type { Fingerprint } from '@/services/api';
import { getFingerprint } from '@/services/api';
import Eyebrow from '@/components/ui/Eyebrow';
import StyleClusterBadge from '@/components/ui/StyleClusterBadge';
import EfficiencyRatioGauge from '@/components/charts/EfficiencyRatioGauge';
import ScoreRadar from '@/components/charts/ScoreRadar';
import ReasoningTrace from '@/components/charts/ReasoningTrace';
import InteractionGraph from '@/components/charts/InteractionGraph';

const SCORE_LABELS: Record<string, string> = {
  efficiency_ratio: 'Efficiency Ratio',
  trust_calibration: 'Trust Calibration',
  correction_velocity: 'Correction Velocity',
  decomposition_score: 'Decomposition',
  chaos_resilience: 'Chaos Resilience',
};

function ScoreKpi({ label, value }: { label: string; value: number }) {
  return (
    <div
      style={{
        backgroundColor: '#fff',
        borderRadius: 12,
        boxShadow: '0 1px 4px rgba(0,51,102,0.08)',
        display: 'flex',
        alignItems: 'stretch',
        overflow: 'hidden',
      }}
    >
      {/* Left accent bar — BRAND KPI card */}
      <div style={{ width: 3, background: 'var(--gold)', flexShrink: 0 }} />
      <div style={{ padding: '18px 20px', flex: 1 }}>
        <div
          style={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: 28,
            fontWeight: 300,
            color: 'var(--dark)',
            lineHeight: 1,
          }}
        >
          {Math.round(value * 100)}%
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

export default function FingerprintPage() {
  const params = useParams<{ sessionId: string }>();
  const [fp, setFp] = useState<Fingerprint | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getTokenFromCookie();
    const tenantId = token ? decodeTenantId(token) : null;
    if (!token || !tenantId || !params.sessionId) {
      setError('Not authenticated or invalid session ID.');
      setLoading(false);
      return;
    }
    getFingerprint(params.sessionId, token, tenantId)
      .then(setFp)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : 'Fingerprint not yet assembled.'),
      )
      .finally(() => setLoading(false));
  }, [params.sessionId]);

  if (loading) {
    return (
      <div style={{ padding: '80px 48px', textAlign: 'center' }}>
        <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'var(--mid)' }}>
          Loading fingerprint…
        </p>
      </div>
    );
  }

  if (error || !fp) {
    return (
      <div
        style={{
          maxWidth: 600,
          margin: '80px auto',
          padding: '40px',
          background: '#fff',
          borderRadius: 14,
          borderLeft: '3px solid var(--gold)',
          boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
        }}
      >
        <h2
          style={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: 20,
            fontWeight: 400,
            color: '#0a1628',
            marginBottom: 8,
          }}
        >
          Fingerprint pending
        </h2>
        <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'var(--mid)' }}>
          {error ?? 'This fingerprint has not been assembled yet. Check back after the Airflow DAG completes.'}
        </p>
      </div>
    );
  }

  const benchmarkLevel =
    fp.benchmark_delta != null ? Math.max(0, 1 - fp.benchmark_delta) : undefined;

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
            Orchestration{' '}
            <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>fingerprint</em>
          </h1>
          <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'rgba(255,255,255,0.6)' }}>
            Scenario: {fp.scenario_id} · Session: {fp.session_id.slice(0, 8)}…
          </p>
          <div style={{ marginTop: 16 }}>
            <StyleClusterBadge cluster={fp.style_cluster ?? null} />
          </div>
        </div>
      </section>

      {/* KPI row */}
      <section style={{ maxWidth: 1200, margin: '0 auto', padding: '40px 48px 0' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 16,
          }}
        >
          {Object.entries(fp.scores).map(([key, val]) => (
            <ScoreKpi key={key} label={SCORE_LABELS[key] ?? key} value={val} />
          ))}
        </div>
      </section>

      {/* Charts */}
      <section style={{ maxWidth: 1200, margin: '0 auto', padding: '40px 48px' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
            gap: 24,
          }}
        >
          {/* ScoreRadar */}
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: '28px',
              boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
            }}
          >
            <Eyebrow>Score radar</Eyebrow>
            <h3
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 16,
                fontWeight: 600,
                color: '#0a1628',
                marginBottom: 20,
              }}
            >
              5-Dimension Profile
            </h3>
            <ScoreRadar scores={fp.scores} benchmarkLevel={benchmarkLevel} />
          </div>

          {/* EfficiencyRatioGauge */}
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: '28px',
              boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
          >
            <Eyebrow>Efficiency</Eyebrow>
            <h3
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 16,
                fontWeight: 600,
                color: '#0a1628',
                marginBottom: 20,
              }}
            >
              vs AI-solo Baseline
            </h3>
            <EfficiencyRatioGauge score={fp.scores.efficiency_ratio} />
          </div>

          {/* InteractionGraph */}
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: '28px',
              boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
            }}
          >
            <Eyebrow>Interaction graph</Eyebrow>
            <h3
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 16,
                fontWeight: 600,
                color: '#0a1628',
                marginBottom: 20,
              }}
            >
              Candidate–Agent Network
            </h3>
            <InteractionGraph graph={fp.interaction_graph} />
          </div>

          {/* ReasoningTrace */}
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: '28px',
              boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
            }}
          >
            <Eyebrow>Reasoning trace</Eyebrow>
            <h3
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 16,
                fontWeight: 600,
                color: '#0a1628',
                marginBottom: 20,
              }}
            >
              Reconstructed Thought Tree
            </h3>
            <ReasoningTrace trace={fp.reasoning_trace} />
          </div>
        </div>

        {/* Report markdown */}
        {fp.report_markdown && (
          <div
            style={{
              marginTop: 24,
              background: '#fff',
              borderRadius: 12,
              padding: '32px',
              boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
              borderLeft: '3px solid var(--gold)',
            }}
          >
            <Eyebrow>Assessment report</Eyebrow>
            <div
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 14,
                color: '#374151',
                lineHeight: 1.75,
                whiteSpace: 'pre-wrap',
              }}
            >
              {fp.report_markdown}
            </div>
          </div>
        )}
      </section>
    </>
  );
}
