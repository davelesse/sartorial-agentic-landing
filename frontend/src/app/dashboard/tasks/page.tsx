'use client';

import { useEffect, useState } from 'react';
import { tasks, type Task } from '@/lib/api';
import { useT } from '@/i18n/LocaleProvider';
import styles from './tasks.module.css';

export default function TasksPage() {
  const { t } = useT();
  const [items, setItems] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Task | null>(null);

  const pageSize = 20;

  const STATUS_OPTIONS = [
    { value: '',          label: t('tasks.filterAll') },
    { value: 'pending',   label: t('tasks.filterPending') },
    { value: 'running',   label: t('tasks.filterRunning') },
    { value: 'completed', label: t('tasks.filterCompleted') },
    { value: 'failed',    label: t('tasks.filterFailed') },
  ];

  useEffect(() => {
    setLoading(true);
    tasks.list({ status: statusFilter || undefined, page, page_size: pageSize })
      .then(({ items, total }) => { setItems(items); setTotal(total); })
      .finally(() => setLoading(false));
  }, [page, statusFilter]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>{t('tasks.eyebrow')}</p>
        <h1 className={styles.title}>{t('tasks.title')}</h1>
      </header>

      <div className={styles.filters}>
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            className={`${styles.filter} ${statusFilter === opt.value ? styles.filterActive : ''}`}
            onClick={() => { setStatusFilter(opt.value); setPage(1); }}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className={styles.loadingRow}>{t('common.loading')}</div>
      ) : items.length === 0 ? (
        <div className={styles.empty}>{t('tasks.empty')}</div>
      ) : (
        <>
          <div className={styles.table}>
            <div className={styles.thead}>
              <div>{t('tasks.colId')}</div>
              <div>{t('tasks.colDate')}</div>
              <div>{t('tasks.colStatus')}</div>
              <div>{t('tasks.colTokens')}</div>
              <div>{t('tasks.colCost')}</div>
              <div></div>
            </div>
            {items.map((task) => (
              <div key={task.id} className={styles.row} onClick={() => setSelected(task)}>
                <div className={styles.idCell}>#{task.id.slice(0, 8)}</div>
                <div>{new Date(task.created_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}</div>
                <div className={`${styles.status} ${styles[`status${task.status.charAt(0).toUpperCase() + task.status.slice(1)}`]}`}>
                  {task.status}
                </div>
                <div>{task.tokens_used.toLocaleString()}</div>
                <div>{(task.cost_cents / 100).toFixed(3)} €</div>
                <div className={styles.arrow}>›</div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className={styles.pagination}>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>‹ {t('common.previous')}</button>
              <span>{t('tasks.pageOf', { page, total: totalPages })}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>{t('common.next')} ›</button>
            </div>
          )}
        </>
      )}

      {selected && (
        <div className={styles.modalOverlay} onClick={() => setSelected(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <button className={styles.modalClose} onClick={() => setSelected(null)}>×</button>
            <h3>{t('tasks.detailsTitle', { id: selected.id.slice(0, 8) })}</h3>
            <dl className={styles.details}>
              <dt>{t('tasks.detailStatus')}</dt><dd>{selected.status}</dd>
              <dt>{t('tasks.detailCreated')}</dt><dd>{new Date(selected.created_at).toLocaleString()}</dd>
              {selected.started_at && (<><dt>{t('tasks.detailStarted')}</dt><dd>{new Date(selected.started_at).toLocaleString()}</dd></>)}
              {selected.completed_at && (<><dt>{t('tasks.detailCompleted')}</dt><dd>{new Date(selected.completed_at).toLocaleString()}</dd></>)}
              <dt>{t('tasks.detailTokens')}</dt><dd>{selected.tokens_used}</dd>
              <dt>{t('tasks.detailCost')}</dt><dd>{(selected.cost_cents / 100).toFixed(4)} €</dd>
            </dl>

            <h4>{t('tasks.detailInput')}</h4>
            <pre className={styles.code}>{JSON.stringify(selected.input_data, null, 2)}</pre>

            {selected.output_data && Object.keys(selected.output_data).length > 0 && (
              <>
                <h4>{t('tasks.detailOutput')}</h4>
                <pre className={styles.code}>{JSON.stringify(selected.output_data, null, 2)}</pre>
              </>
            )}

            {selected.error_message && (
              <>
                <h4 className={styles.errorLabel}>{t('tasks.detailError')}</h4>
                <pre className={`${styles.code} ${styles.codeError}`}>{selected.error_message}</pre>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
