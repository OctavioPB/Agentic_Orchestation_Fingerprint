'use client';
// Info page requires client-side tab state

import { useState } from 'react';
import Eyebrow from '@/components/ui/Eyebrow';

// ─── Shared primitives ────────────────────────────────────────────────────────

function Card({
  children,
  accent = false,
  style,
}: {
  children: React.ReactNode;
  accent?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '28px',
        boxShadow: '0 1px 6px rgba(0,51,102,0.09)',
        ...(accent ? { borderLeft: '3px solid var(--gold)' } : {}),
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2
      style={{
        fontFamily: "'Fraunces', Georgia, serif",
        fontSize: 22,
        fontWeight: 400,
        color: '#0a1628',
        marginBottom: 8,
        marginTop: 0,
      }}
    >
      {children}
    </h2>
  );
}

function Body({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <p
      style={{
        fontFamily: 'var(--fb)',
        fontSize: 14,
        color: '#374151',
        lineHeight: 1.75,
        margin: 0,
        ...style,
      }}
    >
      {children}
    </p>
  );
}

// ─── Business View diagrams ───────────────────────────────────────────────────

function AssessmentLifecycleDiagram() {
  const steps = [
    { n: 1, title: 'Candidate\narrives', note: 'Sandbox\nprovisioned', phase: 'setup' },
    { n: 2, title: 'Scenario\nbegins', note: 'Dirty data\n+ broken pipeline', phase: 'setup' },
    { n: 3, title: 'Chaos\ninjected', note: 'Airflow DAG\ntriggers fault', phase: 'active' },
    { n: 4, title: 'Shadow Agent\nobserves', note: 'Every prompt\nscored live', phase: 'active' },
    { n: 5, title: 'Fingerprint\nassembled', note: 'Embeddings\n+ graph stored', phase: 'eval' },
    { n: 6, title: 'Hiring team\nreviews', note: 'Dashboard\n+ PDF export', phase: 'eval' },
  ];

  const colors: Record<string, { circle: string; text: string }> = {
    setup: { circle: '#003366', text: '#fff' },
    active: { circle: '#C8982A', text: '#fff' },
    eval: { circle: '#27B97C', text: '#fff' },
  };

  const cx = [55, 175, 295, 415, 535, 655];
  const cy = 50;
  const r = 22;

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg
        viewBox="0 0 710 130"
        style={{ display: 'block', width: '100%', minWidth: 560 }}
        role="img"
        aria-label="Assessment lifecycle: 6 phases from candidate arrival to hiring review"
      >
        <title>Assessment lifecycle diagram</title>
        {/* Connector lines */}
        {cx.slice(0, -1).map((x, i) => (
          <line
            key={i}
            x1={x + r + 2}
            y1={cy}
            x2={cx[i + 1] - r - 2}
            y2={cy}
            stroke="#E0EAF4"
            strokeWidth={2}
            strokeDasharray={steps[i].phase !== steps[i + 1].phase ? '5 4' : '0'}
          />
        ))}
        {/* Phase labels */}
        <text x="115" y="12" textAnchor="middle" fontSize="8" fontFamily="Plus Jakarta Sans, sans-serif" fill="#99BBDD" letterSpacing="1.5">SETUP</text>
        <text x="355" y="12" textAnchor="middle" fontSize="8" fontFamily="Plus Jakarta Sans, sans-serif" fill="#99BBDD" letterSpacing="1.5">ACTIVE SESSION</text>
        <text x="595" y="12" textAnchor="middle" fontSize="8" fontFamily="Plus Jakarta Sans, sans-serif" fill="#99BBDD" letterSpacing="1.5">EVALUATION</text>
        {/* Phase bracket lines */}
        {[[25, 205], [245, 485], [505, 685]].map(([x1, x2], i) => (
          <line key={i} x1={x1} y1={16} x2={x2} y2={16} stroke="#E0EAF4" strokeWidth={1} />
        ))}
        {/* Steps */}
        {steps.map((s, i) => {
          const c = colors[s.phase];
          return (
            <g key={i}>
              <circle cx={cx[i]} cy={cy} r={r} fill={c.circle} />
              <text x={cx[i]} y={cy + 5} textAnchor="middle" fontSize="13" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="600" fill={c.text}>
                {s.n}
              </text>
              {/* Title below circle */}
              {s.title.split('\n').map((line, j) => (
                <text
                  key={j}
                  x={cx[i]}
                  y={cy + r + 14 + j * 12}
                  textAnchor="middle"
                  fontSize="9"
                  fontFamily="Plus Jakarta Sans, sans-serif"
                  fontWeight="600"
                  fill="#374151"
                >
                  {line}
                </text>
              ))}
            </g>
          );
        })}
        {/* Legend */}
        {[['#003366', 'Setup'], ['#C8982A', 'Active'], ['#27B97C', 'Evaluation']].map(([color, label], i) => (
          <g key={i} transform={`translate(${10 + i * 100}, 118)`}>
            <circle cx="5" cy="5" r="5" fill={color} />
            <text x="14" y="9" fontSize="8" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">{label}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

// ─── Engineering View diagrams ────────────────────────────────────────────────

function ArchitectureDiagram() {
  return (
    <div style={{ overflowX: 'auto' }}>
      <svg
        viewBox="0 0 680 610"
        style={{ display: 'block', width: '100%', minWidth: 540 }}
        role="img"
        aria-label="System architecture diagram showing all orchid services"
      >
        <title>System architecture diagram</title>
        <defs>
          <marker id="arr" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L7,3 z" fill="#99BBDD" />
          </marker>
        </defs>

        {/* ── Layer 1: Candidate Sandbox ─────────────────────────────── */}
        <rect x="20" y="16" width="640" height="96" rx="8" fill="#E0EAF4" stroke="#003366" strokeWidth="1.5" />
        <text x="340" y="34" textAnchor="middle" fontSize="9" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700" fill="#003366" letterSpacing="1.5">CANDIDATE ENVIRONMENT</text>
        <text x="340" y="48" textAnchor="middle" fontSize="8.5" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">Docker + code-server · isolated runtime · up to 60 min per session</text>
        <line x1="20" y1="56" x2="660" y2="56" stroke="#99BBDD" strokeWidth="0.75" />

        {/* Candidate pill */}
        <rect x="36" y="64" width="90" height="30" rx="6" fill="#003366" />
        <text x="81" y="84" textAnchor="middle" fontSize="10" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="600" fill="#fff">Candidate</text>

        {/* Bidirectional arrows */}
        <path d="M128,75 L156,75" stroke="#C8982A" strokeWidth="1.5" markerEnd="url(#arr)" fill="none" />
        <path d="M156,83 L128,83" stroke="#C8982A" strokeWidth="1.5" markerEnd="url(#arr)" fill="none" />

        {/* Agent pills */}
        {[['DELTA', 165], ['NOVA', 272], ['ECHO', 379]].map(([name, x]) => (
          <g key={name as string}>
            <rect x={x as number} y="64" width="90" height="30" rx="6" fill="#fff" stroke="#003366" strokeWidth="1" />
            <text x={(x as number) + 45} y="84" textAnchor="middle" fontSize="10" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="600" fill="#003366">{name}</text>
          </g>
        ))}

        <text x="500" y="78" fontSize="8.5" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">GPT-4o · distinct personas</text>
        <text x="500" y="91" fontSize="8.5" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">deliberate weaknesses</text>

        {/* Arrow down */}
        <line x1="340" y1="112" x2="340" y2="143" stroke="#99BBDD" strokeWidth="1.5" markerEnd="url(#arr)" />
        <text x="346" y="132" fontSize="8" fontFamily="Plus Jakarta Sans, sans-serif" fill="#99BBDD">telemetry events</text>

        {/* ── Layer 2: Kafka ─────────────────────────────────────────── */}
        <rect x="90" y="144" width="500" height="52" rx="8" fill="#FFF8EC" stroke="#C8982A" strokeWidth="1.5" />
        <text x="340" y="165" textAnchor="middle" fontSize="9" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700" fill="#C8982A" letterSpacing="1.5">APACHE KAFKA · TELEMETRY BUS</text>
        <text x="340" y="181" textAnchor="middle" fontSize="8.5" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">orchid.sandbox.* topics · Schema Registry enforced · consumer groups per service</text>

        {/* Fork arrows to Airflow + Shadow Agent */}
        <polyline points="200,196 200,222" stroke="#99BBDD" strokeWidth="1.5" markerEnd="url(#arr)" fill="none" />
        <polyline points="480,196 480,222" stroke="#99BBDD" strokeWidth="1.5" markerEnd="url(#arr)" fill="none" />

        {/* ── Layer 3a: Airflow ──────────────────────────────────────── */}
        <rect x="20" y="222" width="300" height="110" rx="8" fill="#E8F4EC" stroke="#27B97C" strokeWidth="1.5" />
        <text x="170" y="242" textAnchor="middle" fontSize="9" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700" fill="#1A6B44" letterSpacing="1">APACHE AIRFLOW</text>
        <text x="170" y="257" textAnchor="middle" fontSize="8" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">Scenario orchestration</text>
        {[
          '· Scenario lifecycle DAGs (orchid_scenario_*)',
          '· Chaos injection at scheduled minute marks',
          '· Fault types: Kafka lag, DB corruption,',
          '  config drift, network partition',
          '· Session timeout + cleanup tasks',
        ].map((line, i) => (
          <text key={i} x="32" y={275 + i * 12} fontSize="8" fontFamily="Plus Jakarta Sans, sans-serif" fill="#374151">{line}</text>
        ))}

        {/* ── Layer 3b: Shadow Agent ─────────────────────────────────── */}
        <rect x="360" y="222" width="300" height="110" rx="8" fill="#F0EAF8" stroke="#7C4DBD" strokeWidth="1.5" />
        <text x="510" y="242" textAnchor="middle" fontSize="9" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700" fill="#4A1D8A" letterSpacing="1">SHADOW AGENT EVALUATOR</text>
        <text x="510" y="257" textAnchor="middle" fontSize="8" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">FastAPI · Claude (Anthropic SDK)</text>
        {[
          '· Receives PROMPT_SENT + CORRECTION_ISSUED',
          '· Scores each prompt: clarity, specificity,',
          '  context-richness (0–1)',
          '· Classifies style cluster (architect / executor',
          '  / debugger / delegator)',
          '· Assembles OrchestraFingerprint JSON',
        ].map((line, i) => (
          <text key={i} x="372" y={275 + i * 12} fontSize="8" fontFamily="Plus Jakarta Sans, sans-serif" fill="#374151">{line}</text>
        ))}

        {/* Merge arrows to storage */}
        <line x1="170" y1="332" x2="170" y2="364" stroke="#99BBDD" strokeWidth="1.5" />
        <line x1="510" y1="332" x2="510" y2="364" stroke="#99BBDD" strokeWidth="1.5" />
        <line x1="170" y1="364" x2="510" y2="364" stroke="#99BBDD" strokeWidth="1.5" />
        <line x1="340" y1="364" x2="340" y2="388" stroke="#99BBDD" strokeWidth="1.5" markerEnd="url(#arr)" />

        {/* ── Layer 4: Storage ───────────────────────────────────────── */}
        <rect x="90" y="388" width="500" height="52" rx="8" fill="#EDE8F4" stroke="#7C4DBD" strokeWidth="1.5" />
        <text x="340" y="408" textAnchor="middle" fontSize="9" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700" fill="#4A1D8A" letterSpacing="1">STORAGE LAYER</text>
        <text x="340" y="424" textAnchor="middle" fontSize="8.5" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">Qdrant (embedding vectors + similarity search) · Neo4j (interaction graph) · PostgreSQL (session state)</text>

        {/* Arrow down */}
        <line x1="340" y1="440" x2="340" y2="465" stroke="#99BBDD" strokeWidth="1.5" markerEnd="url(#arr)" />

        {/* ── Layer 5: REST API ──────────────────────────────────────── */}
        <rect x="90" y="465" width="500" height="52" rx="8" fill="#E0EAF4" stroke="#003366" strokeWidth="1.5" />
        <text x="340" y="485" textAnchor="middle" fontSize="9" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700" fill="#003366" letterSpacing="1">MULTI-TENANT REST API</text>
        <text x="340" y="501" textAnchor="middle" fontSize="8.5" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">FastAPI · JWT Bearer auth · X-Tenant-ID isolation · in-process fingerprint cache (1 h TTL)</text>

        {/* Arrow down */}
        <line x1="340" y1="517" x2="340" y2="543" stroke="#99BBDD" strokeWidth="1.5" markerEnd="url(#arr)" />

        {/* ── Layer 6: Dashboard ─────────────────────────────────────── */}
        <rect x="90" y="543" width="500" height="52" rx="8" fill="#FEF8E8" stroke="#C8982A" strokeWidth="1.5" />
        <text x="340" y="563" textAnchor="middle" fontSize="9" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700" fill="#C8982A" letterSpacing="1">COGNITIVE BLUEPRINT DASHBOARD</text>
        <text x="340" y="579" textAnchor="middle" fontSize="8.5" fontFamily="Plus Jakarta Sans, sans-serif" fill="#6B7280">Next.js 14 App Router · Zod validation · Score radar · Interaction graph · window.print() PDF</text>
      </svg>
    </div>
  );
}

function TelemetryEventTable() {
  const events = [
    { type: 'PROMPT_SENT', trigger: 'Candidate sends instruction to a sub-agent', key: 'agent, text, session_id, timestamp' },
    { type: 'AGENT_RESPONSE', trigger: 'Sub-agent replies', key: 'agent, text, model, latency_ms, token_count' },
    { type: 'CORRECTION_ISSUED', trigger: 'Candidate explicitly overrides agent output', key: 'agent, original_text, correction_text' },
    { type: 'CODE_EXECUTED', trigger: 'Terminal command runs in sandbox', key: 'command, exit_code, stdout_hash' },
    { type: 'CHAOS_INJECTED', trigger: 'Airflow DAG triggers a scheduled fault', key: 'fault_type, component, severity' },
    { type: 'SCENARIO_STARTED', trigger: 'Session transitions to active state', key: 'scenario_id, scenario_version' },
    { type: 'SCENARIO_ENDED', trigger: 'Session completes or times out', key: 'reason, duration_sec' },
    { type: 'FOCUS_SHIFT', trigger: 'Optional eye-tracking metadata (feature-flagged)', key: 'from_region, to_region, dwell_ms' },
  ];

  return (
    <div style={{ overflowX: 'auto', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,51,102,0.08)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: 'var(--primary)' }}>
            {['event_type', 'When emitted', 'Key payload fields'].map((h) => (
              <th key={h} style={{ padding: '10px 14px', fontFamily: 'var(--fb)', fontSize: 9, fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'rgba(255,255,255,0.85)', textAlign: 'left', whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {events.map((e, i) => (
            <tr key={e.type} style={{ background: i % 2 === 0 ? '#fff' : 'var(--primary-10)', borderBottom: '1px solid var(--primary-10)' }}>
              <td style={{ padding: '9px 14px', fontFamily: 'Courier New, monospace', fontSize: 10, color: 'var(--primary)', whiteSpace: 'nowrap' }}>{e.type}</td>
              <td style={{ padding: '9px 14px', fontFamily: 'var(--fb)', fontSize: 12, color: '#374151' }}>{e.trigger}</td>
              <td style={{ padding: '9px 14px', fontFamily: 'Courier New, monospace', fontSize: 10, color: '#6B7280' }}>{e.key}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Business View ────────────────────────────────────────────────────────────

function BusinessView() {
  const painPoints = [
    {
      problem: 'Technical interviews measure individual output in isolation',
      solution: 'orchid measures how a candidate leads a team of AI agents toward a shared goal, under operational pressure.',
    },
    {
      problem: 'Resumes and portfolios cannot signal AI orchestration capability',
      solution: 'orchid captures live behavioral signals — the prompts, corrections, and decision patterns — not self-reported experience.',
    },
    {
      problem: 'Coding challenges do not test delegation or error correction',
      solution: 'The scenario requires the candidate to decompose ambiguous tasks and catch deliberate hallucinations from sub-agents.',
    },
    {
      problem: 'Interview questions about AI use are easy to answer well without real experience',
      solution: 'Behavioral signals from a 45-minute sandbox session are harder to fake than interview answers.',
    },
    {
      problem: 'Hiring teams have no baseline for what "good" AI collaboration looks like',
      solution: 'Each fingerprint includes a benchmark_delta — cosine distance from senior engineer reference profiles stored in Qdrant.',
    },
  ];

  const dimensions = [
    { key: 'Efficiency Ratio', desc: 'Whether the human-in-the-loop improved outcomes compared to an unguided AI-only run of the same scenario. A ratio below 1.0 means the candidate added negative value; above 1.0 means net positive contribution.' },
    { key: 'Trust Calibration', desc: 'How well the candidate audits vs. blindly accepts agent output. A high score indicates the candidate challenged agent responses at appropriate points without over-correcting on correct outputs.' },
    { key: 'Correction Velocity', desc: 'How quickly the candidate recognized and corrected agent hallucinations once they appeared. Measured from the AGENT_RESPONSE event to the subsequent CORRECTION_ISSUED event.' },
    { key: 'Decomposition Score', desc: 'The quality of task decomposition before delegation. Scored by the Shadow Agent on clarity, specificity, and completeness of instructions sent to sub-agents.' },
    { key: 'Chaos Resilience', desc: 'Recovery quality and speed after a Chaos-injected fault. Measures whether the candidate correctly diagnosed the fault source, adapted their approach, and avoided compounding errors.' },
  ];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '48px 48px' }}>

      {/* Problem statement */}
      <section style={{ marginBottom: 56 }}>
        <Eyebrow>The problem</Eyebrow>
        <SectionHeading>Software engineering now means directing AI agents, not only writing code</SectionHeading>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginTop: 24 }}>
          <Card>
            <div style={{ fontFamily: 'var(--fb)', fontSize: 10, fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--mid)', marginBottom: 12 }}>Traditional assessment</div>
            {[
              'Candidate writes code independently',
              'No agents, no delegation, no correction',
              'Measures output quality at one point in time',
              'No hallucination to catch — no AI in the loop',
              'Individual work under no operational pressure',
            ].map((t) => (
              <div key={t} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 8 }}>
                <span style={{ color: '#E03448', marginTop: 2, flexShrink: 0 }}>✕</span>
                <Body style={{ fontSize: 13, color: '#6B7280' }}>{t}</Body>
              </div>
            ))}
          </Card>
          <Card accent>
            <div style={{ fontFamily: 'var(--fb)', fontSize: 10, fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 12 }}>How engineering actually works</div>
            {[
              'Engineers direct multiple AI agents concurrently',
              'Must decompose tasks into agent-executable instructions',
              'Responsible for catching and correcting hallucinations',
              'Make strategic decisions across parallel threads of work',
              'Handle unexpected infrastructure failures mid-task',
            ].map((t) => (
              <div key={t} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 8 }}>
                <span style={{ color: '#27B97C', marginTop: 2, flexShrink: 0 }}>✓</span>
                <Body style={{ fontSize: 13 }}>{t}</Body>
              </div>
            ))}
          </Card>
        </div>
      </section>

      {/* Assessment flow */}
      <section style={{ marginBottom: 56 }}>
        <Eyebrow>Assessment lifecycle</Eyebrow>
        <SectionHeading>What happens during a session</SectionHeading>
        <Body style={{ marginBottom: 24 }}>
          Each session runs in a containerized environment. The candidate receives a real, broken codebase — a data warehouse with schema violations and a misconfigured Kafka pipeline. Three AI sub-agents are available as a team. A chaos event is injected mid-session without warning. The Shadow Agent observes every prompt and correction in the background.
        </Body>
        <Card style={{ padding: '32px 28px' }}>
          <AssessmentLifecycleDiagram />
        </Card>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginTop: 16 }}>
          {[
            { phase: 'Setup', color: '#003366', desc: 'Sandbox container launched. Dirty DB seed applied. Sub-agents initialized with scenario-specific system prompts.' },
            { phase: 'Active session', color: '#C8982A', desc: 'Candidate works. A chaos event fires at a scheduled minute mark. Shadow Agent scores each PROMPT_SENT event.' },
            { phase: 'Evaluation', color: '#27B97C', desc: 'Shadow Agent assembles the fingerprint. Embeddings stored in Qdrant. Report generated. Fingerprint available in dashboard.' },
          ].map(({ phase, color, desc }) => (
            <div key={phase} style={{ padding: '16px', background: '#fff', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,51,102,0.07)', borderTop: `3px solid ${color}` }}>
              <div style={{ fontFamily: 'var(--fb)', fontSize: 10, fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase', color, marginBottom: 8 }}>{phase}</div>
              <Body style={{ fontSize: 12, color: '#6B7280' }}>{desc}</Body>
            </div>
          ))}
        </div>
      </section>

      {/* What is measured */}
      <section style={{ marginBottom: 56 }}>
        <Eyebrow>The five dimensions</Eyebrow>
        <SectionHeading>What orchid actually measures</SectionHeading>
        <Body style={{ marginBottom: 24 }}>
          Each session produces five independent scores. They are computed from behavioral signals — prompt text, correction events, chaos recovery timing — not from code output or final deliverable quality.
        </Body>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {dimensions.map(({ key, desc }) => (
            <Card key={key} style={{ display: 'flex', alignItems: 'flex-start', gap: 20, padding: '20px 24px' }}>
              <div style={{ flexShrink: 0, width: 3, background: 'var(--gold)', borderRadius: 2, alignSelf: 'stretch' }} />
              <div>
                <div style={{ fontFamily: 'var(--fb)', fontSize: 11, fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--primary)', marginBottom: 6 }}>{key}</div>
                <Body style={{ fontSize: 13, color: '#6B7280' }}>{desc}</Body>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Pain points addressed */}
      <section style={{ marginBottom: 56 }}>
        <Eyebrow>Pain points addressed</Eyebrow>
        <SectionHeading>Where traditional hiring falls short</SectionHeading>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {painPoints.map(({ problem, solution }, i) => (
            <div
              key={i}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 0,
                borderBottom: '1px solid var(--primary-10)',
                padding: '20px 0',
              }}
            >
              <div style={{ paddingRight: 24, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ fontFamily: 'var(--fb)', fontSize: 11, fontWeight: 700, color: '#E03448', flexShrink: 0, marginTop: 2 }}>Problem</span>
                <Body style={{ fontSize: 13, color: '#6B7280' }}>{problem}</Body>
              </div>
              <div style={{ paddingLeft: 24, borderLeft: '1px solid var(--primary-10)', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ fontFamily: 'var(--fb)', fontSize: 11, fontWeight: 700, color: '#27B97C', flexShrink: 0, marginTop: 2 }}>How</span>
                <Body style={{ fontSize: 13 }}>{solution}</Body>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Output */}
      <section>
        <Eyebrow>Output</Eyebrow>
        <SectionHeading>What hiring teams receive</SectionHeading>
        <Body style={{ marginBottom: 24 }}>
          orchid does not rank candidates against each other and does not make a hire/no-hire decision. It produces a structured profile for each candidate, surfacing signals that are otherwise invisible in a standard hiring process.
        </Body>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
          {[
            { label: 'Orchestration Fingerprint', desc: 'A JSON document containing all five scores, the interaction graph, and the reasoning trace. Versioned and stored per session.' },
            { label: 'Style Cluster', desc: 'One of four leadership profiles — architect, executor, debugger, delegator — classified by the Shadow Agent from prompt patterns.' },
            { label: 'Benchmark Delta', desc: 'Cosine distance from senior engineer reference profiles embedded in Qdrant. Contexualizes the candidate relative to a defined cohort.' },
            { label: 'Interaction Graph', desc: 'A directed graph of candidate-to-agent and agent-to-candidate messages, weighted by volume and annotated with correction events.' },
            { label: 'Leadership Narrative', desc: 'A natural language report generated by the Shadow Agent summarizing key behavioral signals from the session in plain language.' },
          ].map(({ label, desc }) => (
            <Card key={label} accent style={{ padding: '20px 22px' }}>
              <div style={{ fontFamily: 'var(--fb)', fontSize: 11, fontWeight: 700, color: 'var(--primary)', marginBottom: 8, letterSpacing: '0.5px' }}>{label}</div>
              <Body style={{ fontSize: 12, color: '#6B7280' }}>{desc}</Body>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}

// ─── Engineering View ─────────────────────────────────────────────────────────

function EngineeringView() {
  const stack = [
    { layer: 'Sandbox runtime', tech: 'Docker + code-server', purpose: 'Isolated per-session VS Code environment. Candidate cannot escape the container. Rebuilt for each session.' },
    { layer: 'Telemetry bus', tech: 'Apache Kafka', purpose: 'All behavioral events flow through Kafka topics (orchid.sandbox.*). Schema Registry enforced on every producer.' },
    { layer: 'Scenario orchestration', tech: 'Apache Airflow', purpose: 'DAG-driven scenario lifecycle. Chaos events injected at scheduled minute marks from DAGs, never from application code.' },
    { layer: 'Evaluation', tech: 'FastAPI + Claude (Anthropic)', purpose: 'Shadow Agent observes and scores the session transcript. Never communicates with the candidate or sub-agents during an active session.' },
    { layer: 'Sub-agents', tech: 'GPT-4o (OpenAI)', purpose: 'Three candidate-facing agents (DELTA, NOVA, ECHO) with distinct personas and deliberate imperfections. System prompts versioned in data/scenarios/agents/.' },
    { layer: 'Embedding store', tech: 'Qdrant', purpose: 'Stores prompt embeddings and reference senior-engineer profiles. Used for benchmark_delta computation (cosine similarity).' },
    { layer: 'Graph store', tech: 'Neo4j', purpose: 'Stores candidate-to-agent interaction graph. Nodes are the candidate and sub-agents; edges carry message count, correction count, and latency.' },
    { layer: 'Session state', tech: 'PostgreSQL (asyncpg)', purpose: 'Persistent session, candidate, fingerprint, and webhook records. Multi-tenant isolation via tenant_id column on every table.' },
    { layer: 'REST API', tech: 'FastAPI', purpose: 'Multi-tenant API. JWT Bearer authentication; X-Tenant-ID header validated against token sub claim on every request.' },
    { layer: 'Dashboard', tech: 'Next.js 14 (App Router)', purpose: 'Cognitive Blueprint Dashboard. All API responses validated with Zod. Server Components by default; "use client" only where state is required.' },
  ];

  const fingerprint = [
    { field: 'session_id', type: 'str', desc: 'UUID v4. Primary key across all stores.' },
    { field: 'candidate_id', type: 'str', desc: 'UUID v4. Ties to candidates table.' },
    { field: 'scenario_id', type: 'str', desc: 'Scenario slug, e.g. corrupted-warehouse-v1.' },
    { field: 'scores', type: 'dict[str, float]', desc: 'Five 0–1 scores: efficiency_ratio, trust_calibration, correction_velocity, decomposition_score, chaos_resilience.' },
    { field: 'style_cluster', type: 'str', desc: 'One of: architect | executor | debugger | delegator.' },
    { field: 'reasoning_trace', type: 'list[str]', desc: 'Ordered list of key decision moments reconstructed by the Shadow Agent.' },
    { field: 'interaction_graph', type: 'dict', desc: 'nodes (human + 3 agents) and edges (message_count, correction_count, avg_latency_ms).' },
    { field: 'benchmark_delta', type: 'float', desc: 'Cosine distance from senior engineer reference embeddings in Qdrant. Lower = closer to reference.' },
    { field: 'report_markdown', type: 'str', desc: 'Natural language narrative generated by the Shadow Agent.' },
  ];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '48px 48px' }}>

      {/* Architecture diagram */}
      <section style={{ marginBottom: 56 }}>
        <Eyebrow>System architecture</Eyebrow>
        <SectionHeading>Service topology and data flow</SectionHeading>
        <Body style={{ marginBottom: 24 }}>
          All services are containerized. In production, Kafka, Qdrant, Neo4j, and PostgreSQL run as managed services. Airflow and the evaluator run on the same cluster as the API. The sandbox container is provisioned per session and destroyed on completion.
        </Body>
        <Card style={{ padding: '28px' }}>
          <ArchitectureDiagram />
        </Card>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 16 }}>
          {[
            { color: '#003366', label: 'Candidate-facing', desc: 'Sandbox + dashboard. External-facing components.' },
            { color: '#C8982A', label: 'Telemetry', desc: 'Kafka bus. All events flow through here — no service communicates peer-to-peer.' },
            { color: '#7C4DBD', label: 'Evaluation + storage', desc: 'Shadow Agent, Qdrant, Neo4j, PostgreSQL. Internal only.' },
          ].map(({ color, label, desc }) => (
            <div key={label} style={{ padding: '14px 16px', background: '#fff', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,51,102,0.07)', borderLeft: `3px solid ${color}` }}>
              <div style={{ fontFamily: 'var(--fb)', fontSize: 10, fontWeight: 700, color, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 6 }}>{label}</div>
              <Body style={{ fontSize: 12, color: '#6B7280' }}>{desc}</Body>
            </div>
          ))}
        </div>
      </section>

      {/* Tech stack */}
      <section style={{ marginBottom: 56 }}>
        <Eyebrow>Tech stack</Eyebrow>
        <SectionHeading>Technology choices by layer</SectionHeading>
        <div style={{ overflowX: 'auto', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,51,102,0.08)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--primary)' }}>
                {['Layer', 'Technology', 'Role in the system'].map((h) => (
                  <th key={h} style={{ padding: '10px 16px', fontFamily: 'var(--fb)', fontSize: 9, fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'rgba(255,255,255,0.85)', textAlign: 'left', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stack.map(({ layer, tech, purpose }, i) => (
                <tr key={layer} style={{ background: i % 2 === 0 ? '#fff' : 'var(--primary-10)', borderBottom: '1px solid var(--primary-10)' }}>
                  <td style={{ padding: '10px 16px', fontFamily: 'var(--fb)', fontSize: 12, fontWeight: 600, color: 'var(--primary)', whiteSpace: 'nowrap' }}>{layer}</td>
                  <td style={{ padding: '10px 16px', fontFamily: 'Courier New, monospace', fontSize: 11, color: '#374151', whiteSpace: 'nowrap' }}>{tech}</td>
                  <td style={{ padding: '10px 16px', fontFamily: 'var(--fb)', fontSize: 12, color: '#6B7280' }}>{purpose}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Telemetry events */}
      <section style={{ marginBottom: 56 }}>
        <Eyebrow>Telemetry event schema</Eyebrow>
        <SectionHeading>Events produced by the sandbox</SectionHeading>
        <Body style={{ marginBottom: 8 }}>
          Every event shares an envelope: <code style={{ fontFamily: 'Courier New', fontSize: 12, background: 'var(--primary-10)', padding: '1px 5px', borderRadius: 3 }}>event_id</code>, <code style={{ fontFamily: 'Courier New', fontSize: 12, background: 'var(--primary-10)', padding: '1px 5px', borderRadius: 3 }}>session_id</code>, <code style={{ fontFamily: 'Courier New', fontSize: 12, background: 'var(--primary-10)', padding: '1px 5px', borderRadius: 3 }}>timestamp</code> (ISO 8601 UTC), <code style={{ fontFamily: 'Courier New', fontSize: 12, background: 'var(--primary-10)', padding: '1px 5px', borderRadius: 3 }}>event_type</code>, and a <code style={{ fontFamily: 'Courier New', fontSize: 12, background: 'var(--primary-10)', padding: '1px 5px', borderRadius: 3 }}>payload</code> dict. All producers enforce the Schema Registry before emit.
        </Body>
        <Body style={{ marginBottom: 24, color: '#6B7280', fontSize: 13 }}>
          The Shadow Agent subscribes only to PROMPT_SENT and CORRECTION_ISSUED. It never receives CODE_EXECUTED or CHAOS_INJECTED — it scores orchestration behavior, not technical output.
        </Body>
        <TelemetryEventTable />
      </section>

      {/* Fingerprint schema */}
      <section style={{ marginBottom: 56 }}>
        <Eyebrow>Data model</Eyebrow>
        <SectionHeading>Orchestration Fingerprint schema</SectionHeading>
        <Body style={{ marginBottom: 24 }}>
          The fingerprint is assembled by the Shadow Agent after the session ends. It is stored as a JSON blob in PostgreSQL and as a structured embedding in Qdrant. The benchmark_delta is computed at assembly time.
        </Body>
        <div style={{ overflowX: 'auto', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,51,102,0.08)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--primary)' }}>
                {['field', 'type', 'description'].map((h) => (
                  <th key={h} style={{ padding: '10px 16px', fontFamily: 'var(--fb)', fontSize: 9, fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'rgba(255,255,255,0.85)', textAlign: 'left', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fingerprint.map(({ field, type, desc }, i) => (
                <tr key={field} style={{ background: i % 2 === 0 ? '#fff' : 'var(--primary-10)', borderBottom: '1px solid var(--primary-10)' }}>
                  <td style={{ padding: '9px 16px', fontFamily: 'Courier New, monospace', fontSize: 11, color: 'var(--primary)', whiteSpace: 'nowrap' }}>{field}</td>
                  <td style={{ padding: '9px 16px', fontFamily: 'Courier New, monospace', fontSize: 10, color: '#7C4DBD', whiteSpace: 'nowrap' }}>{type}</td>
                  <td style={{ padding: '9px 16px', fontFamily: 'var(--fb)', fontSize: 12, color: '#6B7280' }}>{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Key invariants */}
      <section>
        <Eyebrow>Design invariants</Eyebrow>
        <SectionHeading>Rules the system enforces unconditionally</SectionHeading>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {[
            { title: 'Shadow Agent is read-only', desc: 'The evaluator LLM receives the session transcript after the session ends. It never sends messages to the candidate or sub-agents during an active session. Any violation would compromise assessment integrity.' },
            { title: 'Chaos is DAG-only', desc: 'Faults are injected exclusively by Airflow DAGs and logged as CHAOS_INJECTED events in Kafka before the fault lands. Application code is not permitted to inject faults directly.' },
            { title: 'Evaluation is relative, not absolute', desc: 'efficiency_ratio is always computed relative to a baseline AI-only run of the same scenario. Static baselines are not used. The baseline run is stored per scenario version.' },
            { title: 'Sub-agent personas are versioned', desc: 'DELTA, NOVA, and ECHO system prompts live in data/scenarios/agents/. Changes require a new scenario version. Editing an existing system prompt mid-beta would invalidate cross-session comparisons.' },
            { title: 'No real data in tests', desc: 'All test fixtures use synthetic sessions from data/synthetic/. Using real candidate sessions in tests would violate GDPR and assessment integrity constraints.' },
            { title: 'Every LLM call is instrumented', desc: 'All calls to Claude or GPT-4o emit structured logs containing latency_ms, token_count, and model_version. Cost and latency are observable at the session level.' },
          ].map(({ title, desc }) => (
            <Card key={title} style={{ padding: '20px 22px' }}>
              <div style={{ fontFamily: 'var(--fb)', fontSize: 11, fontWeight: 700, color: 'var(--primary)', letterSpacing: '0.5px', marginBottom: 8 }}>{title}</div>
              <Body style={{ fontSize: 12, color: '#6B7280' }}>{desc}</Body>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function InfoPage() {
  const [view, setView] = useState<'business' | 'engineering'>('business');

  const tabBase: React.CSSProperties = {
    padding: '8px 22px',
    borderRadius: 8,
    border: 'none',
    fontFamily: 'var(--fb)',
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: '2px',
    textTransform: 'uppercase',
    cursor: 'pointer',
    transition: 'background 0.15s, color 0.15s',
  };

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
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
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
            Platform{' '}
            <em style={{ fontStyle: 'italic', color: 'var(--gold-light)' }}>overview</em>
          </h1>
          <p style={{ fontFamily: 'var(--fb)', fontSize: 14, color: 'rgba(255,255,255,0.6)', marginBottom: 32 }}>
            How orchid works — from different perspectives.
          </p>

          {/* Tab switcher */}
          <div
            style={{
              display: 'inline-flex',
              background: 'rgba(255,255,255,0.08)',
              borderRadius: 10,
              padding: 4,
              gap: 4,
            }}
          >
            <button
              onClick={() => setView('business')}
              style={{
                ...tabBase,
                background: view === 'business' ? 'var(--gold)' : 'transparent',
                color: view === 'business' ? '#1C1C2E' : 'rgba(255,255,255,0.55)',
              }}
            >
              Business view
            </button>
            <button
              onClick={() => setView('engineering')}
              style={{
                ...tabBase,
                background: view === 'engineering' ? 'var(--gold)' : 'transparent',
                color: view === 'engineering' ? '#1C1C2E' : 'rgba(255,255,255,0.55)',
              }}
            >
              Engineering view
            </button>
          </div>
        </div>
      </section>

      {view === 'business' ? <BusinessView /> : <EngineeringView />}
    </>
  );
}
