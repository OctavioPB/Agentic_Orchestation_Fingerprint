'use client';
// Login is interactive — requires client component for form state and cookie writing

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { setToken, decodeTenantId } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const [token, setTokenInput] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    const trimmed = token.trim();
    if (!trimmed) {
      setError('Paste your JWT token to continue.');
      return;
    }
    const tenantId = decodeTenantId(trimmed);
    if (!tenantId) {
      setError('Token appears malformed — ensure it is a valid JWT.');
      return;
    }
    setLoading(true);
    setToken(trimmed);
    router.push('/sessions');
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--primary)',
        backgroundImage: `
          linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px)`,
        backgroundSize: '48px 48px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 14,
          padding: '48px 40px',
          width: '100%',
          maxWidth: 440,
          boxShadow: '0 8px 32px rgba(0,51,102,0.18)',
        }}
      >
        {/* Gold accent bar */}
        <div
          style={{ height: 3, background: 'var(--gold)', borderRadius: '2px 2px 0 0', marginBottom: 32, marginTop: -48, marginLeft: -40, marginRight: -40 }}
        />

        {/* OPB Monogram */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <span>
            <span
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontSize: 28,
                fontWeight: 300,
                color: '#003366',
              }}
            >
              O
            </span>
            <em
              style={{
                fontFamily: "'Fraunces', Georgia, serif",
                fontSize: 28,
                fontWeight: 300,
                fontStyle: 'italic',
                color: 'var(--gold)',
              }}
            >
              PB
            </em>
          </span>
        </div>

        <h1
          style={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: 22,
            fontWeight: 400,
            color: '#0a1628',
            textAlign: 'center',
            marginBottom: 8,
          }}
        >
          orchid{' '}
          <em style={{ fontStyle: 'italic', color: 'var(--gold)' }}>dashboard</em>
        </h1>
        <p
          style={{
            fontFamily: 'var(--fb)',
            fontSize: 13,
            color: 'var(--mid)',
            textAlign: 'center',
            marginBottom: 32,
          }}
        >
          Paste your tenant JWT to access the Cognitive Blueprint.
        </p>

        <form onSubmit={handleSubmit}>
          <label
            htmlFor="token-input"
            style={{
              display: 'block',
              fontFamily: 'var(--fb)',
              fontSize: 10,
              fontWeight: 500,
              letterSpacing: '3px',
              textTransform: 'uppercase',
              color: 'var(--mid)',
              marginBottom: 8,
            }}
          >
            JWT Token
          </label>
          <textarea
            id="token-input"
            value={token}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="eyJhbGciOi..."
            rows={4}
            aria-describedby={error ? 'token-error' : undefined}
            style={{
              width: '100%',
              resize: 'vertical',
              borderRadius: 8,
              border: error ? '1.5px solid #E03448' : '1.5px solid #E0EAF4',
              padding: '10px 12px',
              fontFamily: 'Courier New, monospace',
              fontSize: 12,
              color: '#1C1C2E',
              outline: 'none',
              transition: 'border-color 0.15s',
              background: '#FAFBFD',
            }}
          />
          {error && (
            <p
              id="token-error"
              role="alert"
              style={{
                fontFamily: 'var(--fb)',
                fontSize: 12,
                color: '#E03448',
                marginTop: 6,
              }}
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: 20,
              width: '100%',
              padding: '12px',
              background: loading ? '#99BBDD' : 'var(--primary)',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontFamily: 'var(--fb)',
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '3px',
              textTransform: 'uppercase',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'background 0.15s',
            }}
          >
            {loading ? 'Authenticating…' : 'Access Dashboard →'}
          </button>
        </form>
      </div>
    </div>
  );
}
