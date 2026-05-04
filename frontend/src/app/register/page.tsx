'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { auth, setToken } from '@/lib/api';
import { useT } from '@/i18n/LocaleProvider';
import LocaleSwitcher from '@/i18n/LocaleSwitcher';
import styles from '../login/auth.module.css';

export default function RegisterPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useT();
  const affiliate = searchParams.get('ref') || undefined;

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      toast.error(t('auth.passwordMinError'));
      return;
    }
    setLoading(true);
    try {
      const { access_token } = await auth.register({
        email,
        password,
        full_name: fullName || undefined,
        tenant_name: tenantName,
        affiliate_code: affiliate,
      });
      setToken(access_token);
      toast.success(t('auth.welcomeNew'));
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

        <h1 className={styles.title}>{t('auth.registerTitle')}</h1>
        <p className={styles.subtitle}>{t('auth.registerSubtitle')}</p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label>{t('auth.tenantName')}</label>
            <input
              type="text"
              required
              minLength={2}
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              placeholder={t('auth.tenantPlaceholder')}
            />
          </div>

          <div className={styles.field}>
            <label>{t('auth.fullName')}</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder={t('auth.namePlaceholder')}
            />
          </div>

          <div className={styles.field}>
            <label>{t('auth.email')}</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t('auth.emailPlaceholder')}
            />
          </div>

          <div className={styles.field}>
            <label>{t('auth.password')}</label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('auth.passwordPlaceholder')}
            />
          </div>

          {affiliate && (
            <div className={styles.affiliateBadge}>
              {t('auth.affiliateActive')} : {affiliate}
            </div>
          )}

          <button type="submit" className={styles.btnPrimary} disabled={loading}>
            {loading ? t('auth.registerLoading') : t('auth.submitRegister')}
          </button>
        </form>

        <div className={styles.footer}>
          {t('auth.hasAccount')} <Link href="/login">{t('auth.doLogin')}</Link>
        </div>
      </div>

      <footer className={styles.pageFooter}>— {t('common.signature')}</footer>
    </div>
  );
}
