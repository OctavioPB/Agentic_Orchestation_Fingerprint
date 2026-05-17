import { jwtVerify } from 'jose';
import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

const SECRET = new TextEncoder().encode(
  process.env.API_SECRET_KEY ?? 'dev-secret-change-in-prod',
);

export async function middleware(request: NextRequest) {
  const token = request.cookies.get('orchid_token')?.value;
  if (!token) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
  try {
    await jwtVerify(token, SECRET);
    return NextResponse.next();
  } catch {
    // Expired or invalid — clear cookie and redirect
    const response = NextResponse.redirect(new URL('/login', request.url));
    response.cookies.delete('orchid_token');
    return response;
  }
}

export const config = {
  matcher: ['/sessions/:path*'],
};
