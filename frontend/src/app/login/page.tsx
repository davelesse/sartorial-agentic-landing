'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { auth, setToken } from '@/lib/api';
import { useT } from '@/i18n/LocaleProvider';
import LocaleSwitcher from '@/i18n/LocaleSwitcher';
import styles from './auth.module.css';

export default function LoginPage() {
  const router = useRouter();
  const { t } = useT();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const { access_token } = await auth.login(email, password);
      setToken(access_token);
      toast.success(t('auth.welcomeBack'));
      router.push('/dashboard');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.error');
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.orbBg} />

      <div className={styles.topBar}>
        <LocaleSwitcher />
      </div>

      <div className={styles.card}>
        <Link href="/" className={styles.brand}>
          Sartorial <span>Agentic</span>
        </Link>

        <h1 className={styles.title}>{t('auth.loginTitle')}</h1>
        <p className={styles.subtitle}>{t('auth.loginSubtitle')}</p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label>{t('auth.email')}</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t('auth.emailPlaceholder')}
              autoFocus
            />
          </div>

          <div className={styles.field}>
            <label>{t('auth.password')}</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <button type="submit" className={styles.btnPrimary} disabled={loading}>
            {loading ? t('auth.submitLoading') : t('auth.submitLogin')}
          </button>
        </form>

        <div className={styles.footer}>
          {t('auth.noAccount')} <Link href="/register">{t('auth.createAccount')}</Link>
        </div>
      </div>

      <footer className={styles.pageFooter}>— {t('common.signature')}</footer>
    </div>
  );
}
