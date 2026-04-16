import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams, useSearch } from '@tanstack/react-router';
import Cookies from 'js-cookie';
import ReconnectingWebSocket from 'reconnecting-websocket';
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { apiUrl, pollWsUrl } from '../apiBase';
import CopyFeedbackButton from '../components/CopyFeedbackButton';
import { IconShare } from '../components/icons/UiIcons';
import SparklineBars from '../components/SparklineBars';
import SparklineLegend from '../components/SparklineLegend';
import VoteHeatmap from '../components/VoteHeatmap';
import { useOnline } from '../context/OnlineContext';
import { shareUrlForPoll, shareUrlForPollResults } from '../helpers/pollUrl';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch, isApiFetchError } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import type { MessageKey } from '../i18n/locales';
import { formatLocaleInteger } from '../lib/formatLocaleDisplay';
import { formatUtcHourAtTopOfHour } from '../lib/formatUtcHourAtTopOfHour';
import { formatUtcWeekdayShort } from '../lib/formatUtcWeekdayShort';
import {
  formatPollExpiryAbsolute,
  formatPollExpiryRelative,
} from '../lib/formatPollExpirationIntl';
import { openPollSyncChannel, postPollSync } from '../lib/pollBroadcast';
import {
  invalidatePollQueries,
  pollHeatmapQueryKey,
  pollQueryKey,
  pollReplayQueryKey,
} from '../lib/queryKeys';
import { getStoredUserJwt, subscribeUserJwtChanged } from '../lib/userSession';
import { streamingObsDocHref } from '../lib/streamingObsDocHref';
import { withUtm } from '../lib/withUtm';
import { isWebShareLikelyAvailable, shareUrlNative } from '../lib/webShare';
import { Button, cx, FormSection, Select, VisuallyHidden } from '../ui';
import { errMsg } from '../utils/errMsg';

const COOKIE_OPTS: Cookies.CookieAttributes = { path: '/' };

const POLL_REFRESH_MS_VISIBLE = 2000;
const POLL_REFRESH_MS_HIDDEN = 30_000;
/** When the live WebSocket is connected, poll HTTP occasionally as a safety net. */
const POLL_REFRESH_MS_LIVE_WS_FALLBACK = 60_000;
const SIMULATED_POLL_ID_PREFIX = 'sim_';

function isSimulatedPollId(id: string): boolean {
  return id.toLowerCase().startsWith(SIMULATED_POLL_ID_PREFIX);
}

type PollApiRow = { option: string; vote_count: string | number };
type PollApiData = {
  title: string;
  expiration: number | string;
  archived?: boolean;
  options: string[];
  votes: PollApiRow[];
  phase?: string;
  voting_paused?: boolean;
  pause_message?: string | null;
  impression_count?: number;
  show_notes?: string;
  embed_gate?: boolean;
  you_own_this_poll?: boolean;
  metrics?: {
    total_votes?: number;
    votes_last_5m?: number;
    engagement_velocity_votes_per_min?: number | null;
    completion_rate_pct?: number | null;
    option_coverage_pct?: number | null;
    leader_margin_pct?: number | null;
    time_to_first_vote_ms?: number | null;
    peak_hour_utc?: number | null;
    peak_hour_votes?: number;
    peak_dow_utc?: number | null;
    peak_dow_votes?: number;
    hourly_votes_by_hour_utc?: number[];
    weekday_votes_by_dow_utc?: number[];
    option_hourly_votes_utc?: Array<{
      option: string;
      hourly_votes_by_hour_utc?: number[];
    }>;
    vote_velocity_by_minute_utc?: Array<{
      minute_utc: string;
      vote_count: number;
    }>;
    vote_velocity_by_minute_utc_truncated?: boolean;
  };
  results_delay_seconds?: number;
  live_results_are_delayed?: boolean;
  results_visible_through_ms?: number;
  delayed_votes_pending?: number;
  theme_preset?: 'default' | 'sunset' | 'ocean' | 'neon';
  selection_mode?: 'single' | 'multi';
  vote_eligibility?: 'anonymous' | 'account';
  moderation_counters?: {
    quarantined_votes_pending?: number;
    trust_ip_burst?: {
      enabled: boolean;
      window_sec?: number;
      vote_threshold?: number;
    };
    trust_chat_burst?: {
      enabled: boolean;
      window_sec?: number;
      vote_threshold?: number;
    };
  };
};

type PollViewModel = {
  title: string;
  expiration: number;
  archived: boolean;
  phase: string;
  votingPaused: boolean;
  pauseMessage: string | null;
  impressionCount: number;
  showNotes?: string;
  embedGate: boolean;
  youOwnThisPoll: boolean;
  options: { title: string; votes: number }[];
  totalVotes: number;
  maxVotes: number;
  metrics: {
    votesLast5m: number;
    engagementVelocityVotesPerMin: number | null;
    completionRatePct: number | null;
    optionCoveragePct: number | null;
    leaderMarginPct: number | null;
    timeToFirstVoteMs: number | null;
    peakHourUtc: number | null;
    peakHourVotes: number;
    peakDowUtc: number | null;
    peakDowVotes: number;
    hourlyVotesByHourUtc: number[];
    weekdayVotesByDowUtc: number[];
    optionHourlyVotesUtc?: Array<{ option: string; hourlyVotesByHourUtc: number[] }>;
    voteVelocityByMinuteUtc?: Array<{ minuteUtcIso: string; voteCount: number }>;
    voteVelocityByMinuteTruncated?: boolean;
  };
  resultsDelaySeconds: number;
  liveResultsAreDelayed: boolean;
  resultsVisibleThroughMs: number | null;
  delayedVotesPending: number;
  themePreset: 'default' | 'sunset' | 'ocean' | 'neon';
  selectionMode: 'single' | 'multi';
  voteEligibility: 'anonymous' | 'account';
  moderationCounters?: {
    quarantinedVotesPending: number;
    trustIpBurst: { enabled: false } | { enabled: true; windowSec: number; voteThreshold: number };
    trustChatBurst: { enabled: false } | { enabled: true; windowSec: number; voteThreshold: number };
  };
};

function mapPollPayload(json: { data: PollApiData }): PollViewModel {
  const data = json.data;
  const expiration = Number(data.expiration);
  const archived = !!data.archived;
  const phase = data.phase ?? 'open';
  const votingPaused = !!data.voting_paused;
  const pauseMessage =
    data.pause_message === null || data.pause_message === undefined ? null : data.pause_message;
  const impressionCount =
    typeof data.impression_count === 'number' && Number.isFinite(data.impression_count)
      ? data.impression_count
      : 0;
  const showNotes =
    typeof data.show_notes === 'string' && data.show_notes.trim() !== ''
      ? data.show_notes
      : undefined;
  const mc = data.moderation_counters;
  let moderationCounters: PollViewModel['moderationCounters'] | undefined;
  if (mc && typeof mc === 'object') {
    const pending = Number(mc.quarantined_votes_pending ?? 0) || 0;
    const ip = mc.trust_ip_burst;
    const chat = mc.trust_chat_burst;
    const trustIpBurst =
      ip && typeof ip === 'object' && ip.enabled === true
        ? {
            enabled: true as const,
            windowSec: Math.max(1, Number(ip.window_sec) || 10),
            voteThreshold: Math.max(1, Number(ip.vote_threshold) || 1),
          }
        : ({ enabled: false as const });
    const trustChatBurst =
      chat && typeof chat === 'object' && chat.enabled === true
        ? {
            enabled: true as const,
            windowSec: Math.max(1, Number(chat.window_sec) || 10),
            voteThreshold: Math.max(1, Number(chat.vote_threshold) || 1),
          }
        : ({ enabled: false as const });
    moderationCounters = {
      quarantinedVotesPending: pending,
      trustIpBurst,
      trustChatBurst,
    };
  }

  const voteData = data.options.map((option) => ({ title: option, votes: 0 }));
  (data.votes || []).forEach((vote) => {
    const row = voteData.find((o) => o.title === vote.option);
    if (row) row.votes = parseInt(String(vote.vote_count), 10) || 0;
  });
  let total = 0;
  let max = 0;
  voteData.forEach((option) => {
    total += option.votes;
    if (option.votes > max) max = option.votes;
  });
  return {
    title: data.title,
    expiration,
    archived,
    phase,
    votingPaused,
    pauseMessage,
    impressionCount,
    embedGate: !!data.embed_gate,
    youOwnThisPoll: !!data.you_own_this_poll,
    ...(showNotes !== undefined ? { showNotes } : {}),
    options: voteData,
    totalVotes: total,
    maxVotes: max,
    metrics: {
      votesLast5m: Number(data.metrics?.votes_last_5m ?? 0) || 0,
      engagementVelocityVotesPerMin:
        typeof data.metrics?.engagement_velocity_votes_per_min === 'number'
          ? data.metrics.engagement_velocity_votes_per_min
          : null,
      completionRatePct:
        typeof data.metrics?.completion_rate_pct === 'number'
          ? data.metrics.completion_rate_pct
          : null,
      optionCoveragePct:
        typeof data.metrics?.option_coverage_pct === 'number'
          ? data.metrics.option_coverage_pct
          : null,
      leaderMarginPct:
        typeof data.metrics?.leader_margin_pct === 'number' ? data.metrics.leader_margin_pct : null,
      timeToFirstVoteMs:
        typeof data.metrics?.time_to_first_vote_ms === 'number'
          ? data.metrics.time_to_first_vote_ms
          : null,
      peakHourUtc:
        typeof data.metrics?.peak_hour_utc === 'number' ? data.metrics.peak_hour_utc : null,
      peakHourVotes: Number(data.metrics?.peak_hour_votes ?? 0) || 0,
      peakDowUtc: typeof data.metrics?.peak_dow_utc === 'number' ? data.metrics.peak_dow_utc : null,
      peakDowVotes: Number(data.metrics?.peak_dow_votes ?? 0) || 0,
      hourlyVotesByHourUtc: Array.from(
        { length: 24 },
        (_, i) => Number(data.metrics?.hourly_votes_by_hour_utc?.[i] ?? 0) || 0,
      ),
      weekdayVotesByDowUtc: Array.from(
        { length: 7 },
        (_, i) => Number(data.metrics?.weekday_votes_by_dow_utc?.[i] ?? 0) || 0,
      ),
      ...(Array.isArray(data.metrics?.option_hourly_votes_utc) &&
      data.metrics.option_hourly_votes_utc.length > 0
        ? {
            optionHourlyVotesUtc: data.metrics.option_hourly_votes_utc.map((row) => {
              const r = row as { option?: unknown; hourly_votes_by_hour_utc?: unknown };
              const bins = Array.isArray(r.hourly_votes_by_hour_utc) ? r.hourly_votes_by_hour_utc : [];
              return {
                option: typeof r.option === 'string' ? r.option : '',
                hourlyVotesByHourUtc: Array.from(
                  { length: 24 },
                  (_, i) => Number(bins[i] ?? 0) || 0,
                ),
              };
            }),
          }
        : {}),
      ...(Array.isArray(data.metrics?.vote_velocity_by_minute_utc) &&
      data.metrics.vote_velocity_by_minute_utc.length > 0
        ? {
            voteVelocityByMinuteUtc: data.metrics.vote_velocity_by_minute_utc.map((row) => {
              const r = row as { minute_utc?: unknown; vote_count?: unknown };
              const iso =
                typeof r.minute_utc === 'string'
                  ? r.minute_utc
                  : typeof r.minute_utc === 'number' && Number.isFinite(r.minute_utc)
                    ? new Date(r.minute_utc).toISOString()
                    : '';
              return {
                minuteUtcIso: iso,
                voteCount: Number(r.vote_count ?? 0) || 0,
              };
            }),
            ...(data.metrics.vote_velocity_by_minute_utc_truncated === true
              ? { voteVelocityByMinuteTruncated: true }
              : {}),
          }
        : {}),
    },
    resultsDelaySeconds: Math.max(0, Number(data.results_delay_seconds ?? 0) || 0),
    liveResultsAreDelayed: !!data.live_results_are_delayed,
    resultsVisibleThroughMs:
      typeof data.results_visible_through_ms === 'number' &&
      Number.isFinite(data.results_visible_through_ms)
        ? data.results_visible_through_ms
        : null,
    delayedVotesPending: Math.max(0, Number(data.delayed_votes_pending ?? 0) || 0),
    themePreset:
      data.theme_preset === 'sunset' ||
      data.theme_preset === 'ocean' ||
      data.theme_preset === 'neon'
        ? data.theme_preset
        : 'default',
    selectionMode: data.selection_mode === 'multi' ? 'multi' : 'single',
    voteEligibility: data.vote_eligibility === 'account' ? 'account' : 'anonymous',
    ...(moderationCounters !== undefined ? { moderationCounters } : {}),
  };
}

type PollQueryResult =
  | { kind: 'ok'; poll: PollViewModel }
  | { kind: 'notfound' }
  | { kind: 'error'; message: string };

type VoteLocation = {
  latitude: number;
  longitude: number;
  accuracyM?: number;
};

type HeatmapPoint = {
  latitude: number;
  longitude: number;
  intensity: number;
};

type HeatmapApiData = {
  points: HeatmapPoint[];
  minCount: number;
  note?: string;
};

type ReplayEvent = {
  option_index: number;
  offset_ms: number;
};

type ReplayApiData = {
  options: string[];
  total_votes: number;
  completed: boolean;
  events: ReplayEvent[];
};

async function fetchPollQuery(
  id: string,
  loadErrFallback: string,
  embedToken: string,
  campaignParams: { utmSource?: string; utmMedium?: string; utmCampaign?: string },
): Promise<PollQueryResult> {
  try {
    const jwt = getStoredUserJwt()?.trim();
    const qs = new URLSearchParams();
    if (campaignParams.utmSource) qs.set('utm_source', campaignParams.utmSource);
    if (campaignParams.utmMedium) qs.set('utm_medium', campaignParams.utmMedium);
    if (campaignParams.utmCampaign) qs.set('utm_campaign', campaignParams.utmCampaign);
    const path = qs.size > 0 ? `poll/${id}?${qs.toString()}` : `poll/${id}`;
    const json = (await apiFetch(path, {
      embedToken: embedToken || undefined,
      ...(jwt ? { bearerToken: jwt } : {}),
    })) as { data: PollApiData };
    return { kind: 'ok', poll: mapPollPayload(json) };
  } catch (err: unknown) {
    if (isApiFetchError(err) && err.status === 404) return { kind: 'notfound' };
    return { kind: 'error', message: errMsg(err, loadErrFallback) };
  }
}

/** Minute bucket for throttled screen-reader expiry updates (aligned to remaining time). */
function expiryLiveBucket(expiration: number, nowMs: number): number {
  if (!Number.isFinite(expiration) || expiration <= 0) return -3;
  const ms = new Date(expiration).getTime() - nowMs;
  if (ms < 0) return -1;
  const hours = Math.floor(ms / 3600000);
  if (hours > 864000) return -2;
  return Math.floor(ms / 60000);
}

type TMessage = (key: MessageKey, vars?: Record<string, string | number>) => string;

function formatExpiryAnnouncement(
  t: TMessage,
  expiration: number,
  nowMs: number,
  localeTag: string,
): string {
  const rel = formatPollExpiryRelative(localeTag, expiration, nowMs);
  if (rel.state === 'invalid') return '';
  if (rel.state === 'expired') return t('poll.expired');
  if (rel.state === 'never') return `${t('poll.expires')} ${t('poll.timeNever')}`;
  return `${t('poll.expires')} ${rel.text}`;
}

function formatReplayClock(ms: number): string {
  const clamped = Math.max(0, Math.floor(ms));
  const totalSec = Math.floor(clamped / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function Poll() {
  const t = useT();
  const localeTag = useLocaleTag();
  const online = useOnline();
  const { id } = useParams({ from: '/$id', strict: true });
  const {
    embed_token: embedTokenRaw,
    utm_source: utmSourceRaw,
    utm_medium: utmMediumRaw,
    utm_campaign: utmCampaignRaw,
  } = useSearch({ from: '/$id', strict: true });
  const embedToken = embedTokenRaw?.trim() ?? '';
  const utmSource = utmSourceRaw?.trim() ?? '';
  const utmMedium = utmMediumRaw?.trim() ?? '';
  const utmCampaign = utmCampaignRaw?.trim() ?? '';
  const trackingKey = `${utmSource}|${utmMedium}|${utmCampaign}`;
  const queryClient = useQueryClient();

  const [pollRefreshMs, setPollRefreshMs] = useState(() =>
    typeof document !== 'undefined' && document.visibilityState === 'hidden'
      ? POLL_REFRESH_MS_HIDDEN
      : POLL_REFRESH_MS_VISIBLE,
  );
  const [userVotedOn, setUserVotedOn] = useState(-1);
  const [multiDraft, setMultiDraft] = useState<Set<number>>(() => new Set());
  const [multiSubmitted, setMultiSubmitted] = useState(false);
  const [optionIsHovering, setOptionIsHovering] = useState<boolean[]>([]);
  const [linkHint, setLinkHint] = useState('');
  const [ownerShareHint, setOwnerShareHint] = useState('');
  const [voteError, setVoteError] = useState('');
  const [geoOptInChecked, setGeoOptInChecked] = useState(false);
  const [geoOptIn, setGeoOptIn] = useState(false);
  const [geoHint, setGeoHint] = useState('');
  /** Roving tabindex index within the voting radiogroup (keyboard). */
  const [rovingIndex, setRovingIndex] = useState(0);
  const optionBtnRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const moveRovingFocusFromKeyboard = useRef(false);
  /** Bumps once per second so the expiry countdown stays current between API polls. */
  const [uiTick, setUiTick] = useState(0);
  const [expiryAnnouncement, setExpiryAnnouncement] = useState('');
  const lastExpiryBucketRef = useRef<number | null>(null);
  const [hasUserJwt, setHasUserJwt] = useState(() => Boolean(getStoredUserJwt()?.trim()));
  const [liveWsOpen, setLiveWsOpen] = useState(false);
  const [liveWsSubscriberLimitHit, setLiveWsSubscriberLimitHit] = useState(false);
  const [replayEnabled, setReplayEnabled] = useState(false);
  const [replaySpeed, setReplaySpeed] = useState(1);
  const [replayPositionMs, setReplayPositionMs] = useState(0);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [recentlyUpdatedOptions, setRecentlyUpdatedOptions] = useState<Set<number>>(new Set());
  const [resultsLivePulse, setResultsLivePulse] = useState(0);
  const previousOptionVotesRef = useRef<number[]>([]);
  const previousTotalVotesRef = useRef<number | null>(null);
  const liveHighlightClearTimerRef = useRef<number | null>(null);

  const pollHttpRefetchMs = useMemo(() => {
    if (!online) return false;
    if (liveWsOpen) return POLL_REFRESH_MS_LIVE_WS_FALLBACK;
    return pollRefreshMs;
  }, [online, liveWsOpen, pollRefreshMs]);

  const { data, isLoading } = useQuery({
    queryKey: pollQueryKey(id, embedToken, trackingKey),
    queryFn: () =>
      fetchPollQuery(id, t('poll.loadErr'), embedToken, {
        utmSource: utmSource || undefined,
        utmMedium: utmMedium || undefined,
        utmCampaign: utmCampaign || undefined,
      }),
    refetchInterval: pollHttpRefetchMs,
  });

  useEffect(() => {
    if (data?.kind !== 'ok') return;
    const ve = data.poll.voteEligibility ?? 'anonymous';
    if (ve !== 'account' || hasUserJwt) return;
    Cookies.remove(id, COOKIE_OPTS);
    setUserVotedOn(-1);
    setMultiSubmitted(false);
    setMultiDraft(new Set());
  }, [id, data, hasUserJwt]);

  const wsUrlOpts = useMemo(() => {
    const et = embedToken.trim();
    if (et) return { embedToken: et } as const;
    if (!data || data.kind !== 'ok') return undefined;
    if (!data.poll.embedGate || !data.poll.youOwnThisPoll) return undefined;
    const jwt = getStoredUserJwt()?.trim();
    return jwt ? ({ wsBearer: jwt } as const) : undefined;
  }, [data, embedToken]);

  const ownerShareKit = useMemo(() => {
    if (data?.kind !== 'ok' || !data.poll.youOwnThisPoll || !hasUserJwt) return null;
    const pollShareUrl = shareUrlForPoll(id);
    const resultsShareUrl = shareUrlForPollResults(id);
    return {
      chatVoteSnippet: `!vote ${id} <option_number>`,
      chatShareSnippet: `!poll ${pollShareUrl}`,
      qrUrl: `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(pollShareUrl)}`,
      presets: [
        {
          id: 'overlay',
          label: t('myPolls.sharePresetOverlayLabel'),
          url: withUtm(pollShareUrl, { source: 'stream', medium: 'overlay', campaign: 'live_poll' }),
          cta: t('myPolls.sharePresetOverlayCta'),
        },
        {
          id: 'chat',
          label: t('myPolls.sharePresetChatLabel'),
          url: withUtm(pollShareUrl, { source: 'stream', medium: 'chat', campaign: 'live_poll' }),
          cta: t('myPolls.sharePresetChatCta'),
        },
        {
          id: 'mobile',
          label: t('myPolls.sharePresetMobileLabel'),
          url: withUtm(pollShareUrl, { source: 'mobile', medium: 'share', campaign: 'live_poll' }),
          cta: t('myPolls.sharePresetMobileCta'),
        },
        {
          id: 'results',
          label: t('myPolls.sharePresetResultsLabel'),
          url: withUtm(resultsShareUrl, {
            source: 'stream',
            medium: 'results_scene',
            campaign: 'live_poll',
          }),
          cta: t('myPolls.sharePresetResultsCta'),
        },
      ],
    };
  }, [data, id, hasUserJwt, t]);

  useEffect(() => {
    const syncJwt = () => setHasUserJwt(Boolean(getStoredUserJwt()?.trim()));
    syncJwt();
    return subscribeUserJwtChanged(syncJwt);
  }, []);

  useEffect(() => {
    const sync = () => {
      setPollRefreshMs(
        document.visibilityState === 'hidden' ? POLL_REFRESH_MS_HIDDEN : POLL_REFRESH_MS_VISIBLE,
      );
    };
    const onVis = () => {
      sync();
      if (document.visibilityState === 'visible') {
        invalidatePollQueries(queryClient, id, embedToken, trackingKey);
      }
    };
    sync();
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, [id, embedToken, queryClient]);

  const pollBcRef = useRef<BroadcastChannel | null>(null);
  useEffect(() => {
    const ch = openPollSyncChannel();
    pollBcRef.current = ch;
    if (!ch) return;
    const onMsg = (ev: MessageEvent<{ type?: string; pollId?: string }>) => {
      const data = ev.data;
      if (!data || typeof data !== 'object') return;
      if (data.pollId !== id) return;
      if (data.type === 'invalidate' || data.type === 'voted') {
        invalidatePollQueries(queryClient, id, embedToken, trackingKey);
      }
    };
    ch.addEventListener('message', onMsg);
    return () => {
      ch.removeEventListener('message', onMsg);
      ch.close();
      pollBcRef.current = null;
    };
  }, [id, embedToken, queryClient]);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof WebSocket === 'undefined') return;
    if (data?.kind !== 'ok') {
      setLiveWsOpen(false);
      return;
    }
    let ws: ReconnectingWebSocket | undefined;
    setLiveWsOpen(false);
    try {
      const url = pollWsUrl(id, wsUrlOpts);
      ws = new ReconnectingWebSocket(url, [], {
        WebSocket,
        minReconnectionDelay: 1000,
        maxReconnectionDelay: 10_000,
        reconnectionDelayGrowFactor: 1.5,
        connectionTimeout: 4000,
      });
      ws.onopen = () => {
        setLiveWsOpen(true);
        setLiveWsSubscriberLimitHit(false);
      };
      ws.onclose = (ev) => {
        setLiveWsOpen(false);
        const code = typeof ev.code === 'number' ? ev.code : 0;
        const reason = typeof ev.reason === 'string' ? ev.reason : '';
        if (code === 1008 && reason.includes('USAGE_LIMIT_WS_SUBSCRIBERS')) {
          setLiveWsSubscriberLimitHit(true);
        }
      };
      ws.onmessage = (evt) => {
        try {
          const raw = JSON.parse(String(evt.data)) as { type?: string };
          if (raw?.type === 'update' || raw?.type === 'deleted' || raw?.type === 'panic') {
            invalidatePollQueries(queryClient, id, embedToken, trackingKey);
          }
        } catch {
          invalidatePollQueries(queryClient, id, embedToken, trackingKey);
        }
      };
    } catch {
      setLiveWsOpen(false);
    }
    return () => {
      ws?.close(1000, 'component unmount');
      setLiveWsOpen(false);
    };
  }, [data?.kind, id, embedToken, queryClient, wsUrlOpts]);

  useLayoutEffect(() => {
    setVoteError('');
    setLinkHint('');
    setOwnerShareHint('');
    setRovingIndex(0);
    lastExpiryBucketRef.current = null;
    setMultiDraft(new Set());
    setMultiSubmitted(false);
    setLiveWsSubscriberLimitHit(false);
  }, [id]);

  useEffect(() => {
    const raw = Cookies.get(id);
    if (raw !== undefined && raw !== null && raw !== '') {
      if (String(raw).startsWith('m:')) {
        setMultiSubmitted(true);
        const parts = String(raw)
          .slice(2)
          .split(',')
          .map((s) => parseInt(s.trim(), 10))
          .filter((n) => !Number.isNaN(n));
        setMultiDraft(new Set(parts));
        setUserVotedOn(-1);
        return;
      }
      const idx = parseInt(String(raw), 10);
      if (!Number.isNaN(idx)) {
        setUserVotedOn(idx);
        setMultiSubmitted(false);
        setMultiDraft(new Set());
      } else {
        setUserVotedOn(-1);
        setMultiSubmitted(false);
        setMultiDraft(new Set());
      }
    } else {
      setUserVotedOn(-1);
      setMultiSubmitted(false);
      setMultiDraft(new Set());
    }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const embedQ = embedToken ? `?embed_token=${encodeURIComponent(embedToken)}` : '';
    const href = `${apiUrl(`poll/${encodeURIComponent(id)}/embed`)}${embedQ}`;
    const link = document.createElement('link');
    link.rel = 'alternate';
    link.type = 'application/json+oembed';
    link.href = href;
    link.setAttribute('data-asking-ng-oembed', id);
    document.head.appendChild(link);
    return () => {
      link.remove();
    };
  }, [id, embedToken]);

  const poll = data?.kind === 'ok' ? data.poll : null;
  const pollNotFound = data?.kind === 'notfound';
  const fetchError = data?.kind === 'error' ? data.message : '';

  const title = poll?.title ?? '';
  const pollOptions = poll?.options ?? [];
  const totalVotes = poll?.totalVotes ?? 0;
  const maxVotes = poll?.maxVotes ?? 0;
  const expiration = poll?.expiration ?? 0;
  const archived = poll?.archived ?? false;
  const phase = poll?.phase ?? 'open';
  const votingPaused = poll?.votingPaused ?? false;
  const pauseMessage = poll?.pauseMessage ?? null;
  const impressionCount = poll?.impressionCount ?? 0;
  const showNotes = poll?.showNotes;
  const themePreset = poll?.themePreset ?? 'default';
  const selectionMode = poll?.selectionMode ?? 'single';
  const voteEligibility = poll?.voteEligibility ?? 'anonymous';
  const needsAccountToVote = voteEligibility === 'account' && !hasUserJwt;
  const isMulti = selectionMode === 'multi';
  const pollMetrics = poll?.metrics;
  const resultsDelaySeconds = poll?.resultsDelaySeconds ?? 0;
  const liveResultsAreDelayed = poll?.liveResultsAreDelayed ?? false;
  const delayedVotesPending = poll?.delayedVotesPending ?? 0;
  const formatPct = (v: number | null | undefined) =>
    typeof v === 'number' && Number.isFinite(v) ? `${v.toFixed(1)}%` : '—';
  const formatVelocity = (v: number | null | undefined) =>
    typeof v === 'number' && Number.isFinite(v) ? `${v.toFixed(2)}/min` : '—';
  const formatDuration = (ms: number | null | undefined) => {
    if (typeof ms !== 'number' || !Number.isFinite(ms) || ms < 0) return '—';
    if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
    return `${Math.round(ms / 60_000)}m`;
  };
  const formatDowUtc = (dow: number | null | undefined) => formatUtcWeekdayShort(localeTag, dow, '—');
  const formatHourUtc = (hour: number | null | undefined) =>
    formatUtcHourAtTopOfHour(localeTag, hour, '—');
  const formatHourBucketUtc = (h: number) => formatUtcHourAtTopOfHour(localeTag, h, String(h));
  const weekdayAxis = Array.from({ length: 7 }, (_, i) => formatDowUtc(i)).join(' ');

  useEffect(() => {
    if (poll) {
      setOptionIsHovering(poll.options.map(() => false));
    } else {
      setOptionIsHovering([]);
    }
  }, [poll]);

  useEffect(() => {
    optionBtnRefs.current.length = pollOptions.length;
  }, [pollOptions.length]);

  const expired = expiration > 0 && Date.now() > expiration;
  const completed = archived || expired || phase !== 'open';
  const phaseBlocksVoting = phase !== 'open';
  const showResults =
    archived ||
    expired ||
    userVotedOn > -1 ||
    multiSubmitted ||
    votingPaused ||
    phaseBlocksVoting ||
    needsAccountToVote;
  const simulatedPoll = isSimulatedPollId(id);
  const votingDisabled =
    archived ||
    expired ||
    userVotedOn > -1 ||
    multiSubmitted ||
    votingPaused ||
    phaseBlocksVoting ||
    needsAccountToVote;
  const multiPicking = isMulti && !multiSubmitted && !votingDisabled;
  const useVoteRadios = !votingDisabled && !isMulti;
  const pollStateLabel = archived
    ? t('poll.stateArchived')
    : expired
      ? t('poll.stateExpired')
      : votingPaused
        ? t('poll.statePaused')
        : phase === 'locked'
          ? t('poll.stateLocked')
          : phase === 'draft'
            ? t('poll.stateDraft')
            : phase === 'revealed'
              ? t('poll.stateRevealed')
              : userVotedOn > -1 || multiSubmitted
                ? t('poll.stateVoted')
                : t('poll.stateOpen');

  const heatmapQuery = useQuery({
    queryKey: pollHeatmapQueryKey(id, embedToken, trackingKey),
    queryFn: () =>
      apiFetch(`poll/${id}/heatmap?minCount=2`, {
        embedToken: embedToken || undefined,
      }) as Promise<{ data: HeatmapApiData }>,
    enabled: showResults,
    staleTime: 20_000,
    refetchInterval: showResults && online ? 60_000 : false,
  });

  const replayQuery = useQuery({
    queryKey: pollReplayQueryKey(id, embedToken, trackingKey),
    queryFn: () =>
      apiFetch(`poll/${id}/replay?limit=10000`, {
        embedToken: embedToken || undefined,
      }) as Promise<{ data: ReplayApiData }>,
    enabled: completed && showResults,
    staleTime: 60_000,
  });

  const replayEvents = replayQuery.data?.data.events ?? [];
  const replayDurationMs = replayEvents.length
    ? replayEvents[replayEvents.length - 1]?.offset_ms || 0
    : 0;
  const replaySliderMax = Math.max(1, replayDurationMs);

  useEffect(() => {
    setReplayEnabled(false);
    setReplayPlaying(false);
    setReplayPositionMs(0);
    setReplaySpeed(1);
  }, [id]);

  useEffect(() => {
    if (!replayEnabled) return;
    if (!replayEvents.length) {
      setReplayEnabled(false);
      return;
    }
    if (replayPositionMs > replayDurationMs) setReplayPositionMs(replayDurationMs);
  }, [replayEnabled, replayEvents.length, replayDurationMs, replayPositionMs]);

  useEffect(() => {
    if (!replayPlaying || !replayEnabled) return;
    let raf = 0;
    let prevTs = performance.now();
    const onFrame = (ts: number) => {
      const dt = ts - prevTs;
      prevTs = ts;
      setReplayPositionMs((ms) => {
        const next = ms + dt * replaySpeed;
        if (next >= replayDurationMs) {
          setReplayPlaying(false);
          return replayDurationMs;
        }
        return next;
      });
      raf = requestAnimationFrame(onFrame);
    };
    raf = requestAnimationFrame(onFrame);
    return () => cancelAnimationFrame(raf);
  }, [replayEnabled, replayPlaying, replaySpeed, replayDurationMs]);

  const replayOptionCounts = useMemo(() => {
    const counts = pollOptions.map(() => 0);
    if (!replayEnabled || !replayEvents.length) return counts;
    for (const ev of replayEvents) {
      if (ev.offset_ms > replayPositionMs) break;
      if (ev.option_index < 0 || ev.option_index >= counts.length) continue;
      counts[ev.option_index] += 1;
    }
    return counts;
  }, [pollOptions, replayEnabled, replayEvents, replayPositionMs]);

  const replayTotals = useMemo(() => {
    if (!replayEnabled) return { total: totalVotes, max: maxVotes };
    let total = 0;
    let max = 0;
    for (const c of replayOptionCounts) {
      total += c;
      if (c > max) max = c;
    }
    return { total, max };
  }, [replayEnabled, replayOptionCounts, totalVotes, maxVotes]);

  const options = useMemo(() => {
    if (!replayEnabled) return pollOptions;
    return pollOptions.map((o, index) => ({ ...o, votes: replayOptionCounts[index] ?? 0 }));
  }, [pollOptions, replayEnabled, replayOptionCounts]);

  useEffect(() => {
    if (!showResults || replayEnabled || options.length === 0) {
      setRecentlyUpdatedOptions(new Set());
      previousOptionVotesRef.current = options.map((o) => o.votes);
      previousTotalVotesRef.current = totalVotes;
      return;
    }

    const nextVotes = options.map((o) => o.votes);
    const previousVotes = previousOptionVotesRef.current;
    if (previousVotes.length === 0 || previousVotes.length !== nextVotes.length) {
      previousOptionVotesRef.current = nextVotes;
      previousTotalVotesRef.current = totalVotes;
      return;
    }

    const changedIndices: number[] = [];
    for (let i = 0; i < nextVotes.length; i += 1) {
      if (nextVotes[i] !== previousVotes[i]) changedIndices.push(i);
    }
    const totalChanged =
      previousTotalVotesRef.current !== null && previousTotalVotesRef.current !== totalVotes;

    if (changedIndices.length > 0 || totalChanged) {
      setRecentlyUpdatedOptions(new Set(changedIndices));
      setResultsLivePulse((n) => n + 1);
      if (liveHighlightClearTimerRef.current !== null) {
        window.clearTimeout(liveHighlightClearTimerRef.current);
      }
      liveHighlightClearTimerRef.current = window.setTimeout(() => {
        setRecentlyUpdatedOptions(new Set());
      }, 1400);
    }

    previousOptionVotesRef.current = nextVotes;
    previousTotalVotesRef.current = totalVotes;
  }, [options, replayEnabled, showResults, totalVotes]);

  useEffect(() => {
    return () => {
      if (liveHighlightClearTimerRef.current !== null) {
        window.clearTimeout(liveHighlightClearTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!useVoteRadios || options.length === 0) return;
    setRovingIndex((i) => Math.min(Math.max(0, i), options.length - 1));
  }, [options.length, useVoteRadios]);

  useLayoutEffect(() => {
    if (!moveRovingFocusFromKeyboard.current || !useVoteRadios) return;
    moveRovingFocusFromKeyboard.current = false;
    optionBtnRefs.current[rovingIndex]?.focus();
  }, [rovingIndex, useVoteRadios]);

  useDocumentTitle(pollNotFound ? t('poll.docTitleNotFound') : title.trim() || undefined);

  const voteMutation = useMutation({
    mutationFn: (
      args:
        | { optionTitle: string; location?: VoteLocation | null }
        | { option_indices: number[]; location?: VoteLocation | null },
    ) => {
      const sessionJwt = getStoredUserJwt()?.trim();
      return apiFetch(`poll/${id}/vote`, {
        method: 'PUT',
        body:
          'option_indices' in args
            ? { option_indices: args.option_indices, ...(args.location ? { location: args.location } : {}) }
            : { option: args.optionTitle, ...(args.location ? { location: args.location } : {}) },
        embedToken: embedToken || undefined,
        ...(sessionJwt ? { bearerToken: sessionJwt } : {}),
      });
    },
    onSuccess: () => {
      setVoteError('');
      postPollSync(pollBcRef.current, { type: 'voted', pollId: id });
      invalidatePollQueries(queryClient, id, embedToken, trackingKey);
    },
    onError: (err: unknown) => {
      Cookies.remove(id, COOKIE_OPTS);
      setUserVotedOn(-1);
      setMultiSubmitted(false);
      setMultiDraft(new Set());
      setVoteError(errMsg(err, t('poll.voteFail')));
      invalidatePollQueries(queryClient, id, embedToken, trackingKey);
    },
  });

  const pollReady =
    !isLoading && !pollNotFound && !(fetchError && !title.trim()) && Boolean(title.trim());

  useEffect(() => {
    if (!pollReady) return;
    const tick = window.setInterval(() => setUiTick((n) => n + 1), 1000);
    return () => clearInterval(tick);
  }, [pollReady, id]);

  useEffect(() => {
    void uiTick;
    if (!pollReady) {
      setExpiryAnnouncement('');
      lastExpiryBucketRef.current = null;
      return;
    }
    const now = Date.now();
    const bucket = expiryLiveBucket(expiration, now);
    if (bucket === -3) {
      setExpiryAnnouncement('');
      lastExpiryBucketRef.current = bucket;
      return;
    }
    if (lastExpiryBucketRef.current === bucket) return;
    lastExpiryBucketRef.current = bucket;
    setExpiryAnnouncement(formatExpiryAnnouncement(t, expiration, now, localeTag));
  }, [pollReady, expiration, uiTick, t, localeTag]);

  const calculateResultWidth = (votes: number, total: number) => {
    if (!total || total <= 0) return '0%';
    const pct = ((votes / total) * 100) | 0;
    return pct < 7 ? '0%' : `${pct}%`;
  };

  const handleOptionHover = (index: number, hovering: boolean) => {
    const next = [...optionIsHovering];
    next[index] = hovering;
    setOptionIsHovering(next);
  };

  const handleOptionPress = (index: number, pressed: boolean) => {
    handleOptionHover(index, pressed);
  };

  const resolveVoteLocation = async (): Promise<VoteLocation | null> => {
    if (!geoOptIn) return null;
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setGeoHint(t('poll.geoUnavailable'));
      return null;
    }
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const { latitude, longitude, accuracy } = pos.coords;
          resolve({
            latitude,
            longitude,
            accuracyM: Number.isFinite(accuracy) ? Math.round(accuracy) : undefined,
          });
        },
        () => {
          setGeoHint(t('poll.geoDenied'));
          resolve(null);
        },
        {
          enableHighAccuracy: false,
          timeout: 7000,
          maximumAge: 60_000,
        },
      );
    });
  };

  const handleOptionClick = (index: number) => {
    if (votingDisabled) return;
    if (isMulti) {
      setMultiDraft((prev) => {
        const next = new Set(prev);
        if (next.has(index)) next.delete(index);
        else next.add(index);
        return next;
      });
      return;
    }
    const optionTitle = options[index]?.title;
    if (!optionTitle) return;

    setRovingIndex(index);
    setUserVotedOn(index);
    Cookies.set(id, `${index}`, COOKIE_OPTS);

    const newOptions = [...options];
    newOptions[index] = { ...newOptions[index], votes: newOptions[index].votes + 1 };
    let total = 0;
    let max = 0;
    newOptions.forEach((option) => {
      total += option.votes;
      if (option.votes > max) max = option.votes;
    });
    queryClient.setQueryData<PollQueryResult>(pollQueryKey(id, embedToken, trackingKey), (prev) => {
      if (!prev || prev.kind !== 'ok') return prev;
      return {
        kind: 'ok',
        poll: {
          ...prev.poll,
          options: newOptions,
          totalVotes: total,
          maxVotes: max,
        },
      };
    });

    void resolveVoteLocation().then((location) => {
      voteMutation.mutate({ optionTitle, location });
    });
  };

  const handleMultiSubmit = () => {
    if (!isMulti || multiSubmitted || votingDisabled) return;
    const indices = Array.from(multiDraft).sort((a, b) => a - b);
    if (indices.length === 0) return;
    setMultiSubmitted(true);
    Cookies.set(id, `m:${indices.join(',')}`, COOKIE_OPTS);
    const newOptions = options.map((o, i) => ({
      ...o,
      votes: o.votes + (multiDraft.has(i) ? 1 : 0),
    }));
    let total = 0;
    let max = 0;
    newOptions.forEach((option) => {
      total += option.votes;
      if (option.votes > max) max = option.votes;
    });
    queryClient.setQueryData<PollQueryResult>(pollQueryKey(id, embedToken, trackingKey), (prev) => {
      if (!prev || prev.kind !== 'ok') return prev;
      return {
        kind: 'ok',
        poll: {
          ...prev.poll,
          options: newOptions,
          totalVotes: total,
          maxVotes: max,
        },
      };
    });
    void resolveVoteLocation().then((location) => {
      voteMutation.mutate({ option_indices: indices, location });
    });
  };

  const copyPollShareUrlWithHint = async (setHint: (msg: string) => void): Promise<boolean> => {
    const url = shareUrlForPoll(id);
    try {
      await navigator.clipboard.writeText(url);
      setHint(t('poll.copyOk'));
      return true;
    } catch {
      setHint(t('poll.copyManual') + ` ${url}`);
      return false;
    }
  };

  const copyShareLink = async (): Promise<boolean> => copyPollShareUrlWithHint(setLinkHint);

  const sharePollLink = async (setHint: (msg: string) => void = setLinkHint) => {
    setHint('');
    const url = shareUrlForPoll(id);
    const r = await shareUrlNative({
      url,
      title: title.trim() || undefined,
      text: title.trim() ? `${title.trim()} — ${url}` : url,
    });
    if (r.kind === 'shared') {
      setHint(t('poll.shareDone'));
      return;
    }
    if (r.kind === 'aborted') return;
    await copyPollShareUrlWithHint(setHint);
  };

  const showShareButton = useMemo(() => isWebShareLikelyAvailable(shareUrlForPoll(id)), [id]);

  const embedViewerUrl = useMemo(() => {
    const et = embedToken.trim();
    if (!et) return '';
    return `${apiUrl(`poll/${encodeURIComponent(id)}/embed`)}?embed_token=${encodeURIComponent(et)}`;
  }, [embedToken, id]);

  const renderExpiration = () => {
    const nowMs = Date.now();
    const rel = formatPollExpiryRelative(localeTag, expiration, nowMs);
    if (rel.state === 'invalid') return null;
    if (rel.state === 'expired') {
      return <p className='poll-expired-msg'>{t('poll.expired')}</p>;
    }
    if (rel.state === 'never') {
      return (
        <p>
          {t('poll.expires')} {t('poll.timeNever')}
        </p>
      );
    }
    const abs = formatPollExpiryAbsolute(localeTag, expiration);
    return (
      <p title={abs}>
        {t('poll.expires')} {rel.text}
      </p>
    );
  };

  const handleOptionKeyDown = (index: number, e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (multiPicking) {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        handleOptionClick(index);
      }
      return;
    }
    if (!useVoteRadios) return;
    const len = options.length;
    if (len === 0) return;
    switch (e.key) {
      case 'ArrowDown':
      case 'ArrowRight':
        e.preventDefault();
        moveRovingFocusFromKeyboard.current = true;
        setRovingIndex((i) => (i + 1) % len);
        break;
      case 'ArrowUp':
      case 'ArrowLeft':
        e.preventDefault();
        moveRovingFocusFromKeyboard.current = true;
        setRovingIndex((i) => (i - 1 + len) % len);
        break;
      case 'Home':
        e.preventDefault();
        moveRovingFocusFromKeyboard.current = true;
        setRovingIndex(0);
        break;
      case 'End':
        e.preventDefault();
        moveRovingFocusFromKeyboard.current = true;
        setRovingIndex(len - 1);
        break;
      case ' ':
      case 'Enter':
        e.preventDefault();
        handleOptionClick(index);
        break;
      default:
        break;
    }
  };

  const renderOptions = () => {
    return options.map((option, index) => {
      const isLeading = showResults && option.votes === replayTotals.max && replayTotals.max > 0;
      const fillLeader = option.votes === replayTotals.max;

      return (
        <button
          key={index}
          ref={(el) => {
            optionBtnRefs.current[index] = el;
          }}
          type='button'
          className='poll-option'
          disabled={votingDisabled}
          tabIndex={useVoteRadios ? (index === rovingIndex ? 0 : -1) : multiPicking ? 0 : undefined}
          data-hover={optionIsHovering[index] ? 'true' : undefined}
          data-archived={votingDisabled && archived ? 'true' : undefined}
          role={multiPicking ? 'checkbox' : useVoteRadios ? 'radio' : undefined}
          aria-checked={
            multiPicking ? multiDraft.has(index) : useVoteRadios ? userVotedOn === index : undefined
          }
          aria-setsize={useVoteRadios ? options.length : undefined}
          aria-posinset={useVoteRadios ? index + 1 : undefined}
          aria-pressed={!useVoteRadios && !multiPicking ? userVotedOn === index : undefined}
          aria-label={
            showResults
              ? `${t('poll.votesCount', { title: option.title, count: formatLocaleInteger(option.votes, localeTag) })}${isLeading ? `, ${t('poll.leadingSr')}` : ''}`
              : t('poll.voteFor', { title: option.title })
          }
          data-leading={showResults && isLeading ? 'true' : undefined}
          data-updated={showResults && recentlyUpdatedOptions.has(index) ? 'true' : undefined}
          onMouseEnter={() => handleOptionHover(index, true)}
          onMouseLeave={() => handleOptionHover(index, false)}
          onPointerDown={() => handleOptionPress(index, true)}
          onPointerUp={() => handleOptionPress(index, false)}
          onPointerCancel={() => handleOptionPress(index, false)}
          onBlur={() => handleOptionPress(index, false)}
          onKeyDown={(e) => handleOptionKeyDown(index, e)}
          onClick={() => handleOptionClick(index)}
        >
          <span className={`poll-option-title${isLeading ? ' poll-option-title--leading' : ''}`}>
            {option.title}
            {isLeading ? (
              <span className='poll-leading-badge' aria-hidden='true'>
                {t('poll.leadingBadge')}
              </span>
            ) : null}
          </span>
          {showResults && (
            <>
              <span
                className={`poll-option-result${isLeading ? ' poll-option-result--leading' : ''}`}
              >
                {formatLocaleInteger(option.votes, localeTag)}
              </span>
              <div className='poll-option-fill-layer' aria-hidden='true'>
                <div
                  className={`poll-option-fill${fillLeader ? ' poll-option-fill--leader' : ''}`}
                  style={{ width: calculateResultWidth(option.votes, replayTotals.total) }}
                />
              </div>
            </>
          )}
        </button>
      );
    });
  };

  if (isLoading && !pollNotFound && !fetchError) {
    return (
      <div className='ui-page-shell site-public poll-page'>
        <p className='poll-status poll-status-loading' role='status' aria-live='polite'>
          {t('poll.loading')}
        </p>
      </div>
    );
  }

  if (pollNotFound) {
    return (
      <div className='ui-page-shell site-public poll-page'>
        <h1 className='poll-page-title poll-header'>{t('poll.notFound.title')}</h1>
        <p className='poll-status'>{t('poll.notFound.body')}</p>
        <p>
          <Link to='/'>{t('poll.notFound.cta')}</Link>
        </p>
      </div>
    );
  }

  if (fetchError && !title.trim()) {
    return (
      <div className='ui-page-shell site-public poll-page'>
        <p className='error-message' role='alert'>
          {fetchError}
        </p>
        <p>
          <Link to='/'>{t('poll.backHome')}</Link>
        </p>
      </div>
    );
  }

  return (
    <div
      className={`ui-page-shell site-public poll-page${liveWsOpen ? ' poll-page--live-connected' : ''}`}
      data-results-live-pulse={resultsLivePulse}
      data-poll-theme={themePreset}
    >
      <header className='poll-page-header'>
        <h1 className='poll-page-title poll-header' id='poll-page-title'>
          {title}
        </h1>
        <div className='poll-page-toolbar'>
          <CopyFeedbackButton onCopy={copyShareLink}>{t('poll.copyLink')}</CopyFeedbackButton>
          <Link
            to='/$id/results'
            params={{ id }}
            search={embedToken ? { embed_token: embedToken } : {}}
            className={cx('ui-button', 'ui-button--md', 'ui-button--secondary')}
          >
            {t('poll.resultsOnlyTitle')}
          </Link>
          {showShareButton ? (
            <Button
              type='button'
              variant='secondary'
              className='ui-button--with-inline-icon'
              onClick={() => void sharePollLink()}
            >
              <IconShare className='ui-button__icon' aria-hidden />
              {t('poll.shareLink')}
            </Button>
          ) : null}
          {linkHint ? (
            <span
              className='poll-status poll-status-success poll-copy-hint'
              role='status'
              aria-live='polite'
            >
              {linkHint}
            </span>
          ) : null}
        </div>
      </header>
      {archived ? <p className='poll-archived-note'>{t('poll.archived')}</p> : null}
      {simulatedPoll ? <p className='poll-sim-warning'>{t('poll.simulationNotice')}</p> : null}
      {votingPaused && !archived ? (
        <p className='poll-archived-note' role='status'>
          {pauseMessage?.trim() ? pauseMessage : t('poll.votingPausedDefault')}
        </p>
      ) : null}
      {!votingPaused && !archived && phase === 'locked' ? (
        <p className='poll-archived-note'>{t('poll.phaseLockedHint')}</p>
      ) : null}
      {!votingPaused && !archived && phase === 'draft' ? (
        <p className='poll-archived-note'>{t('poll.phaseDraftHint')}</p>
      ) : null}
      {!votingPaused && !archived && phase === 'revealed' ? (
        <p className='poll-archived-note'>{t('poll.phaseRevealedHint')}</p>
      ) : null}
      {showNotes ? (
        <section className='ui-poll-notes-card' aria-labelledby='poll-show-notes-h'>
          <h3 id='poll-show-notes-h' className='ui-poll-notes-card-title'>
            {t('poll.showNotesTitle')}
          </h3>
          <pre className='poll-show-notes'>{showNotes}</pre>
        </section>
      ) : null}
      {ownerShareKit ? (
        <details className='ui-disclosure poll-owner-share-details'>
          <summary className='ui-disclosure-summary'>
            <span className='ui-disclosure-summary-title'>{t('myPolls.distributionHeading')}</span>
            <span className='ui-disclosure-summary-hint'>{t('myPolls.distributionHint')}</span>
          </summary>
          <div className='ui-disclosure-body poll-owner-share-body'>
            {voteEligibility === 'account' ? (
              <p className='poll-refresh-meta' role='note'>
                {t('home.voteEligibility.accountConsentNote')}
              </p>
            ) : null}
            <p className='poll-refresh-meta' style={{ marginBlockEnd: 12 }}>
              <a href={streamingObsDocHref()} target='_blank' rel='noopener noreferrer'>
                {t('docs.streamingObsBrowserSource')}
              </a>
            </p>
            <FormSection className='ui-form-block' title={t('myPolls.chatSnippetVote')}>
              <code className='ui-code-block'>{ownerShareKit.chatVoteSnippet}</code>
            </FormSection>
            <FormSection className='ui-form-block' title={t('myPolls.chatSnippetShare')}>
              <code className='ui-code-block'>{ownerShareKit.chatShareSnippet}</code>
              <CopyFeedbackButton
                onCopy={async () => {
                  try {
                    await navigator.clipboard.writeText(ownerShareKit.chatShareSnippet);
                    setOwnerShareHint(t('myPolls.copyDone'));
                    return true;
                  } catch {
                    return false;
                  }
                }}
              >
                {t('myPolls.copySnippet')}
              </CopyFeedbackButton>
            </FormSection>
            <FormSection className='ui-form-block' title={t('myPolls.publicPollUrl')}>
              <code className='ui-code-block'>{shareUrlForPoll(id)}</code>
              <div className='ui-inline-actions'>
                <CopyFeedbackButton
                  onCopy={async () => {
                    try {
                      await navigator.clipboard.writeText(shareUrlForPoll(id));
                      setOwnerShareHint(t('myPolls.copyDone'));
                      return true;
                    } catch {
                      return false;
                    }
                  }}
                >
                  {t('myPolls.sharePresetCopyLink')}
                </CopyFeedbackButton>
                {showShareButton ? (
                  <Button
                    type='button'
                    variant='secondary'
                    className='ui-button--with-inline-icon'
                    onClick={() => void sharePollLink(setOwnerShareHint)}
                  >
                    <IconShare className='ui-button__icon' aria-hidden />
                    {t('poll.shareLink')}
                  </Button>
                ) : null}
              </div>
            </FormSection>
            {embedViewerUrl ? (
              <FormSection
                className='ui-form-block'
                title={t('myPolls.embedFrameUrl')}
                hint={t('myPolls.embedFrameUrlHint')}
              >
                <code className='ui-code-block'>{embedViewerUrl}</code>
                <div className='ui-inline-actions'>
                  <CopyFeedbackButton
                    onCopy={async () => {
                      try {
                        await navigator.clipboard.writeText(embedViewerUrl);
                        setOwnerShareHint(t('myPolls.copyDone'));
                        return true;
                      } catch {
                        return false;
                      }
                    }}
                  >
                    {t('myPolls.sharePresetCopyLink')}
                  </CopyFeedbackButton>
                </div>
              </FormSection>
            ) : null}
            <FormSection
              className='ui-form-block'
              title={t('myPolls.sharePresets')}
              hint={t('myPolls.sharePresetsHint')}
            >
              {ownerShareKit.presets.map((preset) => (
                <div key={preset.id} className='poll-owner-share-preset'>
                  <p className='ui-form-hint' style={{ marginBlockEnd: 6 }}>
                    <strong>{preset.label}:</strong>
                  </p>
                  <code className='ui-code-block'>{preset.url}</code>
                  <code className='ui-code-block'>
                    {preset.cta} {preset.url}
                  </code>
                  <div className='ui-inline-actions'>
                    <CopyFeedbackButton
                      onCopy={async () => {
                        try {
                          await navigator.clipboard.writeText(preset.url);
                          setOwnerShareHint(t('myPolls.copyDone'));
                          return true;
                        } catch {
                          return false;
                        }
                      }}
                    >
                      {t('myPolls.sharePresetCopyLink')}
                    </CopyFeedbackButton>
                    <CopyFeedbackButton
                      onCopy={async () => {
                        try {
                          await navigator.clipboard.writeText(`${preset.cta} ${preset.url}`);
                          setOwnerShareHint(t('myPolls.copyDone'));
                          return true;
                        } catch {
                          return false;
                        }
                      }}
                    >
                      {t('myPolls.sharePresetCopyCta')}
                    </CopyFeedbackButton>
                  </div>
                </div>
              ))}
            </FormSection>
            <FormSection className='ui-form-block' title={t('myPolls.qrLabel')} hint={t('myPolls.qrHint')}>
              <img
                src={ownerShareKit.qrUrl}
                width={180}
                height={180}
                alt={t('myPolls.qrAlt', { title: title.trim() || id })}
                loading='lazy'
              />
            </FormSection>
            {ownerShareHint ? (
              <p className='poll-status poll-status-success' role='status' aria-live='polite'>
                {ownerShareHint}
              </p>
            ) : null}
            <p className='poll-refresh-meta'>
              <Link to='/my-polls'>{t('nav.myPolls')}</Link>
              {' — '}
              {t('poll.ownerShareAdvancedHint')}
            </p>
            {poll && poll.moderationCounters ? (
              <>
                <p className='poll-refresh-meta poll-owner-trust-hint' role='note'>
                  {poll.moderationCounters.trustIpBurst.enabled
                    ? t('poll.trustIpBurstOn', {
                        window: formatLocaleInteger(
                          poll.moderationCounters.trustIpBurst.windowSec,
                          localeTag,
                        ),
                        threshold: formatLocaleInteger(
                          poll.moderationCounters.trustIpBurst.voteThreshold,
                          localeTag,
                        ),
                        pending: formatLocaleInteger(
                          poll.moderationCounters.quarantinedVotesPending,
                          localeTag,
                        ),
                      })
                    : t('poll.trustIpBurstOff', {
                        pending: formatLocaleInteger(
                          poll.moderationCounters.quarantinedVotesPending,
                          localeTag,
                        ),
                      })}
                </p>
                <p className='poll-refresh-meta poll-owner-trust-hint' role='note'>
                  {poll.moderationCounters.trustChatBurst.enabled
                    ? t('poll.trustChatBurstOn', {
                        window: formatLocaleInteger(
                          poll.moderationCounters.trustChatBurst.windowSec,
                          localeTag,
                        ),
                        threshold: formatLocaleInteger(
                          poll.moderationCounters.trustChatBurst.voteThreshold,
                          localeTag,
                        ),
                        pending: formatLocaleInteger(
                          poll.moderationCounters.quarantinedVotesPending,
                          localeTag,
                        ),
                      })
                    : t('poll.trustChatBurstOff', {
                        pending: formatLocaleInteger(
                          poll.moderationCounters.quarantinedVotesPending,
                          localeTag,
                        ),
                      })}
                </p>
              </>
            ) : null}
          </div>
        </details>
      ) : null}
      <div className='poll-meta-row'>
        <span className='poll-chip' title={t('poll.state.label')}>
          {pollStateLabel}
        </span>
        {simulatedPoll ? (
          <span className='poll-chip poll-chip--sim'>{t('poll.simulationBadge')}</span>
        ) : null}
        <div className='poll-expiry-slot'>{renderExpiration()}</div>
      </div>
      {liveWsSubscriberLimitHit ? (
        <p className='ui-copy-muted' role='status'>
          {t('poll.billingWsSubscriberLimitHint')}
        </p>
      ) : null}
      <p className='poll-instructions'>
        {!votingDisabled
          ? isMulti
            ? t('poll.instructions.multi')
            : t('poll.instructions.vote')
          : t('poll.votingClosedHint')}
      </p>
      {!completed ? (
        <p className='poll-refresh-meta poll-replay-hint'>{t('poll.replayActiveHint')}</p>
      ) : null}
      <div className='poll-footer-meta'>
        <p className='poll-status poll-refresh-meta'>
          {liveWsOpen
            ? t('poll.refreshHintLive', {
                fallback: formatLocaleInteger(POLL_REFRESH_MS_LIVE_WS_FALLBACK / 1000, localeTag),
              })
            : t('poll.refreshHint', {
                visible: formatLocaleInteger(POLL_REFRESH_MS_VISIBLE / 1000, localeTag),
                hidden: formatLocaleInteger(POLL_REFRESH_MS_HIDDEN / 1000, localeTag),
              })}
        </p>
        <p
          className={`poll-status poll-refresh-meta${showResults ? ' poll-results-total poll-results-total--live' : ''}`}
          data-updated={showResults && resultsLivePulse > 0 ? 'true' : undefined}
          role='status'
        >
          {t('poll.impressions', { count: formatLocaleInteger(impressionCount, localeTag) })}
        </p>
        {showResults && liveResultsAreDelayed ? (
          <p className='poll-status poll-refresh-meta'>
            {t('poll.resultsDelayInfo', {
              seconds: formatLocaleInteger(resultsDelaySeconds, localeTag),
              pending: formatLocaleInteger(delayedVotesPending, localeTag),
            })}
          </p>
        ) : null}
      </div>
      {showResults ? (
        <div className='poll-live-insights-grid'>
          <section className='poll-replay-wrap poll-metrics-wrap' aria-label={t('poll.metricsSectionAria')}>
            <h3>{t('poll.metricsTitle')}</h3>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.votesLast5mVelocity', {
                count: formatLocaleInteger(pollMetrics?.votesLast5m ?? 0, localeTag),
              })}
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.lifetimeVelocity', {
                value: formatVelocity(pollMetrics?.engagementVelocityVotesPerMin),
              })}
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.completionRate', { pct: formatPct(pollMetrics?.completionRatePct) })}
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.optionCoverage', { pct: formatPct(pollMetrics?.optionCoveragePct) })}
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.leaderMargin', { pct: formatPct(pollMetrics?.leaderMarginPct) })}
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.timeToFirstResponse', {
                value: formatDuration(pollMetrics?.timeToFirstVoteMs),
              })}
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.peakHour', {
                hour: formatHourUtc(pollMetrics?.peakHourUtc),
                votes: pollMetrics?.peakHourVotes ?? 0,
              })}
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.peakDay', {
                day: formatDowUtc(pollMetrics?.peakDowUtc),
                votes: pollMetrics?.peakDowVotes ?? 0,
              })}
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.hourly')}{' '}
              <span aria-hidden='true'>
                <SparklineBars
                  values={pollMetrics?.hourlyVotesByHourUtc ?? Array.from({ length: 24 }, () => 0)}
                  bucketLabel={(i) => formatHourBucketUtc(i)}
                  maxHeightPx={24}
                />
              </span>
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.hourlyAxis', {
                start: formatHourBucketUtc(0),
                end: formatHourBucketUtc(23),
              })}
            </p>
            <p className='poll-refresh-meta'>
              <SparklineLegend
                values={pollMetrics?.hourlyVotesByHourUtc ?? Array.from({ length: 24 }, () => 0)}
                bucketLabel={(i) => formatHourBucketUtc(i)}
                labels={{
                  min: t('sparkline.min'),
                  max: t('sparkline.max'),
                  peak: t('sparkline.peak'),
                }}
              />
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.weekday')}{' '}
              <span aria-hidden='true'>
                <SparklineBars
                  values={pollMetrics?.weekdayVotesByDowUtc ?? Array.from({ length: 7 }, () => 0)}
                  bucketLabel={(i) => `${formatDowUtc(i)}`}
                  maxHeightPx={24}
                />
              </span>
            </p>
            <p className='poll-refresh-meta'>
              {t('poll.metrics.weekdayAxis', { days: weekdayAxis })}
            </p>
            <p className='poll-refresh-meta'>
              <SparklineLegend
                values={pollMetrics?.weekdayVotesByDowUtc ?? Array.from({ length: 7 }, () => 0)}
                bucketLabel={(i) => `${formatDowUtc(i)}`}
                labels={{
                  min: t('sparkline.min'),
                  max: t('sparkline.max'),
                  peak: t('sparkline.peak'),
                }}
              />
            </p>
            {poll?.youOwnThisPoll &&
            pollMetrics?.voteVelocityByMinuteUtc &&
            pollMetrics.voteVelocityByMinuteUtc.length > 0 ? (
              <>
                <h4 className='poll-metrics-subhead'>{t('poll.metrics.velocityByMinuteTitle')}</h4>
                <p className='poll-refresh-meta ui-copy-muted'>{t('poll.metrics.velocityByMinuteHint')}</p>
                {pollMetrics.voteVelocityByMinuteTruncated ? (
                  <p className='poll-refresh-meta poll-metrics-velocity-truncated' role='status'>
                    {t('poll.metrics.velocityByMinuteTruncated')}
                  </p>
                ) : null}
                <div
                  className='poll-metrics-velocity-scroll'
                  role='group'
                  aria-label={t('poll.metrics.velocityByMinuteAria')}
                >
                  <SparklineBars
                    values={pollMetrics.voteVelocityByMinuteUtc.map((v) => v.voteCount)}
                    bucketLabel={(i) => {
                      const iso = pollMetrics.voteVelocityByMinuteUtc![i]?.minuteUtcIso ?? '';
                      const ms = Date.parse(iso);
                      if (!Number.isFinite(ms)) return iso || String(i);
                      return new Intl.DateTimeFormat(localeTag, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false,
                        timeZone: 'UTC',
                      }).format(new Date(ms));
                    }}
                    maxHeightPx={28}
                    barWidthPx={pollMetrics.voteVelocityByMinuteUtc.length > 200 ? 1 : 2}
                  />
                </div>
                <p className='poll-refresh-meta'>
                  <SparklineLegend
                    values={pollMetrics.voteVelocityByMinuteUtc.map((v) => v.voteCount)}
                    bucketLabel={(i) => {
                      const iso = pollMetrics.voteVelocityByMinuteUtc![i]?.minuteUtcIso ?? '';
                      const ms = Date.parse(iso);
                      if (!Number.isFinite(ms)) return iso || String(i);
                      return new Intl.DateTimeFormat(localeTag, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false,
                        timeZone: 'UTC',
                      }).format(new Date(ms));
                    }}
                    labels={{
                      min: t('sparkline.min'),
                      max: t('sparkline.max'),
                      peak: t('sparkline.peak'),
                    }}
                  />
                </p>
              </>
            ) : null}
            {poll?.youOwnThisPoll &&
            pollMetrics?.optionHourlyVotesUtc &&
            pollMetrics.optionHourlyVotesUtc.length > 0 ? (
              <>
                <h4 className='poll-metrics-subhead'>{t('poll.metrics.optionHourlyTitle')}</h4>
                <p className='poll-refresh-meta ui-copy-muted'>{t('poll.metrics.optionHourlyHint')}</p>
                {pollMetrics.optionHourlyVotesUtc.map((row) => (
                  <p key={row.option} className='poll-refresh-meta poll-metrics-option-hourly-row'>
                    <span className='poll-metrics-option-hourly-label'>{row.option}</span>{' '}
                    <span aria-hidden='true'>
                      <SparklineBars
                        values={row.hourlyVotesByHourUtc}
                        bucketLabel={(i) => formatHourBucketUtc(i)}
                        maxHeightPx={20}
                        barWidthPx={3}
                      />
                    </span>
                  </p>
                ))}
                <p className='poll-refresh-meta'>
                  {t('poll.metrics.hourlyAxis', {
                    start: formatHourBucketUtc(0),
                    end: formatHourBucketUtc(23),
                  })}
                </p>
              </>
            ) : null}
          </section>
          {showResults && completed ? (
            <section className='poll-replay-wrap' aria-live='polite'>
              <h3>{t('poll.replayTitle')}</h3>
              {replayQuery.isLoading ? (
                <p className='poll-status'>{t('poll.replayLoading')}</p>
              ) : null}
              {replayQuery.isError ? (
                <p className='poll-status poll-status-error'>{t('poll.replayError')}</p>
              ) : null}
              {!replayQuery.isLoading && !replayQuery.isError ? (
                replayEvents.length > 0 ? (
                  <div className='poll-replay-controls'>
                    <Button
                      type='button'
                      variant='secondary'
                      onClick={() => {
                        setReplayEnabled((v) => !v);
                        setReplayPlaying(false);
                        setReplayPositionMs(0);
                      }}
                    >
                      {replayEnabled ? t('poll.replayDisable') : t('poll.replayEnable')}
                    </Button>
                    {replayEnabled ? (
                      <>
                        <Button type='button' variant='secondary' onClick={() => setReplayPlaying((v) => !v)}>
                          {replayPlaying ? t('poll.replayPause') : t('poll.replayPlay')}
                        </Button>
                        <Button
                          type='button'
                          variant='secondary'
                          onClick={() => {
                            setReplayPlaying(false);
                            setReplayPositionMs(0);
                          }}
                        >
                          {t('poll.replayReset')}
                        </Button>
                        <Button
                          type='button'
                          variant='secondary'
                          onClick={() => {
                            setReplayPlaying(false);
                            setReplayPositionMs((ms) => Math.max(0, ms - 5000));
                          }}
                        >
                          {t('poll.replaySeekBack')}
                        </Button>
                        <Button
                          type='button'
                          variant='secondary'
                          onClick={() => {
                            setReplayPlaying(false);
                            setReplayPositionMs((ms) => Math.min(replayDurationMs, ms + 5000));
                          }}
                        >
                          {t('poll.replaySeekForward')}
                        </Button>
                        <label className='poll-replay-speed'>
                          {t('poll.replaySpeed')}
                          <Select
                            className='ui-input--stack'
                            value={String(replaySpeed)}
                            onChange={(e) => setReplaySpeed(Number(e.target.value) || 1)}
                          >
                            <option value='0.5'>0.5x</option>
                            <option value='1'>1x</option>
                            <option value='2'>2x</option>
                            <option value='4'>4x</option>
                          </Select>
                        </label>
                        <div className='poll-replay-timeline'>
                          <input
                            type='range'
                            min={0}
                            max={replaySliderMax}
                            step={50}
                            value={Math.min(replayPositionMs, replaySliderMax)}
                            aria-label={t('poll.replayTimelineAria')}
                            onChange={(e) => {
                              setReplayEnabled(true);
                              setReplayPlaying(false);
                              setReplayPositionMs(Number(e.target.value) || 0);
                            }}
                          />
                          <div className='poll-replay-time-row' aria-hidden='true'>
                            <span>{formatReplayClock(replayPositionMs)}</span>
                            <span>{formatReplayClock(replayDurationMs)}</span>
                          </div>
                        </div>
                        <p className='poll-refresh-meta'>
                          {t('poll.replayVotesShown', {
                            shown: replayTotals.total,
                            total: replayEvents.length,
                          })}
                        </p>
                      </>
                    ) : null}
                  </div>
                ) : (
                  <p className='poll-status'>{t('poll.replayEmpty')}</p>
                )
              ) : null}
            </section>
          ) : null}
          {showResults ? (
            <section className='poll-heatmap-wrap' aria-live='polite'>
              <h3>{t('poll.heatmapTitle')}</h3>
              <p className='poll-refresh-meta'>{t('poll.heatmapPrivacy')}</p>
              {heatmapQuery.isLoading ? (
                <p className='poll-status'>{t('poll.heatmapLoading')}</p>
              ) : null}
              {heatmapQuery.isError ? (
                <p className='poll-status poll-status-error'>{t('poll.heatmapError')}</p>
              ) : null}
              {!heatmapQuery.isLoading && !heatmapQuery.isError ? (
                (heatmapQuery.data?.data.points.length || 0) > 0 ? (
                  <VoteHeatmap
                    points={heatmapQuery.data?.data.points || []}
                    ariaLabel={t('poll.heatmapAria')}
                  />
                ) : (
                  <p className='poll-status'>{t('poll.heatmapEmpty')}</p>
                )
              ) : null}
            </section>
          ) : null}
        </div>
      ) : null}
      {fetchError ? (
        <p className='error-message' role='alert'>
          {fetchError}
        </p>
      ) : null}
      {voteError ? (
        <p className='error-message' role='alert'>
          {voteError}
        </p>
      ) : null}
      {needsAccountToVote && pollReady ? (
        <>
          <p className='poll-status' role='status'>
            {t('poll.signInToVote')}{' '}
            <Link to='/login'>{t('poll.signInToVoteCta')}</Link>
          </p>
          <p className='poll-refresh-meta' role='note'>
            {t('poll.accountGatedPrivacy')}
          </p>
        </>
      ) : null}
      <section className='poll-vote-card' aria-label={t('poll.voteCardAria')}>
        {!votingDisabled ? (
          <div className='poll-geo-optin'>
            <label>
              <input
                type='checkbox'
                checked={geoOptIn}
                onChange={(e) => {
                  setGeoOptInChecked(true);
                  setGeoOptIn(e.target.checked);
                  setGeoHint('');
                }}
              />{' '}
              {t('poll.geoOptIn')}
            </label>
            <p className='poll-refresh-meta'>
              {t('poll.geoPrivacy')}
              {geoOptInChecked && geoOptIn ? ` ${t('poll.geoEnabled')}` : ''}
            </p>
            {geoHint ? (
              <p className='poll-status poll-status-error' role='status' aria-live='polite'>
                {geoHint}
              </p>
            ) : null}
          </div>
        ) : null}
        {useVoteRadios && options.length > 1 ? (
          <VisuallyHidden as='p' id='poll-vote-keyboard-hint'>
            {t('poll.voteKeyboardHint')}
          </VisuallyHidden>
        ) : null}
        <div
          className='poll-options-stack'
          role={useVoteRadios ? 'radiogroup' : multiPicking ? 'group' : 'group'}
          aria-labelledby='poll-page-title'
          aria-describedby={
            useVoteRadios && options.length > 1 ? 'poll-vote-keyboard-hint' : undefined
          }
        >
          {renderOptions()}
        </div>
        {multiPicking ? (
          <div className='poll-multi-submit-row'>
            <Button
              type='button'
              variant='primary'
              disabled={multiDraft.size === 0 || voteMutation.isPending}
              onClick={() => handleMultiSubmit()}
            >
              {t('poll.submitMultiVote')}
            </Button>
            {multiDraft.size === 0 ? (
              <span className='poll-refresh-meta'>{t('poll.multiSubmitHint')}</span>
            ) : null}
          </div>
        ) : null}
      </section>
      <div className='poll-mobile-actions' aria-label={t('poll.mobileQuickActionsAria')}>
        <CopyFeedbackButton onCopy={copyShareLink}>{t('poll.copyLink')}</CopyFeedbackButton>
        {showShareButton ? (
          <Button
            type='button'
            variant='secondary'
            className='ui-button--with-inline-icon'
            onClick={() => void sharePollLink()}
          >
            <IconShare className='ui-button__icon' aria-hidden />
            {t('poll.shareLink')}
          </Button>
        ) : null}
      </div>
      {expiryAnnouncement ? (
        <VisuallyHidden as='p' role='status' aria-live='polite' aria-atomic='true'>
          {expiryAnnouncement}
        </VisuallyHidden>
      ) : null}
    </div>
  );
}
