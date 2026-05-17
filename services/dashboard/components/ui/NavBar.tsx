'use client';
// NavBar requires client-side navigation (usePathname, router.push for logout)

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { clearToken } from '@/lib/auth';

const NAV_LINKS = [
  { href: '/sessions', label: 'Sessions' },
  { href: '/sessions/compare', label: 'Compare' },
  { href: '/admin', label: 'Admin' },
];

export default function NavBar() {
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    clearToken();
    router.push('/login');
  }

  const navLinkBase: React.CSSProperties = {
    background: 'none',
    border: 'none',
    color: 'rgba(255,255,255,0.45)',
    cursor: 'pointer',
    fontFamily: 'var(--fb)',
    fontSize: 9,
    letterSpacing: '2px',
    textTransform: 'uppercase',
    padding: '5px 8px',
    borderRadius: 6,
    transition: 'color 0.15s',
    textDecoration: 'none',
    display: 'inline-block',
  };
  const navLinkActive: React.CSSProperties = {
    color: 'var(--gold-light)',
    backgroundColor: 'rgba(201,168,76,0.12)',
  };

  return (
    <nav
      role="navigation"
      aria-label="Main navigation"
      style={{
        background: 'rgba(0,51,102,.97)',
        backdropFilter: 'blur(12px)',
        height: 52,
        position: 'sticky',
        top: 0,
        zIndex: 100,
        borderBottom: '1px solid rgba(255,255,255,.08)',
        padding: '0 40px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      {/* OPB Monogram */}
      <Link href="/sessions" aria-label="orchid home">
        <span>
          <span
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 20,
              fontWeight: 300,
              color: '#ffffff',
            }}
          >
            O
          </span>
          <em
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: 20,
              fontWeight: 300,
              fontStyle: 'italic',
              color: 'var(--gold-light)',
            }}
          >
            PB
          </em>
        </span>
      </Link>

      {/* App title */}
      <span
        style={{
          fontFamily: 'var(--fb)',
          fontSize: 9,
          letterSpacing: '3px',
          textTransform: 'uppercase',
          color: 'rgba(255,255,255,.4)',
        }}
      >
        orchid · cognitive blueprint
      </span>

      {/* Nav links + logout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {NAV_LINKS.map(({ href, label }) => {
          const isActive = pathname === href || pathname.startsWith(href + '/');
          return (
            <Link
              key={href}
              href={href}
              style={isActive ? { ...navLinkBase, ...navLinkActive } : navLinkBase}
              aria-current={isActive ? 'page' : undefined}
            >
              {label}
            </Link>
          );
        })}
        <button
          onClick={handleLogout}
          aria-label="Sign out"
          style={{
            background: 'none',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 6,
            color: 'rgba(255,255,255,0.5)',
            cursor: 'pointer',
            fontFamily: 'var(--fb)',
            fontSize: 9,
            letterSpacing: '2px',
            textTransform: 'uppercase',
            padding: '5px 10px',
          }}
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
