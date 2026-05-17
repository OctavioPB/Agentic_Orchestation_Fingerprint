/** StyleClusterBadge — visual classification per BRAND.md semantic status badges. */

type Cluster = 'architect' | 'executor' | 'debugger' | 'delegator';

interface Props {
  cluster: Cluster | null | undefined;
}

const CLUSTER_META: Record<
  Cluster,
  { color: string; bg: string; textColor: string; description: string }
> = {
  architect: {
    color: '#003366',
    bg: '#E0EAF4',
    textColor: '#001F4D',
    description: 'Decomposes first, specifies interfaces, delegates implementation.',
  },
  executor: {
    color: '#F07020',
    bg: '#FEF0E6',
    textColor: '#7A3800',
    description: 'Action-first, tight iterations, corrects post-hoc.',
  },
  debugger: {
    color: '#27B97C',
    bg: '#E0F7EF',
    textColor: '#0D5C3A',
    description: 'Root-cause before fixing, methodical, observability-focused.',
  },
  delegator: {
    color: '#7C4DBD',
    bg: '#F0EBF9',
    textColor: '#3D1F70',
    description: 'High trust, broad delegation, monitors for correction signals.',
  },
};

export default function StyleClusterBadge({ cluster }: Props) {
  if (!cluster) {
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          borderRadius: 20,
          padding: '4px 12px',
          backgroundColor: '#F4F6F9',
          color: 'var(--mid)',
          fontFamily: 'var(--fb)',
          fontSize: 10,
          fontWeight: 500,
          letterSpacing: '1px',
          textTransform: 'uppercase',
        }}
      >
        <span
          style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--mid)' }}
        />
        Unknown
      </span>
    );
  }

  const meta = CLUSTER_META[cluster];
  return (
    <div>
      <span
        role="status"
        aria-label={`Style cluster: ${cluster}`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          borderRadius: 20,
          padding: '4px 12px',
          backgroundColor: meta.bg,
          color: meta.textColor,
          fontFamily: 'var(--fb)',
          fontSize: 10,
          fontWeight: 500,
          letterSpacing: '1px',
          textTransform: 'uppercase',
        }}
      >
        <span
          style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: meta.color }}
        />
        {cluster}
      </span>
      <p
        style={{
          fontFamily: 'var(--fb)',
          fontSize: 12,
          color: 'var(--mid)',
          marginTop: 6,
          lineHeight: 1.6,
        }}
      >
        {meta.description}
      </p>
    </div>
  );
}
