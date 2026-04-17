import { takeCampaignAttributionIncrementForPoll } from '../../lib/billingCampaignAttributionQuota';
import { pollEmbedViewAllowed, readEmbedReadTokenFromRequest } from '../../lib/embedReadToken';
import { normalizeMediaAttachment, normalizeMediaModeration } from '../../lib/mediaPolicy';
import { pollPhaseScheduleFromRow, resolveEffectivePollPhase } from '../../lib/pollPhaseSchedule';
import { getRequestContext } from '../../lib/requestContext';
import {
  trustChatBurstOwnerSummary,
  trustIpBurstOwnerSummary,
  trustStackSafeguardTags,
} from '../../lib/trustStackSignals';
import Poll from '../../model/Poll';
import type { AppRequest } from '../../types/http';
import { getPollVoteAnalytics } from './getPoll.repository';

export type GetPollServiceResult =
  | { kind: 'not_found' }
  | { kind: 'forbidden_embed_token' }
  | { kind: 'ok'; data: Record<string, unknown> };

function toFiniteMs(value: unknown): number | null {
  if (value instanceof Date) return Number.isFinite(value.getTime()) ? value.getTime() : null;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  return null;
}

function readCampaignParams(
  req: AppRequest,
): { source: string; medium: string; campaign: string } | null {
  const query = (req.query ?? {}) as Record<string, unknown>;
  const source = typeof query.utm_source === 'string' ? query.utm_source.trim().slice(0, 64) : '';
  const medium = typeof query.utm_medium === 'string' ? query.utm_medium.trim().slice(0, 64) : '';
  const campaign =
    typeof query.utm_campaign === 'string' ? query.utm_campaign.trim().slice(0, 96) : '';
  if (!source && !medium && !campaign) return null;
  return {
    source: source || '(none)',
    medium: medium || '(none)',
    campaign: campaign || '(none)',
  };
}

function hourBucketKeyUtc(ms: number): string {
  const d = new Date(ms);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  return `${yyyy}${mm}${dd}${hh}`;
}

function minuteUtcIsoFromRow(minuteUtc: Date | string): string {
  return minuteUtc instanceof Date
    ? minuteUtc.toISOString()
    : new Date(String(minuteUtc)).toISOString();
}

function buildOptionVoteVelocityByMinuteUtc(
  configuredOptions: string[],
  optionVoteMinuteBins: Array<{
    option_label: string;
    minute_utc: Date | string;
    vote_count: string | number;
  }>,
): Array<{
  option: string;
  vote_velocity_by_minute_utc: Array<{ minute_utc: string; vote_count: number }>;
}> {
  const minuteIsoSet = new Set<string>();
  for (const row of optionVoteMinuteBins) {
    minuteIsoSet.add(minuteUtcIsoFromRow(row.minute_utc));
  }
  const minutesAsc = [...minuteIsoSet].sort((a, b) => Date.parse(a) - Date.parse(b));
  const byOption = new Map<string, Map<string, number>>();
  for (const row of optionVoteMinuteBins) {
    const opt = String(row.option_label ?? '');
    const iso = minuteUtcIsoFromRow(row.minute_utc);
    const inner = byOption.get(opt) ?? new Map();
    inner.set(iso, Number(row.vote_count) || 0);
    byOption.set(opt, inner);
  }
  return configuredOptions.map((label) => ({
    option: label,
    vote_velocity_by_minute_utc: minutesAsc.map((iso) => ({
      minute_utc: iso,
      vote_count: byOption.get(label)?.get(iso) ?? 0,
    })),
  }));
}

function pruneHourlyViewBuckets(
  raw: Record<string, unknown>,
  nowMs: number,
  keepHours = 24 * 14,
): Record<string, number> {
  const minBucket = Number(hourBucketKeyUtc(nowMs - keepHours * 3600 * 1000));
  const next: Record<string, number> = {};
  for (const [k, v] of Object.entries(raw)) {
    if (!/^\d{10}$/.test(k)) continue;
    const keyNum = Number(k);
    if (!Number.isFinite(keyNum) || keyNum < minBucket) continue;
    const count = Math.max(0, Number(v) || 0);
    if (count > 0) next[k] = count;
  }
  return next;
}

export async function getPollView(req: AppRequest, pollId: string): Promise<GetPollServiceResult> {
  const ctx = getRequestContext(req);
  const poll = await Poll.findByPk(pollId);
  if (!poll) return { kind: 'not_found' };

  const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
  const embedToken = readEmbedReadTokenFromRequest(req);
  const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
  if (!pollEmbedViewAllowed(req, pollId, embedHash, embedToken, creatorUserId)) {
    return { kind: 'forbidden_embed_token' };
  }

  const campaign = readCampaignParams(req);
  const now = Date.now();
  const bucket = hourBucketKeyUtc(now);
  const currentByHourRaw =
    (poll.get('viewEventsByHour') as Record<string, unknown> | null | undefined) ?? {};
  const nextByHour = pruneHourlyViewBuckets(currentByHourRaw, now);
  nextByHour[bucket] = (nextByHour[bucket] ?? 0) + 1;
  if (!campaign) {
    await Poll.update(
      {
        impressionCount: Number(poll.get('impressionCount') ?? 0) + 1,
        viewEventsByHour: nextByHour,
      },
      { where: { id: pollId } },
    );
  } else {
    const current =
      (poll.get('impressionAttribution') as Record<string, number> | null | undefined) ?? {};
    const key = `${campaign.source}|${campaign.medium}|${campaign.campaign}`;
    const allowAttribution = await takeCampaignAttributionIncrementForPoll({
      pollId,
      creatorUserId,
    });
    if (allowAttribution) {
      const next = { ...current, [key]: Math.max(0, Number(current[key] ?? 0)) + 1 };
      await Poll.update(
        {
          impressionCount: Number(poll.get('impressionCount') ?? 0) + 1,
          impressionAttribution: next,
          viewEventsByHour: nextByHour,
        },
        { where: { id: pollId } },
      );
    } else {
      await Poll.update(
        {
          impressionCount: Number(poll.get('impressionCount') ?? 0) + 1,
          viewEventsByHour: nextByHour,
        },
        { where: { id: pollId } },
      );
    }
  }

  const title = poll.get('title');
  const options = (poll.get('options') as string[]) || [];
  const createdAt = poll.get('createdAt');
  const expiration = poll.get('expiration');
  const archived = !!poll.get('archived');
  const schedule = pollPhaseScheduleFromRow(poll);
  const phase = resolveEffectivePollPhase(poll.get('phase'), schedule, now);
  const votingPaused = !!poll.get('votingPaused');
  const pauseMessage = (poll.get('pauseMessage') as string | null) ?? null;
  const impressionCount = Number(poll.get('impressionCount')) + 1;
  const showNotesRaw = (poll.get('showNotes') as string | null) ?? null;
  const uid = ctx.userId;
  const role = ctx.role;
  const roleCanViewPrivateNotes = role === 'mod' || role === 'admin' || role === 'superadmin';
  const showNotes =
    showNotesRaw != null &&
    showNotesRaw !== '' &&
    ((uid !== undefined && creatorUserId != null && uid === creatorUserId) ||
      roleCanViewPrivateNotes)
      ? showNotesRaw
      : undefined;

  const embedGate = typeof embedHash === 'string' && embedHash.trim() !== '';
  const youOwnThisPoll =
    uid !== undefined && creatorUserId != null && Number(uid) === Number(creatorUserId);

  const optionEntries = options.map((label, index) => ({ index, label }));

  const boostedVotingEnabled = !!poll.get('boostedVotingEnabled');
  const showUnweightedValues = !!poll.get('showUnweightedValues');
  const maxBoostWeight = Number(poll.get('maxBoostWeight') ?? 3);
  const runOfShowKey = (poll.get('runOfShowKey') as string | null | undefined) ?? null;
  const runOfShowOrder = (poll.get('runOfShowOrder') as number | null | undefined) ?? null;
  const vanitySlug = (poll.get('vanitySlug') as string | null | undefined) ?? null;
  const nextPollId = (poll.get('nextPollId') as string | null | undefined) ?? null;
  const autoAdvanceOnClose = !!poll.get('autoAdvanceOnClose');
  const voteFrictionTier = String(poll.get('voteFrictionTier') ?? 'open');
  const softThrottleMaxVotesPerMin = Number(poll.get('softThrottleMaxVotesPerMin') ?? 30);
  const powDifficulty = Number(poll.get('powDifficulty') ?? 4);
  const allowWriteIn = !!poll.get('allowWriteIn');
  const writeInMaxLength = Number(poll.get('writeInMaxLength') ?? 80);
  const writeInBlocklist = (
    (poll.get('writeInBlocklist') as string[] | null | undefined) ?? []
  ).filter((s) => typeof s === 'string' && s.trim() !== '');
  const writeInProfanityFilter = poll.get('writeInProfanityFilter') !== false;
  const resultsDelaySeconds = Math.max(0, Number(poll.get('resultsDelaySeconds') ?? 0) || 0);
  const mediaAttachment = normalizeMediaAttachment(poll.get('mediaAttachment'));
  const mediaModeration = normalizeMediaModeration(poll.get('mediaModeration'));
  const mediaBlurByDefault = poll.get('mediaBlurByDefault') !== false;
  const themePreset = String(poll.get('themePreset') ?? 'default');
  const selectionMode =
    String(poll.get('selectionMode') ?? 'single') === 'multi' ? 'multi' : 'single';
  const voteEligibilityRaw = String(poll.get('voteEligibility') ?? 'anonymous');
  const voteEligibility =
    voteEligibilityRaw === 'account' || voteEligibilityRaw === 'platform_linked'
      ? voteEligibilityRaw
      : 'anonymous';
  const retentionTtlDaysRaw = poll.get('retentionTtlDays');
  const retentionTtlDays =
    retentionTtlDaysRaw == null ? null : Math.max(1, Number(retentionTtlDaysRaw) || 0) || null;
  const retentionLegalHold = poll.get('retentionLegalHold') === true;
  const platformIdentityProvider =
    (poll.get('platformIdentityProvider') as string | null | undefined) ?? null;
  const platformIdentityConsentVersion =
    (poll.get('platformIdentityConsentVersion') as string | null | undefined) ?? null;
  const platformIdentityConsentCapturedAt =
    (poll.get('platformIdentityConsentCapturedAt') as number | null | undefined) ?? null;
  const autoDeleteAtMs =
    !retentionLegalHold &&
    retentionTtlDays != null &&
    Number.isFinite(Number(expiration)) &&
    Number(expiration) > 0
      ? Number(expiration) + retentionTtlDays * 24 * 60 * 60 * 1000
      : null;
  const expired =
    Number.isFinite(Number(expiration)) && Number(expiration) > 0 && now > Number(expiration);
  const liveResultsAreDelayed =
    !youOwnThisPoll && !archived && !expired && phase === 'open' && resultsDelaySeconds > 0;
  const resultsVisibleThroughMs = liveResultsAreDelayed
    ? Math.max(0, now - resultsDelaySeconds * 1000)
    : now;
  const resultsVisibleThroughIso = new Date(resultsVisibleThroughMs).toISOString();

  const {
    voteData,
    metricsRow,
    peakHourRow,
    peakDowRow,
    hourBins,
    dowBins,
    optionHourBins,
    voteMinuteBins,
    optionVoteMinuteBins,
    rateCountersRow,
    delayedVotesPending,
  } = await getPollVoteAnalytics({
    pollId,
    resultsVisibleThroughIso,
    liveResultsAreDelayed,
    youOwnThisPoll,
  });

  const totalVotes = Number(metricsRow?.total_votes ?? 0) || 0;
  const totalWeightedVotes = Number(metricsRow?.total_weighted_votes ?? totalVotes) || totalVotes;
  const votesLast5m = Number(metricsRow?.votes_last_5m ?? 0) || 0;
  const firstVoteAtMs = toFiniteMs(metricsRow?.first_vote_at ?? null);
  const createdAtMs = toFiniteMs(createdAt);
  const nowMs = now;
  const ageMinutes =
    createdAtMs != null && nowMs > createdAtMs
      ? Math.max((nowMs - createdAtMs) / 60000, 1 / 60)
      : null;
  const engagementVelocityVotesPerMin = ageMinutes != null ? totalVotes / ageMinutes : null;
  const completionRatePct =
    impressionCount > 0 ? Math.min(100, (totalVotes / impressionCount) * 100) : null;
  const sortedVoteCounts = voteData
    .map((row) =>
      boostedVotingEnabled ? Number(row.weighted_vote_count) || 0 : Number(row.vote_count) || 0,
    )
    .sort((a, b) => b - a);
  const topVotes = sortedVoteCounts[0] ?? 0;
  const secondVotes = sortedVoteCounts[1] ?? 0;
  const leaderMarginPct = totalVotes > 0 ? ((topVotes - secondVotes) / totalVotes) * 100 : null;
  const optionCoveragePct =
    options.length > 0
      ? (sortedVoteCounts.filter((n) => n > 0).length / options.length) * 100
      : null;
  const timeToFirstVoteMs =
    firstVoteAtMs != null && createdAtMs != null && firstVoteAtMs >= createdAtMs
      ? firstVoteAtMs - createdAtMs
      : null;
  const peakHourUtc =
    peakHourRow != null && peakHourRow.peak_hour_utc !== undefined
      ? Number(peakHourRow.peak_hour_utc)
      : null;
  const peakHourVotes = peakHourRow != null ? Number(peakHourRow.peak_hour_votes ?? 0) || 0 : 0;
  const peakDowUtc =
    peakDowRow != null && peakDowRow.peak_dow_utc !== undefined
      ? Number(peakDowRow.peak_dow_utc)
      : null;
  const peakDowVotes = peakDowRow != null ? Number(peakDowRow.peak_dow_votes ?? 0) || 0 : 0;
  const hourlyVotesByHourUtc = Array.from({ length: 24 }, () => 0);
  for (const row of hourBins) {
    const h = Number(row.hour_utc);
    if (!Number.isInteger(h) || h < 0 || h > 23) continue;
    hourlyVotesByHourUtc[h] = Number(row.vote_count) || 0;
  }
  const weekdayVotesByDowUtc = Array.from({ length: 7 }, () => 0);
  for (const row of dowBins) {
    const d = Number(row.dow_utc);
    if (!Number.isInteger(d) || d < 0 || d > 6) continue;
    weekdayVotesByDowUtc[d] = Number(row.vote_count) || 0;
  }

  const voteVelocityByMinuteUtcTruncated = youOwnThisPoll && voteMinuteBins.length === 4000;

  const voteVelocityByMinuteUtc = youOwnThisPoll
    ? (() => {
        const chronological = [...voteMinuteBins].reverse();
        return chronological.map((r) => ({
          minute_utc:
            r.minute_utc instanceof Date
              ? r.minute_utc.toISOString()
              : new Date(String(r.minute_utc)).toISOString(),
          vote_count: Number(r.vote_count) || 0,
        }));
      })()
    : [];

  const optionHourlyVotesUtc = youOwnThisPoll
    ? (() => {
        const optionHourlyByLabel = new Map<string, number[]>();
        for (const row of optionHourBins) {
          const label = String(row.option_label ?? '');
          if (!optionHourlyByLabel.has(label)) {
            optionHourlyByLabel.set(
              label,
              Array.from({ length: 24 }, () => 0),
            );
          }
          const bins = optionHourlyByLabel.get(label)!;
          const h = Number(row.hour_utc);
          if (Number.isInteger(h) && h >= 0 && h <= 23) {
            bins[h] = Number(row.vote_count) || 0;
          }
        }
        return options.map((label) => ({
          option: label,
          hourly_votes_by_hour_utc:
            optionHourlyByLabel.get(label) ?? Array.from({ length: 24 }, () => 0),
        }));
      })()
    : [];

  const optionVoteVelocityByMinuteUtc = youOwnThisPoll
    ? buildOptionVoteVelocityByMinuteUtc(options, optionVoteMinuteBins)
    : [];

  return {
    kind: 'ok',
    data: {
      title,
      options,
      option_entries: optionEntries,
      createdAt,
      expiration,
      archived,
      phase,
      phase_schedule: schedule,
      server_now_ms: now,
      voting_paused: votingPaused,
      pause_message: pauseMessage,
      impression_count: impressionCount,
      ...(showNotes !== undefined ? { show_notes: showNotes } : {}),
      embed_gate: embedGate,
      you_own_this_poll: youOwnThisPoll,
      boosted_voting_enabled: boostedVotingEnabled,
      max_boost_weight: maxBoostWeight,
      show_unweighted_values: showUnweightedValues,
      run_of_show_key: runOfShowKey,
      run_of_show_order: runOfShowOrder,
      vanity_slug: vanitySlug,
      next_poll_id: nextPollId,
      auto_advance_on_close: autoAdvanceOnClose,
      vote_friction_tier: voteFrictionTier,
      soft_throttle_max_votes_per_min: softThrottleMaxVotesPerMin,
      pow_difficulty: powDifficulty,
      allow_write_in: allowWriteIn,
      write_in_max_length: writeInMaxLength,
      write_in_blocklist: writeInBlocklist,
      write_in_profanity_filter: writeInProfanityFilter,
      results_delay_seconds: resultsDelaySeconds,
      media:
        mediaAttachment != null
          ? {
              ...mediaAttachment,
              blur_by_default: mediaBlurByDefault,
              moderation_status: mediaModeration.status,
            }
          : null,
      theme_preset: themePreset,
      selection_mode: selectionMode,
      vote_eligibility: voteEligibility,
      platform_identity_provider: platformIdentityProvider,
      platform_identity_consent_version: platformIdentityConsentVersion,
      platform_identity_consent_captured_at_ms: platformIdentityConsentCapturedAt,
      retention_ttl_days: retentionTtlDays,
      retention_legal_hold: retentionLegalHold,
      auto_delete_at_ms: autoDeleteAtMs,
      live_results_are_delayed: liveResultsAreDelayed,
      results_visible_through_ms: resultsVisibleThroughMs,
      delayed_votes_pending: delayedVotesPending,
      integrity_panel: {
        safeguards_applied: [
          embedGate ? 'embed_gate' : null,
          boostedVotingEnabled ? 'boosted_voting' : null,
          selectionMode === 'multi' ? 'selection_mode:multi' : null,
          voteEligibility === 'account' || voteEligibility === 'platform_linked'
            ? `vote_eligibility:${voteEligibility}`
            : null,
          voteFrictionTier !== 'open' ? `vote_friction:${voteFrictionTier}` : null,
          resultsDelaySeconds > 0 ? `results_delay:${resultsDelaySeconds}s` : null,
          ...trustStackSafeguardTags(),
        ].filter((v): v is string => v != null),
        vote_friction_tier: voteFrictionTier,
        rate_limits: {
          soft_throttle_max_votes_per_min:
            voteFrictionTier === 'soft_throttle' ? softThrottleMaxVotesPerMin : null,
          pow_difficulty: voteFrictionTier === 'proof_of_work' ? powDifficulty : null,
        },
        moderation: {
          delayed_votes_pending: delayedVotesPending,
          quarantined_votes_pending: Number(rateCountersRow?.quarantined_votes_pending ?? 0) || 0,
        },
      },
      ...(youOwnThisPoll
        ? {
            moderation_counters: {
              votes_last_1m: Number(rateCountersRow?.votes_last_1m ?? 0) || 0,
              unique_ip_hashes_last_1m: Number(rateCountersRow?.unique_ip_hashes_last_1m ?? 0) || 0,
              unique_accounts_last_1m: Number(rateCountersRow?.unique_accounts_last_1m ?? 0) || 0,
              top_ip_votes_last_1m: Number(rateCountersRow?.top_ip_votes_last_1m ?? 0) || 0,
              quarantined_votes_pending:
                Number(rateCountersRow?.quarantined_votes_pending ?? 0) || 0,
              quarantined_votes_pending_account_linked:
                Number(rateCountersRow?.quarantined_votes_pending_account_linked ?? 0) || 0,
              votes_account_linked_last_24h:
                Number(rateCountersRow?.votes_account_linked_last_24h ?? 0) || 0,
              votes_anonymous_last_24h: Number(rateCountersRow?.votes_anonymous_last_24h ?? 0) || 0,
              trust_ip_burst: trustIpBurstOwnerSummary(),
              trust_chat_burst: trustChatBurstOwnerSummary(),
            },
          }
        : {}),
      votes: voteData.map((row) => ({
        option: row.option,
        vote_count: boostedVotingEnabled
          ? Number(row.weighted_vote_count) || 0
          : Number(row.vote_count) || 0,
        ...(boostedVotingEnabled && showUnweightedValues
          ? { unweighted_vote_count: Number(row.vote_count) || 0 }
          : {}),
        ...(boostedVotingEnabled
          ? { weighted_vote_count: Number(row.weighted_vote_count) || 0 }
          : {}),
      })),
      metrics: {
        total_votes: totalVotes,
        total_weighted_votes: totalWeightedVotes,
        votes_last_5m: votesLast5m,
        engagement_velocity_votes_per_min: engagementVelocityVotesPerMin,
        completion_rate_pct: completionRatePct,
        option_coverage_pct: optionCoveragePct,
        leader_margin_pct: leaderMarginPct,
        time_to_first_vote_ms: timeToFirstVoteMs,
        peak_hour_utc: Number.isInteger(peakHourUtc) ? peakHourUtc : null,
        peak_hour_votes: peakHourVotes,
        peak_dow_utc: Number.isInteger(peakDowUtc) ? peakDowUtc : null,
        peak_dow_votes: peakDowVotes,
        hourly_votes_by_hour_utc: hourlyVotesByHourUtc,
        weekday_votes_by_dow_utc: weekdayVotesByDowUtc,
        ...(youOwnThisPoll ? { option_hourly_votes_utc: optionHourlyVotesUtc } : {}),
        ...(youOwnThisPoll ? { vote_velocity_by_minute_utc: voteVelocityByMinuteUtc } : {}),
        ...(youOwnThisPoll && options.length > 0
          ? { option_vote_velocity_by_minute_utc: optionVoteVelocityByMinuteUtc }
          : {}),
        ...(youOwnThisPoll && voteVelocityByMinuteUtcTruncated
          ? { vote_velocity_by_minute_utc_truncated: true }
          : {}),
      },
    },
  };
}
