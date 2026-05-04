/**
 * ═══════════════════════════════════════════════════════════
 * SARTORIAL AGENTIC — i18n Core
 * Type-safe translations with nested key access.
 * ═══════════════════════════════════════════════════════════
 */

import fr from './fr.json';
import en from './en.json';
import de from './de.json';
import nl from './nl.json';
import es from './es.json';

export const SUPPORTED_LOCALES = ['fr', 'en', 'de', 'nl', 'es'] as const;
export type Locale = typeof SUPPORTED_LOCALES[number];

export const DEFAULT_LOCALE: Locale = 'fr';

export const LOCALE_NAMES: Record<Locale, string> = {
  fr: 'Français',
  en: 'English',
  de: 'Deutsch',
  nl: 'Nederlands',
  es: 'Español',
};

export const LOCALE_FLAGS: Record<Locale, string> = {
  fr: '🇫🇷',
  en: '🇬🇧',
  de: '🇩🇪',
  nl: '🇳🇱',
  es: '🇪🇸',
};

export type Dictionary = typeof fr;

const DICTIONARIES: Record<Locale, Dictionary> = {
  fr,
  en: en as Dictionary,
  de: de as Dictionary,
  nl: nl as Dictionary,
  es: es as Dictionary,
};

export function getDictionary(locale: Locale): Dictionary {
  return DICTIONARIES[locale] || DICTIONARIES[DEFAULT_LOCALE];
}

/**
 * Resolve a nested key like "dashboard.greeting" safely.
 */
function resolveKey(dict: unknown, path: string): string | null {
  const parts = path.split('.');
  let cur: unknown = dict;
  for (const p of parts) {
    if (cur && typeof cur === 'object' && p in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[p];
    } else {
      return null;
    }
  }
  return typeof cur === 'string' ? cur : null;
}

/**
 * Interpolate {vars} in a string.
 */
function interpolate(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    const value = vars[key];
    return value !== undefined ? String(value) : `{${key}}`;
  });
}

/**
 * Translate a key for a given locale, with optional variable interpolation.
 * Fallback chain: locale → default → key.
 */
export function translate(
  locale: Locale,
  key: string,
  vars?: Record<string, string | number>
): string {
  const dict = getDictionary(locale);
  let value = resolveKey(dict, key);

  // Fallback to default locale
  if (!value && locale !== DEFAULT_LOCALE) {
    value = resolveKey(getDictionary(DEFAULT_LOCALE), key);
  }

  // Last resort: return the key itself
  if (!value) return key;

  return vars ? interpolate(value, vars) : value;
}

/**
 * Detect the best locale from Accept-Language header or browser.
 */
export function detectLocale(input?: string | null): Locale {
  if (!input) return DEFAULT_LOCALE;
  const normalized = input.toLowerCase().split(/[-,;]/)[0].trim();
  return (SUPPORTED_LOCALES as readonly string[]).includes(normalized)
    ? (normalized as Locale)
    : DEFAULT_LOCALE;
}

/**
 * Extract the plural suffix in the current locale.
 * Simplified — most UE languages share "s" for plural > 1.
 */
export function plural(locale: Locale, n: number): string {
  if (n <= 1) return '';
  // German doesn't add "e" for all nouns; Dutch & French use "s"; English uses "s"
  // Spanish uses "s" for nouns but our keys have {plural} that's handled per dict.
  return 's';
}
