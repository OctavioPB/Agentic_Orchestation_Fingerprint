/** Gold eyebrow label — BRAND.md "Signature Visual Element #5" */
interface Props {
  children: React.ReactNode;
  /** Use light={true} on dark navy backgrounds (impact banners, hero sections). */
  light?: boolean;
}

export default function Eyebrow({ children, light = false }: Props) {
  const color = light ? 'var(--gold-light)' : 'var(--gold)';
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 9,
        fontFamily: 'var(--fb)',
        fontWeight: 500,
        letterSpacing: '4px',
        textTransform: 'uppercase',
        color,
        marginBottom: 10,
      }}
    >
      <div
        style={{ width: 24, height: 1, flexShrink: 0, backgroundColor: color }}
      />
      {children}
    </div>
  );
}
