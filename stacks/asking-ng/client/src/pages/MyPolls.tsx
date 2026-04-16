import {
  allowedPollPhaseTargets,
  normalizePollPhase,
  type PollPhase,
  type UpdatePollBody,
} from '@asking-ng/contracts/poll';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from '@tanstack/react-router';
import React, { useEffect, useMemo, useState } from 'react';
import { apiUrl } from '../apiBase';
import CopyFeedbackButton from '../components/CopyFeedbackButton';
import { IconActivity, IconDownload, IconShare, IconTrash2 } from '../components/icons/UiIcons';
import SparklineBars from '../components/SparklineBars';
import { shareUrlForPoll, shareUrlForPollResults } from '../helpers/pollUrl';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { apiFetch } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import {
  billingPastDueBannerPayload,
  billingUsageAtCap,
  billingUsageWarningSeverity,
  type ProfileBillingApiPayload,
} from '../lib/profileBillingApi';
import { mineQueryKey, mineQueryPrefix, profileBillingQueryKey, quarantineQueryKey } from '../lib/queryKeys';
import { isWebShareLikelyAvailable, shareUrlNative } from '../lib/webShare';
import { withUtm } from '../lib/withUtm';
import { clearStoredUserJwt, getStoredUserJwt, subscribeUserJwtChanged } from '../lib/userSession';
import {
  Button,
  Checkbox,
  Container,
  cx,
  FormRow,
  FormSection,
  Inline,
  Input,
  Select,
  Textarea,
} from '../ui';
import { formatQuarantineReasonLabel } from '../lib/formatQuarantineReasonLabel';
import { formatUtcHourAtTopOfHour } from '../lib/formatUtcHourAtTopOfHour';
import { formatUtcWeekdayShort } from '../lib/formatUtcWeekdayShort';
import { streamingObsDocHref } from '../lib/streamingObsDocHref';
import { errMsg } from '../utils/errMsg';

type MinePoll = {
  id: string;
  title: string;
  archived: boolean;
  createdAt: string;
  hasWebhook: boolean;
  webhook_targets?: Array<{ url: string; secret?: string }>;
  phase: string;
  voting_paused: boolean;
  pause_message: string | null;
  show_notes: string | null;
  shared_editor_user_ids: number[];
  theme_preset?: 'default' | 'sunset' | 'ocean' | 'neon';
  selection_mode?: 'single' | 'multi';
  vote_eligibility?: 'anonymous' | 'account';
  has_embed_read_token: boolean;
  open_at: number | null;
  lock_at: number | null;
  reveal_at: number | null;
  boosted_voting_enabled: boolean;
  max_boost_weight: number;
  show_unweighted_values: boolean;
  run_of_show_key: string | null;
  run_of_show_order: number | null;
  vanity_slug: string | null;
  next_poll_id: string | null;
  auto_advance_on_close: boolean;
  vote_friction_tier: 'open' | 'soft_throttle' | 'proof_of_work';
  soft_throttle_max_votes_per_min: number;
  pow_difficulty: number;
  results_delay_seconds: number;
  impression_count: number;
  views_last_24h?: number;
  total_votes: number;
  votes_last_5m: number;
  votes_last_24h?: number;
  completion_rate_pct: number | null;
  conversion_rate_last_24h_pct?: number | null;
  per_option_funnel?: Array<{
    option: string;
    votes_total: number;
    votes_last_24h: number;
    conversion_total_pct: number | null;
    conversion_last_24h_pct: number | null;
  }>;
  engagement_velocity_votes_per_min: number | null;
  time_to_first_vote_ms: number | null;
  peak_hour_utc: number | null;
  peak_hour_votes: number;
  peak_dow_utc: number | null;
  peak_dow_votes: number;
  top_campaigns?: Array<{
    source: string;
    medium: string;
    campaign: string;
    impressions: number;
  }>;
  hourly_votes_by_hour_utc?: number[];
  weekday_votes_by_dow_utc?: number[];
};

type MineResponse = { polls: MinePoll[]; total: number; limit: number; offset: number };
const SIMULATED_POLL_ID_PREFIX = 'sim_';

function isSimulatedPollId(id: string): boolean {
  return id.toLowerCase().startsWith(SIMULATED_POLL_ID_PREFIX);
}

type UpdatePollApiResponse = {
  status: string;
  message?: string;
  data?: { embed_read_token?: string; id?: string };
};

type QuarantineStatus = 'pending' | 'approved' | 'rejected';

function quarantineVoteStatusMessageKey(status: QuarantineStatus | null) {
  if (status === 'approved') return 'myPolls.queueApproved' as const;
  if (status === 'rejected') return 'myPolls.queueRejected' as const;
  return 'myPolls.queuePending' as const;
}

type QuarantinedVote = {
  id: string;
  option: string;
  weight: number;
  source_ip_hash: string | null;
  user_id: number | null;
  created_at: string;
  is_quarantined: boolean;
  quarantine_reason: string | null;
  quarantine_status: QuarantineStatus | null;
  quarantine_decided_at: string | null;
  quarantine_decided_by: number | null;
  quarantine_note: string | null;
  trust_risk_score?: number | null;
};

async function fetchMine(): Promise<MineResponse> {
  const jwt = getStoredUserJwt();
  if (!jwt) throw new Error('NO_JWT');
  return (await apiFetch('poll/mine?limit=50&offset=0', {
    bearerToken: jwt,
    adminToken: false,
  })) as MineResponse;
}

const PHASE_OPTIONS: PollPhase[] = ['draft', 'open', 'locked', 'revealed'];

function phaseSelectOptions(serverPhase: string): PollPhase[] {
  const canon = normalizePollPhase(serverPhase);
  const allowed = new Set<PollPhase>([canon, ...allowedPollPhaseTargets(canon)]);
  return PHASE_OPTIONS.filter((ph) => allowed.has(ph));
}

function msToLocalInput(ms: number | null | undefined): string {
  if (!Number.isFinite(ms)) return '';
  const d = new Date(Number(ms));
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

function localInputToMs(v: string): number | null {
  const t = v.trim();
  if (t === '') return null;
  const ms = Date.parse(t);
  return Number.isFinite(ms) ? ms : null;
}

function shiftMs(ms: number | null, deltaMs: number): number | null {
  if (!Number.isFinite(ms)) return null;
  return Number(ms) + deltaMs;
}

function resultsDelayPresetFromSeconds(
  seconds: number,
): 'off' | 'low' | 'medium' | 'high' | 'custom' {
  if (seconds <= 0) return 'off';
  if (seconds === 10) return 'low';
  if (seconds === 20) return 'medium';
  if (seconds === 30) return 'high';
  return 'custom';
}

type WebhookTargetDraft = { url: string; secret: string };

function normalizeWebhookTargets(
  input: Array<{ url: string; secret?: string }> | null | undefined,
): WebhookTargetDraft[] {
  return (input ?? [])
    .map((row) => ({
      url: typeof row?.url === 'string' ? row.url.trim() : '',
      secret: typeof row?.secret === 'string' ? row.secret : '',
    }))
    .filter((row) => row.url !== '');
}

function PollManagePanel({ p, jwt }: { p: MinePoll; jwt: string }) {
  const t = useT();
  const qc = useQueryClient();
  const [phase, setPhase] = useState<PollPhase>(() => normalizePollPhase(p.phase));
  const [votingPaused, setVotingPaused] = useState(p.voting_paused);
  const [pauseMessage, setPauseMessage] = useState(p.pause_message ?? '');
  const [showNotes, setShowNotes] = useState(p.show_notes ?? '');
  const [sharedEditorUserIdsInput, setSharedEditorUserIdsInput] = useState(
    (p.shared_editor_user_ids ?? []).join(', '),
  );
  const [themePreset, setThemePreset] = useState<MinePoll['theme_preset']>(p.theme_preset ?? 'default');
  const [selectionMode, setSelectionMode] = useState<'single' | 'multi'>(
    p.selection_mode === 'multi' ? 'multi' : 'single',
  );
  const [voteEligibility, setVoteEligibility] = useState<'anonymous' | 'account'>(
    p.vote_eligibility === 'account' ? 'account' : 'anonymous',
  );
  const [embedToken, setEmbedToken] = useState<string | null>(null);
  const [openAtInput, setOpenAtInput] = useState<string>(() => msToLocalInput(p.open_at));
  const [lockAtInput, setLockAtInput] = useState<string>(() => msToLocalInput(p.lock_at));
  const [revealAtInput, setRevealAtInput] = useState<string>(() => msToLocalInput(p.reveal_at));
  const [boostedVotingEnabled, setBoostedVotingEnabled] = useState<boolean>(
    !!p.boosted_voting_enabled,
  );
  const [maxBoostWeight, setMaxBoostWeight] = useState<number>(Number(p.max_boost_weight) || 3);
  const [showUnweightedValues, setShowUnweightedValues] = useState<boolean>(
    !!p.show_unweighted_values,
  );
  const [runOfShowKey, setRunOfShowKey] = useState<string>(p.run_of_show_key ?? '');
  const [runOfShowOrder, setRunOfShowOrder] = useState<string>(
    p.run_of_show_order != null ? String(p.run_of_show_order) : '',
  );
  const [vanitySlug, setVanitySlug] = useState<string>(p.vanity_slug ?? '');
  const [nextPollId, setNextPollId] = useState<string>(p.next_poll_id ?? '');
  const [autoAdvanceOnClose, setAutoAdvanceOnClose] = useState<boolean>(!!p.auto_advance_on_close);
  const [voteFrictionTier, setVoteFrictionTier] = useState<MinePoll['vote_friction_tier']>(
    p.vote_friction_tier ?? 'open',
  );
  const [softThrottleMaxVotesPerMin, setSoftThrottleMaxVotesPerMin] = useState<number>(
    Number(p.soft_throttle_max_votes_per_min) || 30,
  );
  const [powDifficulty, setPowDifficulty] = useState<number>(Number(p.pow_difficulty) || 4);
  const [resultsDelaySeconds, setResultsDelaySeconds] = useState<number>(
    Number(p.results_delay_seconds) || 0,
  );
  const [resultsDelayPreset, setResultsDelayPreset] = useState<
    'off' | 'low' | 'medium' | 'high' | 'custom'
  >(resultsDelayPresetFromSeconds(Number(p.results_delay_seconds) || 0));
  const [webhookTargets, setWebhookTargets] = useState<WebhookTargetDraft[]>(() =>
    normalizeWebhookTargets(p.webhook_targets),
  );
  const [delayPreviewNowMs, setDelayPreviewNowMs] = useState(() => Date.now());
  const [recurrenceIntervalMinutes, setRecurrenceIntervalMinutes] = useState(60);
  const [saveHint, setSaveHint] = useState('');
  const [saveErr, setSaveErr] = useState('');
  const [exportBusy, setExportBusy] = useState(false);
  const [queueStatus, setQueueStatus] = useState<'pending' | 'approved' | 'rejected' | 'all'>(
    'pending',
  );
  const [moderationNote, setModerationNote] = useState('');
  const [batchSelector, setBatchSelector] = useState<'source_ip_hash' | 'user_id'>(
    'source_ip_hash',
  );
  const [batchSelectorValue, setBatchSelectorValue] = useState('');
  const [batchReasonCode, setBatchReasonCode] = useState<
    'spam_wave' | 'bot_pattern' | 'compromised_account' | 'manual_review'
  >('manual_review');
  const pollShareUrl = shareUrlForPoll(p.id);
  const resultsShareUrl = shareUrlForPollResults(p.id);
  const chatVoteSnippet = `!vote ${p.id} <option_number>`;
  const chatShareSnippet = `!poll ${pollShareUrl}`;
  const canNativeSharePollLink = useMemo(
    () => isWebShareLikelyAvailable(pollShareUrl),
    [pollShareUrl],
  );

  const sharePollLinkNative = async () => {
    setSaveErr('');
    const url = pollShareUrl;
    const titleTrim = p.title.trim();
    const r = await shareUrlNative({
      url,
      title: titleTrim || undefined,
      text: titleTrim ? `${titleTrim} — ${url}` : url,
    });
    if (r.kind === 'shared') {
      setSaveHint(t('poll.shareDone'));
      return;
    }
    if (r.kind === 'aborted') return;
    try {
      await navigator.clipboard.writeText(url);
      setSaveHint(t('poll.copyOk'));
    } catch {
      setSaveHint(t('poll.copyManual') + ` ${url}`);
    }
  };

  const sharePresets = [
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
  ] as const;
  const embedViewerUrl = useMemo(() => {
    const tok = embedToken?.trim();
    if (!tok) return '';
    return `${apiUrl(`poll/${encodeURIComponent(p.id)}/embed`)}?embed_token=${encodeURIComponent(tok)}`;
  }, [embedToken, p.id]);
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(pollShareUrl)}`;
  const resultsVisibleAt = new Date(delayPreviewNowMs - Math.max(0, resultsDelaySeconds) * 1000);

  useEffect(() => {
    setPhase(normalizePollPhase(p.phase));
    setVotingPaused(p.voting_paused);
    setPauseMessage(p.pause_message ?? '');
    setShowNotes(p.show_notes ?? '');
    setSharedEditorUserIdsInput((p.shared_editor_user_ids ?? []).join(', '));
    setThemePreset(p.theme_preset ?? 'default');
    setSelectionMode(p.selection_mode === 'multi' ? 'multi' : 'single');
    setVoteEligibility(p.vote_eligibility === 'account' ? 'account' : 'anonymous');
    setOpenAtInput(msToLocalInput(p.open_at));
    setLockAtInput(msToLocalInput(p.lock_at));
    setRevealAtInput(msToLocalInput(p.reveal_at));
    setBoostedVotingEnabled(!!p.boosted_voting_enabled);
    setMaxBoostWeight(Number(p.max_boost_weight) || 3);
    setShowUnweightedValues(!!p.show_unweighted_values);
    setRunOfShowKey(p.run_of_show_key ?? '');
    setRunOfShowOrder(p.run_of_show_order != null ? String(p.run_of_show_order) : '');
    setVanitySlug(p.vanity_slug ?? '');
    setNextPollId(p.next_poll_id ?? '');
    setAutoAdvanceOnClose(!!p.auto_advance_on_close);
    setVoteFrictionTier(p.vote_friction_tier ?? 'open');
    setSoftThrottleMaxVotesPerMin(Number(p.soft_throttle_max_votes_per_min) || 30);
    setPowDifficulty(Number(p.pow_difficulty) || 4);
    const nextDelay = Number(p.results_delay_seconds) || 0;
    setResultsDelaySeconds(nextDelay);
    setResultsDelayPreset(resultsDelayPresetFromSeconds(nextDelay));
    setWebhookTargets(normalizeWebhookTargets(p.webhook_targets));
    setEmbedToken(null);
    setRecurrenceIntervalMinutes(60);
    setSaveHint('');
    setSaveErr('');
    setExportBusy(false);
    setQueueStatus('pending');
    setModerationNote('');
    setBatchSelector('source_ip_hash');
    setBatchSelectorValue('');
    setBatchReasonCode('manual_review');
  }, [
    p.id,
    p.phase,
    p.voting_paused,
    p.pause_message,
    p.show_notes,
    p.shared_editor_user_ids,
    p.theme_preset,
    p.selection_mode,
    p.vote_eligibility,
    p.open_at,
    p.lock_at,
    p.reveal_at,
    p.boosted_voting_enabled,
    p.max_boost_weight,
    p.show_unweighted_values,
    p.run_of_show_key,
    p.run_of_show_order,
    p.vanity_slug,
    p.next_poll_id,
    p.auto_advance_on_close,
    p.vote_friction_tier,
    p.soft_throttle_max_votes_per_min,
    p.pow_difficulty,
    p.results_delay_seconds,
    p.webhook_targets,
    p.has_embed_read_token,
    p.archived,
  ]);

  useEffect(() => {
    const preset = resultsDelayPresetFromSeconds(resultsDelaySeconds);
    setResultsDelayPreset((current) =>
      current === 'custom' && preset === 'custom' ? current : preset,
    );
  }, [resultsDelaySeconds]);

  useEffect(() => {
    const tick = window.setInterval(() => setDelayPreviewNowMs(Date.now()), 1000);
    return () => window.clearInterval(tick);
  }, []);

  const mineKey = mineQueryKey(jwt);
  const quarantineKey = quarantineQueryKey(p.id, queueStatus, jwt);

  const invalidateMineQueries = () => {
    void qc.invalidateQueries({ queryKey: mineKey });
    void qc.invalidateQueries({ queryKey: profileBillingQueryKey(jwt) });
  };

  const invalidateModerationQueries = () => {
    void qc.invalidateQueries({ queryKey: quarantineKey });
    void qc.invalidateQueries({ queryKey: mineKey });
  };

  const queueQuery = useQuery({
    queryKey: quarantineKey,
    queryFn: async () => {
      const path = `poll/${encodeURIComponent(p.id)}/quarantine?status=${queueStatus}&limit=50&offset=0`;
      const r = (await apiFetch(path, {
        bearerToken: jwt,
        adminToken: false,
      })) as { data: QuarantinedVote[] };
      return r.data ?? [];
    },
    enabled: !p.archived,
  });

  const downloadExport = async (format: 'csv' | 'json', include: 'summary' | 'votes') => {
    setSaveErr('');
    setSaveHint('');
    setExportBusy(true);
    try {
      const q = new URLSearchParams({ format, include });
      const path = `poll/${encodeURIComponent(p.id)}/export?${q.toString()}`;
      const data = await apiFetch(path, { bearerToken: jwt, adminToken: false });
      const body = format === 'json' ? `${JSON.stringify(data, null, 2)}\n` : String(data ?? '');
      const mime = format === 'json' ? 'application/json;charset=utf-8' : 'text/csv;charset=utf-8';
      const ext = format === 'json' ? 'json' : 'csv';
      const blob = new Blob([body], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${p.id}-export-${include}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
      setSaveHint(t('myPolls.exportDone'));
    } catch (e: unknown) {
      setSaveErr(errMsg(e, t('myPolls.exportErr')));
    } finally {
      setExportBusy(false);
    }
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body = {
        phase,
        voting_paused: votingPaused,
        pause_message: pauseMessage.trim() === '' ? null : pauseMessage.trim(),
        show_notes: showNotes.trim() === '' ? null : showNotes,
        shared_editor_user_ids: sharedEditorUserIdsInput
          .split(',')
          .map((part) => Number(part.trim()))
          .filter((id) => Number.isInteger(id) && id > 0),
        theme_preset: themePreset ?? 'default',
        ...(normalizePollPhase(phase) === 'draft'
          ? { selection_mode: selectionMode, vote_eligibility: voteEligibility }
          : {}),
        open_at: localInputToMs(openAtInput),
        lock_at: localInputToMs(lockAtInput),
        reveal_at: localInputToMs(revealAtInput),
        boosted_voting_enabled: boostedVotingEnabled,
        max_boost_weight: boostedVotingEnabled ? Math.max(1, Math.min(10, maxBoostWeight)) : null,
        show_unweighted_values: boostedVotingEnabled ? showUnweightedValues : false,
        run_of_show_key: runOfShowKey.trim() === '' ? null : runOfShowKey.trim(),
        run_of_show_order:
          runOfShowOrder.trim() === ''
            ? null
            : Math.max(0, Number.parseInt(runOfShowOrder, 10) || 0),
        vanity_slug: vanitySlug.trim() === '' ? null : vanitySlug.trim().toLowerCase(),
        next_poll_id: nextPollId.trim() === '' ? null : nextPollId.trim(),
        auto_advance_on_close: autoAdvanceOnClose,
        vote_friction_tier: voteFrictionTier,
        soft_throttle_max_votes_per_min:
          voteFrictionTier === 'soft_throttle'
            ? Math.max(1, Math.min(240, softThrottleMaxVotesPerMin))
            : null,
        pow_difficulty:
          voteFrictionTier === 'proof_of_work' ? Math.max(1, Math.min(6, powDifficulty)) : null,
        results_delay_seconds: Math.max(0, Math.min(600, resultsDelaySeconds)),
        webhook_targets:
          webhookTargets.length === 0
            ? []
            : webhookTargets
                .map((target) => ({
                  url: target.url.trim(),
                  secret: target.secret.trim() === '' ? undefined : target.secret.trim(),
                }))
                .filter((target) => target.url !== ''),
      } as UpdatePollBody;
      return (await apiFetch(`poll/${encodeURIComponent(p.id)}`, {
        method: 'PUT',
        body,
        bearerToken: jwt,
        adminToken: false,
      })) as UpdatePollApiResponse;
    },
    onSuccess: () => {
      setSaveErr('');
      setSaveHint(t('myPolls.saved'));
      invalidateMineQueries();
    },
    onError: (e: unknown) => {
      setSaveHint('');
      setSaveErr(errMsg(e, t('myPolls.saveErr')));
    },
  });

  const rotateEmbedMutation = useMutation({
    mutationFn: async () => {
      const r = (await apiFetch(`poll/${encodeURIComponent(p.id)}`, {
        method: 'PUT',
        body: { generate_embed_read_token: true } satisfies UpdatePollBody,
        bearerToken: jwt,
        adminToken: false,
      })) as UpdatePollApiResponse;
      const tok = r.data?.embed_read_token;
      if (tok) setEmbedToken(tok);
      return r;
    },
    onSuccess: () => {
      setSaveErr('');
      invalidateMineQueries();
    },
    onError: (e: unknown) => {
      setSaveErr(errMsg(e, t('myPolls.embedRotateErr')));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await apiFetch(`poll/${encodeURIComponent(p.id)}`, {
        method: 'DELETE',
        bearerToken: jwt,
        adminToken: false,
      });
    },
    onSuccess: () => {
      invalidateMineQueries();
    },
    onError: (e: unknown) => {
      setSaveErr(errMsg(e, t('myPolls.deleteErr')));
    },
  });

  const panicMutation = useMutation({
    mutationFn: async () => {
      const body: UpdatePollBody = { panic: true };
      return (await apiFetch(`poll/${encodeURIComponent(p.id)}`, {
        method: 'PUT',
        body,
        bearerToken: jwt,
        adminToken: false,
      })) as UpdatePollApiResponse;
    },
    onSuccess: () => {
      setSaveErr('');
      setSaveHint(t('myPolls.panicDone'));
      invalidateMineQueries();
    },
    onError: (e: unknown) => {
      setSaveHint('');
      setSaveErr(errMsg(e, t('myPolls.panicErr')));
    },
  });
  const cloneMutation = useMutation({
    mutationFn: async () => {
      return (await apiFetch(`poll/${encodeURIComponent(p.id)}/clone`, {
        method: 'POST',
        bearerToken: jwt,
        adminToken: false,
      })) as UpdatePollApiResponse;
    },
    onSuccess: (r) => {
      setSaveErr('');
      const cloned = r.data?.id;
      setSaveHint(cloned ? t('myPolls.cloneDoneWithId', { id: cloned }) : t('myPolls.cloneDone'));
      invalidateMineQueries();
    },
    onError: (e: unknown) => {
      setSaveHint('');
      setSaveErr(errMsg(e, t('myPolls.cloneErr')));
    },
  });
  const cloneNextMutation = useMutation({
    mutationFn: async () => {
      const cloneResp = (await apiFetch(`poll/${encodeURIComponent(p.id)}/clone`, {
        method: 'POST',
        bearerToken: jwt,
        adminToken: false,
      })) as UpdatePollApiResponse;
      const clonedId = cloneResp.data?.id?.trim();
      if (!clonedId) throw new Error('Clone response did not include poll id');
      const intervalMs = Math.max(5, recurrenceIntervalMinutes) * 60_000;
      const sourceOpen = localInputToMs(openAtInput);
      const sourceLock = localInputToMs(lockAtInput);
      const sourceReveal = localInputToMs(revealAtInput);
      await apiFetch(`poll/${encodeURIComponent(clonedId)}`, {
        method: 'PUT',
        body: {
          open_at: shiftMs(sourceOpen, intervalMs),
          lock_at: shiftMs(sourceLock, intervalMs),
          reveal_at: shiftMs(sourceReveal, intervalMs),
          run_of_show_key: runOfShowKey.trim() === '' ? null : runOfShowKey.trim(),
          run_of_show_order:
            runOfShowOrder.trim() === ''
              ? null
              : Math.max(0, Number.parseInt(runOfShowOrder, 10) + 1),
        } satisfies UpdatePollBody,
        bearerToken: jwt,
        adminToken: false,
      });
      return clonedId;
    },
    onSuccess: (clonedId) => {
      setSaveErr('');
      setSaveHint(t('myPolls.cloneNextSlotDone', { id: clonedId }));
      invalidateMineQueries();
    },
    onError: (e: unknown) => {
      setSaveHint('');
      setSaveErr(errMsg(e, t('myPolls.cloneNextSlotErr')));
    },
  });

  const decisionMutation = useMutation({
    mutationFn: async ({
      voteId,
      action,
    }: {
      voteId: string;
      action: 'approve' | 'reject' | 'revert';
    }) => {
      await apiFetch(`poll/${encodeURIComponent(p.id)}/quarantine/${encodeURIComponent(voteId)}`, {
        method: 'PUT',
        body: { action, note: moderationNote.trim() === '' ? undefined : moderationNote.trim() },
        bearerToken: jwt,
        adminToken: false,
      });
    },
    onSuccess: () => {
      setSaveErr('');
      setSaveHint(t('myPolls.moderationDone'));
      invalidateModerationQueries();
    },
    onError: (e: unknown) => {
      setSaveHint('');
      setSaveErr(errMsg(e, t('myPolls.moderationErr')));
    },
  });

  const batchMutation = useMutation({
    mutationFn: async (action: 'remove' | 'restore') => {
      await apiFetch(`poll/${encodeURIComponent(p.id)}/moderation/batch`, {
        method: 'PUT',
        body: {
          action,
          selector: batchSelector,
          selector_value: batchSelectorValue.trim(),
          reason_code: batchReasonCode,
          note: moderationNote.trim() === '' ? undefined : moderationNote.trim(),
        },
        bearerToken: jwt,
        adminToken: false,
      });
    },
    onSuccess: () => {
      setSaveErr('');
      setSaveHint(t('myPolls.batchDone'));
      invalidateModerationQueries();
    },
    onError: (e: unknown) => {
      setSaveHint('');
      setSaveErr(errMsg(e, t('myPolls.batchErr')));
    },
  });

  const phaseOptionLabel = (ph: PollPhase): string => {
    switch (ph) {
      case 'draft':
        return t('myPolls.phaseOptionDraft');
      case 'open':
        return t('myPolls.phaseOptionOpen');
      case 'locked':
        return t('myPolls.phaseOptionLocked');
      case 'revealed':
        return t('myPolls.phaseOptionRevealed');
      default:
        return ph;
    }
  };

  const frictionTierSummaryLabel =
    voteFrictionTier === 'soft_throttle'
      ? t('myPolls.voteFrictionSoftThrottle')
      : voteFrictionTier === 'proof_of_work'
        ? t('myPolls.voteFrictionPow')
        : t('myPolls.voteFrictionOpen');
  const activeConfigSummary = [
    phase !== 'open' ? t('myPolls.activeSummary.phaseNotOpen', { phase: phaseOptionLabel(phase) }) : null,
    votingPaused ? t('myPolls.activeSummary.votingPaused') : null,
    resultsDelaySeconds > 0
      ? t('myPolls.activeSummary.resultsDelay', { seconds: resultsDelaySeconds })
      : null,
    boostedVotingEnabled ? t('myPolls.activeSummary.boostedVoting', { max: maxBoostWeight }) : null,
    voteFrictionTier !== 'open'
      ? t('myPolls.activeSummary.friction', { tier: frictionTierSummaryLabel })
      : null,
    webhookTargets.some((target) => target.url.trim() !== '')
      ? t('myPolls.activeSummary.webhookEnabled')
      : null,
    voteEligibility === 'account' ? t('home.featureBadge.accountVotes') : null,
    p.has_embed_read_token || embedToken ? t('myPolls.activeSummary.embedGate') : null,
    openAtInput || lockAtInput || revealAtInput ? t('myPolls.activeSummary.scheduleConfigured') : null,
    nextPollId.trim() !== '' ? t('myPolls.activeSummary.nextPollLinked') : null,
  ].filter(Boolean) as string[];

  const handleDelete = () => {
    if (deleteMutation.isPending) return;
    if (!window.confirm(t('myPolls.deleteConfirm', { title: p.title }))) return;
    deleteMutation.mutate();
  };

  const handlePanic = () => {
    if (panicMutation.isPending) return;
    if (!window.confirm(t('myPolls.panicConfirm', { title: p.title }))) return;
    panicMutation.mutate();
  };

  return (
    <div className='my-polls-manage-form'>
      {p.archived ? <p className='ui-copy-muted'>{t('myPolls.archivedReadOnly')}</p> : null}
      {activeConfigSummary.length > 0 ? (
        <div className='my-polls-export-block'>
          <h3 className='my-polls-embed-heading'>{t('myPolls.sectionCurrentSetup')}</h3>
          <div className='my-polls-config-badges'>
            {activeConfigSummary.map((item) => (
              <span key={item} className='my-polls-config-badge'>
                {item}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {!p.archived ? (
        <>
          <details className='my-polls-section-card' open>
            <summary className='my-polls-section-summary'>{t('myPolls.sectionPollStatus')}</summary>
          <div className='my-polls-manage-row'>
            <label htmlFor={`my-polls-phase-${p.id}`} className='my-polls-manage-label'>
              {t('myPolls.phaseLabel')}
            </label>
            <Select
              id={`my-polls-phase-${p.id}`}
              className='ui-input--stack my-polls-manage-select'
              value={phase}
              onChange={(e) => setPhase(e.target.value as PollPhase)}
              disabled={saveMutation.isPending}
            >
              {phaseSelectOptions(p.phase).map((ph) => (
                <option key={ph} value={ph}>
                  {phaseOptionLabel(ph)}
                </option>
              ))}
            </Select>
          </div>

          <div className='my-polls-manage-row my-polls-manage-row--checkbox'>
            <Checkbox
              id={`my-polls-pause-${p.id}`}
              checked={votingPaused}
              onChange={(e) => setVotingPaused(e.target.checked)}
              disabled={saveMutation.isPending}
              label={t('myPolls.pauseCheck')}
            />
          </div>

          <FormRow
            className='ui-form-block'
            label={t('myPolls.pauseMessageLabel')}
            htmlFor={`my-polls-pause-msg-${p.id}`}
            hint={t('myPolls.pauseMessageHint')}
          >
            <Textarea
              id={`my-polls-pause-msg-${p.id}`}
              className='ui-input--stack'
              rows={2}
              maxLength={280}
              value={pauseMessage}
              onChange={(e) => setPauseMessage(e.target.value)}
              disabled={saveMutation.isPending}
            />
          </FormRow>
          </details>

          <details className='my-polls-section-card' open>
            <summary className='my-polls-section-summary'>{t('myPolls.sectionTeamCollaboration')}</summary>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.showNotesLabel')}
            htmlFor={`my-polls-notes-${p.id}`}
            hint={t('myPolls.showNotesHint')}
          >
            <Textarea
              id={`my-polls-notes-${p.id}`}
              className='ui-input--stack'
              rows={4}
              maxLength={10_000}
              value={showNotes}
              onChange={(e) => setShowNotes(e.target.value)}
              disabled={saveMutation.isPending}
            />
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.sharedEditorsLabel')}
            htmlFor={`my-polls-shared-editors-${p.id}`}
            hint={t('myPolls.sharedEditorsHint')}
          >
            <Input
              id={`my-polls-shared-editors-${p.id}`}
              className='ui-input--stack'
              value={sharedEditorUserIdsInput}
              onChange={(e) => setSharedEditorUserIdsInput(e.target.value)}
              disabled={saveMutation.isPending || phase !== 'draft'}
              placeholder={t('myPolls.sharedEditorsPlaceholder')}
            />
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.selectionModeLabel')}
            htmlFor={`my-polls-selection-mode-${p.id}`}
            hint={t('myPolls.selectionModeHint')}
          >
            <Select
              id={`my-polls-selection-mode-${p.id}`}
              className='ui-input--stack'
              value={selectionMode}
              onChange={(e) => {
                const next = e.target.value === 'multi' ? 'multi' : 'single';
                setSelectionMode(next);
                if (next === 'multi') setBoostedVotingEnabled(false);
              }}
              disabled={saveMutation.isPending || phase !== 'draft'}
            >
              <option value='single'>{t('myPolls.selectionMode.single')}</option>
              <option value='multi'>{t('myPolls.selectionMode.multi')}</option>
            </Select>
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.voteEligibilityLabel')}
            htmlFor={`my-polls-vote-eligibility-${p.id}`}
            hint={t('myPolls.voteEligibilityHint')}
          >
            <Select
              id={`my-polls-vote-eligibility-${p.id}`}
              className='ui-input--stack'
              value={voteEligibility}
              onChange={(e) =>
                setVoteEligibility(e.target.value === 'account' ? 'account' : 'anonymous')
              }
              disabled={saveMutation.isPending || phase !== 'draft'}
            >
              <option value='anonymous'>{t('myPolls.voteEligibility.anonymous')}</option>
              <option value='account'>{t('myPolls.voteEligibility.account')}</option>
            </Select>
          </FormRow>
          {voteEligibility === 'account' ? (
            <p className='ui-form-hint'>{t('home.voteEligibility.accountConsentNote')}</p>
          ) : null}
          <FormRow
            className='ui-form-block'
            label={t('myPolls.themePresetLabel')}
            htmlFor={`my-polls-theme-preset-${p.id}`}
            hint={t('myPolls.themePresetHint')}
          >
            <Select
              id={`my-polls-theme-preset-${p.id}`}
              className='ui-input--stack'
              value={themePreset ?? 'default'}
              onChange={(e) => setThemePreset(e.target.value as MinePoll['theme_preset'])}
              disabled={saveMutation.isPending}
            >
              <option value='default'>{t('myPolls.themePreset.default')}</option>
              <option value='sunset'>{t('myPolls.themePreset.sunset')}</option>
              <option value='ocean'>{t('myPolls.themePreset.ocean')}</option>
              <option value='neon'>{t('myPolls.themePreset.neon')}</option>
            </Select>
          </FormRow>
          </details>

          <details className='my-polls-section-card' open>
            <summary className='my-polls-section-summary'>{t('myPolls.sectionAudienceSafeguards')}</summary>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.openAtLabel')}
            htmlFor={`my-polls-open-at-${p.id}`}
            hint={t('myPolls.openAtHint')}
          >
            <Input
              id={`my-polls-open-at-${p.id}`}
              className='ui-input--stack'
              type='datetime-local'
              value={openAtInput}
              onChange={(e) => setOpenAtInput(e.target.value)}
              disabled={saveMutation.isPending}
            />
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.lockAtLabel')}
            htmlFor={`my-polls-lock-at-${p.id}`}
            hint={t('myPolls.lockAtHint')}
          >
            <Input
              id={`my-polls-lock-at-${p.id}`}
              className='ui-input--stack'
              type='datetime-local'
              value={lockAtInput}
              onChange={(e) => setLockAtInput(e.target.value)}
              disabled={saveMutation.isPending}
            />
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.revealAtLabel')}
            htmlFor={`my-polls-reveal-at-${p.id}`}
            hint={t('myPolls.revealAtHint')}
          >
            <Input
              id={`my-polls-reveal-at-${p.id}`}
              className='ui-input--stack'
              type='datetime-local'
              value={revealAtInput}
              onChange={(e) => setRevealAtInput(e.target.value)}
              disabled={saveMutation.isPending}
            />
          </FormRow>
          <div className='my-polls-manage-actions'>
            <Button
              type='button'
              variant='secondary'
              disabled={saveMutation.isPending}
              onClick={() => {
                const now = Date.now();
                setOpenAtInput(msToLocalInput(now + 60_000));
                setLockAtInput(msToLocalInput(now + 31 * 60_000));
                setRevealAtInput(msToLocalInput(now + 36 * 60_000));
              }}
            >
              Apply 30m live session
            </Button>
            <Button
              type='button'
              variant='secondary'
              disabled={saveMutation.isPending}
              onClick={() => {
                const now = Date.now();
                setOpenAtInput(msToLocalInput(now + 60_000));
                setLockAtInput(msToLocalInput(now + 121 * 60_000));
                setRevealAtInput(msToLocalInput(now + 126 * 60_000));
              }}
            >
              Apply 2h show block
            </Button>
            <Button
              type='button'
              variant='secondary'
              disabled={saveMutation.isPending}
              onClick={() => {
                setOpenAtInput('');
                setLockAtInput('');
                setRevealAtInput('');
              }}
            >
              Clear schedule
            </Button>
          </div>

          <div className='my-polls-manage-row my-polls-manage-row--checkbox'>
            <Checkbox
              id={`my-polls-boost-enabled-${p.id}`}
              checked={boostedVotingEnabled}
              onChange={(e) => setBoostedVotingEnabled(e.target.checked)}
              disabled={saveMutation.isPending || selectionMode === 'multi'}
              label={t('myPolls.boostedVotingEnabled')}
            />
          </div>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.maxBoostWeightLabel')}
            htmlFor={`my-polls-max-boost-${p.id}`}
            hint={t('myPolls.maxBoostWeightHint')}
          >
            <Input
              id={`my-polls-max-boost-${p.id}`}
              className='ui-input--stack'
              type='number'
              min={1}
              max={10}
              step={1}
              value={maxBoostWeight}
              onChange={(e) => setMaxBoostWeight(Number(e.target.value) || 1)}
              disabled={saveMutation.isPending || !boostedVotingEnabled}
            />
          </FormRow>
          <div className='my-polls-manage-row my-polls-manage-row--checkbox'>
            <Checkbox
              id={`my-polls-show-unweighted-${p.id}`}
              checked={showUnweightedValues}
              onChange={(e) => setShowUnweightedValues(e.target.checked)}
              disabled={saveMutation.isPending || !boostedVotingEnabled}
              label={t('myPolls.showUnweightedValues')}
            />
          </div>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.runOfShowKeyLabel')}
            htmlFor={`my-polls-run-key-${p.id}`}
            hint={t('myPolls.runOfShowKeyHint')}
          >
            <Input
              id={`my-polls-run-key-${p.id}`}
              className='ui-input--stack'
              value={runOfShowKey}
              maxLength={64}
              onChange={(e) => setRunOfShowKey(e.target.value)}
              disabled={saveMutation.isPending}
            />
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.runOfShowOrderLabel')}
            htmlFor={`my-polls-run-order-${p.id}`}
            hint={t('myPolls.runOfShowOrderHint')}
          >
            <Input
              id={`my-polls-run-order-${p.id}`}
              className='ui-input--stack'
              type='number'
              min={0}
              step={1}
              value={runOfShowOrder}
              onChange={(e) => setRunOfShowOrder(e.target.value)}
              disabled={saveMutation.isPending}
            />
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.nextPollIdLabel')}
            htmlFor={`my-polls-next-poll-${p.id}`}
            hint={t('myPolls.nextPollIdHint')}
          >
            <Input
              id={`my-polls-next-poll-${p.id}`}
              className='ui-input--stack'
              value={nextPollId}
              onChange={(e) => setNextPollId(e.target.value)}
              disabled={saveMutation.isPending}
            />
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.vanitySlugLabel')}
            htmlFor={`my-polls-vanity-slug-${p.id}`}
            hint={t('myPolls.vanitySlugHint')}
          >
            <Input
              id={`my-polls-vanity-slug-${p.id}`}
              className='ui-input--stack'
              value={vanitySlug}
              maxLength={64}
              pattern='[a-z0-9][a-z0-9-]*'
              onChange={(e) => setVanitySlug(e.target.value)}
              disabled={saveMutation.isPending}
            />
          </FormRow>
          <div className='my-polls-manage-row my-polls-manage-row--checkbox'>
            <Checkbox
              id={`my-polls-auto-advance-${p.id}`}
              checked={autoAdvanceOnClose}
              onChange={(e) => setAutoAdvanceOnClose(e.target.checked)}
              disabled={saveMutation.isPending || nextPollId.trim() === ''}
              label={t('myPolls.autoAdvanceOnClose')}
            />
          </div>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.voteFrictionTierLabel')}
            htmlFor={`my-polls-friction-${p.id}`}
            hint={t('myPolls.voteFrictionTierHint')}
          >
            <Select
              id={`my-polls-friction-${p.id}`}
              className='ui-input--stack'
              value={voteFrictionTier}
              onChange={(e) =>
                setVoteFrictionTier(e.target.value as MinePoll['vote_friction_tier'])
              }
              disabled={saveMutation.isPending}
            >
              <option value='open'>{t('myPolls.voteFrictionOpen')}</option>
              <option value='soft_throttle'>{t('myPolls.voteFrictionSoftThrottle')}</option>
              <option value='proof_of_work'>{t('myPolls.voteFrictionPow')}</option>
            </Select>
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.softThrottleMaxVotesLabel')}
            htmlFor={`my-polls-soft-throttle-${p.id}`}
            hint={t('myPolls.softThrottleMaxVotesHint')}
          >
            <Input
              id={`my-polls-soft-throttle-${p.id}`}
              className='ui-input--stack'
              type='number'
              min={1}
              max={240}
              step={1}
              value={softThrottleMaxVotesPerMin}
              onChange={(e) => setSoftThrottleMaxVotesPerMin(Number(e.target.value) || 1)}
              disabled={saveMutation.isPending || voteFrictionTier !== 'soft_throttle'}
            />
          </FormRow>
          <FormRow
            className='ui-form-block'
            label={t('myPolls.powDifficultyLabel')}
            htmlFor={`my-polls-pow-difficulty-${p.id}`}
            hint={t('myPolls.powDifficultyHint')}
          >
            <Input
              id={`my-polls-pow-difficulty-${p.id}`}
              className='ui-input--stack'
              type='number'
              min={1}
              max={6}
              step={1}
              value={powDifficulty}
              onChange={(e) => setPowDifficulty(Number(e.target.value) || 1)}
              disabled={saveMutation.isPending || voteFrictionTier !== 'proof_of_work'}
            />
          </FormRow>
          </details>
          <details className='my-polls-section-card' open>
            <summary className='my-polls-section-summary'>{t('myPolls.sectionSharingAutomation')}</summary>
          <FormSection
            className='ui-form-block'
            title={t('myPolls.webhookTargetsLabel')}
            hint={t('myPolls.webhookTargetsHint')}
          >
            {(webhookTargets.length === 0 ? [{ url: '', secret: '' }] : webhookTargets).map(
              (target, idx) => (
                <div key={`${p.id}-webhook-target-${idx}`} className='my-polls-manage-row'>
                  <Input
                    className='ui-input--stack'
                    type='url'
                    placeholder={t('myPolls.webhookUrlPlaceholder')}
                    value={target.url}
                    onChange={(e) =>
                      setWebhookTargets((prev) =>
                        (prev.length === 0 ? [{ url: '', secret: '' }] : prev).map((row, rowIdx) =>
                          rowIdx === idx ? { ...row, url: e.target.value } : row,
                        ),
                      )
                    }
                    disabled={saveMutation.isPending}
                  />
                  <Input
                    className='ui-input--stack'
                    placeholder={t('myPolls.webhookSecretPlaceholder')}
                    value={target.secret}
                    onChange={(e) =>
                      setWebhookTargets((prev) =>
                        (prev.length === 0 ? [{ url: '', secret: '' }] : prev).map((row, rowIdx) =>
                          rowIdx === idx ? { ...row, secret: e.target.value } : row,
                        ),
                      )
                    }
                    disabled={saveMutation.isPending}
                  />
                  <Button
                    type='button'
                    variant='secondary'
                    disabled={saveMutation.isPending}
                    onClick={() =>
                      setWebhookTargets((prev) => {
                        const base = prev.length === 0 ? [{ url: '', secret: '' }] : prev;
                        if (base.length <= 1) return [{ url: '', secret: '' }];
                        return base.filter((_, rowIdx) => rowIdx !== idx);
                      })
                    }
                  >
                    {t('myPolls.webhookTargetRemove')}
                  </Button>
                </div>
              ),
            )}
            <div className='my-polls-manage-actions'>
              <Button
                type='button'
                variant='secondary'
                disabled={saveMutation.isPending || webhookTargets.length >= 10}
                onClick={() =>
                  setWebhookTargets((prev) => [
                    ...(prev.length === 0 ? [] : prev),
                    { url: '', secret: '' },
                  ])
                }
              >
                {t('myPolls.webhookTargetAdd')}
              </Button>
            </div>
          </FormSection>

          <FormSection
            className='ui-form-block'
            title={t('myPolls.resultsDelaySecondsLabel')}
            hint={t('myPolls.resultsDelaySecondsHint')}
          >
            <Select
              id={`my-polls-results-delay-preset-${p.id}`}
              className='ui-input--stack'
              value={resultsDelayPreset}
              onChange={(e) => {
                const preset = e.target.value as 'off' | 'low' | 'medium' | 'high' | 'custom';
                setResultsDelayPreset(preset);
                if (preset === 'off') setResultsDelaySeconds(0);
                else if (preset === 'low') setResultsDelaySeconds(10);
                else if (preset === 'medium') setResultsDelaySeconds(20);
                else if (preset === 'high') setResultsDelaySeconds(30);
              }}
              disabled={saveMutation.isPending}
            >
              <option value='off'>{t('myPolls.resultsDelayPreset.off')}</option>
              <option value='low'>{t('myPolls.resultsDelayPreset.low')}</option>
              <option value='medium'>{t('myPolls.resultsDelayPreset.medium')}</option>
              <option value='high'>{t('myPolls.resultsDelayPreset.high')}</option>
              <option value='custom'>{t('myPolls.resultsDelayPreset.custom')}</option>
            </Select>
            <Input
              id={`my-polls-results-delay-${p.id}`}
              className='ui-input--stack'
              type='number'
              min={0}
              max={600}
              step={5}
              value={resultsDelaySeconds}
              onChange={(e) => setResultsDelaySeconds(Number(e.target.value) || 0)}
              disabled={saveMutation.isPending}
            />
            <p
              className='ui-form-hint my-polls-delay-preview'
              role='status'
              aria-live='polite'
            >
              {t('myPolls.resultsDelayRevealPreview', {
                ts: resultsVisibleAt.toLocaleTimeString(),
                seconds: Math.max(0, resultsDelaySeconds),
              })}
            </p>
          </FormSection>
          </details>

          <div className='my-polls-manage-actions'>
            <Button
              type='button'
              variant='primary'
              disabled={saveMutation.isPending}
              onClick={() => {
                setSaveHint('');
                saveMutation.mutate();
              }}
            >
              {saveMutation.isPending ? t('myPolls.saving') : t('myPolls.saveSettings')}
            </Button>
          </div>

          <div className='my-polls-embed-block'>
            <h3 className='my-polls-embed-heading'>{t('myPolls.embedHeading')}</h3>
            <p className='ui-copy-muted'>
              {p.has_embed_read_token ? t('myPolls.embedOn') : t('myPolls.embedOff')}
            </p>
            <p className='ui-form-hint'>{t('myPolls.embedRotateHint')}</p>
            <Button
              type='button'
              variant='secondary'
              disabled={rotateEmbedMutation.isPending}
              onClick={() => rotateEmbedMutation.mutate()}
            >
              {rotateEmbedMutation.isPending
                ? t('myPolls.rotatingEmbed')
                : t('myPolls.embedRotate')}
            </Button>
            {embedToken ? (
              <div className='my-polls-embed-token'>
                <p className='ui-copy-subtle'>{t('myPolls.embedTokenTitle')}</p>
                <details open>
                  <summary className='ui-disclosure-summary--simple'>
                    {t('home.banner.showEmbedToken')}
                  </summary>
                  <code className='ui-code-block'>{embedToken}</code>
                </details>
                <CopyFeedbackButton
                  onCopy={async () => {
                    try {
                      await navigator.clipboard.writeText(embedToken);
                      setSaveHint(t('home.banner.embedCopyOk'));
                      return true;
                    } catch {
                      setSaveHint(`${t('home.banner.copyManual')} ${embedToken}`);
                      return false;
                    }
                  }}
                >
                  {t('myPolls.embedCopy')}
                </CopyFeedbackButton>
              </div>
            ) : null}
          </div>
        </>
      ) : null}

      <div className='my-polls-export-block'>
        <h3 className='my-polls-embed-heading'>{t('myPolls.exportHeading')}</h3>
        <p className='ui-form-hint'>{t('myPolls.exportHint')}</p>
        <div className='my-polls-manage-actions my-polls-export-actions'>
          <Button
            type='button'
            variant='secondary'
            className='ui-button--with-inline-icon'
            disabled={exportBusy}
            onClick={() => void downloadExport('csv', 'summary')}
          >
            <IconDownload className='ui-button__icon' aria-hidden />
            {exportBusy ? t('myPolls.exporting') : t('myPolls.exportCsvSummary')}
          </Button>
          <Button
            type='button'
            variant='secondary'
            className='ui-button--with-inline-icon'
            disabled={exportBusy}
            onClick={() => void downloadExport('json', 'summary')}
          >
            <IconDownload className='ui-button__icon' aria-hidden />
            {exportBusy ? t('myPolls.exporting') : t('myPolls.exportJsonSummary')}
          </Button>
          <Button
            type='button'
            variant='secondary'
            className='ui-button--with-inline-icon'
            disabled={exportBusy}
            onClick={() => void downloadExport('csv', 'votes')}
          >
            <IconDownload className='ui-button__icon' aria-hidden />
            {exportBusy ? t('myPolls.exporting') : t('myPolls.exportCsvVotes')}
          </Button>
        </div>
      </div>

      <div className='my-polls-export-block'>
        <h3 className='my-polls-embed-heading'>{t('myPolls.distributionHeading')}</h3>
        <FormSection hint={t('myPolls.distributionHint')}>
        <p className='poll-refresh-meta' style={{ marginBlockEnd: 12 }}>
          <a href={streamingObsDocHref()} target='_blank' rel='noopener noreferrer'>
            {t('docs.streamingObsBrowserSource')}
          </a>
        </p>
        <Inline className='my-polls-manage-actions' gap='md'>
          <Button
            type='button'
            variant='secondary'
            disabled={cloneMutation.isPending}
            onClick={() => cloneMutation.mutate()}
          >
            {cloneMutation.isPending ? t('myPolls.cloning') : t('myPolls.cloneBtn')}
          </Button>
          <Input
            className='ui-input--stack'
            type='number'
            min={5}
            step={5}
            value={recurrenceIntervalMinutes}
            onChange={(e) => setRecurrenceIntervalMinutes(Math.max(5, Number(e.target.value) || 60))}
            disabled={cloneNextMutation.isPending}
            style={{ maxWidth: 120 }}
            aria-label={t('myPolls.cloneNextIntervalAria')}
          />
          <Button
            type='button'
            variant='secondary'
            disabled={cloneNextMutation.isPending}
            onClick={() => cloneNextMutation.mutate()}
          >
            {cloneNextMutation.isPending
              ? t('myPolls.cloneNextSlotWorking')
              : t('myPolls.cloneNextSlotBtn')}
          </Button>
        </Inline>
        <FormSection className='ui-form-block' title={t('myPolls.chatSnippetVote')}>
          <code className='ui-code-block'>{chatVoteSnippet}</code>
        </FormSection>
        <FormSection className='ui-form-block' title={t('myPolls.chatSnippetShare')}>
          <code className='ui-code-block'>{chatShareSnippet}</code>
          <CopyFeedbackButton
            onCopy={async () => {
              try {
                await navigator.clipboard.writeText(chatShareSnippet);
                setSaveHint(t('myPolls.copyDone'));
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
          <code className='ui-code-block'>{pollShareUrl}</code>
          <Inline className='my-polls-manage-actions' gap='sm'>
            <CopyFeedbackButton
              onCopy={async () => {
                try {
                  await navigator.clipboard.writeText(pollShareUrl);
                  setSaveHint(t('myPolls.copyDone'));
                  return true;
                } catch {
                  return false;
                }
              }}
            >
              {t('myPolls.sharePresetCopyLink')}
            </CopyFeedbackButton>
            {canNativeSharePollLink ? (
              <Button
                type='button'
                variant='secondary'
                className='ui-button--with-inline-icon'
                onClick={() => void sharePollLinkNative()}
              >
                <IconShare className='ui-button__icon' aria-hidden />
                {t('poll.shareLink')}
              </Button>
            ) : null}
          </Inline>
        </FormSection>
        {embedViewerUrl ? (
          <FormSection
            className='ui-form-block'
            title={t('myPolls.embedFrameUrl')}
            hint={t('myPolls.embedFrameUrlHint')}
          >
            <code className='ui-code-block'>{embedViewerUrl}</code>
            <Inline className='my-polls-manage-actions' gap='sm'>
              <CopyFeedbackButton
                onCopy={async () => {
                  try {
                    await navigator.clipboard.writeText(embedViewerUrl);
                    setSaveHint(t('myPolls.copyDone'));
                    return true;
                  } catch {
                    return false;
                  }
                }}
              >
                {t('myPolls.sharePresetCopyLink')}
              </CopyFeedbackButton>
            </Inline>
          </FormSection>
        ) : null}
        <FormSection
          className='ui-form-block'
          title={t('myPolls.sharePresets')}
          hint={t('myPolls.sharePresetsHint')}
        >
          {sharePresets.map((preset) => (
            <div key={preset.id}>
              <p className='ui-form-hint' style={{ marginBlockEnd: 6 }}>
                <strong>{preset.label}:</strong>
              </p>
              <code className='ui-code-block'>{preset.url}</code>
              <code className='ui-code-block'>
                {preset.cta} {preset.url}
              </code>
              <Inline className='my-polls-manage-actions' gap='sm'>
                <CopyFeedbackButton
                  onCopy={async () => {
                    try {
                      await navigator.clipboard.writeText(preset.url);
                      setSaveHint(t('myPolls.copyDone'));
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
                      setSaveHint(t('myPolls.copyDone'));
                      return true;
                    } catch {
                      return false;
                    }
                  }}
                >
                  {t('myPolls.sharePresetCopyCta')}
                </CopyFeedbackButton>
              </Inline>
            </div>
          ))}
        </FormSection>
        <FormSection className='ui-form-block' title={t('myPolls.qrLabel')} hint={t('myPolls.qrHint')}>
          <img src={qrUrl} width={180} height={180} alt={t('myPolls.qrAlt', { title: p.title })} />
        </FormSection>
        </FormSection>
      </div>

      {!p.archived ? (
        <div className='my-polls-export-block'>
          <h3 className='my-polls-embed-heading'>{t('myPolls.moderationQueueHeading')}</h3>
          <p className='ui-form-hint'>{t('myPolls.moderationQueueHint')}</p>

          <FormRow
            className='ui-form-block'
            label={t('myPolls.moderationQueueStatus')}
            htmlFor={`my-polls-queue-status-${p.id}`}
          >
            <Select
              id={`my-polls-queue-status-${p.id}`}
              className='ui-input--stack'
              value={queueStatus}
              onChange={(e) =>
                setQueueStatus(e.target.value as 'pending' | 'approved' | 'rejected' | 'all')
              }
              disabled={
                queueQuery.isFetching || decisionMutation.isPending || batchMutation.isPending
              }
            >
              <option value='pending'>{t('myPolls.queuePending')}</option>
              <option value='approved'>{t('myPolls.queueApproved')}</option>
              <option value='rejected'>{t('myPolls.queueRejected')}</option>
              <option value='all'>{t('myPolls.queueAll')}</option>
            </Select>
          </FormRow>

          <FormRow
            className='ui-form-block'
            label={t('myPolls.moderationNote')}
            htmlFor={`my-polls-moderation-note-${p.id}`}
          >
            <Input
              id={`my-polls-moderation-note-${p.id}`}
              className='ui-input--stack'
              value={moderationNote}
              maxLength={500}
              onChange={(e) => setModerationNote(e.target.value)}
              disabled={decisionMutation.isPending || batchMutation.isPending}
            />
          </FormRow>

          {queueQuery.isLoading ? (
            <p className='ui-copy-muted'>{t('myPolls.moderationQueueLoading')}</p>
          ) : null}
          {!queueQuery.isLoading && (queueQuery.data?.length ?? 0) === 0 ? (
            <p className='ui-copy-muted'>{t('myPolls.moderationQueueEmpty')}</p>
          ) : null}
          {!queueQuery.isLoading && (queueQuery.data?.length ?? 0) > 0 ? (
            <div className='my-polls-embed-token'>
              {(queueQuery.data ?? []).map((row) => (
                <div key={row.id} className='ui-copy-muted' style={{ marginBottom: '0.75rem' }}>
                  <div>
                    <strong>{row.option}</strong>
                    {' · '}
                    {t('myPolls.quarantineVoteMeta', {
                      voteId: row.id,
                      status: t(quarantineVoteStatusMessageKey(row.quarantine_status)),
                      weight: row.weight,
                    })}
                  </div>
                  <div className='my-polls-quarantine-meta'>
                    {formatQuarantineReasonLabel(t, row.quarantine_reason)}
                    {row.trust_risk_score != null && Number.isFinite(row.trust_risk_score) ? (
                      <>
                        {' · '}
                        {t('myPolls.trustRiskScore', { score: String(row.trust_risk_score) })}
                      </>
                    ) : null}
                  </div>
                  <div>
                    {t('myPolls.quarantineSourceLine', {
                      ip: row.source_ip_hash ?? '—',
                      user: row.user_id ?? '—',
                    })}
                  </div>
                  <div className='my-polls-manage-actions'>
                    <Button
                      type='button'
                      variant='secondary'
                      disabled={decisionMutation.isPending}
                      onClick={() => decisionMutation.mutate({ voteId: row.id, action: 'approve' })}
                    >
                      {t('myPolls.moderationApprove')}
                    </Button>
                    <Button
                      type='button'
                      variant='secondary'
                      disabled={decisionMutation.isPending}
                      onClick={() => decisionMutation.mutate({ voteId: row.id, action: 'reject' })}
                    >
                      {t('myPolls.moderationReject')}
                    </Button>
                    <Button
                      type='button'
                      variant='secondary'
                      disabled={decisionMutation.isPending}
                      onClick={() => decisionMutation.mutate({ voteId: row.id, action: 'revert' })}
                    >
                      {t('myPolls.moderationRevert')}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          <details>
            <summary className='ui-disclosure-summary--simple'>{t('myPolls.batchHeading')}</summary>
            <FormSection hint={t('myPolls.batchHint')}>
            <FormRow
              className='ui-form-block'
              label={t('myPolls.batchSelector')}
              htmlFor={`my-polls-batch-selector-${p.id}`}
            >
              <Select
                id={`my-polls-batch-selector-${p.id}`}
                className='ui-input--stack'
                value={batchSelector}
                onChange={(e) => setBatchSelector(e.target.value as 'source_ip_hash' | 'user_id')}
                disabled={batchMutation.isPending}
              >
                <option value='source_ip_hash'>{t('myPolls.batchSelectorIp')}</option>
                <option value='user_id'>{t('myPolls.batchSelectorUser')}</option>
              </Select>
            </FormRow>
            <FormRow
              className='ui-form-block'
              label={t('myPolls.batchSelectorValue')}
              htmlFor={`my-polls-batch-value-${p.id}`}
            >
              <Input
                id={`my-polls-batch-value-${p.id}`}
                className='ui-input--stack'
                value={batchSelectorValue}
                onChange={(e) => setBatchSelectorValue(e.target.value)}
                disabled={batchMutation.isPending}
              />
            </FormRow>
            <FormRow
              className='ui-form-block'
              label={t('myPolls.batchReasonCode')}
              htmlFor={`my-polls-batch-reason-${p.id}`}
            >
              <Select
                id={`my-polls-batch-reason-${p.id}`}
                className='ui-input--stack'
                value={batchReasonCode}
                onChange={(e) =>
                  setBatchReasonCode(
                    e.target.value as
                      | 'spam_wave'
                      | 'bot_pattern'
                      | 'compromised_account'
                      | 'manual_review',
                  )
                }
                disabled={batchMutation.isPending}
              >
                <option value='spam_wave'>spam_wave</option>
                <option value='bot_pattern'>bot_pattern</option>
                <option value='compromised_account'>compromised_account</option>
                <option value='manual_review'>manual_review</option>
              </Select>
            </FormRow>
            <div className='my-polls-manage-actions'>
              <Button
                type='button'
                variant='secondary'
                disabled={batchMutation.isPending || batchSelectorValue.trim() === ''}
                onClick={() => batchMutation.mutate('remove')}
              >
                {t('myPolls.batchRemove')}
              </Button>
              <Button
                type='button'
                variant='secondary'
                disabled={batchMutation.isPending || batchSelectorValue.trim() === ''}
                onClick={() => batchMutation.mutate('restore')}
              >
                {t('myPolls.batchRestore')}
              </Button>
            </div>
            </FormSection>
          </details>
        </div>
      ) : null}

      <div className='my-polls-danger-zone'>
        {!p.archived ? <p className='ui-form-hint'>{t('myPolls.panicHint')}</p> : null}
        <div className='my-polls-manage-actions my-polls-danger-actions'>
          {!p.archived ? (
            <Button
              type='button'
              variant='secondary'
              className={cx('ui-button--with-inline-icon', 'my-polls-panic-btn')}
              disabled={panicMutation.isPending || deleteMutation.isPending}
              onClick={handlePanic}
            >
              <IconActivity className='ui-button__icon' aria-hidden />
              {panicMutation.isPending ? t('myPolls.panicWorking') : t('myPolls.panicBtn')}
            </Button>
          ) : null}
          <Button
            type='button'
            variant='secondary'
            className={cx('ui-button--with-inline-icon', 'my-polls-delete-btn')}
            disabled={deleteMutation.isPending || panicMutation.isPending}
            onClick={handleDelete}
          >
            <IconTrash2 className='ui-button__icon' aria-hidden />
            {deleteMutation.isPending ? t('myPolls.deleting') : t('myPolls.deletePoll')}
          </Button>
        </div>
      </div>

      {saveHint ? (
        <p className='ui-copy-muted' role='status' aria-live='polite'>
          {saveHint}
        </p>
      ) : null}
      {saveErr ? (
        <p className='error-message' role='alert'>
          {saveErr}
        </p>
      ) : null}
    </div>
  );
}

export default function MyPolls() {
  const t = useT();
  const localeTag = useLocaleTag();
  const weekdayAxis = useMemo(
    () => Array.from({ length: 7 }, (_, i) => formatUtcWeekdayShort(localeTag, i, String(i))).join(' '),
    [localeTag],
  );
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  useDocumentTitle(t('myPolls.docTitle'));

  const [jwt, setJwt] = useState<string | null>(() => getStoredUserJwt());
  useEffect(() => {
    const sync = () => setJwt(getStoredUserJwt());
    sync();
    return subscribeUserJwtChanged(sync);
  }, []);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: mineQueryKey(jwt ?? ''),
    queryFn: fetchMine,
    enabled: Boolean(jwt),
  });

  const billingUsageQuery = useQuery({
    queryKey: profileBillingQueryKey(jwt ?? ''),
    queryFn: () =>
      apiFetch('profile/billing', {
        adminToken: false,
        bearerToken: jwt!.trim(),
      }) as Promise<ProfileBillingApiPayload>,
    enabled: Boolean(jwt),
  });

  if (!jwt) {
    return (
      <Container size='lg' className='ui-page-shell'>
        <h1 className='ui-page-heading'>{t('myPolls.needLogin')}</h1>
        <p>
          <Link to='/login'>{t('nav.signIn')}</Link>
        </p>
      </Container>
    );
  }

  const handleLogout = () => {
    const j = jwt;
    clearStoredUserJwt();
    void queryClient.removeQueries({ queryKey: mineQueryPrefix() });
    if (j) void queryClient.removeQueries({ queryKey: profileBillingQueryKey(j) });
    void navigate({ to: '/' });
  };

  const billingUsageWarning = billingUsageWarningSeverity(billingUsageQuery.data);
  const billingPastDue = billingPastDueBannerPayload(billingUsageQuery.data);

  return (
    <Container size='lg' className='ui-page-shell'>
      <h1 className='ui-page-heading my-polls-header'>{t('myPolls.title')}</h1>
      <p className='my-polls-actions'>
        <Button type='button' variant='secondary' size='sm' className='ui-button--lane-secondary' onClick={handleLogout}>
          {t('nav.signOut')}
        </Button>
        {' · '}
        <Link to='/'>{t('myPolls.backHome')}</Link>
      </p>
      {billingPastDue ? (
        <p className='error-message ui-usage-banner' role='alert'>
          {t('billing.pastDueBanner')}{' '}
          <a href={billingPastDue.portalUrl} target='_blank' rel='noreferrer' className='ui-link'>
            {t('billing.openCustomerPortal')}
          </a>
        </p>
      ) : null}
      {billingUsageWarning ? (
        <p
          className={billingUsageWarning === '95' ? 'error-message' : 'ui-copy-muted'}
          role='status'
        >
          {billingUsageWarning === '95'
            ? t('billing.usageNearLimit95')
            : t('billing.usageNearLimit80')}
        </p>
      ) : null}
      {billingUsageQuery.data?.usage?.limitsEnforced &&
      typeof billingUsageQuery.data.usage.activePolls === 'number' &&
      typeof billingUsageQuery.data.usage.maxActivePolls === 'number' ? (
        <p
          className={billingUsageAtCap(billingUsageQuery.data) ? 'error-message' : 'ui-copy-muted'}
          role='status'
        >
          {t('myPolls.pollUsageBanner', {
            current: billingUsageQuery.data.usage.activePolls,
            max: billingUsageQuery.data.usage.maxActivePolls,
            plan: billingUsageQuery.data.billing?.plan ?? 'free',
          })}
        </p>
      ) : null}
      {isLoading ? <p role='status'>{t('myPolls.loading')}</p> : null}
      {isError ? (
        <p className='error-message' role='alert'>
          {error instanceof Error && error.message === 'NO_JWT'
            ? t('myPolls.needLogin')
            : errMsg(error, t('myPolls.errLoad'))}
        </p>
      ) : null}
      {data?.polls?.length === 0 ? <p>{t('myPolls.empty')}</p> : null}
      {data && data.polls.length > 0 ? (
        <ul className='my-polls-list'>
          {data.polls.map((p) => (
            <li key={p.id} className='my-polls-item'>
              <div className='my-polls-item-head'>
                <Link to='/$id' params={{ id: p.id }}>
                  {p.title}
                </Link>
                {isSimulatedPollId(p.id) ? (
                  <span className='ui-copy-muted'> — {t('myPolls.simulationBadge')}</span>
                ) : null}
                {p.archived ? (
                  <span className='ui-copy-muted'> — {t('myPolls.archived')}</span>
                ) : null}
                {p.voting_paused ? (
                  <span className='ui-copy-muted'> — {t('myPolls.paused')}</span>
                ) : null}
                {!p.archived && p.phase !== 'open' ? (
                  <span className='ui-copy-muted'>
                    {' '}
                    — {t('myPolls.phase', { phase: p.phase })}
                  </span>
                ) : null}
                {p.hasWebhook ? (
                  <span className='ui-copy-muted'> — {t('myPolls.webhookOn')}</span>
                ) : null}
                {p.has_embed_read_token ? (
                  <span className='ui-copy-muted'> — {t('myPolls.embedBadge')}</span>
                ) : null}
              </div>
              <div className='ui-copy-muted my-polls-item-meta'>
                {t('myPolls.views', { count: p.impression_count })} ·{' '}
                {t('myPolls.viewsLast24h', { count: Number(p.views_last_24h ?? 0) })} ·{' '}
                {t('myPolls.votes', { count: p.total_votes })} ·{' '}
                {t('myPolls.votesLast24h', { count: Number(p.votes_last_24h ?? 0) })} ·{' '}
                {t('myPolls.votesLast5m', { count: p.votes_last_5m })} ·{' '}
                {new Date(p.createdAt).toLocaleString(localeTag)}
              </div>
              <div className='ui-copy-muted my-polls-item-meta'>
                {t('myPolls.completionRate', {
                  pct:
                    p.completion_rate_pct != null && Number.isFinite(p.completion_rate_pct)
                      ? p.completion_rate_pct.toFixed(1)
                      : '—',
                })}{' '}
                ·{' '}
                {t('myPolls.conversionLast24h', {
                  pct:
                    p.conversion_rate_last_24h_pct != null &&
                    Number.isFinite(p.conversion_rate_last_24h_pct)
                      ? p.conversion_rate_last_24h_pct.toFixed(1)
                      : '—',
                })}{' '}
                ·{' '}
                {t('myPolls.velocity', {
                  value:
                    p.engagement_velocity_votes_per_min != null &&
                    Number.isFinite(p.engagement_velocity_votes_per_min)
                      ? p.engagement_velocity_votes_per_min.toFixed(2)
                      : '—',
                })}{' '}
                ·{' '}
                {t('myPolls.timeToFirstVote', {
                  value:
                    p.time_to_first_vote_ms != null && Number.isFinite(p.time_to_first_vote_ms)
                      ? `${Math.round(p.time_to_first_vote_ms / 1000)}s`
                      : '—',
                })}{' '}
                ·{' '}
                {t('myPolls.peakHour', {
                  hour: formatUtcHourAtTopOfHour(localeTag, p.peak_hour_utc, '—'),
                  votes: p.peak_hour_votes,
                })}{' '}
                ·{' '}
                {t('myPolls.peakDay', {
                  day:
                    p.peak_dow_utc != null && Number.isFinite(p.peak_dow_utc)
                      ? formatUtcWeekdayShort(localeTag, p.peak_dow_utc, '—')
                      : '—',
                  votes: p.peak_dow_votes,
                })}
                {p.top_campaigns && p.top_campaigns.length > 0
                  ? ` · ${t('myPolls.topCampaign', {
                      source: p.top_campaigns[0].source,
                      medium: p.top_campaigns[0].medium,
                      impressions: p.top_campaigns[0].impressions,
                    })}`
                  : ''}
              </div>
              {p.total_votes > 0 ? (
                <div
                  className='my-polls-vote-histograms'
                  aria-label={t('myPolls.listVoteTimingAria')}
                >
                  <p className='ui-copy-muted my-polls-item-meta my-polls-sparkline-row'>
                    <span className='my-polls-sparkline-label'>{t('poll.metrics.hourly')}</span>{' '}
                    <span aria-hidden='true'>
                      <SparklineBars
                        values={p.hourly_votes_by_hour_utc ?? Array.from({ length: 24 }, () => 0)}
                        bucketLabel={(i) => formatUtcHourAtTopOfHour(localeTag, i, String(i))}
                        maxHeightPx={18}
                        barWidthPx={3}
                      />
                    </span>
                    <span className='my-polls-sparkline-axis'>
                      {t('poll.metrics.hourlyAxis', {
                        start: formatUtcHourAtTopOfHour(localeTag, 0, '0'),
                        end: formatUtcHourAtTopOfHour(localeTag, 23, '23'),
                      })}
                    </span>
                  </p>
                  <p className='ui-copy-muted my-polls-item-meta my-polls-sparkline-row'>
                    <span className='my-polls-sparkline-label'>{t('poll.metrics.weekday')}</span>{' '}
                    <span aria-hidden='true'>
                      <SparklineBars
                        values={p.weekday_votes_by_dow_utc ?? Array.from({ length: 7 }, () => 0)}
                        bucketLabel={(i) => formatUtcWeekdayShort(localeTag, i, String(i))}
                        maxHeightPx={18}
                        barWidthPx={5}
                      />
                    </span>
                    <span className='my-polls-sparkline-axis'>
                      {t('poll.metrics.weekdayAxis', { days: weekdayAxis })}
                    </span>
                  </p>
                </div>
              ) : null}
              {p.per_option_funnel && p.per_option_funnel.length > 0 ? (
                <div className='ui-copy-muted my-polls-item-meta'>
                  {t('myPolls.optionFunnelLabel')}:&nbsp;
                  {p.per_option_funnel
                    .slice(0, 3)
                    .map((row) => {
                      const pct =
                        row.conversion_last_24h_pct != null &&
                        Number.isFinite(row.conversion_last_24h_pct)
                          ? row.conversion_last_24h_pct.toFixed(1)
                          : row.conversion_total_pct != null &&
                              Number.isFinite(row.conversion_total_pct)
                            ? row.conversion_total_pct.toFixed(1)
                            : '—';
                      return `${row.option} ${pct}%`;
                    })
                    .join(' · ')}
                </div>
              ) : null}
              <details className='my-polls-manage'>
                <summary className='my-polls-manage-summary'>{t('myPolls.manageToggle')}</summary>
                <PollManagePanel p={p} jwt={jwt} />
              </details>
            </li>
          ))}
        </ul>
      ) : null}
    </Container>
  );
}
