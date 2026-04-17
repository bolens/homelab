import { Link } from '@tanstack/react-router';
import React, { useEffect, useState } from 'react';
import { apiUrl } from '../apiBase';
import { IconDownload } from '../components/icons/UiIcons';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetchErrorFromText, buildAdminBrowserAuthHeaders } from '../http';
import { useT } from '../i18n/I18nContext';
import { Button, Notice, PageHeader, SectionPanel, cx } from '../ui';
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
      <Notice tone='error' className='asking-admin-page__error'>
        {t('admin.export.accessDenied')}
      </Notice>
    );
  }

  return (
    <div className='asking-admin-shell asking-admin-export-page asking-admin-page__cq-root' id='asking-admin-export-page'>
      <PageHeader
        className='asking-admin-page__header'
        titleId='asking-admin-export-page__title'
        titleClassName='asking-admin-page__title'
        subtitleClassName='asking-admin-page__subtitle'
        title={t('admin.export.title')}
        subtitle={t('admin.export.subtitle')}
      />

      <p className='asking-admin-export-page__intro'>{t('admin.export.intro')}</p>
      <p className='asking-admin-export-page__flow-hint asking-admin-page__help-text'>{t('admin.export.flowHint')}</p>

      {error ? (
        <Notice tone='error' className='asking-admin-page__banner-error'>
          {error}
        </Notice>
      ) : null}

      {successFile ? (
        <Notice tone='success' className='asking-admin-export-page__success' aria-live='polite'>
          <span className='asking-admin-export-page__success-text'>
            {t('admin.exportDone', { file: successFile })}
          </span>
          <Button
            type='button'
            variant='secondary'
            className='asking-admin-page__btn asking-admin-page__dismiss-btn'
            onClick={() => setSuccessFile(null)}
          >
            {t('admin.export.dismissNotice')}
          </Button>
        </Notice>
      ) : null}

      <SectionPanel
        className='asking-admin-page__section'
        titleId='asking-admin-export-page__datasets-heading'
        title={<span className='asking-admin-page__section-title'>{t('admin.export.sectionTitle')}</span>}
      >
        <div className='asking-admin-page__card-stack'>
          {EXPORT_ROWS.map((row) => {
            const title = t(row.titleKey);
            const csvName = datedExportBasename(row.fileBase, 'csv');
            const jsonName = datedExportBasename(row.fileBase, 'json');
            const csvBusy = Boolean(busy[row.busyCsv]);
            const jsonBusy = Boolean(busy[row.busyJson]);
            return (
              <article key={row.pathBase} className='asking-admin-page__card'>
                <div className='asking-admin-page__card-text'>
                  <h3 className='asking-admin-page__card-title' id={`asking-admin-export-page__dataset-${row.fileBase}-title`}>
                    {title}
                  </h3>
                  <p className='asking-admin-page__card-desc'>{t(row.descKey)}</p>
                  {row.showBrowseAudit ? (
                    <p className='asking-admin-page__card-meta'>
                      <Link
                        to='/admin/audit-logs'
                        search={{ limit: undefined }}
                        className='asking-admin-page__jump-link'
                      >
                        {t('admin.export.viewInApp')}
                      </Link>
                    </p>
                  ) : null}
                </div>
                <div
                  className='asking-admin-page__card-actions'
                  role='group'
                  aria-labelledby={`asking-admin-export-page__dataset-${row.fileBase}-title`}
                >
                  <Button
                    type='button'
                    variant='secondary'
                    className={cx(
                      'asking-admin-page__btn',
                      'asking-admin-page__download-btn',
                      csvBusy && 'asking-admin-page__download-btn--busy',
                    )}
                    disabled={csvBusy}
                    aria-busy={csvBusy}
                    aria-label={t('admin.export.ariaDownload', {
                      dataset: title,
                      format: t('admin.export.formatCsv'),
                    })}
                    onClick={() => void run(row.busyCsv, `${row.pathBase}?format=csv`, csvName)}
                  >
                    <IconDownload className='asking-admin-page__download-icon' aria-hidden />
                    {csvBusy ? t('admin.exporting') : t('admin.export.formatCsv')}
                  </Button>
                  <Button
                    type='button'
                    variant='secondary'
                    className={cx(
                      'asking-admin-page__btn',
                      'asking-admin-page__download-btn',
                      jsonBusy && 'asking-admin-page__download-btn--busy',
                    )}
                    disabled={jsonBusy}
                    aria-busy={jsonBusy}
                    aria-label={t('admin.export.ariaDownload', {
                      dataset: title,
                      format: t('admin.export.formatJson'),
                    })}
                    onClick={() => void run(row.busyJson, `${row.pathBase}?format=json`, jsonName)}
                  >
                    <IconDownload className='asking-admin-page__download-icon' aria-hidden />
                    {jsonBusy ? t('admin.exporting') : t('admin.export.formatJson')}
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      </SectionPanel>
    </div>
  );
}
