'use client';
// Client component: uses browser-side SVG geometry computations

import type { Scores } from '@/services/api';

const AXES = [
  { key: 'efficiency_ratio' as const, label: 'Efficiency' },
  { key: 'trust_calibration' as const, label: 'Trust' },
  { key: 'correction_velocity' as const, label: 'Velocity' },
  { key: 'decomposition_score' as const, label: 'Decomposition' },
  { key: 'chaos_resilience' as const, label: 'Chaos Resilience' },
];

const CX = 200;
const CY = 200;
const R = 140;
const N = AXES.length;
const LABEL_R = 165;

function axisPoint(index: number, radius: number): [number, number] {
  const angle = (index * 2 * Math.PI) / N - Math.PI / 2;
  return [CX + radius * Math.cos(angle), CY + radius * Math.sin(angle)];
}

function scorePolygon(scores: number[]): string {
  return scores
    .map((s, i) => {
      const [x, y] = axisPoint(i, Math.max(0, Math.min(1, s)) * R);
      return `${x},${y}`;
    })
    .join(' ');
}

interface Props {
  scores: Scores;
  /** Optional benchmark reference level (0-1), shown as dashed purple overlay. */
  benchmarkLevel?: number;
  className?: string;
}

export default function ScoreRadar({ scores, benchmarkLevel = 0.65 }: Props) {
  const scoreValues = AXES.map((a) => scores[a.key]);
  const candidatePoints = scorePolygon(scoreValues);
  const benchmarkPoints = scorePolygon(Array(N).fill(benchmarkLevel));

  const gridLevels = [0.25, 0.5, 0.75, 1.0];
  const axisLabels = AXES.map((axis, i) => {
    const [x, y] = axisPoint(i, LABEL_R);
    return { axis, x, y };
  });

  return (
    <svg
      viewBox="0 0 400 400"
      width="100%"
      style={{ display: 'block', maxWidth: 420 }}
      role="img"
      aria-label="Score radar chart showing 5 orchestration dimensions"
    >
      <title>Orchestration Score Radar</title>

      {/* Grid rings */}
      {gridLevels.map((level) => {
        const pts = Array.from({ length: N }, (_, i) => {
          const [x, y] = axisPoint(i, level * R);
          return `${x},${y}`;
        }).join(' ');
        return (
          <polygon
            key={level}
            points={pts}
            fill="none"
            stroke="#E0EAF4"
            strokeWidth={1}
          />
        );
      })}

      {/* Axis lines */}
      {AXES.map((_, i) => {
        const [x, y] = axisPoint(i, R);
        return (
          <line
            key={i}
            x1={CX}
            y1={CY}
            x2={x}
            y2={y}
            stroke="#E0EAF4"
            strokeWidth={1}
          />
        );
      })}

      {/* Benchmark polygon (senior engineer reference) */}
      <polygon
        points={benchmarkPoints}
        fill="rgba(124,77,189,0.08)"
        stroke="#7C4DBD"
        strokeWidth={1.5}
        strokeDasharray="5 3"
        aria-label={`Benchmark level ${Math.round(benchmarkLevel * 100)}%`}
      />

      {/* Candidate score polygon */}
      <polygon
        points={candidatePoints}
        fill="rgba(0,51,102,0.18)"
        stroke="#003366"
        strokeWidth={2}
        aria-label="Candidate scores"
      />

      {/* Score dots */}
      {scoreValues.map((s, i) => {
        const [x, y] = axisPoint(i, Math.max(0, Math.min(1, s)) * R);
        return (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={5}
            fill="#003366"
            stroke="#fff"
            strokeWidth={1.5}
            aria-label={`${AXES[i].label}: ${Math.round(s * 100)}%`}
          />
        );
      })}

      {/* Grid % labels (innermost ring) */}
      {gridLevels.map((level) => (
        <text
          key={level}
          x={CX + 4}
          y={CY - level * R + 4}
          fontSize={8}
          fontFamily="Plus Jakarta Sans"
          fill="#99BBDD"
        >
          {Math.round(level * 100)}%
        </text>
      ))}

      {/* Axis labels */}
      {axisLabels.map(({ axis, x, y }) => (
        <text
          key={axis.key}
          x={x}
          y={y}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={10}
          fontFamily="Plus Jakarta Sans"
          fontWeight={500}
          fill="#6B7280"
        >
          {axis.label}
        </text>
      ))}

      {/* Legend */}
      <g transform="translate(16,370)">
        <rect x={0} y={0} width={10} height={10} fill="rgba(0,51,102,0.18)" stroke="#003366" strokeWidth={1.5} />
        <text x={14} y={9} fontSize={9} fontFamily="Plus Jakarta Sans" fill="#6B7280">Candidate</text>
        <rect x={80} y={0} width={10} height={6} fill="rgba(124,77,189,0.08)" stroke="#7C4DBD" strokeWidth={1.5} strokeDasharray="3 2" />
        <text x={94} y={9} fontSize={9} fontFamily="Plus Jakarta Sans" fill="#6B7280">Benchmark</text>
      </g>
    </svg>
  );
}
