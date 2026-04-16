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
  const canView = !!(admin && (admin.role === 'mod' || admin.role === 'admin' || admin.role === 'superadmin'));
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
    <div className='admin-dashboard admin-users-container'>
      <header className='admin-page-header'>
        <h1 className='admin-page-title'>{t('admin.dashboard.title')}</h1>
        <p className='admin-page-subtitle'>{t('admin.dashboard.subtitle')}</p>
        {admin ? (
          <p className='admin-page-meta'>
            {t('admin.dashboard.signedIn', { user: admin.homelab-user, role: admin.role })}
          </p>
        ) : null}
      </header>

      <div
        className={`admin-health-row${readyOk ? ' admin-health-row--ok' : ''}${readyFailed ? ' admin-health-row--bad' : ''}${readyPending ? ' admin-health-row--pending' : ''}`}
        role='status'
        aria-live='polite'
      >
        <span className='admin-health-row-label'>{t('admin.dashboard.health.title')}</span>
        <span className='admin-health-row-value'>
          {readyPending
            ? t('admin.status.pending')
            : readyOk
              ? t('admin.dashboard.health.ok')
              : t('admin.dashboard.health.fail')}
        </span>
        {readyFailed ? (
          <Link to='/admin/status' className='admin-health-row-cta'>
            {t('admin.dashboard.health.cta')}
          </Link>
        ) : null}
      </div>

      <section className='admin-kpi-section' aria-labelledby='admin-kpi-heading'>
        <h2 id='admin-kpi-heading' className='visually-hidden'>
          {t('admin.dashboard.kpi.heading')}
        </h2>
        <div className='admin-kpi-grid'>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.usersTotal')}</span>
            <span className='admin-kpi-value'>{fmt(status?.users.total)}</span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.usersActive')}</span>
            <span className='admin-kpi-value'>{fmt(status?.users.active)}</span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.pollsTotal')}</span>
            <span className='admin-kpi-value'>{fmt(status?.polls.total)}</span>
            {!kpiLoading && status ? (
              <span className='admin-kpi-meta'>
                {t('admin.dashboard.kpi.pollsMeta', { archived: status.polls.archived })}
              </span>
            ) : null}
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.audit24h')}</span>
            <span className='admin-kpi-value'>{fmt(status?.auditLogs.last24h)}</span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.trustPending')}</span>
            <span className='admin-kpi-value'>
              {fmt(status?.trustMetrics?.quarantine_pending_total)}
            </span>
            {!kpiLoading && status?.trustMetrics ? (
              <span className='admin-kpi-meta'>
                {t('admin.dashboard.kpi.trustPendingMeta', {
                  polls: status.trustMetrics.quarantine_pending_polls,
                })}
              </span>
            ) : null}
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.trustDecisions24h')}</span>
            <span className='admin-kpi-value'>
              {kpiLoading
                ? t('admin.dashboard.kpi.placeholder')
                : String(
                    (status?.trustMetrics?.quarantine_approved_last_24h ?? 0) +
                      (status?.trustMetrics?.quarantine_rejected_last_24h ?? 0),
                  )}
            </span>
            {!kpiLoading && status?.trustMetrics ? (
              <span className='admin-kpi-meta'>
                {t('admin.dashboard.kpi.trustDecisions24hMeta', {
                  approved: status.trustMetrics.quarantine_approved_last_24h,
                  rejected: status.trustMetrics.quarantine_rejected_last_24h,
                })}
              </span>
            ) : null}
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.trustRiskAvg')}</span>
            <span className='admin-kpi-value'>
              {kpiLoading
                ? t('admin.dashboard.kpi.placeholder')
                : status?.trustMetrics?.trust_risk_avg_pending != null
                  ? String(status.trustMetrics.trust_risk_avg_pending)
                  : t('admin.dashboard.kpi.placeholder')}
            </span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.quarantinePendingSignedIn')}</span>
            <span className='admin-kpi-value'>
              {fmt(status?.trustMetrics?.quarantine_pending_account_linked)}
            </span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.votes24hAccountBallots')}</span>
            <span className='admin-kpi-value'>
              {fmt(status?.trustMetrics?.votes_account_linked_last_24h)}
            </span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.votes24hAnonymousBallots')}</span>
            <span className='admin-kpi-value'>
              {fmt(status?.trustMetrics?.votes_anonymous_last_24h)}
            </span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.votes24h')}</span>
            <span className='admin-kpi-value'>{fmt(status?.creatorMetrics?.votes_last_24h)}</span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.totalVotes')}</span>
            <span className='admin-kpi-value'>{fmt(status?.creatorMetrics?.total_votes)}</span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.peakHour')}</span>
            <span className='admin-kpi-value'>
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
              <span className='admin-kpi-meta'>
                {t('admin.dashboard.kpi.peakHourMeta', {
                  votes: status.creatorMetrics.peak_hour_votes,
                })}
              </span>
            ) : null}
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.peakDay')}</span>
            <span className='admin-kpi-value'>
              {kpiLoading
                ? t('admin.dashboard.kpi.placeholder')
                : formatDowUtc(status?.creatorMetrics?.peak_dow_utc ?? null)}
            </span>
            {!kpiLoading && status?.creatorMetrics?.peak_dow_utc != null ? (
              <span className='admin-kpi-meta'>
                {t('admin.dashboard.kpi.peakDayMeta', {
                  votes: status.creatorMetrics.peak_dow_votes,
                })}
              </span>
            ) : null}
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.hourlySparkline')}</span>
            <span className='admin-kpi-value' aria-hidden='true'>
              <SparklineBars
                values={
                  status?.creatorMetrics?.hourly_votes_by_hour_utc ??
                  Array.from({ length: 24 }, () => 0)
                }
                bucketLabel={(i) => `${formatHourBucketUtc(i)} UTC`}
              />
            </span>
            <span className='admin-kpi-meta'>
              {t('admin.dashboard.kpi.hourlySparklineAxis', { start: '00:00', end: '23:00' })}
            </span>
            <span className='admin-kpi-meta'>
              <SparklineLegend
                values={
                  status?.creatorMetrics?.hourly_votes_by_hour_utc ??
                  Array.from({ length: 24 }, () => 0)
                }
                bucketLabel={(i) => `${formatHourBucketUtc(i)} UTC`}
                labels={{
                  min: t('sparkline.min'),
                  max: t('sparkline.max'),
                  peak: t('sparkline.peak'),
                }}
              />
            </span>
          </div>
          <div className='admin-kpi-card'>
            <span className='admin-kpi-label'>{t('admin.dashboard.kpi.weekdaySparkline')}</span>
            <span className='admin-kpi-value' aria-hidden='true'>
              <SparklineBars
                values={
                  status?.creatorMetrics?.weekday_votes_by_dow_utc ??
                  Array.from({ length: 7 }, () => 0)
                }
                bucketLabel={(i) => `${formatDowUtc(i)}`}
              />
            </span>
            <span className='admin-kpi-meta'>
              {t('admin.dashboard.kpi.weekdaySparklineAxis', { days: weekdayAxis })}
            </span>
            <span className='admin-kpi-meta'>
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
          </div>
        </div>
      </section>

      {canRunSimulation ? (
        <section
          className='admin-setup-card admin-simulation-card'
          aria-labelledby='admin-simulation-heading'
        >
        <div className='admin-setup-header'>
          <h2 id='admin-simulation-heading' className='admin-setup-title'>
            {t('admin.dashboard.simulation.title')}
          </h2>
          <p className='admin-help-text admin-simulation-help'>
            {t('admin.dashboard.simulation.subtitle')}
          </p>
        </div>
        <form
          className='admin-simulation-form'
          onSubmit={(e) => {
            e.preventDefault();
            simulationMutation.mutate();
          }}
        >
          <label className='admin-simulation-field'>
            <span>{t('admin.dashboard.simulation.users')}</span>
            <input
              type='number'
              min={0}
              max={50}
              value={simUsers}
              onChange={(e) => setSimUsers(Number(e.target.value) || 0)}
            />
          </label>
          <label className='admin-simulation-field'>
            <span>{t('admin.dashboard.simulation.polls')}</span>
            <input
              type='number'
              min={1}
              max={25}
              value={simPolls}
              onChange={(e) => setSimPolls(Math.max(1, Number(e.target.value) || 1))}
            />
          </label>
          <label className='admin-simulation-field'>
            <span>{t('admin.dashboard.simulation.votes')}</span>
            <input
              type='number'
              min={0}
              max={1000}
              value={simVotesPerPoll}
              onChange={(e) => setSimVotesPerPoll(Math.max(0, Number(e.target.value) || 0))}
            />
          </label>
          <Button type='submit' variant='primary' className='poll-btn' disabled={simulationMutation.isPending}>
            {simulationMutation.isPending
              ? t('admin.dashboard.simulation.running')
              : t('admin.dashboard.simulation.run')}
          </Button>
        </form>
        {simulationSuccess ? (
          <div className='poll-status poll-status-success' role='status' aria-live='polite'>
            {simulationSuccess}
          </div>
        ) : null}
        {simulationError ? (
          <div className='poll-status poll-status-error' role='alert'>
            {simulationError}
          </div>
        ) : null}
        </section>
      ) : null}

      <div className='admin-dashboard-columns'>
        <section className='admin-setup-card' aria-labelledby='admin-setup-heading'>
          <div className='admin-setup-header'>
            <h2 id='admin-setup-heading' className='admin-setup-title'>
              {t('admin.dashboard.setup.title')}
            </h2>
            <p className='admin-setup-progress'>
              {t('admin.dashboard.setup.progress', { done: doneCount, total: setupSteps.length })}
            </p>
          </div>
          <ul className='admin-setup-list'>
            {setupSteps.map((step) => (
              <li key={step.key} className='admin-setup-item'>
                <span
                  className={step.done ? 'poll-status-success' : 'poll-status-error'}
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
          <div className='admin-setup-actions'>
            {admin?.role === 'admin' || admin?.role === 'superadmin' ? (
              <Link to='/admin/users'>{t('admin.dashboard.users')}</Link>
            ) : null}
            <Link to='/admin/polls'>{t('admin.dashboard.polls')}</Link>
            <Link to='/admin/status'>{t('admin.dashboard.status')}</Link>
          </div>
        </section>

        <section className='admin-quick-section' aria-labelledby='admin-quick-heading'>
          <h2 id='admin-quick-heading' className='admin-quick-section-title'>
            {t('admin.dashboard.quick.title')}
          </h2>
          <div className='admin-quick-grid'>
            {quickActions.map((action) => (
              <Link
                key={action.to + (action.search ? JSON.stringify(action.search) : '')}
                to={action.to}
                {...(action.search ? { search: action.search } : {})}
                className='admin-quick-card'
              >
                <span className='admin-quick-card-title'>{action.title}</span>
                <span className='admin-quick-card-desc'>{action.desc}</span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
