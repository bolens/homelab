import { Link } from '@tanstack/react-router';
import React, { useEffect, useState } from 'react';
import { apiUrl } from '../apiBase';
import { IconDownload } from '../components/icons/UiIcons';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetchErrorFromText, buildAdminBrowserAuthHeaders } from '../http';
import { useT } from '../i18n/I18nContext';
import { Button, cx } from '../ui';
import { errMsg } from '../utils/errMsg';

async function downloadExport(path: string, filename: string): Promise<void> {
  const normalized = path.replace(/^\/+/, '');
  const url = apiUrl(normalized);
  const res = await fetch(url, { headers: buildAdminBrowserAuthHeaders() });
  if (!res.ok) {
    const raw = await res.text();
    throw apiFetchErrorFromText(res.status, raw);
  }
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  }, 100);
}

function datedExportBasename(base: string, ext: string): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${base}-${y}-${m}-${day}.${ext}`;
}

type ExportBusyKey =
  | 'users-csv'
  | 'users-json'
  | 'polls-csv'
  | 'polls-json'
  | 'audit-csv'
  | 'audit-json';

type ExportRowConfig = {
  busyCsv: ExportBusyKey;
  busyJson: ExportBusyKey;
  pathBase: string;
  fileBase: string;
  titleKey: 'admin.export.usersTitle' | 'admin.export.pollsTitle' | 'admin.export.auditTitle';
  descKey: 'admin.export.usersDesc' | 'admin.export.pollsDesc' | 'admin.export.auditDesc';
  showBrowseAudit?: boolean;
};

const EXPORT_ROWS: ExportRowConfig[] = [
  {
    busyCsv: 'users-csv',
    busyJson: 'users-json',
    pathBase: 'admin/export/users',
    fileBase: 'users',
    titleKey: 'admin.export.usersTitle',
    descKey: 'admin.export.usersDesc',
  },
  {
    busyCsv: 'polls-csv',
    busyJson: 'polls-json',
    pathBase: 'admin/export/polls',
    fileBase: 'polls',
    titleKey: 'admin.export.pollsTitle',
    descKey: 'admin.export.pollsDesc',
  },
  {
    busyCsv: 'audit-csv',
    busyJson: 'audit-json',
    pathBase: 'admin/export/audit-logs',
    fileBase: 'audit_logs',
    titleKey: 'admin.export.auditTitle',
    descKey: 'admin.export.auditDesc',
    showBrowseAudit: true,
  },
];

export default function AdminExport() {
  const t = useT();
  useDocumentTitle(t('admin.docTitleExport'));
  const { admin } = useAdmin();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<Partial<Record<ExportBusyKey, boolean>>>({});
  const [successFile, setSuccessFile] = useState<string | null>(null);

  useEffect(() => {
    if (!successFile) return;
    const id = window.setTimeout(() => setSuccessFile(null), 10_000);
    return () => window.clearTimeout(id);
  }, [successFile]);

  const run = async (key: ExportBusyKey, path: string, filename: string) => {
    setError('');
    setBusy((b) => ({ ...b, [key]: true }));
    try {
      await downloadExport(path, filename);
      setSuccessFile(filename);
    } catch (err: unknown) {
      setError(errMsg(err, t('admin.exportErr')));
    } finally {
      setBusy((b) => {
        const next = { ...b };
        delete next[key];
        return next;
      });
    }
  };

  if (!admin || (admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return (
      <div className='polls-page-container-error' role='alert'>
        {t('admin.export.accessDenied')}
      </div>
    );
  }

  return (
    <div className='admin-users-container admin-export-page'>
      <header className='admin-page-header'>
        <h1 className='admin-page-title'>{t('admin.export.title')}</h1>
        <p className='admin-page-subtitle'>{t('admin.export.subtitle')}</p>
      </header>

      <p className='admin-export-intro'>{t('admin.export.intro')}</p>
      <p className='admin-export-flow-hint admin-help-text'>{t('admin.export.flowHint')}</p>

      {error ? (
        <div className='admin-banner-error' role='alert'>
          {error}
        </div>
      ) : null}

      {successFile ? (
        <div className='admin-export-success' role='status' aria-live='polite'>
          <span className='admin-export-success-text'>
            {t('admin.exportDone', { file: successFile })}
          </span>
          <Button
            type='button'
            variant='secondary'
            className='admin-users-btn admin-export-dismiss'
            onClick={() => setSuccessFile(null)}
          >
            {t('admin.export.dismissNotice')}
          </Button>
        </div>
      ) : null}

      <section className='admin-export-section' aria-labelledby='admin-export-datasets-heading'>
        <h2 id='admin-export-datasets-heading' className='admin-export-section-title'>
          {t('admin.export.sectionTitle')}
        </h2>
        <div className='admin-export-card-stack'>
          {EXPORT_ROWS.map((row) => {
            const title = t(row.titleKey);
            const csvName = datedExportBasename(row.fileBase, 'csv');
            const jsonName = datedExportBasename(row.fileBase, 'json');
            const csvBusy = Boolean(busy[row.busyCsv]);
            const jsonBusy = Boolean(busy[row.busyJson]);
            return (
              <article key={row.pathBase} className='admin-export-card'>
                <div className='admin-export-card-text'>
                  <h3 className='admin-export-card-title'>{title}</h3>
                  <p className='admin-export-card-desc'>{t(row.descKey)}</p>
                  {row.showBrowseAudit ? (
                    <p className='admin-export-card-meta'>
                      <Link
                        to='/admin/audit-logs'
                        search={{ limit: undefined }}
                        className='admin-jump-link'
                      >
                        {t('admin.export.viewInApp')}
                      </Link>
                    </p>
                  ) : null}
                </div>
                <div className='admin-export-card-actions' role='group' aria-label={title}>
                  <Button
                    type='button'
                    variant='secondary'
                    className={cx(
                      'admin-users-btn',
                      'admin-export-dl-btn',
                      csvBusy && 'admin-export-dl-btn--busy',
                    )}
                    disabled={csvBusy}
                    aria-busy={csvBusy}
                    aria-label={t('admin.export.ariaDownload', {
                      dataset: title,
                      format: t('admin.export.formatCsv'),
                    })}
                    onClick={() => void run(row.busyCsv, `${row.pathBase}?format=csv`, csvName)}
                  >
                    <IconDownload className='admin-export-dl-icon' aria-hidden />
                    {csvBusy ? t('admin.exporting') : t('admin.export.formatCsv')}
                  </Button>
                  <Button
                    type='button'
                    variant='secondary'
                    className={cx(
                      'admin-users-btn',
                      'admin-export-dl-btn',
                      jsonBusy && 'admin-export-dl-btn--busy',
                    )}
                    disabled={jsonBusy}
                    aria-busy={jsonBusy}
                    aria-label={t('admin.export.ariaDownload', {
                      dataset: title,
                      format: t('admin.export.formatJson'),
                    })}
                    onClick={() => void run(row.busyJson, `${row.pathBase}?format=json`, jsonName)}
                  >
                    <IconDownload className='admin-export-dl-icon' aria-hidden />
                    {jsonBusy ? t('admin.exporting') : t('admin.export.formatJson')}
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
