'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Cpu, ListChecks, Zap, TrendingUp, ArrowRight } from 'lucide-react';
import { agents, tasks, tenants, type Tenant, type TenantAgent, type Task } from '@/lib/api';
import { useT } from '@/i18n/LocaleProvider';
import styles from './overview.module.css';

const PLAN_LIMITS: Record<string, number> = {
  atelier: 500,
  manufacture: 2500,
  maison: -1,
};

export default function DashboardPage() {
  const { t: tr } = useT();
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [myAgents, setMyAgents] = useState<TenantAgent[]>([]);
  const [recentTasks, setRecentTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      tenants.me().catch(() => null),
      agents.mine().catch(() => [] as TenantAgent[]),
      tasks.list({ page_size: 5 }).catch(() => ({ items: [] as Task[] })),
    ])
      .then(([t, a, tk]) => {
        if (t) setTenant(t);
        setMyAgents(a);
        setRecentTasks(tk.items);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading || !tenant) return <div className={styles.skeleton} />;

  const limit = PLAN_LIMITS[tenant.plan] ?? 0;
  const usagePct = limit > 0 ? Math.min(100, (tenant.executions_used / limit) * 100) : 0;
  const activeAgents = myAgents.filter((a) => a.is_enabled).length;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>{tr('dashboard.overview')}</p>
          <h1 className={styles.title}>
            {tr('dashboard.greeting', { name: '' }).replace(', ', '')}, <em>{tenant.name}</em>
          </h1>
        </div>
      </header>

      <section className={styles.statsGrid}>
        <div className={styles.statCard}>
          <div className={styles.statIcon}><Cpu size={20} /></div>
          <div className={styles.statValue}>{activeAgents}</div>
          <div className={styles.statLabel}>{tr('dashboard.statsActiveAgents')}</div>
        </div>

        <div className={styles.statCard}>
          <div className={styles.statIcon}><ListChecks size={20} /></div>
          <div className={styles.statValue}>{tenant.executions_used}</div>
          <div className={styles.statLabel}>
            {tr('dashboard.statsExecutionsMonth')}
            {limit > 0 && <span> · {tr('dashboard.statsExecutionsOf')} {limit.toLocaleString()}</span>}
            {limit === -1 && <span> · {tr('dashboard.statsUnlimited')}</span>}
          </div>
          {limit > 0 && (
            <div className={styles.progressBar}>
              <div className={styles.progressFill} style={{ width: `${usagePct}%` }} />
            </div>
          )}
        </div>

        <div className={styles.statCard}>
          <div className={styles.statIcon}><Zap size={20} /></div>
          <div className={styles.statValue}>{recentTasks.filter(t => t.status === 'running').length}</div>
          <div className={styles.statLabel}>{tr('dashboard.statsRunning')}</div>
        </div>

        <div className={styles.statCard}>
          <div className={styles.statIcon}><TrendingUp size={20} /></div>
          <div className={styles.statValue}>{recentTasks.filter(t => t.status === 'completed').length}</div>
          <div className={styles.statLabel}>{tr('dashboard.statsCompleted')}</div>
        </div>
      </section>

      {activeAgents === 0 && (
        <section className={styles.emptyState}>
          <div className={styles.emptyIcon}>◆</div>
          <h2 className={styles.emptyTitle}>{tr('dashboard.emptyFirstAgent')}</h2>
          <p className={styles.emptyDesc}>{tr('dashboard.emptyDesc')}</p>
          <Link href="/dashboard/agents" className={styles.btnPrimary}>
            {tr('dashboard.emptyCTA')} <ArrowRight size={16} />
          </Link>
        </section>
      )}

      {recentTasks.length > 0 && (
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>{tr('dashboard.recentExecutions')}</h2>
            <Link href="/dashboard/tasks" className={styles.linkAll}>
              {tr('dashboard.viewAll')} <ArrowRight size={14} />
            </Link>
          </div>
          <div className={styles.taskList}>
            {recentTasks.map((task) => (
              <div key={task.id} className={styles.taskRow}>
                <div className={styles.taskInfo}>
                  <div className={styles.taskId}>#{task.id.slice(0, 8)}</div>
                  <div className={styles.taskDate}>
                    {new Date(task.created_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}
                  </div>
                </div>
                <div className={`${styles.taskStatus} ${styles[`status${task.status.charAt(0).toUpperCase() + task.status.slice(1)}`]}`}>
                  {task.status}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {myAgents.length > 0 && (
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>{tr('dashboard.yourAgents')}</h2>
            <Link href="/dashboard/agents" className={styles.linkAll}>
              {tr('dashboard.manage')} <ArrowRight size={14} />
            </Link>
          </div>
          <div className={styles.agentGrid}>
            {myAgents.slice(0, 3).map((ta) => (
              <div key={ta.id} className={styles.agentCard}>
                <div className={styles.agentName}>{ta.agent.name}</div>
                <div className={styles.agentDesc}>{ta.agent.description}</div>
                <div className={styles.agentMeta}>
                  <span className={styles.sectorTag}>{tr(`agents.sectors.${ta.agent.sector}`)}</span>
                  <span className={ta.is_enabled ? styles.statusOn : styles.statusOff}>
                    {ta.is_enabled ? tr('dashboard.active') : tr('dashboard.inactive')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
