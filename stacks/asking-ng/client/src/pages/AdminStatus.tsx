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
import { Button, KpiCard, Notice, PageHeader, SectionPanel } from '../ui';
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
  retentionPolicy?: {
    poll_retention_ttl_days_default: number;
    poll_retention_sweep_interval_sec: number;
    poll_retention_sweep_batch_size: number;
    audit_log_retention_days: number;
    moderation_rejected_vote_retention_days: number;
    audit_log_retention_legal_hold: boolean;
    moderation_rejected_vote_retention_legal_hold: boolean;
  };
  webhookDeliveryTelemetry?: {
    window_minutes: number;
    as_of_ms: number;
    attempted: number;
    delivered_ok: number;
    delivered_non_2xx: number;
    delivery_failed: number;
    shed: number;
    current_minute_attempted: number;
    current_minute_shed: number;
  };
  timestamp: string;
};

type RetentionPolicyPayload = NonNullable<AdminStatusPayload['retentionPolicy']>;
type BillingDowngradeSimulationPayload = {
  ok: boolean;
  user: { id: number; homelab-user: string; workspaceId: number | null };
  currentPlan: string;
  targetPlan: 'free' | 'cloud-team' | 'cloud-pro' | 'selfhost-pro' | 'enterprise-custom';
  usage: {
    activePolls: number;
    votesThisMonth: number;
    exportsToday: number;
    pollsWithWebhookAutomation: number;
    pollsWithExtendedRetention: number;
  };
  limits: {
    activePolls: number;
    votesPerMonth: number;
    exportsPerDay: number;
  };
  flags: {
    webhookAutomationAllowed: boolean;
    extendedRetentionAllowed: boolean;
  };
  violations: Array<Record<string, unknown> & { code: string }>;
  wouldBlock: boolean;
  generatedAt: string;
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

  const canView = !!(
    admin &&
    (admin.role === 'mod' || admin.role === 'admin' || admin.role === 'superadmin')
  );
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
  const retentionPolicyQuery = useQuery({
    queryKey: ['admin', 'retention-policy'],
    queryFn: () => apiFetch('admin/retention-policy') as Promise<RetentionPolicyPayload>,
    enabled: canManageVoteGeo,
  });
  const [retentionDraft, setRetentionDraft] = React.useState<RetentionPolicyPayload | null>(null);
  React.useEffect(() => {
    if (retentionPolicyQuery.data) setRetentionDraft(retentionPolicyQuery.data);
  }, [retentionPolicyQuery.data]);
  const retentionPolicyMutation = useMutation({
    mutationFn: (payload: RetentionPolicyPayload) =>
      apiFetch('admin/retention-policy', {
        method: 'POST',
        body: payload,
      }) as Promise<RetentionPolicyPayload>,
    onSuccess: () => {
      invalidateAdminStatusSurfaceQueries(queryClient);
      queryClient.invalidateQueries({ queryKey: ['admin', 'retention-policy'] });
    },
  });
  const parsePolicyNumber = (raw: string, fallback: number, min: number, max: number) => {
    const n = Number.parseInt(raw, 10);
    if (!Number.isFinite(n)) return fallback;
    return Math.max(min, Math.min(max, n));
  };
  const [simUserId, setSimUserId] = React.useState('');
  const [simTargetPlan, setSimTargetPlan] =
    React.useState<BillingDowngradeSimulationPayload['targetPlan']>('free');
  const downgradeSimMutation = useMutation({
    mutationFn: () =>
      apiFetch('admin/billing/downgrade-simulate', {
        method: 'POST',
        body: { userId: Number.parseInt(simUserId.trim(), 10), targetPlan: simTargetPlan },
      }) as Promise<BillingDowngradeSimulationPayload>,
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
  const retentionPolicyError = retentionPolicyMutation.isError
    ? errMsg(retentionPolicyMutation.error, t('admin.status.retentionPolicyErr'))
    : '';
  const downgradeSimError = downgradeSimMutation.isError
    ? errMsg(downgradeSimMutation.error, 'Downgrade simulation failed.')
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
      <Notice tone='error' className='asking-admin-page__error'>
        {t('admin.status.accessDenied')}
      </Notice>
    );
  }

  return (
    <div
      className='asking-admin-shell asking-admin-status-page asking-admin-page__cq-root'
      id='asking-admin-status-page'
    >
      <PageHeader
        className='asking-admin-page__header'
        titleId='asking-admin-status-page__title'
        titleClassName='asking-admin-page__title'
        subtitleClassName='asking-admin-page__subtitle'
        title={t('admin.status.heading')}
        subtitle={t('admin.status.subtitle')}
      />

      {error ? (
        <Notice tone='error' className='asking-admin-page__banner-error'>
          {error}
        </Notice>
      ) : null}

      <div className='asking-admin-page__card-stack asking-admin-status-page__stack'>
        <SectionPanel
          className='asking-admin-status-page__section'
          titleId='asking-admin-status-page__health-heading'
          title={t('admin.status.sectionHealth')}
          hint={t('admin.status.sectionHealthHint')}
          bodyClassName='asking-admin-page__card asking-admin-status-page__probe-card'
        >
          <div className='asking-admin-status-page__probe-grid'>
            <div
              className={`asking-admin-status-page__probe-tile asking-admin-status-page__probe-tile--${healthTone}`}
              aria-label={t('admin.status.liveness')}
            >
              <div className='asking-admin-status-page__probe-head'>
                <span className='asking-admin-status-page__probe-name'>
                  {t('admin.status.liveness')}
                </span>
                <code className='asking-admin-status-page__probe-route'>
                  {t('admin.status.livenessRoute')}
                </code>
              </div>
              <div className='asking-admin-status-page__probe-value'>
                {healthQuery.isPending ? (
                  <span className='asking-admin-status-page__probe-pending'>
                    {t('admin.status.pending')}
                  </span>
                ) : healthQuery.isError ? (
                  <span className='asking-admin-page__status asking-admin-page__status--error'>
                    {errMsg(healthQuery.error, t('admin.status.requestFailed'))}
                  </span>
                ) : healthQuery.data?.ok ? (
                  <span className='asking-admin-page__status asking-admin-page__status--success'>
                    {t('admin.status.ok', {
                      status: formatLocaleInteger(healthQuery.data.status, localeTag),
                    })}
                  </span>
                ) : (
                  <span
                    className='asking-admin-page__status asking-admin-page__status--error'
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
              className={`asking-admin-status-page__probe-tile asking-admin-status-page__probe-tile--${readyTone}`}
              aria-label={t('admin.status.readiness')}
            >
              <div className='asking-admin-status-page__probe-head'>
                <span className='asking-admin-status-page__probe-name'>
                  {t('admin.status.readiness')}
                </span>
                <code className='asking-admin-status-page__probe-route'>
                  {t('admin.status.readinessRoute')}
                </code>
              </div>
              <div className='asking-admin-status-page__probe-value'>
                {readyQuery.isPending ? (
                  <span className='asking-admin-status-page__probe-pending'>
                    {t('admin.status.pending')}
                  </span>
                ) : readyQuery.isError ? (
                  <span className='asking-admin-page__status asking-admin-page__status--error'>
                    {errMsg(readyQuery.error, t('admin.status.requestFailed'))}
                  </span>
                ) : readyQuery.data?.ok ? (
                  <span className='asking-admin-page__status asking-admin-page__status--success'>
                    {t('admin.status.ok', {
                      status: formatLocaleInteger(readyQuery.data.status, localeTag),
                    })}
                  </span>
                ) : (
                  <span
                    className='asking-admin-page__status asking-admin-page__status--error'
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
        </SectionPanel>

        <SectionPanel
          className='asking-admin-status-page__section'
          titleId='asking-admin-status-page__build-heading'
          title={t('admin.status.sectionBuild')}
          hint={t('admin.status.sectionBuildHint')}
          bodyClassName='asking-admin-page__card'
        >
          {apiInfoQuery.isPending ? (
            <Notice as='p' tone='loading' className='asking-admin-status-page__build-pending'>
              {t('admin.status.pending')}
            </Notice>
          ) : apiInfoQuery.isError ? (
            <Notice
              as='p'
              tone='error'
              className='asking-admin-page__status asking-admin-page__status--error'
            >
              {errMsg(apiInfoQuery.error, t('admin.status.buildErr'))}
            </Notice>
          ) : apiInfo ? (
            <dl className='asking-admin-status-page__dl'>
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
            <p className='asking-admin-page__help-text'>{t('admin.status.buildEmpty')}</p>
          )}
        </SectionPanel>

        <SectionPanel
          className='asking-admin-status-page__section'
          titleId='asking-admin-status-page__data-heading'
          title={t('admin.status.sectionData')}
          hint={t('admin.status.sectionDataHint')}
          bodyClassName='asking-admin-page__card asking-admin-status-page__data-card'
        >
          <div className='asking-admin-page__kpi-grid asking-admin-status-page__kpi-grid'>
            <KpiCard title={t('admin.status.usersTitle')}>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.dashboard.kpi.usersTotal')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status ? formatLocaleInteger(status.users.total, localeTag) : kpiPlaceholder}
              </span>
              {status ? (
                <span className='asking-admin-page__kpi-meta'>
                  {t('admin.dashboard.kpi.usersActive')}:{' '}
                  {formatLocaleInteger(status.users.active, localeTag)}
                </span>
              ) : null}
            </KpiCard>
            <KpiCard title={t('admin.status.pollsTitle')}>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.dashboard.kpi.pollsTotal')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status ? formatLocaleInteger(status.polls.total, localeTag) : kpiPlaceholder}
              </span>
              {status ? (
                <span className='asking-admin-page__kpi-meta'>
                  {t('admin.dashboard.kpi.pollsMeta', { archived: status.polls.archived })}
                </span>
              ) : null}
            </KpiCard>
            <KpiCard title={t('admin.status.auditTitle')}>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.dashboard.kpi.audit24h')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status ? formatLocaleInteger(status.auditLogs.last24h, localeTag) : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard title={t('admin.status.tsTitle')}>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.snapshotGenerated')}
              </span>
              <span className='asking-admin-page__kpi-value asking-admin-status-page__kpi-ts'>
                {status ? formatLocaleDateTime(status.timestamp, localeTag) : kpiPlaceholder}
              </span>
            </KpiCard>
          </div>
          <p className='asking-admin-status-page__data-footer'>
            <Link to='/admin/export' className='asking-admin-page__jump-link'>
              {t('admin.status.linkFullExport')}
            </Link>
          </p>
        </SectionPanel>

        <SectionPanel
          className='asking-admin-status-page__section'
          titleId='asking-admin-status-page__trust-heading'
          title={t('admin.status.sectionTrust')}
          hint={t('admin.status.sectionTrustHint')}
          bodyClassName='asking-admin-page__card asking-admin-status-page__data-card'
        >
          <div className='asking-admin-page__kpi-grid asking-admin-status-page__kpi-grid'>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.trustPendingTotal')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.trustMetrics?.quarantine_pending_total ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.trustPendingPolls')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.trustMetrics?.quarantine_pending_polls ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.trustQuarantinePendingAccount')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.trustMetrics?.quarantine_pending_account_linked ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.trustApproved24h')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.trustMetrics?.quarantine_approved_last_24h ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.trustRejected24h')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.trustMetrics?.quarantine_rejected_last_24h ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.trustVotes24hAccount')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.trustMetrics?.votes_account_linked_last_24h ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.trustVotes24hAnonymous')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.trustMetrics?.votes_anonymous_last_24h ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.trustRiskAvgPending')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {statusQuery.isPending
                  ? kpiPlaceholder
                  : status?.trustMetrics?.trust_risk_avg_pending != null
                    ? String(status.trustMetrics.trust_risk_avg_pending)
                    : '—'}
              </span>
            </KpiCard>
          </div>
          <h3
            className='asking-admin-status-page__trust-subheading'
            id='asking-admin-status-page__trust-by-reason-heading'
          >
            {t('admin.status.trustByReason')}
          </h3>
          {!status ? (
            <p className='asking-admin-page__help-text'>{kpiPlaceholder}</p>
          ) : trustReasonRows.length === 0 ? (
            <p className='asking-admin-page__help-text'>{t('admin.status.trustByReasonEmpty')}</p>
          ) : (
            <dl className='asking-admin-status-page__dl asking-admin-status-page__trust-reason-dl'>
              {trustReasonRows.map(({ reason, count }) => (
                <React.Fragment key={reason}>
                  <dt>{formatQuarantineReasonLabel(t, reason)}</dt>
                  <dd>{formatLocaleInteger(count, localeTag)}</dd>
                </React.Fragment>
              ))}
            </dl>
          )}
        </SectionPanel>

        <SectionPanel
          className='asking-admin-status-page__section'
          titleId='asking-admin-status-page__webhooks-heading'
          title={t('admin.status.sectionWebhooks')}
          hint={t('admin.status.sectionWebhooksHint')}
          bodyClassName='asking-admin-page__card asking-admin-status-page__data-card'
        >
          <div className='asking-admin-page__kpi-grid asking-admin-status-page__kpi-grid'>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.webhooksAttempts')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(status.webhookDeliveryTelemetry?.attempted ?? 0, localeTag)
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.webhooksDeliveredOk')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.webhookDeliveryTelemetry?.delivered_ok ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.webhooksDeliveredNon2xx')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.webhookDeliveryTelemetry?.delivered_non_2xx ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.webhooksDeliveryFailed')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.webhookDeliveryTelemetry?.delivery_failed ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>{t('admin.status.webhooksShed')}</span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(status.webhookDeliveryTelemetry?.shed ?? 0, localeTag)
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.webhooksCurrentMinute')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.webhookDeliveryTelemetry?.current_minute_attempted ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
              {status ? (
                <span className='asking-admin-page__kpi-meta'>
                  {t('admin.status.webhooksCurrentMinuteShed', {
                    count: formatLocaleInteger(
                      status.webhookDeliveryTelemetry?.current_minute_shed ?? 0,
                      localeTag,
                    ),
                  })}
                </span>
              ) : null}
            </KpiCard>
          </div>
          <p className='asking-admin-page__help-text'>
            {t('admin.status.webhooksWindowNote', {
              window: status?.webhookDeliveryTelemetry?.window_minutes ?? 15,
            })}
          </p>
        </SectionPanel>

        <SectionPanel
          className='asking-admin-status-page__section'
          titleId='asking-admin-status-page__retention-heading'
          title={t('admin.status.sectionRetention')}
          hint={t('admin.status.sectionRetentionHint')}
          bodyClassName='asking-admin-page__card asking-admin-status-page__data-card'
        >
          <div className='asking-admin-page__kpi-grid asking-admin-status-page__kpi-grid'>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.retentionPollDefault')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.retentionPolicy?.poll_retention_ttl_days_default ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.retentionSweepInterval')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.retentionPolicy?.poll_retention_sweep_interval_sec ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.retentionSweepBatch')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.retentionPolicy?.poll_retention_sweep_batch_size ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.retentionAuditLogs')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.retentionPolicy?.audit_log_retention_days ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
            <KpiCard>
              <span className='asking-admin-page__kpi-label'>
                {t('admin.status.retentionRejectedVotes')}
              </span>
              <span className='asking-admin-page__kpi-value'>
                {status
                  ? formatLocaleInteger(
                      status.retentionPolicy?.moderation_rejected_vote_retention_days ?? 0,
                      localeTag,
                    )
                  : kpiPlaceholder}
              </span>
            </KpiCard>
          </div>
          {canManageVoteGeo && retentionDraft ? (
            <div className='asking-admin-page__card-actions asking-admin-status-page__votegeo-actions'>
              <label>
                {t('admin.status.retentionPollDefault')}
                <input
                  type='number'
                  min={0}
                  max={3650}
                  value={retentionDraft.poll_retention_ttl_days_default}
                  onChange={(e) =>
                    setRetentionDraft((prev) =>
                      prev
                        ? {
                            ...prev,
                            poll_retention_ttl_days_default: parsePolicyNumber(
                              e.target.value,
                              prev.poll_retention_ttl_days_default,
                              0,
                              3650,
                            ),
                          }
                        : prev,
                    )
                  }
                />
              </label>
              <label>
                {t('admin.status.retentionSweepInterval')}
                <input
                  type='number'
                  min={30}
                  max={86400}
                  value={retentionDraft.poll_retention_sweep_interval_sec}
                  onChange={(e) =>
                    setRetentionDraft((prev) =>
                      prev
                        ? {
                            ...prev,
                            poll_retention_sweep_interval_sec: parsePolicyNumber(
                              e.target.value,
                              prev.poll_retention_sweep_interval_sec,
                              30,
                              86400,
                            ),
                          }
                        : prev,
                    )
                  }
                />
              </label>
              <label>
                {t('admin.status.retentionSweepBatch')}
                <input
                  type='number'
                  min={10}
                  max={5000}
                  value={retentionDraft.poll_retention_sweep_batch_size}
                  onChange={(e) =>
                    setRetentionDraft((prev) =>
                      prev
                        ? {
                            ...prev,
                            poll_retention_sweep_batch_size: parsePolicyNumber(
                              e.target.value,
                              prev.poll_retention_sweep_batch_size,
                              10,
                              5000,
                            ),
                          }
                        : prev,
                    )
                  }
                />
              </label>
              <label>
                {t('admin.status.retentionAuditLogs')}
                <input
                  type='number'
                  min={0}
                  max={3650}
                  value={retentionDraft.audit_log_retention_days}
                  onChange={(e) =>
                    setRetentionDraft((prev) =>
                      prev
                        ? {
                            ...prev,
                            audit_log_retention_days: parsePolicyNumber(
                              e.target.value,
                              prev.audit_log_retention_days,
                              0,
                              3650,
                            ),
                          }
                        : prev,
                    )
                  }
                />
              </label>
              <label>
                {t('admin.status.retentionRejectedVotes')}
                <input
                  type='number'
                  min={0}
                  max={3650}
                  value={retentionDraft.moderation_rejected_vote_retention_days}
                  onChange={(e) =>
                    setRetentionDraft((prev) =>
                      prev
                        ? {
                            ...prev,
                            moderation_rejected_vote_retention_days: parsePolicyNumber(
                              e.target.value,
                              prev.moderation_rejected_vote_retention_days,
                              0,
                              3650,
                            ),
                          }
                        : prev,
                    )
                  }
                />
              </label>
              <label>
                <input
                  type='checkbox'
                  checked={retentionDraft.audit_log_retention_legal_hold === true}
                  onChange={(e) =>
                    setRetentionDraft((prev) =>
                      prev
                        ? {
                            ...prev,
                            audit_log_retention_legal_hold: e.target.checked,
                          }
                        : prev,
                    )
                  }
                />
                {t('admin.status.retentionAuditLogsLegalHold')}
              </label>
              <label>
                <input
                  type='checkbox'
                  checked={retentionDraft.moderation_rejected_vote_retention_legal_hold === true}
                  onChange={(e) =>
                    setRetentionDraft((prev) =>
                      prev
                        ? {
                            ...prev,
                            moderation_rejected_vote_retention_legal_hold: e.target.checked,
                          }
                        : prev,
                    )
                  }
                />
                {t('admin.status.retentionRejectedVotesLegalHold')}
              </label>
              <Button
                type='button'
                variant='secondary'
                onClick={() => retentionPolicyMutation.mutate(retentionDraft)}
                disabled={retentionPolicyMutation.isPending || retentionPolicyQuery.isPending}
              >
                {retentionPolicyMutation.isPending
                  ? t('admin.status.retentionPolicySaving')
                  : t('admin.status.retentionPolicySave')}
              </Button>
            </div>
          ) : null}
          {retentionPolicyError ? (
            <Notice
              tone='error'
              className='asking-admin-page__status asking-admin-page__status--error'
            >
              {retentionPolicyError}
            </Notice>
          ) : null}
        </SectionPanel>

        {canManageVoteGeo ? (
          <SectionPanel
            className='asking-admin-status-page__section'
            titleId='asking-admin-status-page__votegeo-heading'
            title={t('admin.status.sectionVoteGeo')}
            hint={t('admin.status.voteGeoDesc')}
            bodyClassName='asking-admin-page__card'
          >
            <div
              className='asking-admin-status-page__votegeo-row'
              role='status'
              aria-live='polite'
              aria-label={t('admin.status.voteGeoHeading')}
            >
              {voteGeoQuery.isPending ? (
                <span className='asking-admin-status-page__probe-pending'>
                  {t('admin.status.pending')}
                </span>
              ) : voteGeoQuery.isError ? (
                <span className='asking-admin-page__status asking-admin-page__status--error'>
                  {t('admin.status.voteGeoErr')}
                </span>
              ) : voteGeoQuery.data?.enabled ? (
                <span className='asking-admin-status-page__badge asking-admin-status-page__badge--ok'>
                  {t('admin.status.voteGeoEnabled')}
                </span>
              ) : (
                <span className='asking-admin-status-page__badge asking-admin-status-page__badge--off'>
                  {t('admin.status.voteGeoDisabled')}
                </span>
              )}
            </div>
            <div className='asking-admin-page__card-actions asking-admin-status-page__votegeo-actions'>
              <Button
                type='button'
                variant='secondary'
                className='asking-admin-page__btn asking-admin-page__download-btn'
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
                className='asking-admin-page__btn asking-admin-page__download-btn'
                onClick={() => voteGeoMutation.mutate(false)}
                disabled={voteGeoMutation.isPending || voteGeoQuery.data?.enabled === false}
              >
                {voteGeoMutation.isPending
                  ? t('admin.status.voteGeoSaving')
                  : t('admin.status.voteGeoDisable')}
              </Button>
            </div>
            {voteGeoError ? (
              <Notice
                tone='error'
                className='asking-admin-page__status asking-admin-page__status--error asking-admin-status-page__votegeo-err'
              >
                {voteGeoError}
              </Notice>
            ) : null}
          </SectionPanel>
        ) : null}
        {canManageVoteGeo ? (
          <SectionPanel
            className='asking-admin-status-page__section'
            titleId='asking-admin-status-page__billing-sim-heading'
            title='Billing downgrade simulator'
            hint='Preview which limits/plan gates would block before changing a workspace plan.'
            bodyClassName='asking-admin-page__card'
          >
            <div className='asking-admin-page__card-actions asking-admin-status-page__votegeo-actions'>
              <label>
                User ID
                <input
                  type='number'
                  min={1}
                  step={1}
                  value={simUserId}
                  onChange={(e) => setSimUserId(e.target.value)}
                />
              </label>
              <label>
                Target plan
                <select
                  value={simTargetPlan}
                  onChange={(e) =>
                    setSimTargetPlan(
                      e.target.value as BillingDowngradeSimulationPayload['targetPlan'],
                    )
                  }
                >
                  <option value='free'>free</option>
                  <option value='cloud-team'>cloud-team</option>
                  <option value='cloud-pro'>cloud-pro</option>
                  <option value='selfhost-pro'>selfhost-pro</option>
                  <option value='enterprise-custom'>enterprise-custom</option>
                </select>
              </label>
              <Button
                type='button'
                variant='secondary'
                onClick={() => downgradeSimMutation.mutate()}
                disabled={downgradeSimMutation.isPending || Number.parseInt(simUserId, 10) <= 0}
              >
                {downgradeSimMutation.isPending ? 'Simulating…' : 'Simulate downgrade'}
              </Button>
            </div>
            {downgradeSimError ? (
              <Notice
                tone='error'
                className='asking-admin-page__status asking-admin-page__status--error'
              >
                {downgradeSimError}
              </Notice>
            ) : null}
            {downgradeSimMutation.data ? (
              <div className='asking-admin-status-page__dl'>
                <p>
                  <strong>User:</strong> {downgradeSimMutation.data.user.homelab-user} (
                  {formatLocaleInteger(downgradeSimMutation.data.user.id, localeTag)}) ·{' '}
                  <strong>Current:</strong> <code>{downgradeSimMutation.data.currentPlan}</code> ·{' '}
                  <strong>Target:</strong> <code>{downgradeSimMutation.data.targetPlan}</code>
                </p>
                <p>
                  <strong>Active polls:</strong>{' '}
                  {formatLocaleInteger(downgradeSimMutation.data.usage.activePolls, localeTag)} /{' '}
                  {formatLocaleInteger(downgradeSimMutation.data.limits.activePolls, localeTag)} ·{' '}
                  <strong>Votes (UTC month):</strong>{' '}
                  {formatLocaleInteger(downgradeSimMutation.data.usage.votesThisMonth, localeTag)} /{' '}
                  {formatLocaleInteger(downgradeSimMutation.data.limits.votesPerMonth, localeTag)} ·{' '}
                  <strong>Exports (UTC day):</strong>{' '}
                  {formatLocaleInteger(downgradeSimMutation.data.usage.exportsToday, localeTag)} /{' '}
                  {formatLocaleInteger(downgradeSimMutation.data.limits.exportsPerDay, localeTag)}
                </p>
                <p>
                  <strong>Violations:</strong>{' '}
                  {downgradeSimMutation.data.violations.length === 0
                    ? 'none'
                    : downgradeSimMutation.data.violations.map((v) => v.code).join(', ')}
                </p>
              </div>
            ) : null}
          </SectionPanel>
        ) : null}
      </div>
    </div>
  );
}
