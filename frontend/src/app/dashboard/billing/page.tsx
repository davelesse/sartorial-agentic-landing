'use client';

import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { Check, ExternalLink } from 'lucide-react';
import { stripe, tenants, auth, type Tenant, type User } from '@/lib/api';
import { useT } from '@/i18n/LocaleProvider';
import styles from './billing.module.css';

interface Plan {
  plan_id: string;
  name: string;
  description: string;
  price_eur_cents: number;
  price_display: string;
  features: Record<string, string>;
}

const PLAN_ORDER = ['atelier', 'manufacture', 'maison'];

export default function BillingPage() {
  const { t: tr, locale: loc } = useT();

  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([tenants.me(), auth.me(), stripe.plans()])
      .then(([tn, u, p]) => {
        setTenant(tn);
        setUser(u);
        setPlans(p.plans);
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleCheckout(planId: string) {
    if (!tenant || !user) return;
    setCheckoutLoading(planId);
    try {
      const { checkout_url } = await stripe.checkout({
        plan_id: planId,
        email: user.email,
        tenant_id: tenant.id,
        locale: loc || 'fr',
      });
      window.location.href = checkout_url;
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : tr('common.error'));
      setCheckoutLoading(null);
    }
  }

  if (loading || !tenant) return <div className={styles.skeleton} />;

  const trialDays = tenant.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(tenant.trial_ends_at).getTime() - Date.now()) / 86400000))
    : 0;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>{tr('billing.eyebrow')}</p>
        <h1 className={styles.title}>{tr('billing.title')}</h1>
      </header>

      <section className={styles.currentPlan}>
        <div className={styles.currentBadge}>{tr('billing.currentPlan')}</div>
        <h2 className={styles.currentName}>{tenant.plan.charAt(0).toUpperCase() + tenant.plan.slice(1)}</h2>
        <div className={styles.currentStatus}>
          {tr('billing.status')} : <span className={styles[`status_${tenant.subscription_status}`]}>{tenant.subscription_status}</span>
        </div>
        {tenant.subscription_status === 'trialing' && (
          <p className={styles.trialInfo}>
            {tr('billing.trialInfo', { days: trialDays, plural: trialDays > 1 ? 's' : '' })}
          </p>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{tr('billing.availablePlans')}</h2>
        <div className={styles.plansGrid}>
          {plans
            .sort((a, b) => PLAN_ORDER.indexOf(a.plan_id) - PLAN_ORDER.indexOf(b.plan_id))
            .map((plan) => {
              const isCurrent = tenant.plan === plan.plan_id && tenant.subscription_status === 'active';
              const isFeatured = plan.plan_id === 'manufacture';

              return (
                <div
                  key={plan.plan_id}
                  className={`${styles.planCard} ${isFeatured ? styles.planFeatured : ''} ${isCurrent ? styles.planCurrent : ''}`}
                >
                  {isFeatured && <div className={styles.badge}>{tr('billing.popular')}</div>}

                  <div className={styles.planTier}>{plan.name}</div>
                  <div className={styles.planPrice}>
                    {plan.price_display.split('/')[0]}
                    <span>{tr('billing.perMonth')}</span>
                  </div>
                  <p className={styles.planDesc}>{plan.description}</p>

                  <ul className={styles.features}>
                    <li><Check size={14} /> Agents : {plan.features.agents_limit}</li>
                    <li><Check size={14} /> Secteurs : {plan.features.sectors_limit}</li>
                    <li><Check size={14} /> Exec. : {plan.features.executions_limit}</li>
                    <li><Check size={14} /> Support : {plan.features.support_level?.replace(/_/g, ' ')}</li>
                    {plan.features.chatbot === 'true' && <li><Check size={14} /> Chatbot white-label</li>}
                  </ul>

                  {isCurrent ? (
                    <button className={styles.btnCurrent} disabled>{tr('billing.currentBadge')}</button>
                  ) : (
                    <button
                      className={styles.btnSelect}
                      onClick={() => handleCheckout(plan.plan_id)}
                      disabled={checkoutLoading === plan.plan_id}
                    >
                      {checkoutLoading === plan.plan_id ? tr('billing.checkoutRedirect') : (
                        <>
                          {tr('billing.selectPlan')} {plan.name}
                          <ExternalLink size={14} />
                        </>
                      )}
                    </button>
                  )}
                </div>
              );
            })}
        </div>
      </section>
    </div>
  );
}
