import {
  formatAllowedPhasesList,
  isPollPhaseTransitionAllowed,
  normalizePollPhase,
  type UpdatePollBody,
} from '@asking-ng/contracts/poll';
import type { AppRequestHandler } from '../../types/http';
import { generateEmbedReadToken, hashEmbedReadToken } from '../../lib/embedReadToken';
import { jsonError } from '../../lib/jsonError';
import { notifyPollLive } from '../../lib/pollLive';
import { recordPollPhaseTransition } from '../../lib/pollPhaseHistory';
import {
  pollPhaseScheduleFromRow,
  validatePollPhaseScheduleWindow,
} from '../../lib/pollPhaseSchedule';
import { appEnv } from '../../lib/env';
import { queuePollWebhook } from '../../lib/pollWebhooks';
import Poll from '../../model/Poll';
import { singleString } from '../../utils/http';

function apiKeyFrom(req: Parameters<AppRequestHandler>[0]): string | undefined {
  const v = req.headers.api_key;
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v[0];
  return undefined;
}

const DEFAULT_PANIC_PAUSE_MESSAGE = 'Voting is temporarily paused.';

function resolvePanicPauseMessage(bodyPause: string | null | undefined): string {
  if (typeof bodyPause === 'string') {
    const trimmed = bodyPause.trim();
    if (trimmed !== '') return trimmed.slice(0, 280);
  }
  const fromEnv = appEnv.panicPauseMessage;
  if (fromEnv) return fromEnv.slice(0, 280);
  return DEFAULT_PANIC_PAUSE_MESSAGE;
}

const updatePoll: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params.id);
  const apiKey = apiKeyFrom(req);
  const body = req.body as UpdatePollBody;
  const {
    expiration,
    phase,
    voting_paused,
    pause_message,
    show_notes,
    generate_embed_read_token,
    open_at,
    lock_at,
    reveal_at,
    boosted_voting_enabled,
    max_boost_weight,
    show_unweighted_values,
    run_of_show_key,
    run_of_show_order,
    next_poll_id,
    auto_advance_on_close,
    vanity_slug,
    vote_friction_tier,
    soft_throttle_max_votes_per_min,
    pow_difficulty,
    results_delay_seconds,
    allow_write_in,
    write_in_max_length,
    write_in_blocklist,
    write_in_profanity_filter,
    webhook_targets,
    panic,
    vote_eligibility,
  } = body;

  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  const poll = await Poll.findByPk(pollId);
  if (!poll) {
    jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
    return;
  }

  const targetApiKey = poll.get('api_key') as string | undefined;
  const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
  const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
  const ownerId = poll.get('creatorUserId') as number | null | undefined;
  const jwtOk = req.user != null && ownerId != null && Number(ownerId) === Number(req.user.id);

  if (!apiKeyOk && !jwtOk) {
    jsonError(
      res,
      req,
      401,
      'UNAUTHORIZED',
      'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
    );
    return;
  }

  if (panic === true && poll.get('archived')) {
    jsonError(res, req, 400, 'POLL_ARCHIVED', 'Cannot panic an archived poll.');
    return;
  }

  const patch: Record<string, unknown> = {};
  let usedPanic = false;
  if (panic === true) {
    usedPanic = true;
    patch.phase = 'locked';
    patch.votingPaused = true;
    patch.pauseMessage = resolvePanicPauseMessage(pause_message);
  } else {
    if (expiration !== undefined) patch.expiration = expiration;
    if (phase !== undefined) patch.phase = phase;
    if (voting_paused !== undefined) patch.votingPaused = voting_paused;
    if (pause_message !== undefined) {
      patch.pauseMessage = pause_message === null ? null : pause_message;
    }
    if (show_notes !== undefined) {
      patch.showNotes = show_notes === null ? null : show_notes;
    }
    if (open_at !== undefined) patch.openAt = open_at;
    if (lock_at !== undefined) patch.lockAt = lock_at;
    if (reveal_at !== undefined) patch.revealAt = reveal_at;
    if (boosted_voting_enabled !== undefined) patch.boostedVotingEnabled = boosted_voting_enabled;
    if (show_unweighted_values !== undefined) patch.showUnweightedValues = show_unweighted_values;
    if (max_boost_weight !== undefined) {
      patch.maxBoostWeight = max_boost_weight === null ? 3 : max_boost_weight;
    }
    if (run_of_show_key !== undefined) patch.runOfShowKey = run_of_show_key;
    if (run_of_show_order !== undefined) patch.runOfShowOrder = run_of_show_order;
    if (next_poll_id !== undefined) patch.nextPollId = next_poll_id;
    if (auto_advance_on_close !== undefined) patch.autoAdvanceOnClose = auto_advance_on_close;
    if (vanity_slug !== undefined) patch.vanitySlug = vanity_slug;
    if (vote_friction_tier !== undefined) patch.voteFrictionTier = vote_friction_tier;
    if (soft_throttle_max_votes_per_min !== undefined) {
      patch.softThrottleMaxVotesPerMin =
        soft_throttle_max_votes_per_min === null ? 30 : soft_throttle_max_votes_per_min;
    }
    if (pow_difficulty !== undefined) {
      patch.powDifficulty = pow_difficulty === null ? 4 : pow_difficulty;
    }
    if (results_delay_seconds !== undefined) {
      patch.resultsDelaySeconds = results_delay_seconds === null ? 0 : results_delay_seconds;
    }
    if (allow_write_in !== undefined) patch.allowWriteIn = allow_write_in;
    if (write_in_max_length !== undefined) {
      patch.writeInMaxLength = write_in_max_length === null ? 80 : write_in_max_length;
    }
    if (write_in_blocklist !== undefined) {
      patch.writeInBlocklist = write_in_blocklist === null ? [] : write_in_blocklist;
    }
    if (write_in_profanity_filter !== undefined) {
      patch.writeInProfanityFilter = write_in_profanity_filter;
    }
    if (webhook_targets !== undefined) {
      patch.webhookTargets = webhook_targets === null ? [] : webhook_targets;
    }
    if (vote_eligibility !== undefined) {
      const currentPhase = normalizePollPhase(poll.get('phase'));
      if (currentPhase !== 'draft') {
        jsonError(
          res,
          req,
          400,
          'VOTE_ELIGIBILITY_LOCKED',
          'vote_eligibility can only be changed while the poll is in draft phase.',
        );
        return;
      }
      patch.voteEligibility = vote_eligibility === null ? 'anonymous' : vote_eligibility;
    }
  }

  let embedReadToken: string | undefined;
  if (generate_embed_read_token === true) {
    embedReadToken = generateEmbedReadToken();
    patch.embedReadTokenHash = hashEmbedReadToken(embedReadToken);
  }

  const nextPhaseRaw = patch.phase;
  if (typeof nextPhaseRaw === 'string') {
    const fromPhase = normalizePollPhase(poll.get('phase'));
    const toPhase = nextPhaseRaw as typeof fromPhase;
    if (
      !isPollPhaseTransitionAllowed(fromPhase, toPhase, {
        panic: usedPanic,
      })
    ) {
      jsonError(
        res,
        req,
        400,
        'INVALID_PHASE_TRANSITION',
        `Cannot change poll phase from ${fromPhase} to ${toPhase}. Allowed targets: ${formatAllowedPhasesList(fromPhase)}.`,
      );
      return;
    }
  }

  const currentSchedule = pollPhaseScheduleFromRow(poll);
  const mergedSchedule = {
    open_at:
      patch.openAt !== undefined
        ? patch.openAt === null
          ? null
          : Number(patch.openAt)
        : currentSchedule.open_at,
    lock_at:
      patch.lockAt !== undefined
        ? patch.lockAt === null
          ? null
          : Number(patch.lockAt)
        : currentSchedule.lock_at,
    reveal_at:
      patch.revealAt !== undefined
        ? patch.revealAt === null
          ? null
          : Number(patch.revealAt)
        : currentSchedule.reveal_at,
  };
  const scheduleErr = validatePollPhaseScheduleWindow(mergedSchedule);
  if (scheduleErr) {
    jsonError(res, req, 400, 'INVALID_PHASE_SCHEDULE', scheduleErr);
    return;
  }

  const mergedBoostEnabled =
    patch.boostedVotingEnabled !== undefined
      ? Boolean(patch.boostedVotingEnabled)
      : Boolean(poll.get('boostedVotingEnabled'));
  const mergedMaxBoost =
    patch.maxBoostWeight !== undefined
      ? Number(patch.maxBoostWeight)
      : Number(poll.get('maxBoostWeight') ?? 3);
  if (!mergedBoostEnabled && patch.maxBoostWeight !== undefined && max_boost_weight !== null) {
    jsonError(
      res,
      req,
      400,
      'INVALID_BOOSTED_VOTING_CONFIG',
      'max_boost_weight requires boosted_voting_enabled to be true.',
    );
    return;
  }
  if (!Number.isFinite(mergedMaxBoost) || mergedMaxBoost < 1 || mergedMaxBoost > 10) {
    jsonError(
      res,
      req,
      400,
      'INVALID_BOOSTED_VOTING_CONFIG',
      'max_boost_weight must be between 1 and 10.',
    );
    return;
  }
  const mergedFrictionTier =
    patch.voteFrictionTier !== undefined
      ? String(patch.voteFrictionTier)
      : String(poll.get('voteFrictionTier') ?? 'open');
  const mergedSoftThrottle =
    patch.softThrottleMaxVotesPerMin !== undefined
      ? Number(patch.softThrottleMaxVotesPerMin)
      : Number(poll.get('softThrottleMaxVotesPerMin') ?? 30);
  const mergedPowDifficulty =
    patch.powDifficulty !== undefined
      ? Number(patch.powDifficulty)
      : Number(poll.get('powDifficulty') ?? 4);
  if (
    mergedFrictionTier === 'soft_throttle' &&
    (!Number.isFinite(mergedSoftThrottle) || mergedSoftThrottle < 1)
  ) {
    jsonError(
      res,
      req,
      400,
      'INVALID_VOTE_FRICTION_CONFIG',
      'soft_throttle_max_votes_per_min must be >= 1 when vote_friction_tier=soft_throttle.',
    );
    return;
  }
  if (
    mergedFrictionTier === 'proof_of_work' &&
    (!Number.isFinite(mergedPowDifficulty) || mergedPowDifficulty < 1 || mergedPowDifficulty > 6)
  ) {
    jsonError(
      res,
      req,
      400,
      'INVALID_VOTE_FRICTION_CONFIG',
      'pow_difficulty must be between 1 and 6 when vote_friction_tier=proof_of_work.',
    );
    return;
  }

  const mergedNextPollId =
    patch.nextPollId !== undefined
      ? patch.nextPollId === null
        ? null
        : String(patch.nextPollId).trim()
      : ((poll.get('nextPollId') as string | null | undefined) ?? null);
  const mergedAutoAdvance =
    patch.autoAdvanceOnClose !== undefined
      ? Boolean(patch.autoAdvanceOnClose)
      : Boolean(poll.get('autoAdvanceOnClose'));
  if (mergedNextPollId != null && mergedNextPollId !== '' && ownerId == null) {
    jsonError(
      res,
      req,
      400,
      'INVALID_NEXT_POLL',
      'next_poll_id requires a signed-in creator-owned poll.',
    );
    return;
  }
  if (mergedAutoAdvance && (!mergedNextPollId || mergedNextPollId === '')) {
    jsonError(res, req, 400, 'INVALID_NEXT_POLL', 'auto_advance_on_close requires next_poll_id.');
    return;
  }
  if (mergedNextPollId != null && mergedNextPollId !== '') {
    if (mergedNextPollId === pollId) {
      jsonError(
        res,
        req,
        400,
        'INVALID_NEXT_POLL',
        'next_poll_id cannot equal the current poll id.',
      );
      return;
    }
    const nextPoll = await Poll.findByPk(mergedNextPollId);
    if (!nextPoll) {
      jsonError(res, req, 400, 'INVALID_NEXT_POLL', 'next_poll_id does not exist.');
      return;
    }
    if (ownerId != null && Number(nextPoll.get('creatorUserId')) !== Number(ownerId)) {
      jsonError(
        res,
        req,
        400,
        'INVALID_NEXT_POLL',
        'next_poll_id must belong to the same signed-in creator.',
      );
      return;
    }
  }
  if (patch.vanitySlug !== undefined) {
    const candidate = patch.vanitySlug === null ? null : String(patch.vanitySlug).trim();
    if (candidate) {
      const existing = await Poll.findOne({ where: { vanitySlug: candidate } });
      if (existing && String(existing.get('id')) !== pollId) {
        jsonError(res, req, 400, 'INVALID_VANITY_SLUG', 'vanity_slug is already in use.');
        return;
      }
      patch.vanitySlug = candidate;
    } else {
      patch.vanitySlug = null;
    }
  }

  await Poll.update(patch, { where: { id: pollId } });
  const fromPhase = normalizePollPhase(poll.get('phase'));
  const toPhase = typeof patch.phase === 'string' ? normalizePollPhase(patch.phase) : fromPhase;
  if (fromPhase !== toPhase) {
    await recordPollPhaseTransition({
      pollId,
      fromPhase,
      toPhase,
      actorType: jwtOk ? 'owner_jwt' : 'api_key',
      actorUserId: jwtOk ? Number(req.user?.id) : null,
      source: usedPanic ? 'panic' : 'poll_update',
    });
  }
  let autoAdvancedPollId: string | null = null;
  const closedThisPoll = fromPhase !== toPhase && (toPhase === 'locked' || toPhase === 'revealed');
  if (closedThisPoll && mergedAutoAdvance && mergedNextPollId && mergedNextPollId !== '') {
    const nextPoll = await Poll.findByPk(mergedNextPollId);
    if (nextPoll && !nextPoll.get('archived')) {
      const nextFrom = normalizePollPhase(nextPoll.get('phase'));
      if (nextFrom !== 'open' && isPollPhaseTransitionAllowed(nextFrom, 'open')) {
        await Poll.update(
          { phase: 'open', votingPaused: false, pauseMessage: null },
          { where: { id: mergedNextPollId } },
        );
        await recordPollPhaseTransition({
          pollId: mergedNextPollId,
          fromPhase: nextFrom,
          toPhase: 'open',
          actorType: 'admin_token',
          actorUserId: null,
          source: 'auto_advance',
        });
        notifyPollLive(mergedNextPollId, { type: 'update' });
        queuePollWebhook(mergedNextPollId, 'poll_updated', {
          phase: 'open',
          voting_paused: false,
          pause_message: null,
          auto_advanced_from_poll_id: pollId,
        });
        autoAdvancedPollId = mergedNextPollId;
      }
    }
  }
  notifyPollLive(pollId, usedPanic ? { type: 'panic' } : { type: 'update' });
  const resolvedPauseForWebhook = usedPanic
    ? resolvePanicPauseMessage(pause_message)
    : pause_message;
  queuePollWebhook(pollId, 'poll_updated', {
    panic: usedPanic,
    expiration: usedPanic ? undefined : expiration,
    phase: usedPanic ? 'locked' : phase,
    open_at: usedPanic ? undefined : open_at,
    lock_at: usedPanic ? undefined : lock_at,
    reveal_at: usedPanic ? undefined : reveal_at,
    boosted_voting_enabled: usedPanic ? undefined : boosted_voting_enabled,
    max_boost_weight: usedPanic ? undefined : max_boost_weight,
    show_unweighted_values: usedPanic ? undefined : show_unweighted_values,
    run_of_show_key: usedPanic ? undefined : run_of_show_key,
    run_of_show_order: usedPanic ? undefined : run_of_show_order,
    vanity_slug: usedPanic ? undefined : vanity_slug,
    next_poll_id: usedPanic ? undefined : next_poll_id,
    auto_advance_on_close: usedPanic ? undefined : auto_advance_on_close,
    vote_friction_tier: usedPanic ? undefined : vote_friction_tier,
    soft_throttle_max_votes_per_min: usedPanic ? undefined : soft_throttle_max_votes_per_min,
    pow_difficulty: usedPanic ? undefined : pow_difficulty,
    results_delay_seconds: usedPanic ? undefined : results_delay_seconds,
    allow_write_in: usedPanic ? undefined : allow_write_in,
    write_in_max_length: usedPanic ? undefined : write_in_max_length,
    write_in_blocklist: usedPanic ? undefined : write_in_blocklist,
    write_in_profanity_filter: usedPanic ? undefined : write_in_profanity_filter,
    webhook_targets: usedPanic ? undefined : webhook_targets,
    voting_paused: usedPanic ? true : voting_paused,
    pause_message: resolvedPauseForWebhook,
    show_notes: show_notes === undefined ? undefined : show_notes === null ? null : '[redacted]',
    embed_read_token_rotated: generate_embed_read_token === true,
  });

  const payload: {
    status: string;
    message: string;
    data?: { embed_read_token?: string; auto_advanced_poll_id?: string };
  } = {
    status: 'success',
    message: 'Poll successfully updated.',
  };
  if (embedReadToken || autoAdvancedPollId) {
    payload.data = {
      ...(embedReadToken ? { embed_read_token: embedReadToken } : {}),
      ...(autoAdvancedPollId ? { auto_advanced_poll_id: autoAdvancedPollId } : {}),
    };
  }
  res.status(200).json(payload);
};

export default updatePoll;
