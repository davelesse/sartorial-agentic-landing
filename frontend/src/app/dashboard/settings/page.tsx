'use client';

import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { tenants, type Tenant } from '@/lib/api';
import { useT } from '@/i18n/LocaleProvider';
import styles from './settings.module.css';

const SECTOR_KEYS = ['automobile', 'immobilier', 'ecommerce', 'beaute', 'sante', 'restauration'];

export default function SettingsPage() {
  const { t } = useT();
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [name, setName] = useState('');
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    tenants.me().then((tn) => {
      setTenant(tn);
      setName(tn.name);
      setSelectedSectors(tn.sectors);
    });
  }, []);

  function toggleSector(s: string) {
    setSelectedSectors((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await tenants.update({ name, sectors: selectedSectors });
      setTenant(updated);
      toast.success(t('settings.saveSuccess'));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('common.error'));
    } finally {
      setSaving(false);
    }
  }

  if (!tenant) return <div className={styles.skeleton} />;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>{t('settings.eyebrow')}</p>
        <h1 className={styles.title}>{t('settings.title')}</h1>
      </header>

      <section className={styles.card}>
        <h2 className={styles.cardTitle}>{t('settings.workshopInfo')}</h2>

        <div className={styles.field}>
          <label>{t('settings.workshopName')}</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className={styles.field}>
          <label>{t('settings.slug')}</label>
          <input type="text" value={tenant.slug} disabled />
          <p className={styles.hint}>{t('settings.slugHint')}</p>
        </div>
      </section>

      <section className={styles.card}>
        <h2 className={styles.cardTitle}>{t('settings.sectorsTitle')}</h2>
        <p className={styles.cardDesc}>{t('settings.sectorsDesc')}</p>
        <div className={styles.sectorGrid}>
          {SECTOR_KEYS.map((s) => {
            const selected = selectedSectors.includes(s);
            return (
              <button
                key={s}
                className={`${styles.sectorChip} ${selected ? styles.sectorSelected : ''}`}
                onClick={() => toggleSector(s)}
              >
                {t(`agents.sectors.${s}`)}
              </button>
            );
          })}
        </div>
      </section>

      <div className={styles.actions}>
        <button className={styles.btnSave} onClick={handleSave} disabled={saving}>
          {saving ? t('settings.saving') : t('settings.saveBtn')}
        </button>
      </div>
    </div>
  );
}
