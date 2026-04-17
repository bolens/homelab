import { useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearch } from '@tanstack/react-router';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch, isApiFetchError } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import { formatLocaleInteger } from '../lib/formatLocaleDisplay';
import { pollResultsQueryKey } from '../lib/queryKeys';
import { Alert, Button } from '../ui';
import { errMsg } from '../utils/errMsg';

type PollApiRow = {
  option: string;
  vote_count: number | string;
};
type PollResultsApiData = {
  title: string;
  options: string[];
  votes: PollApiRow[];
  phase?: string;
  archived?: boolean;
  voting_paused?: boolean;
  results_delay_seconds?: number;
  live_results_are_delayed?: boolean;
  delayed_votes_pending?: number;
};

async function fetchResults(id: string, embedToken: string): Promise<PollResultsApiData> {
  const json = (await apiFetch(`poll/${id}`, {
    embedToken: embedToken || undefined,
  })) as { data: PollResultsApiData };
  return json.data;
}

function resultWidth(votes: number, total: number): string {
  if (total <= 0) return '0%';
  return `${Math.max(0, Math.min(100, (votes / total) * 100))}%`;
}

function resultPercent(votes: number, total: number): string {
  if (total <= 0) return '0%';
  const pct = (votes / total) * 100;
  const rounded = pct >= 10 ? Math.round(pct) : Math.round(pct * 10) / 10;
  return `${rounded}%`;
}

export default function PollResults() {
  const t = useT();
  const localeTag = useLocaleTag();
  const { id } = useParams({ from: '/$id/results', strict: true });
  const { embed_token: embedTokenRaw } = useSearch({ from: '/$id/results', strict: true });
  const embedToken = embedTokenRaw?.trim() ?? '';
  const [refreshMs, setRefreshMs] = useState(5_000);
  const [sceneSafeMode, setSceneSafeMode] = useState(false);
  const [presenterContrast, setPresenterContrast] = useState(false);
  const [fullscreenEnabled, setFullscreenEnabled] = useState(false);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: pollResultsQueryKey(id, embedToken),
    queryFn: () => fetchResults(id, embedToken),
    refetchInterval: refreshMs,
  });

  useEffect(() => {
    const onFullscreenChange = () => {
      setFullscreenEnabled(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      void document.documentElement.requestFullscreen?.();
    } else {
      void document.exitFullscreen?.();
    }
  };

  useEffect(() => {
    const onKeyDown = (evt: KeyboardEvent) => {
      if (evt.defaultPrevented) return;
      const target = evt.target;
      if (
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' || target.tagName === 'SELECT' || target.tagName === 'TEXTAREA')
      ) {
        return;
      }
      if (evt.key.toLowerCase() !== 'f') return;
      evt.preventDefault();
      if (!document.fullscreenElement) {
        void document.documentElement.requestFullscreen?.();
      } else {
        void document.exitFullscreen?.();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useDocumentTitle(
    data?.title ? `${data.title} · ${t('poll.resultsOnlyTitle')}` : t('poll.resultsOnlyTitle'),
  );

  const options = useMemo(
    () =>
      (data?.options ?? []).map((label) => {
        const row = (data?.votes ?? []).find((v) => v.option === label);
        return { label, votes: Number(row?.vote_count ?? 0) || 0 };
      }),
    [data?.options, data?.votes],
  );
  const totalVotes = options.reduce((acc, o) => acc + o.votes, 0);
  const hasVotes = totalVotes > 0;
  const liveResultsAreDelayed = !!data?.live_results_are_delayed;
  const resultsDelaySeconds = Math.max(0, Number(data?.results_delay_seconds ?? 0) || 0);
  const delayedVotesPending = Math.max(0, Number(data?.delayed_votes_pending ?? 0) || 0);
  const [recentlyUpdatedOptions, setRecentlyUpdatedOptions] = useState<Set<string>>(new Set());
  const [resultsLivePulse, setResultsLivePulse] = useState(0);
  const previousVotesRef = useRef<Map<string, number>>(new Map());
  const previousTotalRef = useRef<number | null>(null);
  const clearHighlightsTimerRef = useRef<number | null>(null);

  const voteMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const option of options) map.set(option.label, option.votes);
    return map;
  }, [options]);

  useEffect(() => {
    if (voteMap.size === 0) {
      previousVotesRef.current = voteMap;
      previousTotalRef.current = totalVotes;
      setRecentlyUpdatedOptions((prev) => (prev.size === 0 ? prev : new Set()));
      return;
    }
    if (previousVotesRef.current.size === 0) {
      previousVotesRef.current = voteMap;
      previousTotalRef.current = totalVotes;
      return;
    }

    const changed = new Set<string>();
    for (const [label, votes] of voteMap.entries()) {
      if ((previousVotesRef.current.get(label) ?? votes) !== votes) changed.add(label);
    }
    const totalChanged =
      previousTotalRef.current !== null && previousTotalRef.current !== totalVotes;
    if (changed.size > 0 || totalChanged) {
      setRecentlyUpdatedOptions(changed);
      setResultsLivePulse((n) => n + 1);
      if (clearHighlightsTimerRef.current !== null) {
        window.clearTimeout(clearHighlightsTimerRef.current);
      }
      clearHighlightsTimerRef.current = window.setTimeout(() => {
        setRecentlyUpdatedOptions(new Set());
      }, 1400);
    }
    previousVotesRef.current = voteMap;
    previousTotalRef.current = totalVotes;
  }, [totalVotes, voteMap]);

  useEffect(() => {
    return () => {
      if (clearHighlightsTimerRef.current !== null) {
        window.clearTimeout(clearHighlightsTimerRef.current);
      }
    };
  }, []);

  if (isLoading) {
    return (
      <div className='ui-page-shell asking-public-layout asking-poll-page' id='asking-poll-page'>
        <p className='asking-poll-page__status asking-poll-page__status--loading'>{t('poll.loading')}</p>
      </div>
    );
  }

  if (isError) {
    const notFound = isApiFetchError(error) && error.status === 404;
    return (
      <div className='ui-page-shell asking-public-layout asking-poll-page' id='asking-poll-page'>
        <h1 className='asking-poll-page__title' id='asking-poll-page__title'>
          {notFound ? t('poll.notFound.title') : t('poll.resultsOnlyTitle')}
        </h1>
        <Alert>{notFound ? t('poll.notFound.body') : errMsg(error, t('poll.loadErr'))}</Alert>
        <p>
          <Link to='/$id' params={{ id }}>
            {t('poll.resultsBackToPoll')}
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div
      id='asking-poll-page'
      className={`ui-page-shell asking-public-layout asking-poll-page asking-poll-page--results-live${sceneSafeMode ? ' asking-poll-page--scene-safe' : ''}${presenterContrast ? ' asking-poll-page--presenter-contrast' : ''}`}
      data-results-live-pulse={resultsLivePulse}
    >
      <header className='asking-poll-page__header'>
        <div className='asking-poll-page__title-wrap'>
          <h1 className='asking-poll-page__title' id='asking-poll-page__title'>
            {data?.title}
          </h1>
          <p className='asking-poll-page__refresh-meta'>{t('poll.resultsOnlySubtitle')}</p>
        </div>
        <div
          className='asking-poll-page__results-toolbar'
          id='asking-poll-page__results-toolbar'
          role='group'
          aria-label={t('poll.resultsToolbarAria')}
        >
          <label
            className='asking-poll-page__results-toolbar-field'
            htmlFor='asking-poll-page__results-refresh-interval'
          >
            {t('poll.resultsRefreshLabel')}
            <select
              id='asking-poll-page__results-refresh-interval'
              className='ui-input ui-select ui-input--stack'
              value={String(refreshMs)}
              onChange={(evt) => setRefreshMs(Number(evt.target.value) || 5_000)}
            >
              <option value='2000'>{t('poll.resultsRefresh2s')}</option>
              <option value='5000'>{t('poll.resultsRefresh5s')}</option>
              <option value='10000'>{t('poll.resultsRefresh10s')}</option>
              <option value='30000'>{t('poll.resultsRefresh30s')}</option>
            </select>
          </label>
          <Button
            type='button'
            variant='secondary'
            size='sm'
            className='asking-poll-page__results-toolbar-btn'
            onClick={() => setSceneSafeMode((enabled) => !enabled)}
            aria-pressed={sceneSafeMode}
            title={t('poll.resultsSceneSafeTitle')}
          >
            {sceneSafeMode ? t('poll.resultsSceneSafeOn') : t('poll.resultsSceneSafeOff')}
          </Button>
          <Button
            type='button'
            variant='secondary'
            size='sm'
            className='asking-poll-page__results-toolbar-btn'
            onClick={() => setPresenterContrast((enabled) => !enabled)}
            aria-pressed={presenterContrast}
            title={t('poll.resultsContrastTitle')}
          >
            {presenterContrast ? t('poll.resultsContrastOn') : t('poll.resultsContrastOff')}
          </Button>
          <Button
            type='button'
            variant='secondary'
            size='sm'
            className='asking-poll-page__results-toolbar-btn'
            onClick={toggleFullscreen}
            title={t('poll.resultsFullscreenTitle')}
          >
            {fullscreenEnabled ? t('poll.resultsFullscreenOff') : t('poll.resultsFullscreenOn')}
          </Button>
        </div>
      </header>
      {data?.phase !== 'open' || data?.archived || data?.voting_paused ? (
        <p className='asking-poll-page__archived-note'>{t('poll.resultsOnlyClosedBadge')}</p>
      ) : (
        <p className='asking-poll-page__refresh-meta'>{t('poll.resultsOnlyLiveBadge')}</p>
      )}
      <section
        className={`asking-poll-page__vote-card${hasVotes ? '' : ' asking-poll-page__vote-card--empty'}`}
        id='asking-poll-page__results-summary'
        aria-label={t('poll.resultsOnlyAria')}
      >
        <div
          className='asking-poll-page__options-stack'
          id='asking-poll-page__results-options'
          role='group'
          aria-labelledby='asking-poll-page__title'
        >
          {options.map((o) => (
            <div
              key={o.label}
              className='asking-poll-page__option'
              data-updated={recentlyUpdatedOptions.has(o.label) ? 'true' : undefined}
              data-empty={hasVotes ? undefined : 'true'}
              aria-label={t('poll.votesCount', {
                title: o.label,
                count: formatLocaleInteger(o.votes, localeTag),
              })}
            >
              <span className='asking-poll-page__option-title'>{o.label}</span>
              <span className='asking-poll-page__option-result' title={resultPercent(o.votes, totalVotes)}>
                {formatLocaleInteger(o.votes, localeTag)} · {resultPercent(o.votes, totalVotes)}
              </span>
              <div className='asking-poll-page__option-fill-layer' aria-hidden='true'>
                <div
                  className='asking-poll-page__option-fill'
                  style={{ width: resultWidth(o.votes, totalVotes) }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>
      {liveResultsAreDelayed ? (
        <p className='asking-poll-page__refresh-meta'>
          {t('poll.resultsDelayInfo', {
            seconds: formatLocaleInteger(resultsDelaySeconds, localeTag),
            pending: formatLocaleInteger(delayedVotesPending, localeTag),
          })}
        </p>
      ) : null}
      <p
        className={`asking-poll-page__refresh-meta asking-poll-page__results-total asking-poll-page__results-total--live${hasVotes ? '' : ' asking-poll-page__results-total--empty'}`}
        data-updated={resultsLivePulse > 0 ? 'true' : undefined}
        role='status'
        aria-live='polite'
      >
        {t('poll.totalVotes', { count: formatLocaleInteger(totalVotes, localeTag) })}
      </p>
      {!sceneSafeMode ? (
        <p>
          <Link to='/$id' params={{ id }}>
            {t('poll.resultsBackToPoll')}
          </Link>
        </p>
      ) : null}
      {sceneSafeMode ? (
        <p className='asking-poll-page__refresh-meta asking-poll-page__results-shortcut-hint'>{t('poll.resultsFullscreenHint')}</p>
      ) : null}
    </div>
  );
}
