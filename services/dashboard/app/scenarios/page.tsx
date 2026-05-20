'use client';

import { useEffect, useState } from 'react';
import { decodeTenantId, getTokenFromCookie } from '@/lib/auth';
import { getScenarios } from '@/services/api';
import type { Scenario } from '@/services/api';
import Eyebrow from '@/components/ui/Eyebrow';

// ─── Dimension labels for recruiters ─────────────────────────────────────────

const DIMENSION_LABELS: Record<string, string> = {
  decomposition_score: 'Decomposition',
  trust_calibration: 'Trust Calibration',
  correction_velocity: 'Correction Velocity',
  chaos_resilience: 'Chaos Resilience',
  efficiency_ratio: 'Efficiency Ratio',
};

// ─── Difficulty badge ─────────────────────────────────────────────────────────

const DIFFICULTY_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  easy:   { bg: '#E0F7EF', text: '#0D5C3A', dot: '#27B97C' },
  medium: { bg: '#FEF3D7', text: '#7A4F00', dot: '#C8982A' },
  hard:   { bg: '#FDECEA', text: '#7A1E1E', dot: '#E03448' },
};

function DifficultyBadge({ level }: { level: string }) {
  const s = DIFFICULTY_STYLES[level] ?? DIFFICULTY_STYLES.medium;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        borderRadius: 20,
        padding: '3px 10px',
        backgroundColor: s.bg,
        color: s.text,
        fontFamily: 'var(--fb)',
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '1.5px',
        textTransform: 'uppercase',
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: s.dot }} />
      {level}
    </span>
  );
}

// ─── Chaos component badge ────────────────────────────────────────────────────

const CHAOS_STYLES: Record<string, { bg: string; text: string }> = {
  KILL_CONSUMER:  { bg: '#FDECEA', text: '#7A1E1E' },
  CORRUPT_SCHEMA: { bg: '#FEF0E6', text: '#7A3800' },
};

function ChaosBadge({ type }: { type: string }) {
  const s = CHAOS_STYLES[type] ?? { bg: '#F4F6F9', text: '#374151' };
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        borderRadius: 6,
        padding: '3px 8px',
        backgroundColor: s.bg,
        color: s.text,
        fontFamily: 'Courier New, monospace',
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '0.5px',
      }}
    >
      {type}
    </span>
  );
}

// ─── Metrics row ──────────────────────────────────────────────────────────────

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        padding: '10px 16px',
        background: 'var(--primary-10)',
        borderRadius: 8,
        minWidth: 80,
      }}
    >
      <span
        style={{
          fontFamily: 'var(--fb)',
          fontSize: 9,
          letterSpacing: '1.5px',
          textTransform: 'uppercase',
          color: 'var(--mid)',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 20,
          fontWeight: 400,
          color: 'var(--primary)',
          lineHeight: 1,
        }}
      >
        {value}
      </span>
    </div>
  );
}

// ─── Chaos timeline bar ───────────────────────────────────────────────────────

function ChaosTimeline({
  triggerMin,
  maxMin,
  type,
}: {
  triggerMin: number;
  maxMin: number;
  type: string;
}) {
  const pct = Math.round((triggerMin / maxMin) * 100);
  const chaosColor = type === 'KILL_CONSUMER' ? '#E03448' : '#F07020';
  return (
    <div style={{ marginTop: 16 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontFamily: 'var(--fb)',
          fontSize: 9,
          letterSpacing: '1px',
          color: 'var(--mid)',
          marginBottom: 6,
          textTransform: 'uppercase',
        }}
      >
        <span>Session start</span>
        <span>T+{maxMin} min</span>
      </div>
      <div
        style={{
          position: 'relative',
          height: 8,
          background: '#E0EAF4',
          borderRadius: 4,
          overflow: 'visible',
        }}
      >
        {/* filled portion before chaos */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            height: '100%',
            width: `${pct}%`,
            background: 'var(--primary)',
            borderRadius: 4,
          }}
        />
        {/* chaos marker */}
        <div
          style={{
            position: 'absolute',
            left: `${pct}%`,
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: chaosColor,
            border: '2px solid #fff',
            boxShadow: `0 0 0 2px ${chaosColor}`,
          }}
        />
      </div>
      <div
        style={{
          marginTop: 8,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: chaosColor,
            flexShrink: 0,
            display: 'inline-block',
          }}
        />
        <span style={{ fontFamily: 'var(--fb)', fontSize: 12, color: '#374151' }}>
          <strong style={{ color: chaosColor }}>
            {type}
          </strong>{' '}
          fires at T+{triggerMin} min
        </span>
      </div>
    </div>
  );
}

// ─── AI baseline bar ──────────────────────────────────────────────────────────

function AiBaselineRow({ scenario }: { scenario: Scenario }) {
  const { ai_solo_steps, ai_solo_duration_sec, ai_solo_violations_found, violations_count } = scenario;
  if (!ai_solo_steps || !ai_solo_duration_sec) return null;
  const minutes = Math.round(ai_solo_duration_sec / 60);
  const foundLabel =
    ai_solo_violations_found != null && violations_count != null
      ? `${ai_solo_violations_found}/${violations_count} violations found`
      : null;

  return (
    <div
      style={{
        marginTop: 20,
        padding: '12px 16px',
        background: '#F8F9FB',
        borderRadius: 8,
        borderLeft: '3px solid #C8D8E8',
      }}
    >
      <p
        style={{
          fontFamily: 'var(--fb)',
          fontSize: 10,
          letterSpacing: '1.5px',
          textTransform: 'uppercase',
          color: 'var(--mid)',
          margin: '0 0 6px',
        }}
      >
        AI-solo baseline (for efficiency ratio)
      </p>
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        {[
          { label: 'Steps', value: String(ai_solo_steps) },
          { label: 'Duration', value: `${minutes} min` },
          ...(foundLabel ? [{ label: 'Coverage', value: foundLabel }] : []),
        ].map(({ label, value }) => (
          <div key={label}>
            <span
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 9,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                color: 'var(--mid)',
                display: 'block',
              }}
            >
              {label}
            </span>
            <span
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 13,
                fontWeight: 600,
                color: '#374151',
              }}
            >
              {value}
            </span>
          </div>
        ))}
      </div>
      <p
        style={{
          fontFamily: 'var(--fb)',
          fontSize: 11,
          color: 'var(--mid)',
          margin: '8px 0 0',
          lineHeight: 1.6,
        }}
      >
        The efficiency ratio score compares each candidate&apos;s step count and duration against
        these figures. A ratio above 1.0 means the candidate outpaced the AI run.
      </p>
    </div>
  );
}

// ─── Scoring signals table ────────────────────────────────────────────────────

function ScoringSignalsTable({ scenario }: { scenario: Scenario }) {
  if (!scenario.scoring_signals.length) return null;
  return (
    <div style={{ marginTop: 20 }}>
      <p
        style={{
          fontFamily: 'var(--fb)',
          fontSize: 10,
          letterSpacing: '1.5px',
          textTransform: 'uppercase',
          color: 'var(--mid)',
          margin: '0 0 10px',
        }}
      >
        What this scenario measures
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {scenario.scoring_signals.map((sig) => (
          <div
            key={sig.dimension}
            style={{
              display: 'grid',
              gridTemplateColumns: '140px 1fr',
              gap: 12,
              alignItems: 'start',
              padding: '8px 0',
              borderBottom: '1px solid #F0F4F8',
            }}
          >
            <span
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--primary)',
                paddingTop: 1,
              }}
            >
              {DIMENSION_LABELS[sig.dimension] ?? sig.dimension}
            </span>
            <span
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 12,
                color: '#374151',
                lineHeight: 1.6,
              }}
            >
              {sig.signal}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Scenario card ────────────────────────────────────────────────────────────

function ScenarioCard({ scenario }: { scenario: Scenario }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 14,
        boxShadow: '0 2px 10px rgba(0,51,102,0.09)',
        overflow: 'hidden',
      }}
    >
      {/* Card header — navy accent */}
      <div
        style={{
          background: 'var(--primary)',
          padding: '20px 28px 16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
              <DifficultyBadge level={scenario.difficulty} />
              <span
                style={{
                  fontFamily: 'Courier New, monospace',
                  fontSize: 10,
                  color: 'rgba(255,255,255,0.4)',
                  letterSpacing: '1px',
                }}
              >
                {scenario.version}
              </span>
            </div>
            <h2
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontSize: 24,
                fontWeight: 400,
                color: '#fff',
                margin: 0,
                lineHeight: 1.2,
              }}
            >
              {scenario.name}
            </h2>
          </div>
          {scenario.chaos_component && (
            <ChaosBadge type={scenario.chaos_component} />
          )}
        </div>
        <p
          style={{
            fontFamily: 'var(--fb)',
            fontSize: 13,
            color: 'rgba(255,255,255,0.7)',
            lineHeight: 1.7,
            margin: '12px 0 0',
          }}
        >
          {scenario.description}
        </p>
      </div>

      {/* Metrics row */}
      <div
        style={{
          padding: '20px 28px',
          borderBottom: '1px solid #F0F4F8',
          display: 'flex',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        {scenario.max_duration_min != null && (
          <MetricPill label="Max Duration" value={`${scenario.max_duration_min} min`} />
        )}
        {scenario.violations_count != null && (
          <MetricPill label="Violations" value={String(scenario.violations_count)} />
        )}
        {scenario.expected_resolution_steps != null && (
          <MetricPill label="Exp. Steps" value={String(scenario.expected_resolution_steps)} />
        )}
        {scenario.chaos_trigger_min != null && (
          <MetricPill label="Chaos at" value={`T+${scenario.chaos_trigger_min} min`} />
        )}
      </div>

      {/* Chaos timeline */}
      {scenario.chaos_trigger_min != null &&
        scenario.max_duration_min != null &&
        scenario.chaos_component && (
          <div style={{ padding: '20px 28px', borderBottom: '1px solid #F0F4F8' }}>
            <ChaosTimeline
              triggerMin={scenario.chaos_trigger_min}
              maxMin={scenario.max_duration_min}
              type={scenario.chaos_component}
            />
          </div>
        )}

      {/* Expandable detail section */}
      <div style={{ padding: '0 28px' }}>
        <button
          onClick={() => setExpanded((v) => !v)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '16px 0',
            width: '100%',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontFamily: 'var(--fb)',
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '2px',
            textTransform: 'uppercase',
            color: 'var(--primary)',
            borderBottom: expanded ? '1px solid #F0F4F8' : 'none',
          }}
          aria-expanded={expanded}
        >
          <span
            style={{
              display: 'inline-block',
              width: 14,
              textAlign: 'center',
              transition: 'transform 0.15s',
              transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
            }}
          >
            ›
          </span>
          {expanded ? 'Hide detail' : 'Scoring signals & AI baseline'}
        </button>

        {expanded && (
          <div style={{ paddingBottom: 24 }}>
            <ScoringSignalsTable scenario={scenario} />
            <AiBaselineRow scenario={scenario} />
          </div>
        )}
      </div>

      {/* Footer — scenario ID */}
      <div
        style={{
          padding: '12px 28px',
          background: '#F8F9FB',
          borderTop: '1px solid #F0F4F8',
        }}
      >
        <span
          style={{
            fontFamily: 'Courier New, monospace',
            fontSize: 10,
            color: 'var(--mid)',
          }}
        >
          {scenario.scenario_id}
        </span>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ScenariosPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getTokenFromCookie();
    const tenantId = token ? decodeTenantId(token) : null;
    if (!token || !tenantId) {
      setError('Not authenticated.');
      setLoading(false);
      return;
    }
    getScenarios(token, tenantId)
      .then(setScenarios)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : 'Failed to load scenarios.'),
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
          <Eyebrow light>Scenario catalogue</Eyebrow>
          <h1
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 32,
              fontWeight: 400,
              color: '#fff',
              lineHeight: 1.2,
              marginBottom: 8,
              marginTop: 0,
            }}
          >
            Assessment{' '}
            <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>scenarios</em>
          </h1>
          <p
            style={{
              fontFamily: 'var(--fb)',
              fontSize: 14,
              color: 'rgba(255,255,255,0.6)',
              lineHeight: 1.75,
              maxWidth: 600,
            }}
          >
            Each scenario places a candidate inside a broken engineering environment. The chaos
            event, expected resolution path, and scoring signals are fixed per scenario version
            so every candidate is evaluated on the same conditions.
          </p>
        </div>
      </section>

      {/* Content */}
      <section style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 48px' }}>

        {loading && (
          <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'var(--mid)' }}>
            Loading scenarios…
          </p>
        )}

        {error && (
          <p role="alert" style={{ fontFamily: 'var(--fb)', fontSize: 14, color: '#E03448' }}>
            {error}
          </p>
        )}

        {!loading && !error && scenarios.length === 0 && (
          <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'var(--mid)' }}>
            No scenarios found. Ensure scenario meta.json files are present in data/scenarios/.
          </p>
        )}

        {!loading && !error && scenarios.length > 0 && (
          <>
            {/* Stats strip */}
            <div
              style={{
                display: 'flex',
                gap: 32,
                marginBottom: 36,
                padding: '16px 0',
                borderBottom: '1px solid #E0EAF4',
              }}
            >
              <div>
                <span
                  style={{
                    fontFamily: 'var(--fb)',
                    fontSize: 9,
                    letterSpacing: '2px',
                    textTransform: 'uppercase',
                    color: 'var(--mid)',
                    display: 'block',
                  }}
                >
                  Scenarios available
                </span>
                <span
                  style={{
                    fontFamily: "'Fraunces', Georgia, serif",
                    fontSize: 28,
                    fontWeight: 400,
                    color: 'var(--primary)',
                  }}
                >
                  {scenarios.length}
                </span>
              </div>
              <div>
                <span
                  style={{
                    fontFamily: 'var(--fb)',
                    fontSize: 9,
                    letterSpacing: '2px',
                    textTransform: 'uppercase',
                    color: 'var(--mid)',
                    display: 'block',
                  }}
                >
                  Dimensions scored
                </span>
                <span
                  style={{
                    fontFamily: "'Fraunces', Georgia, serif",
                    fontSize: 28,
                    fontWeight: 400,
                    color: 'var(--primary)',
                  }}
                >
                  5
                </span>
              </div>
              <div>
                <span
                  style={{
                    fontFamily: 'var(--fb)',
                    fontSize: 9,
                    letterSpacing: '2px',
                    textTransform: 'uppercase',
                    color: 'var(--mid)',
                    display: 'block',
                  }}
                >
                  Max duration
                </span>
                <span
                  style={{
                    fontFamily: "'Fraunces', Georgia, serif",
                    fontSize: 28,
                    fontWeight: 400,
                    color: 'var(--primary)',
                  }}
                >
                  60 min
                </span>
              </div>
            </div>

            {/* Scenario cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
              {scenarios.map((s) => (
                <ScenarioCard key={s.scenario_id} scenario={s} />
              ))}
            </div>

            {/* Footer note */}
            <p
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 11,
                color: 'var(--mid)',
                marginTop: 32,
                lineHeight: 1.7,
                maxWidth: 640,
              }}
            >
              Scenario versions are immutable. When a scenario is updated, a new version
              (v2, v3, …) is created so all sessions within a version remain directly comparable.
              The chaos event fires at a fixed time regardless of candidate progress.
            </p>
          </>
        )}
      </section>
    </>
  );
}
