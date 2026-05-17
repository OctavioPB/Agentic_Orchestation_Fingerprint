/** BRAND.md footer — primary navy background, 9px uppercase, author + date. */
export default function Footer() {
  const dateStr = new Date()
    .toLocaleDateString('en-US', { year: 'numeric', month: 'long' })
    .toUpperCase();

  return (
    <footer
      style={{
        backgroundColor: 'var(--primary)',
        padding: '20px 48px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontFamily: 'var(--fb)',
        fontSize: 9,
        letterSpacing: '3px',
        textTransform: 'uppercase',
        color: 'rgba(255,255,255,0.4)',
      }}
    >
      <span>OPB · Octavio Pérez Bravo · orchid</span>
      <span>{dateStr}</span>
    </footer>
  );
}
