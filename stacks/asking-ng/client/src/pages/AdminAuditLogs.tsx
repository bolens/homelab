import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { type ColumnDef, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import React, { useEffect, useMemo, useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import { formatLocaleDateTime } from '../lib/formatLocaleDisplay';
import { adminAuditLogsQueryKey } from '../lib/queryKeys';
import { Button, Notice, PageHeader, SectionPanel } from '../ui';
import { errMsg } from '../utils/errMsg';

type AuditLogRow = {
  id: string | number;
  action: string;
  actor: string;
  target: string;
  createdAt: string;
};

function buildAuditUrl(
  action: string,
  actor: string,
  target: string,
  start: string,
  end: string,
  limit: string,
): string {
  let url = 'admin/audit-logs?';
  if (action) url += `action=${encodeURIComponent(action)}&`;
  if (actor) url += `actor=${encodeURIComponent(actor)}&`;
  if (target) url += `target=${encodeURIComponent(target)}&`;
  if (start) url += `start=${encodeURIComponent(start)}&`;
  if (end) url += `end=${encodeURIComponent(end)}&`;
  if (limit.trim()) url += `limit=${encodeURIComponent(limit.trim())}&`;
  return url;
}

export default function AdminAuditLogs() {
  const t = useT();
  const localeTag = useLocaleTag();
  useDocumentTitle(t('admin.docTitleAudit'));
  const { admin } = useAdmin();
  const search = useSearch({ from: '/admin/audit-logs', strict: true });
  const navigate = useNavigate({ from: '/admin/audit-logs' });
  const [action, setAction] = useState(() => search.action ?? '');
  const [actor, setActor] = useState(() => search.actor ?? '');
  const [target, setTarget] = useState(() => search.target ?? '');
  const [start, setStart] = useState(() => search.start ?? '');
  const [end, setEnd] = useState(() => search.end ?? '');
  const [limit, setLimit] = useState(() => String(search.limit ?? ''));

  const appliedAction = search.action ?? '';
  const appliedActor = search.actor ?? '';
  const appliedTarget = search.target ?? '';
  const appliedStart = search.start ?? '';
  const appliedEnd = search.end ?? '';
  const appliedLimit = String(search.limit ?? '');

  useEffect(() => {
    setAction(search.action ?? '');
    setActor(search.actor ?? '');
    setTarget(search.target ?? '');
    setStart(search.start ?? '');
    setEnd(search.end ?? '');
    setLimit(String(search.limit ?? ''));
  }, [search.action, search.actor, search.target, search.start, search.end, search.limit]);

  const canView = !!(admin && (admin.role === 'admin' || admin.role === 'superadmin'));

  const { data, error, isFetching } = useQuery({
    queryKey: adminAuditLogsQueryKey(
      appliedAction,
      appliedActor,
      appliedTarget,
      appliedStart,
      appliedEnd,
      appliedLimit,
    ),
    queryFn: async (): Promise<AuditLogRow[]> => {
      const json = (await apiFetch(
        buildAuditUrl(
          appliedAction,
          appliedActor,
          appliedTarget,
          appliedStart,
          appliedEnd,
          appliedLimit,
        ),
      )) as { logs?: AuditLogRow[] };
      return json.logs ?? [];
    },
    enabled: canView,
  });

  const logs = data ?? [];

  const columns = useMemo<ColumnDef<AuditLogRow>[]>(
    () => [
      { accessorKey: 'id', header: t('admin.audit.colId') },
      { accessorKey: 'action', header: t('admin.audit.colAction') },
      { accessorKey: 'actor', header: t('admin.audit.colActor') },
      { accessorKey: 'target', header: t('admin.audit.colTarget') },
      {
        accessorKey: 'createdAt',
        header: t('admin.audit.colTime'),
        cell: ({ getValue }) => formatLocaleDateTime(getValue(), localeTag),
      },
    ],
    [t, localeTag],
  );

  const table = useReactTable({
    data: logs,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const loadError = error ? errMsg(error, t('admin.audit.errLoad')) : '';

  const applyFilters = () => {
    void navigate({
      to: '/admin/audit-logs',
      search: {
        action: action || undefined,
        actor: actor || undefined,
        target: target || undefined,
        start: start || undefined,
        end: end || undefined,
        limit: (() => {
          const lim = limit.trim();
          if (!lim) return undefined;
          const n = Number.parseInt(lim, 10);
          return Number.isFinite(n) ? n : undefined;
        })(),
      },
    });
  };

  if (!admin || (admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return (
      <Notice tone='error' className='asking-admin-page__error'>
        {t('admin.audit.accessDenied')}
      </Notice>
    );
  }

  return (
    <div className='asking-admin-page asking-admin-audit-page asking-admin-page__cq-root' id='asking-admin-audit-page'>
      <PageHeader
        className='asking-admin-page__header'
        titleId='asking-admin-audit-page__title'
        titleClassName='asking-admin-page__title'
        subtitleClassName='asking-admin-page__subtitle'
        title={t('admin.audit.heading')}
        subtitle={t('admin.audit.intro')}
      />
      <SectionPanel
        className='asking-admin-page__section'
        titleId='asking-admin-audit-page__filters-heading'
        title={<span className='asking-admin-page__section-title'>{t('admin.audit.filter')}</span>}
      >
        <div className='asking-admin-audit-page__filter-form' id='asking-admin-audit-page__filter-form'>
          <input
            placeholder={t('admin.audit.placeholderAction')}
            value={action}
            onChange={(e) => setAction(e.target.value)}
            aria-label={t('admin.audit.filterAction')}
          />
          <input
            placeholder={t('admin.audit.placeholderActor')}
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            aria-label={t('admin.audit.filterActor')}
          />
          <input
            placeholder={t('admin.audit.placeholderTarget')}
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className='asking-admin-audit-page__target-input'
            aria-label={t('admin.audit.filterTarget')}
          />
          <input
            type='date'
            value={start}
            onChange={(e) => setStart(e.target.value)}
            aria-label={t('admin.audit.startDate')}
          />
          <input
            type='date'
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            aria-label={t('admin.audit.endDate')}
          />
          <label className='asking-admin-audit-page__limit-label'>
            {t('admin.audit.limitLabel')}{' '}
            <input
              type='number'
              min={1}
              max={500}
              placeholder={t('admin.audit.placeholderLimit')}
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              className='asking-admin-audit-page__limit-input'
              aria-label={t('admin.audit.limitAria')}
            />
          </label>
          <Button
            type='button'
            variant='secondary'
            className='asking-admin-page__toolbar-btn'
            onClick={applyFilters}
            aria-label={t('admin.audit.filterAria')}
            title={t('admin.audit.filterTitle')}
          >
            {t('admin.audit.filter')}
          </Button>
          {isFetching ? (
            <span className='asking-admin-audit-page__filter-status' role='status' aria-live='polite'>
              {t('admin.audit.loading')}
            </span>
          ) : null}
        </div>
      </SectionPanel>
      {loadError ? (
        <Notice tone='error' className='asking-admin-page__status asking-admin-page__status--error'>
          {loadError}
        </Notice>
      ) : null}
      <SectionPanel
        className='asking-admin-page__section'
        titleId='asking-admin-audit-page__table-heading'
        title={<span className='asking-admin-page__section-title'>{t('admin.audit.heading')}</span>}
      >
        <div className='asking-admin-page__table-wrap'>
          <table className='asking-admin-audit-page__table'>
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th key={header.id} scope='col'>
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {logs.length === 0 && !isFetching ? (
                <tr>
                  <td colSpan={columns.length} className='asking-admin-audit-page__empty-cell'>
                    {t('admin.auditEmpty')}
                  </td>
                </tr>
              ) : null}
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionPanel>
    </div>
  );
}
