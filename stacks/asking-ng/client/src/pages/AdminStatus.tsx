import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import React from 'react';
import { apiUrl } from '../apiBase';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch, summaryFromApiErrorBody } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import { formatLocaleDateTime, formatLocaleInteger } from '../lib/formatLocaleDisplay';
import { formatQuarantineReasonLabel } from '../lib/formatQuarantineReasonLabel';
import {
  adminStatusQueryKey,
  adminVoteGeoQueryKey,
  invalidateAdminStatusSurfaceQueries,
  publicHealthcheckQueryKey,
  publicInfoQueryKey,
  publicReadyQueryKey,
} from '../lib/queryKeys';
import { Button } from '../ui';
import { errMsg } from '../utils/errMsg';

type AdminTrustMetrics = {
  quarantine_pending_total: number;
  quarantine_pending_polls: number;
  quarantine_pending_by_reason: Record<string, number>;
  quarantine_approved_last_24h: number;
  quarantine_rejected_last_24h: number;
  trust_risk_avg_pending: number | null;
  quarantine_pending_account_linked: number;
  votes_account_linked_last_24h: number;
  votes_anonymous_last_24h: number;
};

type AdminStatusPayload = {
  users: { total: number; active: number };
  polls: { total: number; archived: number };
  auditLogs: { last24h: number };
  trustMetrics?: AdminTrustMetrics;
  timestamp: string;
};

type ApiInfoPayload = {
  service: string;
  version: string;
  node?: string;
  environment?: string;
  commit?: string;
};

type JsonProbe = { ok: boolean; status: number; body: Record<string, unknown> };

async function fetchJsonProbe(path: string): Promise<JsonProbe> {
  const res = await fetch(apiUrl(path));
  let body: Record<string, unknown> = {};
  try {
    body = (await res.json()) as Record<string, unknown>;
  } catch {
    /* non-JSON */
  }
  return { ok: res.ok, status: res.status, body };
}

function probeTone(
  pending: boolean,
  queryError: boolean,
  ok: boolean | undefined,
): 'pending' | 'error' | 'ok' | 'bad' {
  if (pending) return 'pending';
  if (queryError) return 'error';
  if (ok === true) return 'ok';
  return 'bad';
}

export default function AdminStatus() {
  const t = useT();
  const localeTag = useLocaleTag();
  useDocumentTitle(t('admin.docTitleStatus'));
  const { admin } = useAdmin();
  const queryClient = useQueryClient();

  const canView = !!(admin && (admin.role === 'mod' || admin.role === 'admin' || admin.role === 'superadmin'));
  const canManageVoteGeo = !!(admin && (admin.role === 'admin' || admin.role === 'superadmin'));

  const statusQuery = useQuery({
    queryKey: adminStatusQueryKey(),
    queryFn: () => apiFetch('admin/status') as Promise<AdminStatusPayload>,
    enabled: canView,
  });

  const apiInfoQuery = useQuery({
    queryKey: publicInfoQueryKey(),
    queryFn: () => apiFetch('info', { adminToken: false }) as Promise<ApiInfoPayload>,
    enabled: canView,
  });

  const healthQuery = useQuery({
    queryKey: publicHealthcheckQueryKey(),
    queryFn: () => fetchJsonProbe('healthcheck'),
    enabled: canView,
  });

  const readyQuery = useQuery({
    queryKey: publicReadyQueryKey(),
    queryFn: () => fetchJsonProbe('ready'),
    enabled: canView,
  });
  const voteGeoQuery = useQuery({
    queryKey: adminVoteGeoQueryKey(),
    queryFn: () => apiFetch('admin/vote-geo') as Promise<{ enabled: boolean }>,
    enabled: canManageVoteGeo,
  });

  const voteGeoMutation = useMutation({
    mutationFn: (enabled: boolean) =>
      apiFetch(enabled ? 'admin/vote-geo/enable' : 'admin/vote-geo/disable', {
        method: 'POST',
      }) as Promise<{ enabled: boolean }>,
    onSuccess: () => {
      invalidateAdminStatusSurfaceQueries(queryClient);
    },
  });

  const status = statusQuery.data ?? null;
  const apiInfo = apiInfoQuery.data ?? null;
  const error = statusQuery.isError ? errMsg(statusQuery.error, t('admin.status.errLoad')) : '';

  const healthFail =
    healthQuery.data && !healthQuery.data.ok
      ? summaryFromApiErrorBody(healthQuery.data.body, healthQuery.data.status)
      : null;
  const readyFail =
    readyQuery.data && !readyQuery.data.ok
      ? summaryFromApiErrorBody(readyQuery.data.body, readyQuery.data.status)
      : null;
  const voteGeoError = voteGeoMutation.isError
    ? errMsg(voteGeoMutation.error, t('admin.status.voteGeoErr'))
    : '';

  const healthTone = probeTone(healthQuery.isPending, healthQuery.isError, healthQuery.data?.ok);
  const readyTone = probeTone(readyQuery.isPending, readyQuery.isError, readyQuery.data?.ok);

  const kpiPlaceholder = statusQuery.isPending ? t('admin.status.pending') : '—';

  const trustReasonRows = React.useMemo(() => {
    const tm = status?.trustMetrics;
    if (!tm) return [];
    return Object.entries(tm.quarantine_pending_by_reason)
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason));
  }, [status?.trustMetrics]);

  if (!admin || (admin.role !== 'mod' && admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return (
      <div className='polls-page-container-error' role='alert'>
        {t('admin.status.accessDenied')}
      </div>
    );
  }

  return (
    <div className='admin-users-container admin-status-page'>
      <header className='admin-page-header'>
        <h1 className='admin-page-title'>{t('admin.status.heading')}</h1>
        <p className='admin-page-subtitle'>{t('admin.status.subtitle')}</p>
      </header>

      {error ? (
        <div className='admin-banner-error' role='alert'>
          {error}
        </div>
      ) : null}

      <div className='admin-export-card-stack admin-status-stack'>
        <section className='admin-status-section' aria-labelledby='admin-status-health-heading'>
          <h2 id='admin-status-health-heading' className='admin-export-section-title'>
            {t('admin.status.sectionHealth')}
          </h2>
          <p className='admin-help-text admin-status-section-hint'>
            {t('admin.status.sectionHealthHint')}
          </p>
          <div className='admin-export-card admin-status-probe-card'>
            <div className='admin-status-probe-grid'>
              <div
                className={`admin-status-probe-tile admin-status-probe-tile--${healthTone}`}
                aria-label={t('admin.status.liveness')}
              >
                <div className='admin-status-probe-head'>
                  <span className='admin-status-probe-name'>{t('admin.status.liveness')}</span>
                  <code className='admin-status-probe-route'>
                    {t('admin.status.livenessRoute')}
                  </code>
                </div>
                <div className='admin-status-probe-value'>
                  {healthQuery.isPending ? (
                    <span className='admin-status-probe-pending'>{t('admin.status.pending')}</span>
                  ) : healthQuery.isError ? (
                    <span className='poll-status-error'>
                      {errMsg(healthQuery.error, t('admin.status.requestFailed'))}
                    </span>
                  ) : healthQuery.data?.ok ? (
                    <span className='poll-status-success'>
                      {t('admin.status.ok', {
                        status: formatLocaleInteger(healthQuery.data.status, localeTag),
                      })}
                    </span>
                  ) : (
                    <span
                      className='poll-status-error'
                      title={t('admin.status.healthUnexpectedTitle')}
                    >
                      {healthFail ??
                        t('admin.status.httpError', {
                          status:
                            healthQuery.data?.status != null
                              ? formatLocaleInteger(healthQuery.data.status, localeTag)
                              : '—',
                        })}
                    </span>
                  )}
                </div>
              </div>
              <div
                className={`admin-status-probe-tile admin-status-probe-tile--${readyTone}`}
                aria-label={t('admin.status.readiness')}
              >
                <div className='admin-status-probe-head'>
                  <span className='admin-status-probe-name'>{t('admin.status.readiness')}</span>
                  <code className='admin-status-probe-route'>
                    {t('admin.status.readinessRoute')}
                  </code>
                </div>
                <div className='admin-status-probe-value'>
                  {readyQuery.isPending ? (
                    <span className='admin-status-probe-pending'>{t('admin.status.pending')}</span>
                  ) : readyQuery.isError ? (
                    <span className='poll-status-error'>
                      {errMsg(readyQuery.error, t('admin.status.requestFailed'))}
                    </span>
                  ) : readyQuery.data?.ok ? (
                    <span className='poll-status-success'>
                      {t('admin.status.ok', {
                        status: formatLocaleInteger(readyQuery.data.status, localeTag),
                      })}
                    </span>
                  ) : (
                    <span
                      className='poll-status-error'
                      title={t('admin.status.readinessFailTitle')}
                    >
                      {readyFail ??
                        t('admin.status.unavailable', {
                          status:
                            readyQuery.data?.status != null
                              ? formatLocaleInteger(readyQuery.data.status, localeTag)
                              : '—',
                        })}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className='admin-status-section' aria-labelledby='admin-status-build-heading'>
          <h2 id='admin-status-build-heading' className='admin-export-section-title'>
            {t('admin.status.sectionBuild')}
          </h2>
          <p className='admin-help-text admin-status-section-hint'>
            {t('admin.status.sectionBuildHint')}
          </p>
          <div className='admin-export-card'>
            {apiInfoQuery.isPending ? (
              <p className='admin-status-build-pending'>{t('admin.status.pending')}</p>
            ) : apiInfoQuery.isError ? (
              <p className='poll-status-error' role='alert'>
                {errMsg(apiInfoQuery.error, t('admin.status.buildErr'))}
              </p>
            ) : apiInfo ? (
              <dl className='admin-status-dl'>
                <dt>{t('admin.status.buildLabelService')}</dt>
                <dd>{apiInfo.service}</dd>
                <dt>{t('admin.status.buildLabelVersion')}</dt>
                <dd>{apiInfo.version}</dd>
                {apiInfo.node ? (
                  <>
                    <dt>{t('admin.status.buildLabelNode')}</dt>
                    <dd>{t('admin.status.node', { node: apiInfo.node })}</dd>
                  </>
                ) : null}
                {apiInfo.environment ? (
                  <>
                    <dt>{t('admin.status.buildLabelEnv')}</dt>
                    <dd>{apiInfo.environment}</dd>
                  </>
                ) : null}
                {apiInfo.commit ? (
                  <>
                    <dt>{t('admin.status.buildLabelCommit')}</dt>
                    <dd>
                      <code title={t('admin.status.commitTitle')}>{apiInfo.commit}</code>
                    </dd>
                  </>
                ) : null}
              </dl>
            ) : (
              <p className='admin-help-text'>{t('admin.status.buildEmpty')}</p>
            )}
          </div>
        </section>

        <section className='admin-status-section' aria-labelledby='admin-status-data-heading'>
          <h2 id='admin-status-data-heading' className='admin-export-section-title'>
            {t('admin.status.sectionData')}
          </h2>
          <p className='admin-help-text admin-status-section-hint'>
            {t('admin.status.sectionDataHint')}
          </p>
          <div className='admin-export-card admin-status-data-card'>
            <div className='admin-kpi-grid admin-status-kpi-grid'>
              <div className='admin-kpi-card' title={t('admin.status.usersTitle')}>
                <span className='admin-kpi-label'>{t('admin.dashboard.kpi.usersTotal')}</span>
                <span className='admin-kpi-value'>
                  {status ? formatLocaleInteger(status.users.total, localeTag) : kpiPlaceholder}
                </span>
                {status ? (
                  <span className='admin-kpi-meta'>
                    {t('admin.dashboard.kpi.usersActive')}:{' '}
                    {formatLocaleInteger(status.users.active, localeTag)}
                  </span>
                ) : null}
              </div>
              <div className='admin-kpi-card' title={t('admin.status.pollsTitle')}>
                <span className='admin-kpi-label'>{t('admin.dashboard.kpi.pollsTotal')}</span>
                <span className='admin-kpi-value'>
                  {status ? formatLocaleInteger(status.polls.total, localeTag) : kpiPlaceholder}
                </span>
                {status ? (
                  <span className='admin-kpi-meta'>
                    {t('admin.dashboard.kpi.pollsMeta', { archived: status.polls.archived })}
                  </span>
                ) : null}
              </div>
              <div className='admin-kpi-card' title={t('admin.status.auditTitle')}>
                <span className='admin-kpi-label'>{t('admin.dashboard.kpi.audit24h')}</span>
                <span className='admin-kpi-value'>
                  {status
                    ? formatLocaleInteger(status.auditLogs.last24h, localeTag)
                    : kpiPlaceholder}
                </span>
              </div>
              <div className='admin-kpi-card' title={t('admin.status.tsTitle')}>
                <span className='admin-kpi-label'>{t('admin.status.snapshotGenerated')}</span>
                <span className='admin-kpi-value admin-status-kpi-ts'>
                  {status ? formatLocaleDateTime(status.timestamp, localeTag) : kpiPlaceholder}
                </span>
              </div>
            </div>
            <p className='admin-status-data-footer'>
              <Link to='/admin/export' className='admin-jump-link'>
                {t('admin.status.linkFullExport')}
              </Link>
            </p>
          </div>
        </section>

        <section className='admin-status-section' aria-labelledby='admin-status-trust-heading'>
          <h2 id='admin-status-trust-heading' className='admin-export-section-title'>
            {t('admin.status.sectionTrust')}
          </h2>
          <p className='admin-help-text admin-status-section-hint'>
            {t('admin.status.sectionTrustHint')}
          </p>
          <div className='admin-export-card admin-status-data-card'>
            <div className='admin-kpi-grid admin-status-kpi-grid'>
              <div className='admin-kpi-card'>
                <span className='admin-kpi-label'>{t('admin.status.trustPendingTotal')}</span>
                <span className='admin-kpi-value'>
                  {status
                    ? formatLocaleInteger(status.trustMetrics?.quarantine_pending_total ?? 0, localeTag)
                    : kpiPlaceholder}
                </span>
              </div>
              <div className='admin-kpi-card'>
                <span className='admin-kpi-label'>{t('admin.status.trustPendingPolls')}</span>
                <span className='admin-kpi-value'>
                  {status
                    ? formatLocaleInteger(status.trustMetrics?.quarantine_pending_polls ?? 0, localeTag)
                    : kpiPlaceholder}
                </span>
              </div>
              <div className='admin-kpi-card'>
                <span className='admin-kpi-label'>{t('admin.status.trustQuarantinePendingAccount')}</span>
                <span className='admin-kpi-value'>
                  {status
                    ? formatLocaleInteger(
                        status.trustMetrics?.quarantine_pending_account_linked ?? 0,
                        localeTag,
                      )
                    : kpiPlaceholder}
                </span>
              </div>
              <div className='admin-kpi-card'>
                <span className='admin-kpi-label'>{t('admin.status.trustApproved24h')}</span>
                <span className='admin-kpi-value'>
                  {status
                    ? formatLocaleInteger(status.trustMetrics?.quarantine_approved_last_24h ?? 0, localeTag)
                    : kpiPlaceholder}
                </span>
              </div>
              <div className='admin-kpi-card'>
                <span className='admin-kpi-label'>{t('admin.status.trustRejected24h')}</span>
                <span className='admin-kpi-value'>
                  {status
                    ? formatLocaleInteger(status.trustMetrics?.quarantine_rejected_last_24h ?? 0, localeTag)
                    : kpiPlaceholder}
                </span>
              </div>
              <div className='admin-kpi-card'>
                <span className='admin-kpi-label'>{t('admin.status.trustVotes24hAccount')}</span>
                <span className='admin-kpi-value'>
                  {status
                    ? formatLocaleInteger(
                        status.trustMetrics?.votes_account_linked_last_24h ?? 0,
                        localeTag,
                      )
                    : kpiPlaceholder}
                </span>
              </div>
              <div className='admin-kpi-card'>
                <span className='admin-kpi-label'>{t('admin.status.trustVotes24hAnonymous')}</span>
                <span className='admin-kpi-value'>
                  {status
                    ? formatLocaleInteger(status.trustMetrics?.votes_anonymous_last_24h ?? 0, localeTag)
                    : kpiPlaceholder}
                </span>
              </div>
              <div className='admin-kpi-card'>
                <span className='admin-kpi-label'>{t('admin.status.trustRiskAvgPending')}</span>
                <span className='admin-kpi-value'>
                  {statusQuery.isPending
                    ? kpiPlaceholder
                    : status?.trustMetrics?.trust_risk_avg_pending != null
                      ? String(status.trustMetrics.trust_risk_avg_pending)
                      : '—'}
                </span>
              </div>
            </div>
            <h3 className='admin-status-trust-subheading'>{t('admin.status.trustByReason')}</h3>
            {!status ? (
              <p className='admin-help-text'>{kpiPlaceholder}</p>
            ) : trustReasonRows.length === 0 ? (
              <p className='admin-help-text'>{t('admin.status.trustByReasonEmpty')}</p>
            ) : (
              <dl className='admin-status-dl admin-status-trust-reason-dl'>
                {trustReasonRows.map(({ reason, count }) => (
                  <React.Fragment key={reason}>
                    <dt>{formatQuarantineReasonLabel(t, reason)}</dt>
                    <dd>{formatLocaleInteger(count, localeTag)}</dd>
                  </React.Fragment>
                ))}
              </dl>
            )}
          </div>
        </section>

        {canManageVoteGeo ? (
          <section className='admin-status-section' aria-labelledby='admin-status-votegeo-heading'>
          <h2 id='admin-status-votegeo-heading' className='admin-export-section-title'>
            {t('admin.status.sectionVoteGeo')}
          </h2>
          <p className='admin-help-text admin-status-section-hint'>
            {t('admin.status.voteGeoDesc')}
          </p>
          <div className='admin-export-card'>
            <div
              className='admin-status-votegeo-row'
              role='status'
              aria-live='polite'
              aria-label={t('admin.status.voteGeoHeading')}
            >
              {voteGeoQuery.isPending ? (
                <span className='admin-status-probe-pending'>{t('admin.status.pending')}</span>
              ) : voteGeoQuery.isError ? (
                <span className='poll-status-error'>{t('admin.status.voteGeoErr')}</span>
              ) : voteGeoQuery.data?.enabled ? (
                <span className='admin-status-badge admin-status-badge--ok'>
                  {t('admin.status.voteGeoEnabled')}
                </span>
              ) : (
                <span className='admin-status-badge admin-status-badge--off'>
                  {t('admin.status.voteGeoDisabled')}
                </span>
              )}
            </div>
            <div className='admin-export-card-actions admin-status-votegeo-actions'>
              <Button
                type='button'
                variant='secondary'
                className='admin-users-btn admin-export-dl-btn'
                onClick={() => voteGeoMutation.mutate(true)}
                disabled={voteGeoMutation.isPending || voteGeoQuery.data?.enabled === true}
              >
                {voteGeoMutation.isPending
                  ? t('admin.status.voteGeoSaving')
                  : t('admin.status.voteGeoEnable')}
              </Button>
              <Button
                type='button'
                variant='secondary'
                className='admin-users-btn admin-export-dl-btn'
                onClick={() => voteGeoMutation.mutate(false)}
                disabled={voteGeoMutation.isPending || voteGeoQuery.data?.enabled === false}
              >
                {voteGeoMutation.isPending
                  ? t('admin.status.voteGeoSaving')
                  : t('admin.status.voteGeoDisable')}
              </Button>
            </div>
            {voteGeoError ? (
              <div className='poll-status poll-status-error admin-status-votegeo-err' role='alert'>
                {voteGeoError}
              </div>
            ) : null}
          </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
