'use client';

/**
 * ═══════════════════════════════════════════════════════════
 * SARTORIAL AGENTIC — i18n React Context
 * LocaleProvider + useT() hook for client components.
 * ═══════════════════════════════════════════════════════════
 */

import { createContext, useContext, useCallback, useEffect, useState, ReactNode } from 'react';
import {
  DEFAULT_LOCALE,
  Locale,
  SUPPORTED_LOCALES,
  detectLocale,
  translate,
} from './index';

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

const STORAGE_KEY = 'sa_locale';
const COOKIE_NAME = 'sa_locale';

function getInitialLocale(): Locale {
  if (typeof window === 'undefined') return DEFAULT_LOCALE;

  // 1. User preference (localStorage)
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && (SUPPORTED_LOCALES as readonly string[]).includes(stored)) {
    return stored as Locale;
  }

  // 2. Cookie (set by server-side detection)
  const cookieMatch = document.cookie.match(new RegExp(`(^|; )${COOKIE_NAME}=([^;]+)`));
  if (cookieMatch && (SUPPORTED_LOCALES as readonly string[]).includes(cookieMatch[2])) {
    return cookieMatch[2] as Locale;
  }

  // 3. Browser language
  return detectLocale(navigator.language);
}

export function LocaleProvider({
  children,
  initialLocale,
}: {
  children: ReactNode;
  initialLocale?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale || DEFAULT_LOCALE);

  // Hydrate from browser after mount
  useEffect(() => {
    if (!initialLocale) {
      setLocaleState(getInitialLocale());
    }
  }, [initialLocale]);

  // Persist on change
  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, newLocale);
      // Cookie 1 an pour détection server-side
      document.cookie = `${COOKIE_NAME}=${newLocale}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
      // Update <html lang="">
      document.documentElement.lang = newLocale;
    }
  }, []);

  // Sync <html lang="">
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => translate(locale, key, vars),
    [locale]
  );

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useT() {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error('useT must be used within LocaleProvider');
  }
  return ctx;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error('useLocale must be used within LocaleProvider');
  }
  return { locale: ctx.locale, setLocale: ctx.setLocale };
}
