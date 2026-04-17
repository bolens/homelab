import { useQuery, useQueryClient } from '@tanstack/react-query';
import React, { useEffect, useState } from 'react';
import { apiUrl } from '../apiBase';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import { formatLocaleDateTime, formatLocaleInteger } from '../lib/formatLocaleDisplay';
import {
  invalidatePublicStatusQueries,
  publicStatusHealthcheckQueryKey,
  publicStatusHistoryQueryKey,
  publicStatusInfoQueryKey,
  publicStatusReadyQueryKey,
} from '../lib/queryKeys';
import { Button, Card, cx } from '../ui';
import { errMsg } from '../utils/errMsg';

type ApiInfoPayload = {
  service?: string;
  version?: string;
  environment?: string;
  commit?: string;
};

type JsonProbe = { ok: boolean; status: number; body: Record<string, unknown> };
type StatusHistoryPayload = {
  windowHours: number;
  generatedAt: string;
  sampleCount: number;
  uptimePct: number | null;
  incidents: {
    startedAt: string;
    endedAt: string | null;
    summary: string;
    status: 'investigating' | 'resolved';
    durationMinutes: number | null;
  }[];
};

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

function statusTone(
  pending: boolean,
  hasError: boolean,
  ok: boolean | undefined,
): 'pending' | 'ok' | 'error' {
  if (pending) return 'pending';
  if (hasError || ok === false) return 'error';
  return 'ok';
}

function toneLabel(
  tone: 'pending' | 'ok' | 'error',
  t: ReturnType<typeof useT>,
  status: number | undefined,
  localeTag: string,
) {
  if (tone === 'pending') return t('status.checking');
  if (tone === 'ok') {
    return t('status.ok', { status: formatLocaleInteger(status ?? 200, localeTag) });
  }
  return t('status.fail', { status: formatLocaleInteger(status ?? 0, localeTag) });
}

export default function PublicStatus() {
  const t = useT();
  const localeTag = useLocaleTag();
  const queryClient = useQueryClient();
  useDocumentTitle(t('status.docTitle'));
  const [linkCopied, setLinkCopied] = useState(false);

  const healthQuery = useQuery({
    queryKey: publicStatusHealthcheckQueryKey(),
    queryFn: () => fetchJsonProbe('healthcheck'),
    refetchInterval: 30_000,
  });
  const readyQuery = useQuery({
    queryKey: publicStatusReadyQueryKey(),
    queryFn: () => fetchJsonProbe('ready'),
    refetchInterval: 30_000,
  });
  const infoQuery = useQuery({
    queryKey: publicStatusInfoQueryKey(),
    queryFn: () => fetchJsonProbe('info'),
    refetchInterval: 60_000,
  });
  const historyQuery = useQuery({
    queryKey: publicStatusHistoryQueryKey(),
    queryFn: () =>
      apiFetch('status/history?windowHours=24', {
        adminToken: false,
      }) as Promise<StatusHistoryPayload>,
    refetchInterval: 60_000,
  });

  const healthTone = statusTone(healthQuery.isPending, healthQuery.isError, healthQuery.data?.ok);
  const readyTone = statusTone(readyQuery.isPending, readyQuery.isError, readyQuery.data?.ok);
  const apiHealthy =
    !healthQuery.isPending &&
    !readyQuery.isPending &&
    !healthQuery.isError &&
    !readyQuery.isError &&
    healthQuery.data?.ok === true &&
    readyQuery.data?.ok === true;

  const info = infoQuery.data?.body as ApiInfoPayload | undefined;
  const isChecking = healthQuery.isPending || readyQuery.isPending;
  const updatedAtMs = Math.max(
    healthQuery.dataUpdatedAt ?? 0,
    readyQuery.dataUpdatedAt ?? 0,
    infoQuery.dataUpdatedAt ?? 0,
    historyQuery.dataUpdatedAt ?? 0,
  );
  const updatedAtIso =
    updatedAtMs > 0 ? new Date(updatedAtMs).toISOString() : new Date().toISOString();
  const uptimeSummary = apiHealthy ? t('status.uptimeHealthy') : t('status.uptimeDegraded');
  const uptimePct = historyQuery.data?.uptimePct ?? null;
  const incidents = historyQuery.data?.incidents ?? [];

  useEffect(() => {
    if (!linkCopied) return;
    const timer = window.setTimeout(() => setLinkCopied(false), 2200);
    return () => window.clearTimeout(timer);
  }, [linkCopied]);

  async function copyStatusUrl() {
    const href = window.location.href;
    try {
      await navigator.clipboard.writeText(href);
      setLinkCopied(true);
    } catch {
      setLinkCopied(false);
    }
  }

  function refreshNow() {
    invalidatePublicStatusQueries(queryClient);
  }

  return (
    <article
      className='ui-page-shell asking-public-layout asking-status-page'
      id='asking-status-page'
    >
      <header className='ui-page-hero'>
        <h1 className='ui-page-hero-title' id='asking-status-page__title'>
          {t('status.title')}
        </h1>
        <p className='ui-page-hero-tagline'>{t('status.subtitle')}</p>
      </header>

      <div className='asking-status-page__grid'>
        <Card
          as='section'
          padding='none'
          className={cx(
            'ui-card--form-panel',
            'asking-status-page__card',
            'asking-status-page__overall',
          )}
          aria-labelledby='asking-status-page__current-heading'
        >
          <h2 id='asking-status-page__current-heading' className='ui-flow-heading'>
            {t('status.current')}
          </h2>
          <p
            className={`asking-status-page__overall-state ${
              apiHealthy
                ? 'asking-status-page__status--success'
                : isChecking
                  ? ''
                  : 'asking-status-page__status--error'
            }`}
          >
            {isChecking
              ? t('status.checking')
              : apiHealthy
                ? t('status.operational')
                : t('status.incident')}
          </p>
          <p className='asking-status-page__overall-meta'>
            {t('status.updatedAt', { ts: formatLocaleDateTime(updatedAtIso, localeTag) })}
            {' · '}
            {t('status.autoRefresh')}
          </p>
        </Card>

        <Card
          as='section'
          padding='none'
          className={cx('ui-card--form-panel', 'asking-status-page__card')}
          aria-labelledby='asking-status-page__components-heading'
        >
          <h2 id='asking-status-page__components-heading' className='ui-flow-heading'>
            {t('status.components')}
          </h2>
          <ul className='asking-status-page__components' role='list'>
            <li className='asking-status-page__component'>
              <div className='asking-status-page__component-main'>
                <span className='asking-status-page__component-name'>{t('status.liveness')}</span>
                <code className='asking-status-page__component-route'>GET /healthcheck</code>
              </div>
              <span
                className={`asking-status-page__badge asking-status-page__badge--${healthTone}`}
              >
                <span className='asking-status-page__badge-dot' aria-hidden='true' />
                {healthQuery.isError
                  ? errMsg(healthQuery.error, t('status.requestFailed'))
                  : toneLabel(healthTone, t, healthQuery.data?.status, localeTag)}
              </span>
            </li>
            <li className='asking-status-page__component'>
              <div className='asking-status-page__component-main'>
                <span className='asking-status-page__component-name'>{t('status.readiness')}</span>
                <code className='asking-status-page__component-route'>GET /ready</code>
              </div>
              <span className={`asking-status-page__badge asking-status-page__badge--${readyTone}`}>
                <span className='asking-status-page__badge-dot' aria-hidden='true' />
                {readyQuery.isError
                  ? errMsg(readyQuery.error, t('status.requestFailed'))
                  : toneLabel(readyTone, t, readyQuery.data?.status, localeTag)}
              </span>
            </li>
          </ul>
        </Card>

        <Card
          as='section'
          padding='none'
          className={cx('ui-card--form-panel', 'asking-status-page__card')}
          aria-labelledby='asking-status-page__uptime-heading'
        >
          <h2 id='asking-status-page__uptime-heading' className='ui-flow-heading'>
            {t('status.uptimeHeading')}
          </h2>
          <p className='asking-status-page__uptime-value'>{uptimeSummary}</p>
          <p className='asking-status-page__uptime-note'>
            {historyQuery.isPending
              ? t('status.checking')
              : historyQuery.isError
                ? errMsg(historyQuery.error, t('status.historyError'))
                : uptimePct == null
                  ? t('status.uptimeNoData')
                  : t('status.uptimePercent', {
                      pct: new Intl.NumberFormat(localeTag, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      }).format(uptimePct),
                      samples: formatLocaleInteger(historyQuery.data?.sampleCount ?? 0, localeTag),
                    })}
          </p>
        </Card>

        <Card
          as='section'
          padding='none'
          className={cx('ui-card--form-panel', 'asking-status-page__card')}
          aria-labelledby='asking-status-page__incidents-heading'
        >
          <h2 id='asking-status-page__incidents-heading' className='ui-flow-heading'>
            {t('status.recentIncidents')}
          </h2>
          {historyQuery.isPending ? (
            <p className='asking-status-page__incident-empty'>{t('status.checking')}</p>
          ) : null}
          {historyQuery.isError ? (
            <p
              className='asking-status-page__status asking-status-page__status--error'
              role='alert'
            >
              {errMsg(historyQuery.error, t('status.historyError'))}
            </p>
          ) : null}
          {!historyQuery.isPending && !historyQuery.isError && incidents.length === 0 ? (
            <p className='asking-status-page__incident-empty'>{t('status.noRecentIncidents')}</p>
          ) : null}
          {!historyQuery.isPending && !historyQuery.isError && incidents.length > 0 ? (
            <ul className='asking-status-page__incidents' role='list'>
              {incidents.map((incident) => (
                <li
                  key={`${incident.startedAt}-${incident.endedAt ?? 'open'}`}
                  className='asking-status-page__incident'
                >
                  <div className='asking-status-page__incident-head'>
                    <strong>{incident.summary}</strong>
                    <span
                      className={`asking-status-page__badge asking-status-page__badge--${
                        incident.status === 'resolved' ? 'ok' : 'error'
                      }`}
                    >
                      <span className='asking-status-page__badge-dot' aria-hidden='true' />
                      {incident.status === 'resolved'
                        ? t('status.incidentResolved')
                        : t('status.incidentInvestigating')}
                    </span>
                  </div>
                  <p className='asking-status-page__incident-meta'>
                    {t('status.incidentRange', {
                      start: formatLocaleDateTime(incident.startedAt, localeTag),
                      end: incident.endedAt
                        ? formatLocaleDateTime(incident.endedAt, localeTag)
                        : t('status.incidentOngoing'),
                    })}
                    {incident.durationMinutes != null
                      ? ` · ${t('status.incidentDuration', {
                          mins: formatLocaleInteger(incident.durationMinutes, localeTag),
                        })}`
                      : ''}
                  </p>
                </li>
              ))}
            </ul>
          ) : null}
        </Card>

        <Card
          as='section'
          padding='none'
          className={cx('ui-card--form-panel', 'asking-status-page__card')}
          aria-labelledby='asking-status-page__build-heading'
        >
          <h2 id='asking-status-page__build-heading' className='ui-flow-heading'>
            {t('status.buildInfo')}
          </h2>
          {infoQuery.isPending ? (
            <p>{t('status.checking')}</p>
          ) : infoQuery.isError ? (
            <p
              className='asking-status-page__status asking-status-page__status--error'
              role='alert'
            >
              {errMsg(infoQuery.error, t('status.infoError'))}
            </p>
          ) : (
            <dl className='asking-admin-status-page__dl'>
              <dt>{t('status.service')}</dt>
              <dd>{info?.service ?? t('status.unknown')}</dd>
              <dt>{t('status.version')}</dt>
              <dd>{info?.version ?? t('status.unknown')}</dd>
              {info?.environment ? (
                <>
                  <dt>{t('status.environment')}</dt>
                  <dd>{info.environment}</dd>
                </>
              ) : null}
              {info?.commit ? (
                <>
                  <dt>{t('status.commit')}</dt>
                  <dd>
                    <code>{info.commit}</code>
                  </dd>
                </>
              ) : null}
            </dl>
          )}
        </Card>

        <Card
          as='section'
          padding='none'
          className={cx('ui-card--form-panel', 'asking-status-page__card')}
          aria-labelledby='asking-status-page__stay-updated-heading'
        >
          <h2 id='asking-status-page__stay-updated-heading' className='ui-flow-heading'>
            {t('status.stayUpdated')}
          </h2>
          <p className='asking-status-page__stay-updated-copy'>{t('status.stayUpdatedHint')}</p>
          <div className='asking-status-page__actions'>
            <Button type='button' variant='secondary' onClick={() => void copyStatusUrl()}>
              {linkCopied ? t('status.copyLinkDone') : t('status.copyLink')}
            </Button>
            <Button type='button' variant='primary' onClick={refreshNow}>
              {t('status.refreshNow')}
            </Button>
          </div>
        </Card>
      </div>
    </article>
  );
}
