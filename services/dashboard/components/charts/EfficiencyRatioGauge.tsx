'use client';
// Client component: SVG arc geometry computed in browser

interface Props {
  score: number; // 0–1
  label?: string;
}

const CX = 100;
const CY = 105;
const R = 80;
const NEEDLE_R = 62;

/** Map score [0,1] → SVG point on the semicircle above the baseline. */
function gaugePoint(score: number, radius: number): [number, number] {
  const angle = Math.PI - Math.max(0, Math.min(1, score)) * Math.PI;
  return [CX + radius * Math.cos(angle), CY - radius * Math.sin(angle)];
}

export default function EfficiencyRatioGauge({ score, label = 'Efficiency Ratio' }: Props) {
  const clamped = Math.max(0, Math.min(1, score));
  const [ex, ey] = gaugePoint(clamped, R);
  const [nx, ny] = gaugePoint(clamped, NEEDLE_R);

  const trackD = `M ${CX - R},${CY} A ${R},${R} 0 0,0 ${CX + R},${CY}`;
  // Progress arc: counterclockwise (sweep=0) from left endpoint to score point.
  // Arc is always ≤ 180° so large-arc=0. At score=1 the endpoints are collinear
  // with the diameter so we avoid a degenerate arc.
  const fillD =
    clamped < 0.001
      ? ''
      : clamped > 0.999
        ? `M ${CX - R},${CY} A ${R},${R} 0 1,0 ${CX + R},${CY}`
        : `M ${CX - R},${CY} A ${R},${R} 0 0,0 ${ex},${ey}`;

  const pct = Math.round(clamped * 100);

  return (
    <svg
      viewBox="0 0 200 130"
      width="100%"
      style={{ display: 'block', maxWidth: 280 }}
      role="img"
      aria-label={`${label}: ${pct}% of AI-solo baseline`}
    >
      <title>{label}</title>

      {/* Track */}
      <path d={trackD} fill="none" stroke="#E0EAF4" strokeWidth={14} strokeLinecap="round" />

      {/* Fill (BRAND primary blue) */}
      {fillD && (
        <path
          d={fillD}
          fill="none"
          stroke="var(--primary)"
          strokeWidth={14}
          strokeLinecap="round"
        />
      )}

      {/* Needle (BRAND gold) */}
      <line
        x1={CX}
        y1={CY}
        x2={nx}
        y2={ny}
        stroke="#C8982A"
        strokeWidth={3}
        strokeLinecap="round"
      />
      <circle cx={CX} cy={CY} r={5} fill="#C8982A" />

      {/* Score text — Fraunces per BRAND typography */}
      <text
        x={CX}
        y={CY - 18}
        textAnchor="middle"
        fontSize={22}
        fontFamily="Fraunces, Georgia, serif"
        fontWeight={300}
        fill="#003366"
      >
        {pct}%
      </text>

      {/* Endpoint labels */}
      <text
        x={CX - R}
        y={CY + 18}
        textAnchor="middle"
        fontSize={9}
        fontFamily="Plus Jakarta Sans"
        fill="#99BBDD"
      >
        0%
      </text>
      <text
        x={CX + R}
        y={CY + 18}
        textAnchor="middle"
        fontSize={9}
        fontFamily="Plus Jakarta Sans"
        fill="#99BBDD"
      >
        100%
      </text>

      {/* Label */}
      <text
        x={CX}
        y={CY + 18}
        textAnchor="middle"
        fontSize={9}
        fontFamily="Plus Jakarta Sans"
        fontWeight={500}
        letterSpacing={1}
        fill="#6B7280"
        style={{ textTransform: 'uppercase' }}
      >
        vs AI solo
      </text>
    </svg>
  );
}
