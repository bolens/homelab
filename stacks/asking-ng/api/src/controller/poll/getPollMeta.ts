import type { AppRequestHandler } from '../../types/http';
import { QueryTypes } from 'sequelize';
import db from '../../connections';
import { pollEmbedViewAllowed, readEmbedReadTokenFromRequest } from '../../lib/embedReadToken';
import { jsonError } from '../../lib/jsonError';
import { normalizeMediaAttachment, normalizeMediaModeration } from '../../lib/mediaPolicy';
import { listPollPhaseHistory } from '../../lib/pollPhaseHistory';
import { pollPhaseScheduleFromRow, resolveEffectivePollPhase } from '../../lib/pollPhaseSchedule';
import { publicPollPageUrl, publicPollResultsUrl } from '../../lib/sitePublicUrl';
import {
  trustChatBurstOwnerSummary,
  trustIpBurstOwnerSummary,
  trustStackSafeguardTags,
} from '../../lib/trustStackSignals';
import Poll from '../../model/Poll';
import { singleString } from '../../utils/http';

/**
 * Compact poll metadata for bots / chat integrations (no vote tallies, no impression bump).
 */
const getPollMeta: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params.id);
  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  const poll = await Poll.findByPk(pollId);
  if (!poll) {
    jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
    return;
  }

  const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
  const embedToken = readEmbedReadTokenFromRequest(req);
  const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
  if (!pollEmbedViewAllowed(req, pollId, embedHash, embedToken, creatorUserId)) {
    jsonError(
      res,
      req,
      403,
      'POLL_EMBED_TOKEN_REQUIRED',
      'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
    );
    return;
  }

  const title = poll.get('title') as string;
  const options = (poll.get('options') as string[]) || [];
  const expiration = Number.parseInt(String(poll.get('expiration')), 10);
  const archived = !!poll.get('archived');
  const now = Date.now();
  const schedule = pollPhaseScheduleFromRow(poll);
  const phase = resolveEffectivePollPhase(poll.get('phase'), schedule, now);
  const votingPaused = !!poll.get('votingPaused');
  const pauseMessage = (poll.get('pauseMessage') as string | null) ?? null;
  const embedGate = typeof embedHash === 'string' && embedHash.trim() !== '';
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
  const selectionMode = String(poll.get('selectionMode') ?? 'single') === 'multi' ? 'multi' : 'single';
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
    !retentionLegalHold && retentionTtlDays != null && Number.isFinite(expiration) && expiration > 0
      ? expiration + retentionTtlDays * 24 * 60 * 60 * 1000
      : null;
  const expired = Number.isFinite(expiration) && expiration > 0 && now > expiration;
  const signedInOk =
    req.user != null && Number.isFinite(Number(req.user.id)) && Number(req.user.id) > 0;
  const canVote =
    !archived &&
    !votingPaused &&
    !expired &&
    phase === 'open' &&
    options.length >= 2 &&
    (voteEligibility === 'anonymous' || signedInOk);

  const votePath = `poll/${encodeURIComponent(pollId)}/vote`;
  const phaseHistory = await listPollPhaseHistory(pollId, { limit: 50 });
  const youOwnThisPoll =
    req.user != null && creatorUserId != null && Number(req.user.id) === Number(creatorUserId);
  const [rateCountersRow] = youOwnThisPoll
    ? ((await db.query(
        `SELECT
          COUNT(*) FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '1 minute' AND COALESCE("isQuarantined", false) = false
          )::int AS votes_last_1m,
          COUNT(DISTINCT "sourceIpHash") FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '1 minute'
              AND "sourceIpHash" IS NOT NULL
              AND COALESCE("isQuarantined", false) = false
          )::int AS unique_ip_hashes_last_1m,
          COUNT(DISTINCT "userId") FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '1 minute'
              AND "userId" IS NOT NULL
              AND COALESCE("isQuarantined", false) = false
          )::int AS unique_accounts_last_1m,
          COALESCE((
            SELECT MAX(c) FROM (
              SELECT COUNT(*)::int AS c
              FROM votes
              WHERE "pollId" = :pollId
                AND "createdAt" >= NOW() - INTERVAL '1 minute'
                AND "sourceIpHash" IS NOT NULL
                AND COALESCE("isQuarantined", false) = false
              GROUP BY "sourceIpHash"
            ) t
          ), 0)::int AS top_ip_votes_last_1m
          ,
          COUNT(*) FILTER (
            WHERE COALESCE("isQuarantined", false) = true AND COALESCE("quarantineStatus", 'pending') = 'pending'
          )::int AS quarantined_votes_pending,
          COUNT(*) FILTER (
            WHERE COALESCE("isQuarantined", false) = true
              AND COALESCE("quarantineStatus", 'pending') = 'pending'
              AND "userId" IS NOT NULL
          )::int AS quarantined_votes_pending_account_linked,
          COUNT(*) FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '24 hours'
              AND "userId" IS NOT NULL
          )::int AS votes_account_linked_last_24h,
          COUNT(*) FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '24 hours'
              AND "userId" IS NULL
          )::int AS votes_anonymous_last_24h
         FROM votes
         WHERE "pollId" = :pollId`,
        { replacements: { pollId }, type: QueryTypes.SELECT },
      )) as Array<{
        votes_last_1m: string | number;
        unique_ip_hashes_last_1m: string | number;
        unique_accounts_last_1m: string | number;
        top_ip_votes_last_1m: string | number;
        quarantined_votes_pending: string | number;
        quarantined_votes_pending_account_linked: string | number;
        votes_account_linked_last_24h: string | number;
        votes_anonymous_last_24h: string | number;
      }>)
    : [];

  res.status(200).json({
    status: 'success',
    data: {
      id: pollId,
      title,
      phase,
      phase_schedule: schedule,
      archived,
      voting_paused: votingPaused,
      pause_message: pauseMessage,
      boosted_voting_enabled: boostedVotingEnabled,
      show_unweighted_values: showUnweightedValues,
      max_boost_weight: maxBoostWeight,
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
      expiration,
      embed_gate: embedGate,
      public_poll_url: publicPollPageUrl(req, pollId),
      public_results_url: publicPollResultsUrl(req, pollId),
      /** Same path convention as HTTP clients using the API base (`poll/…`, not a leading slash). */
      vote_path: votePath,
      vote_http_method: 'PUT',
      timestamps_timezone: 'UTC',
      server_now_ms: now,
      phase_history: phaseHistory,
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
          quarantined_votes_pending: Number(rateCountersRow?.quarantined_votes_pending ?? 0) || 0,
        },
      },
      options: options.map((label, index) => ({ index, label })),
      can_vote: canVote,
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
              votes_anonymous_last_24h:
                Number(rateCountersRow?.votes_anonymous_last_24h ?? 0) || 0,
              trust_ip_burst: trustIpBurstOwnerSummary(),
              trust_chat_burst: trustChatBurstOwnerSummary(),
            },
          }
        : {}),
    },
  });
};

export default getPollMeta;
