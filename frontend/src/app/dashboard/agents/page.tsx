'use client';

import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { Check, Plus, Lock } from 'lucide-react';
import { agents, tenants, type Agent, type TenantAgent, type Tenant } from '@/lib/api';
import { useT } from '@/i18n/LocaleProvider';
import styles from './agents.module.css';

const PLAN_LEVEL: Record<string, number> = { atelier: 1, manufacture: 2, maison: 3 };

export default function AgentsPage() {
  const { t } = useT();
  const [catalog, setCatalog] = useState<Agent[]>([]);
  const [myAgents, setMyAgents] = useState<TenantAgent[]>([]);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [sectorFilter, setSectorFilter] = useState<string>('all');
  const [activatingId, setActivatingId] = useState<string | null>(null);

  async function refresh() {
    const [c, m, tn] = await Promise.all([agents.catalog(), agents.mine(), tenants.me()]);
    setCatalog(c);
    setMyAgents(m);
    setTenant(tn);
  }

  useEffect(() => { refresh().finally(() => setLoading(false)); }, []);

  async function handleActivate(agentId: string) {
    setActivatingId(agentId);
    try {
      await agents.activate(agentId);
      toast.success(t('agents.toastActivated'));
      await refresh();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('common.error'));
    } finally { setActivatingId(null); }
  }

  async function handleToggle(ta: TenantAgent) {
    try {
      await agents.update(ta.id, { is_enabled: !ta.is_enabled });
      toast.success(ta.is_enabled ? t('agents.toastDeactivated') : t('agents.toastActivated'));
      await refresh();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('common.error'));
    }
  }

  async function handleRemove(ta: TenantAgent) {
    if (!confirm(t('agents.removeConfirm', { name: ta.agent.name }))) return;
    try {
      await agents.deactivate(ta.id);
      toast.success(t('agents.toastRemoved'));
      await refresh();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('common.error'));
    }
  }

  if (loading || !tenant) return <div className={styles.skeleton} />;

  const activeAgentIds = new Set(myAgents.map((a) => a.agent.id));
  const sectors = ['all', ...Array.from(new Set(catalog.map((a) => a.sector)))];
  const filteredCatalog = sectorFilter === 'all' ? catalog : catalog.filter((a) => a.sector === sectorFilter);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>{t('agents.eyebrow')}</p>
        <h1 className={styles.title}>{t('agents.title')}</h1>
        <p className={styles.desc}>{t('agents.description')}</p>
      </header>

      {myAgents.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>{t('agents.yourActive')} ({myAgents.length})</h2>
          <div className={styles.grid}>
            {myAgents.map((ta) => (
              <div key={ta.id} className={`${styles.card} ${styles.cardActive}`}>
                <div className={styles.cardHeader}>
                  <div className={styles.cardName}>{ta.agent.name}</div>
                  <button
                    className={`${styles.toggle} ${ta.is_enabled ? styles.toggleOn : ''}`}
                    onClick={() => handleToggle(ta)}
                    aria-label="Toggle"
                  />
                </div>
                <p className={styles.cardDesc}>{ta.agent.description}</p>
                <div className={styles.cardFooter}>
                  <span className={styles.sectorTag}>{t(`agents.sectors.${ta.agent.sector}`)}</span>
                  <button className={styles.btnRemove} onClick={() => handleRemove(ta)}>
                    {t('agents.remove')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t('agents.catalogFull')}</h2>
          <div className={styles.filters}>
            {sectors.map((s) => (
              <button
                key={s}
                className={`${styles.filter} ${sectorFilter === s ? styles.filterActive : ''}`}
                onClick={() => setSectorFilter(s)}
              >
                {s === 'all' ? t('agents.filterAll') : t(`agents.sectors.${s}`)}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.grid}>
          {filteredCatalog.map((agent) => {
            const alreadyActive = activeAgentIds.has(agent.id);
            const planOk = PLAN_LEVEL[tenant.plan] >= PLAN_LEVEL[agent.min_plan];

            return (
              <div key={agent.id} className={styles.card}>
                <div className={styles.cardHeader}>
                  <div className={styles.cardName}>{agent.name}</div>
                  {!planOk && <Lock size={16} className={styles.lockIcon} />}
                </div>
                <p className={styles.cardDesc}>{agent.description}</p>
                <div className={styles.cardFooter}>
                  <span className={styles.sectorTag}>{t(`agents.sectors.${agent.sector}`)}</span>
                  {alreadyActive ? (
                    <span className={styles.activeBadge}>
                      <Check size={14} /> {t('agents.activated')}
                    </span>
                  ) : !planOk ? (
                    <span className={styles.planLocked}>{t('agents.requiresPlan', { plan: agent.min_plan })}</span>
                  ) : (
                    <button
                      className={styles.btnActivate}
                      onClick={() => handleActivate(agent.id)}
                      disabled={activatingId === agent.id}
                    >
                      <Plus size={14} />
                      {activatingId === agent.id ? t('agents.activating') : t('agents.activate')}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
