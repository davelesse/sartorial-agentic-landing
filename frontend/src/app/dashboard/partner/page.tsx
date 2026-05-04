'use client';

import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { Users, TrendingUp, Link2, Copy, DollarSign } from 'lucide-react';
import { useT } from '@/i18n/LocaleProvider';
import styles from './partner.module.css';

interface PartnerStats {
  total_referrals: number;
  active_referrals: number;
  total_earned_cents: number;
  total_earned_eur: number;
  affiliate_code: string;
  affiliate_url: string;
  commission_rate: number;
  plan: string;
}

interface Referral {
  tenant_name: string;
  tenant_plan: string;
  subscription_status: string;
  commission_rate: number;
  total_paid_eur: number;
  created_at: string;
}

interface PartnerDashboard {
  partner: { id: string; plan: string; affiliate_code: string; total_earnings_cents: number; is_active: boolean };
  stats: PartnerStats;
  referrals: Referral[];
}

async function fetchPartnerDashboard(): Promise<PartnerDashboard | null> {
  const token = localStorage.getItem('sa_token');
  if (!token) return null;
  const res = await fetch('/api/partners/me', {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return res.json();
}

export default function PartnerPage() {
  const { t } = useT();
  const [data, setData] = useState<PartnerDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [notPartner, setNotPartner] = useState(false);
  const [registering, setRegistering] = useState(false);

  useEffect(() => {
    fetchPartnerDashboard()
      .then((d) => {
        if (d) setData(d);
        else setNotPartner(true);
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleRegister(plan: string) {
    setRegistering(true);
    try {
      const token = localStorage.getItem('sa_token');
      const res = await fetch('/api/partners/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan }),
      });
      if (!res.ok) throw new Error((await res.json()).detail);
      toast.success(t('partner.welcomeToast'));
      const d = await fetchPartnerDashboard();
      if (d) { setData(d); setNotPartner(false); }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('partner.error'));
    } finally {
      setRegistering(false);
    }
  }

  function copyLink() {
    if (data?.stats.affiliate_url) {
      navigator.clipboard.writeText(data.stats.affiliate_url);
      toast.success(t('partner.linkCopied'));
    }
  }

  if (loading) return <div className={styles.skeleton} />;

  if (notPartner) {
    return (
      <div className={styles.container}>
        <header className={styles.header}>
          <p className={styles.eyebrow}>{t('partner.eyebrow')}</p>
          <h1 className={styles.title} dangerouslySetInnerHTML={{ __html: t('partner.titleNew') }} />
          <p className={styles.desc}>{t('partner.desc')}</p>
        </header>

        <div className={styles.plansGrid}>
          <div className={styles.planCard}>
            <h3>{t('partner.planAssocieName')}</h3>
            <div className={styles.planPrice}>0€<span>/mois</span></div>
            <p>{t('partner.planAssocieDesc')}</p>
            <button
              className={styles.btnSelect}
              onClick={() => handleRegister('associe')}
              disabled={registering}
            >
              {registering ? t('partner.registering') : t('partner.planAssocieBtn')}
            </button>
          </div>

          <div className={`${styles.planCard} ${styles.planFeatured}`}>
            <div className={styles.badge}>Premium</div>
            <h3>{t('partner.planMaisonName')}</h3>
            <div className={styles.planPrice}>497€<span>/mois</span></div>
            <p>{t('partner.planMaisonDesc')}</p>
            <button
              className={styles.btnSelect}
              onClick={() => handleRegister('maison_partenaire')}
              disabled={registering}
            >
              {registering ? t('partner.registering') : t('partner.planMaisonBtn')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;
  const { stats, referrals } = data;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>{t('partner.eyebrow')}</p>
        <h1 className={styles.title} dangerouslySetInnerHTML={{ __html: t('partner.dashboardTitle') }} />
      </header>

      <section className={styles.affiliateBox}>
        <div className={styles.affiliateLabel}>
          <Link2 size={16} /> {t('partner.affiliateLabel')}
        </div>
        <div className={styles.affiliateRow}>
          <code className={styles.affiliateUrl}>{stats.affiliate_url}</code>
          <button className={styles.copyBtn} onClick={copyLink}>
            <Copy size={14} /> {t('partner.copyBtn')}
          </button>
        </div>
        <p className={styles.affiliateHint}>
          {t('partner.affiliateHint', { rate: stats.commission_rate })}
        </p>
      </section>

      <section className={styles.statsGrid}>
        <div className={styles.statCard}>
          <div className={styles.statIcon}><Users size={20} /></div>
          <div className={styles.statValue}>{stats.total_referrals}</div>
          <div className={styles.statLabel}>{t('partner.statReferrals')}</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statIcon}><TrendingUp size={20} /></div>
          <div className={styles.statValue}>{stats.active_referrals}</div>
          <div className={styles.statLabel}>{t('partner.statActive')}</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statIcon}><DollarSign size={20} /></div>
          <div className={styles.statValue}>{stats.total_earned_eur.toFixed(2)}€</div>
          <div className={styles.statLabel}>{t('partner.statEarnings')}</div>
        </div>
      </section>

      {referrals.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>{t('partner.clientsTitle')}</h2>
          <div className={styles.table}>
            <div className={styles.thead}>
              <div>{t('partner.colClient')}</div>
              <div>{t('partner.colPlan')}</div>
              <div>{t('partner.colStatus')}</div>
              <div>{t('partner.colCommissions')}</div>
            </div>
            {referrals.map((ref, idx) => (
              <div key={idx} className={styles.row}>
                <div className={styles.clientName}>{ref.tenant_name}</div>
                <div className={styles.planTag}>{ref.tenant_plan}</div>
                <div className={`${styles.statusTag} ${styles[`st_${ref.subscription_status}`]}`}>
                  {ref.subscription_status}
                </div>
                <div>{ref.total_paid_eur.toFixed(2)}€</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {referrals.length === 0 && (
        <section className={styles.emptyState}>
          <div className={styles.emptyIcon}>◆</div>
          <h2>{t('partner.emptyTitle')}</h2>
          <p>{t('partner.emptyDesc')}</p>
        </section>
      )}
    </div>
  );
}
