import type { Metadata } from 'next';
import { cookies, headers } from 'next/headers';
import { Toaster } from 'react-hot-toast';

import { LocaleProvider } from '@/i18n/LocaleProvider';
import { DEFAULT_LOCALE, SUPPORTED_LOCALES, detectLocale, type Locale } from '@/i18n';
import './globals.css';

export const metadata: Metadata = {
  title: 'Sartorial Agentic — L\'IA sur mesure',
  description: 'Plateforme SaaS agentique premium. Des agents IA autonomes taillés pour votre secteur.',
};

async function resolveInitialLocale(): Promise<Locale> {
  const cookieStore = await cookies();
  const fromCookie = cookieStore.get('sa_locale')?.value;
  if (fromCookie && (SUPPORTED_LOCALES as readonly string[]).includes(fromCookie)) {
    return fromCookie as Locale;
  }
  const hdrs = await headers();
  return detectLocale(hdrs.get('accept-language'));
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const initialLocale = await resolveInitialLocale();

  return (
    <html lang={initialLocale}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <LocaleProvider initialLocale={initialLocale}>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#060E1A',
                color: '#F5F0EB',
                border: '1px solid rgba(201, 168, 76, 0.2)',
                fontFamily: 'DM Sans, sans-serif',
                fontSize: '14px',
              },
              success: {
                iconTheme: { primary: '#C9A84C', secondary: '#060E1A' },
              },
              error: {
                iconTheme: { primary: '#E74C3C', secondary: '#F5F0EB' },
              },
            }}
          />
        </LocaleProvider>
      </body>
    </html>
  );
}
