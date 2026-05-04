import { NextRequest, NextResponse } from 'next/server';

const SUPPORTED = ['fr', 'en', 'de', 'nl', 'es'] as const;
const DEFAULT = 'fr';
const COOKIE = 'sa_locale';

function detectFromHeader(acceptLang: string | null): string {
  if (!acceptLang) return DEFAULT;
  // Parse "fr-FR,fr;q=0.9,en-US;q=0.8"
  const langs = acceptLang
    .split(',')
    .map((l) => l.split(';')[0].trim().toLowerCase().split('-')[0]);
  for (const l of langs) {
    if ((SUPPORTED as readonly string[]).includes(l)) return l;
  }
  return DEFAULT;
}

export function middleware(request: NextRequest) {
  const existing = request.cookies.get(COOKIE)?.value;

  // Si un cookie valide existe déjà, on ne touche à rien
  if (existing && (SUPPORTED as readonly string[]).includes(existing)) {
    return NextResponse.next();
  }

  // Sinon on détecte depuis Accept-Language et on pose le cookie
  const detected = detectFromHeader(request.headers.get('accept-language'));
  const response = NextResponse.next();
  response.cookies.set(COOKIE, detected, {
    path: '/',
    maxAge: 60 * 60 * 24 * 365, // 1 an
    sameSite: 'lax',
  });
  return response;
}

export const config = {
  matcher: [
    // Exclude static assets, API, Next internals
    '/((?!api|_next/static|_next/image|favicon.ico|widget.js).*)',
  ],
};
