'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  LayoutDashboard, Cpu, ListChecks, Settings, CreditCard,
  LogOut, Menu, X, Users,
} from 'lucide-react';
import { auth, tenants, clearToken, isAuthenticated, type User, type Tenant } from '@/lib/api';
import { useT } from '@/i18n/LocaleProvider';
import LocaleSwitcher from '@/i18n/LocaleSwitcher';
import styles from './dashboard.module.css';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { t } = useT();

  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  const NAV_ITEMS = [
    { href: '/dashboard',           key: 'dashboard.overview',   icon: LayoutDashboard },
    { href: '/dashboard/agents',    key: 'dashboard.myAgents',   icon: Cpu },
    { href: '/dashboard/tasks',     key: 'dashboard.executions', icon: ListChecks },
    { href: '/dashboard/billing',   key: 'dashboard.billing',    icon: CreditCard },
    { href: '/dashboard/partner',   key: 'dashboard.partner',    icon: Users },
    { href: '/dashboard/settings',  key: 'dashboard.settings',   icon: Settings },
  ];

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/login');
      return;
    }
    Promise.all([auth.me(), tenants.me()])
      .then(([u, t]) => {
        setUser(u);
        setTenant(t);
      })
      .catch(() => router.replace('/login'))
      .finally(() => setLoading(false));
  }, [router]);

  function handleLogout() {
    clearToken();
    router.push('/login');
  }

  if (loading) {
    return (
      <div className={styles.loading}>
        <div className={styles.spinner} />
      </div>
    );
  }

  if (!user || !tenant) return null;

  const trialDaysLeft = tenant.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(tenant.trial_ends_at).getTime() - Date.now()) / 86400000))
    : 0;

  return (
    <div className={styles.layout}>
      <aside className={`${styles.sidebar} ${mobileOpen ? styles.sidebarOpen : ''}`}>
        <div className={styles.sidebarHeader}>
          <Link href="/dashboard" className={styles.brand}>
            Sartorial <span>Agentic</span>
          </Link>
          <button
            className={styles.mobileClose}
            onClick={() => setMobileOpen(false)}
            aria-label={t('common.close')}
          >
            <X size={20} />
          </button>
        </div>

        <div className={styles.tenantCard}>
          <div className={styles.tenantName}>{tenant.name}</div>
          <div className={styles.tenantPlan}>
            {t('dashboard.plan')} <span>{tenant.plan}</span>
          </div>
          {tenant.subscription_status === 'trialing' && tenant.trial_ends_at && (
            <div className={styles.trialBadge}>
              {t('dashboard.trialRemaining', {
                days: trialDaysLeft,
                plural: trialDaysLeft > 1 ? 's' : '',
              })}
            </div>
          )}
        </div>

        <nav className={styles.nav}>
          {NAV_ITEMS.map(({ href, key, icon: Icon }) => {
            const active = pathname === href || (href !== '/dashboard' && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`${styles.navItem} ${active ? styles.navActive : ''}`}
                onClick={() => setMobileOpen(false)}
              >
                <Icon size={18} />
                <span>{t(key)}</span>
              </Link>
            );
          })}
        </nav>

        <div className={styles.sidebarFooter}>
          <div className={styles.localeRow}>
            <LocaleSwitcher />
          </div>

          <div className={styles.userCard}>
            <div className={styles.avatar}>
              {(user.full_name || user.email).charAt(0).toUpperCase()}
            </div>
            <div className={styles.userInfo}>
              <div className={styles.userName}>{user.full_name || user.email.split('@')[0]}</div>
              <div className={styles.userEmail}>{user.email}</div>
            </div>
          </div>
          <button className={styles.logoutBtn} onClick={handleLogout}>
            <LogOut size={16} />
            <span>{t('dashboard.logout')}</span>
          </button>
        </div>
      </aside>

      <main className={styles.main}>
        <button
          className={styles.mobileToggle}
          onClick={() => setMobileOpen(true)}
          aria-label="Menu"
        >
          <Menu size={22} />
        </button>
        {children}
      </main>
    </div>
  );
}
