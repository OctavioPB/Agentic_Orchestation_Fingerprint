'use client';
// Client component: timeline is interactive (hover states)

interface Props {
  trace: string[];
  /** aria-label for the timeline container */
  ariaLabel?: string;
}

export default function ReasoningTrace({ trace, ariaLabel = 'Reasoning trace timeline' }: Props) {
  if (trace.length === 0) {
    return (
      <p
        style={{
          fontFamily: 'var(--fb)',
          fontSize: 13,
          color: 'var(--mid)',
          fontStyle: 'italic',
        }}
      >
        No reasoning trace available for this session.
      </p>
    );
  }

  return (
    <ol
      aria-label={ariaLabel}
      style={{ listStyle: 'none', padding: 0, position: 'relative' }}
    >
      {/* Vertical gold timeline line */}
      <li
        aria-hidden="true"
        style={{
          position: 'absolute',
          left: 15,
          top: 0,
          bottom: 0,
          width: 2,
          backgroundColor: 'var(--gold)',
          opacity: 0.3,
          pointerEvents: 'none',
        }}
      />

      {trace.map((step, index) => (
        <li
          key={index}
          style={{
            display: 'flex',
            gap: 16,
            marginBottom: 20,
            position: 'relative',
          }}
        >
          {/* Step number circle */}
          <div
            aria-label={`Step ${index + 1}`}
            style={{
              flexShrink: 0,
              width: 32,
              height: 32,
              borderRadius: '50%',
              backgroundColor: index === 0 ? 'var(--primary)' : 'var(--white)',
              border: '2px solid var(--gold)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 13,
              fontWeight: 300,
              color: index === 0 ? 'var(--white)' : 'var(--primary)',
              zIndex: 1,
            }}
          >
            {index + 1}
          </div>

          {/* Step text */}
          <p
            style={{
              fontFamily: 'var(--fb)',
              fontSize: 14,
              color: '#374151',
              lineHeight: 1.65,
              paddingTop: 4,
              margin: 0,
            }}
          >
            {step}
          </p>
        </li>
      ))}
    </ol>
  );
}
