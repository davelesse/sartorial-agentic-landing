'use client';

import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { useLocale } from './LocaleProvider';
import { LOCALE_FLAGS, LOCALE_NAMES, SUPPORTED_LOCALES, type Locale } from './index';
import styles from './LocaleSwitcher.module.css';

export default function LocaleSwitcher({ variant = 'dark' }: { variant?: 'dark' | 'light' }) {
  const { locale, setLocale } = useLocale();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  return (
    <div className={`${styles.root} ${styles[variant]}`} ref={ref}>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span className={styles.flag} aria-hidden>{LOCALE_FLAGS[locale]}</span>
        <span className={styles.code}>{locale.toUpperCase()}</span>
        <ChevronDown size={14} className={`${styles.chev} ${open ? styles.chevOpen : ''}`} />
      </button>

      {open && (
        <div className={styles.menu} role="listbox">
          {SUPPORTED_LOCALES.map((loc) => (
            <button
              key={loc}
              type="button"
              className={`${styles.option} ${loc === locale ? styles.optionActive : ''}`}
              onClick={() => { setLocale(loc as Locale); setOpen(false); }}
              role="option"
              aria-selected={loc === locale}
            >
              <span className={styles.flag} aria-hidden>{LOCALE_FLAGS[loc]}</span>
              <span className={styles.name}>{LOCALE_NAMES[loc]}</span>
              {loc === locale && <Check size={14} className={styles.checkIcon} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
