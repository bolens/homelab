import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import React from 'react';
import { apiUrl } from '../apiBase';
import SparklineBars from '../components/SparklineBars';
import SparklineLegend from '../components/SparklineLegend';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import { formatUtcHourAtTopOfHour } from '../lib/formatUtcHourAtTopOfHour';
import { formatUtcWeekdayShort } from '../lib/formatUtcWeekdayShort';
import {
  adminDashboardReadyProbeQueryKey,
  adminStatusDashboardQueryKey,
  invalidateAdminOverviewQueries,
} from '../lib/queryKeys';
import { Button, KpiCard, Notice, PageHeader, SectionPanel, VisuallyHidden } from '../ui';
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
  creatorMetrics?: {
    total_votes: number;
    votes_last_24h: number;
    avg_time_to_first_vote_ms: number | null;
    polls_per_active_user_pct: number | null;
    peak_hour_utc: number | null;
    peak_hour_votes: number;
    peak_dow_utc: number | null;
    peak_dow_votes: number;
    hourly_votes_by_hour_utc: number[];
    weekday_votes_by_dow_utc: number[];
  };
  timestamp: string;
};

async function fetchReadyProbe(): Promise<{ ok: boolean; status: number }> {
  const res = await fetch(apiUrl('ready'));
  return { ok: res.ok, status: res.status };
}

export default function AdminDashboard() {
  const t = useT();
  const localeTag = useLocaleTag();
  useDocumentTitle(t('admin.docTitle'));
  const { admin } = useAdmin();
  const queryClient = useQueryClient();
  const canView = !!(
    admin &&
    (admin.role === 'mod' || admin.role === 'admin' || admin.role === 'superadmin')
  );
  const canRunSimulation = !!(admin && (admin.role === 'admin' || admin.role === 'superadmin'));
  const [simUsers, setSimUsers] = React.useState(8);
  const [simPolls, setSimPolls] = React.useState(2);
  const [simVotesPerPoll, setSimVotesPerPoll] = React.useState(20);

  const statusQuery = useQuery({
    queryKey: adminStatusDashboardQueryKey(),
    queryFn: () => apiFetch('admin/status') as Promise<AdminStatusPayload>,
    enabled: canView,
  });

  const readyQuery = useQuery({
    queryKey: adminDashboardReadyProbeQueryKey(),
    queryFn: fetchReadyProbe,
    enabled: canView,
  });

  const status = statusQuery.data ?? null;
  const kpiLoading = statusQuery.isPending || statusQuery.isFetching;
  const fmt = (v: number | undefined) =>
    kpiLoading || v === undefined ? t('admin.dashboard.kpi.placeholder') : String(v);
  const formatDowUtc = (dow: number | null | undefined) =>
    formatUtcWeekdayShort(localeTag, dow, t('admin.dashboard.kpi.placeholder'));
  const formatHourBucketUtc = (h: number) =>
    formatUtcHourAtTopOfHour(localeTag, h, String(Math.max(0, Math.min(23, Math.floor(h)))));
  const weekdayAxis = Array.from({ length: 7 }, (_, i) => formatDowUtc(i)).join(' ');

  const setupSteps = [
    { key: 'session' as const, done: Boolean(admin) },
    { key: 'api' as const, done: readyQuery.data?.ok === true },
    { key: 'user' as const, done: (status?.users.total ?? 0) > 0 },
    { key: 'poll' as const, done: (status?.polls.total ?? 0) > 0 },
  ];
  const doneCount = setupSteps.filter((step) => step.done).length;
  const stepLabel = (key: (typeof setupSteps)[number]['key']) =>
    ({
      session: t('admin.dashboard.setup.step.session'),
      api: t('admin.dashboard.setup.step.api'),
      user: t('admin.dashboard.setup.step.user'),
      poll: t('admin.dashboard.setup.step.poll'),
    })[key];

  const readyPending = readyQuery.isPending || readyQuery.isFetching;
  const readyOk = readyQuery.data?.ok === true;
  const readyFailed = !readyPending && readyQuery.data && !readyOk;
  const healthRowToneClass = readyPending
    ? 'asking-admin-dashboard__health-row--pending'
    : readyOk
      ? 'asking-admin-dashboard__health-row--ok'
      : readyFailed
        ? 'asking-admin-dashboard__health-row--bad'
        : '';
  const simulationMutation = useMutation({
    mutationFn: () =>
      apiFetch('admin/simulate', {
        method: 'POST',
        body: { users: simUsers, polls: simPolls, votesPerPoll: simVotesPerPoll },
      }) as Promise<{ created: { users: number; polls: number; votes: number } }>,
    onSuccess: () => {
      invalidateAdminOverviewQueries(queryClient);
    },
  });
  const simulationSuccess = simulationMutation.data?.created
    ? t('admin.dashboard.simulation.done', {
        users: simulationMutation.data.created.users,
        polls: simulationMutation.data.created.polls,
        votes: simulationMutation.data.created.votes,
      })
    : '';
  const simulationError = simulationMutation.isError
    ? errMsg(simulationMutation.error, t('admin.dashboard.simulation.err'))
    : '';

  const quickActions: Array<{
    to: string;
    title: string;
    desc: string;
    search?: Record<string, undefined>;
  }> = [
    {
      to: '/admin/polls',
      title: t('admin.dashboard.polls'),
      desc: t('admin.dashboard.quick.polls.desc'),
    },
    ...(admin?.role === 'admin' || admin?.role === 'superadmin'
      ? [
          {
            to: '/admin/users',
            title: t('admin.dashboard.users'),
            desc: t('admin.dashboard.quick.users.desc'),
          },
        ]
      : []),
    {
      to: '/admin/audit-logs',
      search: { limit: undefined },
      title: t('admin.dashboard.audit'),
      desc: t('admin.dashboard.quick.audit.desc'),
    },
    {
      to: '/admin/export',
      title: t('admin.dashboard.export'),
      desc: t('admin.dashboard.quick.export.desc'),
    },
    {
      to: '/admin/status',
      title: t('admin.dashboard.status'),
      desc: t('admin.dashboard.quick.status.desc'),
    },
    ...(admin?.role === 'superadmin'
      ? [
          {
            to: '/admin/impersonate',
            title: t('admin.dashboard.impersonate'),
            desc: t('admin.dashboard.quick.impersonate.desc'),
          },
        ]
      : []),
    {
      to: '/developer',
      title: t('nav.developer'),
      desc: t('admin.dashboard.quick.developer.desc'),
    },
  ];

  return (
    <div
      className='asking-admin-dashboard asking-admin-shell asking-admin-page__cq-root'
      id='asking-admin-dashboard-page'
    >
      <PageHeader
        className='asking-admin-page__header'
        titleId='asking-admin-dashboard-page__title'
        titleClassName='asking-admin-page__title'
        subtitleClassName='asking-admin-page__subtitle'
        title={t('admin.dashboard.title')}
        subtitle={t('admin.dashboard.subtitle')}
      >
        {admin ? (
          <p className='ui-copy-muted'>
            {t('admin.dashboard.signedIn', { user: admin.homelab-user, role: admin.role })}
          </p>
        ) : null}
      </PageHeader>

      <div
        className={`asking-admin-dashboard__health-row${healthRowToneClass ? ` ${healthRowToneClass}` : ''}`}
        role='status'
        aria-live='polite'
      >
        <span className='asking-admin-dashboard__health-row-label'>
          {t('admin.dashboard.health.title')}
        </span>
        <span className='asking-admin-dashboard__health-row-value'>
          {readyPending
            ? t('admin.status.pending')
            : readyOk
              ? t('admin.dashboard.health.ok')
              : t('admin.dashboard.health.fail')}
        </span>
        {readyFailed ? (
          <Link to='/admin/status' className='asking-admin-dashboard__health-row-cta'>
            {t('admin.dashboard.health.cta')}
          </Link>
        ) : null}
      </div>

      <section
        className='asking-admin-page__kpi-section'
        aria-labelledby='asking-admin-dashboard-page__kpi-heading'
      >
        <VisuallyHidden as='h2' id='asking-admin-dashboard-page__kpi-heading'>
          {t('admin.dashboard.kpi.heading')}
        </VisuallyHidden>
        <div className='asking-admin-page__kpi-grid'>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.usersTotal')}
            </span>
            <span className='asking-admin-page__kpi-value'>{fmt(status?.users.total)}</span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.usersActive')}
            </span>
            <span className='asking-admin-page__kpi-value'>{fmt(status?.users.active)}</span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.pollsTotal')}
            </span>
            <span className='asking-admin-page__kpi-value'>{fmt(status?.polls.total)}</span>
            {!kpiLoading && status ? (
              <span className='asking-admin-page__kpi-meta'>
                {t('admin.dashboard.kpi.pollsMeta', { archived: status.polls.archived })}
              </span>
            ) : null}
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.audit24h')}
            </span>
            <span className='asking-admin-page__kpi-value'>{fmt(status?.auditLogs.last24h)}</span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.retentionPollDefault')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {fmt(status?.retentionPolicy?.poll_retention_ttl_days_default)}
            </span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.retentionAuditLogs')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {fmt(status?.retentionPolicy?.audit_log_retention_days)}
            </span>
            {!kpiLoading && status?.retentionPolicy ? (
              <span className='asking-admin-page__kpi-meta'>
                {t('admin.dashboard.kpi.retentionRejectedVotesMeta', {
                  days: status.retentionPolicy.moderation_rejected_vote_retention_days,
                })}
              </span>
            ) : null}
            {!kpiLoading && status?.retentionPolicy?.audit_log_retention_legal_hold ? (
              <span className='asking-admin-page__kpi-meta'>
                {t('admin.dashboard.kpi.retentionLegalHoldOn')}
              </span>
            ) : null}
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.trustPending')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {fmt(status?.trustMetrics?.quarantine_pending_total)}
            </span>
            {!kpiLoading && status?.trustMetrics ? (
              <span className='asking-admin-page__kpi-meta'>
                {t('admin.dashboard.kpi.trustPendingMeta', {
                  polls: status.trustMetrics.quarantine_pending_polls,
                })}
              </span>
            ) : null}
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.trustDecisions24h')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {kpiLoading
                ? t('admin.dashboard.kpi.placeholder')
                : String(
                    (status?.trustMetrics?.quarantine_approved_last_24h ?? 0) +
                      (status?.trustMetrics?.quarantine_rejected_last_24h ?? 0),
                  )}
            </span>
            {!kpiLoading && status?.trustMetrics ? (
              <span className='asking-admin-page__kpi-meta'>
                {t('admin.dashboard.kpi.trustDecisions24hMeta', {
                  approved: status.trustMetrics.quarantine_approved_last_24h,
                  rejected: status.trustMetrics.quarantine_rejected_last_24h,
                })}
              </span>
            ) : null}
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.trustRiskAvg')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {kpiLoading
                ? t('admin.dashboard.kpi.placeholder')
                : status?.trustMetrics?.trust_risk_avg_pending != null
                  ? String(status.trustMetrics.trust_risk_avg_pending)
                  : t('admin.dashboard.kpi.placeholder')}
            </span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.quarantinePendingSignedIn')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {fmt(status?.trustMetrics?.quarantine_pending_account_linked)}
            </span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.votes24hAccountBallots')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {fmt(status?.trustMetrics?.votes_account_linked_last_24h)}
            </span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.votes24hAnonymousBallots')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {fmt(status?.trustMetrics?.votes_anonymous_last_24h)}
            </span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.votes24h')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {fmt(status?.creatorMetrics?.votes_last_24h)}
            </span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.totalVotes')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {fmt(status?.creatorMetrics?.total_votes)}
            </span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.peakHour')}
            </span>
            <span className='asking-admin-page__kpi-value'>
              {kpiLoading
                ? t('admin.dashboard.kpi.placeholder')
                : status?.creatorMetrics?.peak_hour_utc != null
                  ? formatUtcHourAtTopOfHour(
                      localeTag,
                      status.creatorMetrics.peak_hour_utc,
                      t('admin.dashboard.kpi.placeholder'),
                    )
                  : t('admin.dashboard.kpi.placeholder')}
            </span>
            {!kpiLoading && status?.creatorMetrics?.peak_hour_utc != null ? (
              <span className='asking-admin-page__kpi-meta'>
                {t('admin.dashboard.kpi.peakHourMeta', {
                  votes: status.creatorMetrics.peak_hour_votes,
                })}
              </span>
            ) : null}
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>{t('admin.dashboard.kpi.peakDay')}</span>
            <span className='asking-admin-page__kpi-value'>
              {kpiLoading
                ? t('admin.dashboard.kpi.placeholder')
                : formatDowUtc(status?.creatorMetrics?.peak_dow_utc ?? null)}
            </span>
            {!kpiLoading && status?.creatorMetrics?.peak_dow_utc != null ? (
              <span className='asking-admin-page__kpi-meta'>
                {t('admin.dashboard.kpi.peakDayMeta', {
                  votes: status.creatorMetrics.peak_dow_votes,
                })}
              </span>
            ) : null}
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.hourlySparkline')}
            </span>
            <span className='asking-admin-page__kpi-value' aria-hidden='true'>
              <SparklineBars
                values={
                  status?.creatorMetrics?.hourly_votes_by_hour_utc ??
                  Array.from({ length: 24 }, () => 0)
                }
                bucketLabel={(i) => formatHourBucketUtc(i)}
              />
            </span>
            <span className='asking-admin-page__kpi-meta'>
              {t('admin.dashboard.kpi.hourlySparklineAxis', {
                start: formatHourBucketUtc(0),
                end: formatHourBucketUtc(23),
              })}
            </span>
            <span className='asking-admin-page__kpi-meta'>
              <SparklineLegend
                values={
                  status?.creatorMetrics?.hourly_votes_by_hour_utc ??
                  Array.from({ length: 24 }, () => 0)
                }
                bucketLabel={(i) => formatHourBucketUtc(i)}
                labels={{
                  min: t('sparkline.min'),
                  max: t('sparkline.max'),
                  peak: t('sparkline.peak'),
                }}
              />
            </span>
          </KpiCard>
          <KpiCard>
            <span className='asking-admin-page__kpi-label'>
              {t('admin.dashboard.kpi.weekdaySparkline')}
            </span>
            <span className='asking-admin-page__kpi-value' aria-hidden='true'>
              <SparklineBars
                values={
                  status?.creatorMetrics?.weekday_votes_by_dow_utc ??
                  Array.from({ length: 7 }, () => 0)
                }
                bucketLabel={(i) => `${formatDowUtc(i)}`}
              />
            </span>
            <span className='asking-admin-page__kpi-meta'>
              {t('admin.dashboard.kpi.weekdaySparklineAxis', { days: weekdayAxis })}
            </span>
            <span className='asking-admin-page__kpi-meta'>
              <SparklineLegend
                values={
                  status?.creatorMetrics?.weekday_votes_by_dow_utc ??
                  Array.from({ length: 7 }, () => 0)
                }
                bucketLabel={(i) => `${formatDowUtc(i)}`}
                labels={{
                  min: t('sparkline.min'),
                  max: t('sparkline.max'),
                  peak: t('sparkline.peak'),
                }}
              />
            </span>
          </KpiCard>
        </div>
      </section>

      {canRunSimulation ? (
        <SectionPanel
          className='asking-admin-page__setup-card asking-admin-page__simulation-card'
          titleId='asking-admin-dashboard-page__simulation-heading'
          title={
            <span className='asking-admin-page__setup-title'>
              {t('admin.dashboard.simulation.title')}
            </span>
          }
          hint={
            <span className='asking-admin-page__help-text asking-admin-page__simulation-help'>
              {t('admin.dashboard.simulation.subtitle')}
            </span>
          }
          headerClassName='asking-admin-page__setup-header'
        >
          <form
            id='asking-admin-dashboard-page__simulation-form'
            className='asking-admin-page__simulation-form'
            onSubmit={(e) => {
              e.preventDefault();
              simulationMutation.mutate();
            }}
          >
            <label className='asking-admin-page__simulation-field'>
              <span>{t('admin.dashboard.simulation.users')}</span>
              <input
                type='number'
                min={0}
                max={50}
                value={simUsers}
                onChange={(e) => setSimUsers(Number(e.target.value) || 0)}
              />
            </label>
            <label className='asking-admin-page__simulation-field'>
              <span>{t('admin.dashboard.simulation.polls')}</span>
              <input
                type='number'
                min={1}
                max={25}
                value={simPolls}
                onChange={(e) => setSimPolls(Math.max(1, Number(e.target.value) || 1))}
              />
            </label>
            <label className='asking-admin-page__simulation-field'>
              <span>{t('admin.dashboard.simulation.votes')}</span>
              <input
                type='number'
                min={0}
                max={1000}
                value={simVotesPerPoll}
                onChange={(e) => setSimVotesPerPoll(Math.max(0, Number(e.target.value) || 0))}
              />
            </label>
            <Button
              type='submit'
              variant='primary'
              className='asking-admin-page__toolbar-btn'
              disabled={simulationMutation.isPending}
            >
              {simulationMutation.isPending
                ? t('admin.dashboard.simulation.running')
                : t('admin.dashboard.simulation.run')}
            </Button>
          </form>
          {simulationSuccess ? (
            <Notice
              tone='success'
              className='asking-admin-page__status asking-admin-page__status--success'
              aria-live='polite'
            >
              {simulationSuccess}
            </Notice>
          ) : null}
          {simulationError ? (
            <Notice
              tone='error'
              className='asking-admin-page__status asking-admin-page__status--error'
            >
              {simulationError}
            </Notice>
          ) : null}
        </SectionPanel>
      ) : null}

      <div className='asking-admin-dashboard__columns'>
        <SectionPanel
          className='asking-admin-page__setup-card'
          titleId='asking-admin-dashboard-page__setup-heading'
          title={
            <span className='asking-admin-page__setup-title'>
              {t('admin.dashboard.setup.title')}
            </span>
          }
          hint={
            <span className='asking-admin-page__setup-progress'>
              {t('admin.dashboard.setup.progress', { done: doneCount, total: setupSteps.length })}
            </span>
          }
          headerClassName='asking-admin-page__setup-header'
        >
          <ul className='asking-admin-page__setup-list'>
            {setupSteps.map((step) => (
              <li key={step.key} className='asking-admin-page__setup-item'>
                <span
                  className={
                    step.done
                      ? 'asking-admin-page__status--success'
                      : 'asking-admin-page__status--error'
                  }
                  aria-hidden
                >
                  {step.done
                    ? t('admin.dashboard.setup.status.done')
                    : t('admin.dashboard.setup.status.pending')}
                </span>{' '}
                {stepLabel(step.key)}
              </li>
            ))}
          </ul>
          <div className='asking-admin-page__setup-actions'>
            {admin?.role === 'admin' || admin?.role === 'superadmin' ? (
              <Link to='/admin/users'>{t('admin.dashboard.users')}</Link>
            ) : null}
            <Link to='/admin/polls'>{t('admin.dashboard.polls')}</Link>
            <Link to='/admin/status'>{t('admin.dashboard.status')}</Link>
          </div>
        </SectionPanel>

        <SectionPanel
          className='asking-admin-page__quick-section'
          titleId='asking-admin-dashboard-page__quick-heading'
          title={
            <span className='asking-admin-page__quick-section-title'>
              {t('admin.dashboard.quick.title')}
            </span>
          }
        >
          <div className='asking-admin-page__quick-grid'>
            {quickActions.map((action) => (
              <Link
                key={action.to + (action.search ? JSON.stringify(action.search) : '')}
                to={action.to}
                {...(action.search ? { search: action.search } : {})}
                className='asking-admin-page__quick-card'
              >
                <span className='asking-admin-page__quick-card-title'>{action.title}</span>
                <span className='asking-admin-page__quick-card-desc'>{action.desc}</span>
              </Link>
            ))}
          </div>
        </SectionPanel>
      </div>
    </div>
  );
}
