/**
 * Client-side auth utilities.
 * JWT stored as cookie `orchid_token`; tenant_id decoded from the `sub` claim.
 */

const COOKIE = 'orchid_token';
const MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export function setToken(token: string): void {
  document.cookie = `${COOKIE}=${token}; path=/; max-age=${MAX_AGE}; SameSite=Lax`;
}

export function clearToken(): void {
  document.cookie = `${COOKIE}=; path=/; max-age=0`;
}

export function getTokenFromCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Decode the JWT payload (no signature verification — that happens server-side in middleware).
 * Returns null if the token is malformed.
 */
export function decodeTenantId(token: string): string | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return (payload?.sub as string) ?? null;
  } catch {
    return null;
  }
}
