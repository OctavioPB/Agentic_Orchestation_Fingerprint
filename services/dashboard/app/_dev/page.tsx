'use client';
/**
 * Component gallery — renders all 5 chart components with synthetic fixture data.
 * Used to verify visual correctness without a live backend.
 * Sprint 9 DoD: "All 5 chart/visualization components render correctly with synthetic fixture data."
 */

import EfficiencyRatioGauge from '@/components/charts/EfficiencyRatioGauge';
import InteractionGraph from '@/components/charts/InteractionGraph';
import ReasoningTrace from '@/components/charts/ReasoningTrace';
import ScoreRadar from '@/components/charts/ScoreRadar';
import Eyebrow from '@/components/ui/Eyebrow';
import StyleClusterBadge from '@/components/ui/StyleClusterBadge';
import type { InteractionGraphData, Scores } from '@/services/api';

// ---------------------------------------------------------------------------
// Synthetic fixture data (mirrors data/synthetic/session_001.json patterns)
// ---------------------------------------------------------------------------

const SCORES: Scores = {
  efficiency_ratio: 0.82,
  trust_calibration: 0.75,
  correction_velocity: 0.91,
  decomposition_score: 0.68,
  chaos_resilience: 0.54,
};

const GRAPH: InteractionGraphData = {
  nodes: [
    { id: 'human', label: 'Candidate', node_type: 'human' },
    { id: 'DELTA', label: 'DELTA', node_type: 'agent', agent_name: 'DELTA' },
    { id: 'NOVA', label: 'NOVA', node_type: 'agent', agent_name: 'NOVA' },
    { id: 'ECHO', label: 'ECHO', node_type: 'agent', agent_name: 'ECHO' },
  ],
  edges: [
    { source: 'human', target: 'DELTA', message_count: 8, correction_count: 2, avg_latency_ms: 1240 },
    { source: 'DELTA', target: 'human', message_count: 8, correction_count: 0, avg_latency_ms: 1240 },
    { source: 'human', target: 'NOVA', message_count: 5, correction_count: 1, avg_latency_ms: 980 },
    { source: 'NOVA', target: 'human', message_count: 5, correction_count: 0, avg_latency_ms: 980 },
    { source: 'human', target: 'ECHO', message_count: 3, correction_count: 0, avg_latency_ms: 1860 },
    { source: 'ECHO', target: 'human', message_count: 3, correction_count: 0, avg_latency_ms: 1860 },
  ],
};

const TRACE = [
  'Candidate assessed the broken pipeline schema before engaging any sub-agent.',
  'Delegated initial column mapping investigation to DELTA with specific table context.',
  'Caught DELTA hallucinating the `order_value` column — issued correction within 45s.',
  'Redirected NOVA to validate consumer group offsets after chaos injection.',
  'Demonstrated methodical triage: addressed data integrity before performance concerns.',
  'Finalized recovery by consolidating ECHO schema proposal with DELTA pipeline fix.',
];

function Card({ title, eyebrow, children }: { title: string; eyebrow: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '28px',
        boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
      }}
    >
      <Eyebrow>{eyebrow}</Eyebrow>
      <h3
        style={{
          fontFamily: 'var(--fb)',
          fontSize: 16,
          fontWeight: 600,
          color: '#0a1628',
          marginBottom: 20,
        }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function DevGalleryPage() {
  return (
    <div style={{ background: 'var(--light)', minHeight: '100vh', padding: '48px' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        {/* Page header */}
        <div style={{ marginBottom: 40 }}>
          <div
            style={{
              display: 'inline-block',
              fontFamily: 'var(--fb)',
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: '4px',
              textTransform: 'uppercase',
              color: 'var(--gold)',
              marginBottom: 12,
              padding: '4px 0',
              borderBottom: '1px solid var(--gold)',
            }}
          >
            Sprint 9 · Component gallery
          </div>
          <h1
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 32,
              fontWeight: 400,
              color: '#0a1628',
              marginBottom: 8,
            }}
          >
            Cognitive Blueprint{' '}
            <em style={{ fontStyle: 'italic', color: 'var(--primary)' }}>components</em>
          </h1>
          <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'var(--mid)' }}>
            All 5 chart/visualization components rendered with synthetic fixture data. Route:{' '}
            <code style={{ fontFamily: 'Courier New', fontSize: 12 }}>/dev</code>
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
            gap: 24,
          }}
        >
          {/* 1. ScoreRadar */}
          <Card eyebrow="Chart 1 of 5" title="Score Radar">
            <ScoreRadar scores={SCORES} benchmarkLevel={0.65} />
          </Card>

          {/* 2. EfficiencyRatioGauge */}
          <Card eyebrow="Chart 2 of 5" title="Efficiency Ratio Gauge">
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 24 }}>
              <div>
                <p style={{ fontFamily: 'var(--fb)', fontSize: 11, color: 'var(--mid)', textAlign: 'center', marginBottom: 8 }}>score=0.82</p>
                <EfficiencyRatioGauge score={0.82} />
              </div>
              <div>
                <p style={{ fontFamily: 'var(--fb)', fontSize: 11, color: 'var(--mid)', textAlign: 'center', marginBottom: 8 }}>score=0.30</p>
                <EfficiencyRatioGauge score={0.30} />
              </div>
            </div>
          </Card>

          {/* 3. InteractionGraph (D3 force) */}
          <Card eyebrow="Chart 3 of 5" title="Interaction Graph">
            <InteractionGraph graph={GRAPH} />
          </Card>

          {/* 4. ReasoningTrace */}
          <Card eyebrow="Chart 4 of 5" title="Reasoning Trace">
            <ReasoningTrace trace={TRACE} />
          </Card>

          {/* 5. StyleClusterBadge */}
          <Card eyebrow="Chart 5 of 5" title="Style Cluster Badge">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {(['architect', 'executor', 'debugger', 'delegator'] as const).map((c) => (
                <StyleClusterBadge key={c} cluster={c} />
              ))}
              <StyleClusterBadge cluster={null} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
