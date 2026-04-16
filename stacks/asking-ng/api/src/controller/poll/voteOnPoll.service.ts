import type { VotePollBody } from '@asking-ng/contracts/poll';
import { createHash } from 'crypto';
import { UniqueConstraintError } from 'sequelize';
import { getVoteGeoEnabled } from '../../lib/appSettings';
import { checkMonthlyVoteQuotaForCreator } from '../../lib/billingVoteQuota';
import { appEnv } from '../../lib/env';
import { pollEmbedReadAllowed, readEmbedReadTokenFromRequest } from '../../lib/embedReadToken';
import { notifyPollLive } from '../../lib/pollLive';
import { pollPhaseScheduleFromRow, resolveEffectivePollPhase } from '../../lib/pollPhaseSchedule';
import { queuePollWebhook } from '../../lib/pollWebhooks';
import { validateWriteInText } from '../../lib/writeInHygiene';
import type { AppRequest } from '../../types/http';
import randomId from '../../helpers/randomId';
import db from '../../connections';
import {
  countLimitIpBallotsForPoll,
  countRecentVotesForChatChannel,
  countRecentVotesForChatChannelWindowSeconds,
  countRecentVotesForSourceIp,
  countRecentVotesForSourceIpWindowSeconds,
  createVoteRow,
  createVoteRowInTransaction,
  findPollByIdOrSlug,
  findVoteByIdempotencyKey,
  findVotesByIdempotencyKey,
  countVotesByPollAndUser,
} from './voteOnPoll.repository';

function quantizeCoordinate(raw: unknown, min: number, max: number): number | null {
  if (typeof raw !== 'number' || !Number.isFinite(raw) || raw < min || raw > max) return null;
  return Math.round(raw * 10) / 10;
}

function isPostgresUniqueViolation(err: unknown): boolean {
  if (err instanceof UniqueConstraintError) return true;
  const o = err as { original?: { code?: string } } | null;
  return o?.original?.code === '23505';
}

function hashIp(ipRaw: string): string {
  const salt = appEnv.voteIpHashSalt;
  return createHash('sha256').update(`${salt}:${ipRaw.trim()}`).digest('hex');
}

function validatePow(pollId: string, nonce: string, difficulty: number): boolean {
  const prefix = '0'.repeat(Math.max(1, Math.min(6, difficulty)));
  const digest = createHash('sha256').update(`${pollId}:${nonce}`).digest('hex');
  return digest.startsWith(prefix);
}

function normalizeChatChannelId(raw: string | undefined): string | null {
  const v = raw?.trim();
  if (!v) return null;
  return v.slice(0, 128);
}

function normalizeIdempotencyKey(raw: string | undefined): string | null {
  const v = raw?.trim();
  if (!v) return null;
  return v.slice(0, 128);
}

export type VoteOnPollResult =
  | { kind: 'not_found' }
  | { kind: 'forbidden_embed_token' }
  | { kind: 'poll_archived' }
  | { kind: 'poll_not_accepting_votes' }
  | { kind: 'poll_voting_paused' }
  | { kind: 'boost_weight_disabled' }
  | { kind: 'invalid_boost_weight'; maxBoostWeight: number }
  | { kind: 'poll_soft_throttled'; softThrottleMaxVotesPerMin: number }
  | { kind: 'pow_required'; pollId: string; powDifficulty: number }
  | { kind: 'invalid_option_index' }
  | { kind: 'invalid_option_indices' }
  | { kind: 'vote_shape_mismatch'; detail: string }
  | { kind: 'invalid_write_in'; code: string; message: string }
  | { kind: 'poll_expired' }
  | { kind: 'channel_rate_limited'; perChannelMax: number }
  | { kind: 'idempotent_replay'; vote: unknown; ballotVotes?: unknown[] }
  | { kind: 'duplicate_vote' }
  | {
      kind: 'usage_limit_votes_month';
      max: number;
      current: number;
      plan: string;
      incoming: number;
    }
  | { kind: 'vote_requires_sign_in' }
  | {
      kind: 'ok';
      vote: unknown;
      ballotVotes?: unknown[];
      optionIndices?: number[];
      moderation?: { quarantined: true; reason: string | null; trust_risk_score: number | null };
    };

type TrustSignalBits = { soft: boolean; ip: boolean; chat: boolean };

/** Bit-pack soft (1) + ip (2) + chat (4) into a single quarantine_reason code (≤64 chars). */
function reasonFromTrustSignals(s: TrustSignalBits): string | null {
  const n = (s.soft ? 1 : 0) + (s.ip ? 2 : 0) + (s.chat ? 4 : 0);
  switch (n) {
    case 1:
      return 'soft_throttle_over_limit';
    case 2:
      return 'ip_burst';
    case 4:
      return 'chat_burst';
    case 3:
      return 'soft_plus_burst';
    case 5:
      return 'soft_chat_burst';
    case 6:
      return 'ip_chat_burst';
    case 7:
      return 'triple_signal';
    default:
      return null;
  }
}

function computeTrustRiskScore(p: {
  shouldQuarantine: boolean;
  softThrottleTier: boolean;
  softMax: number;
  votes1mFromIp: number | null;
  ipBurst: { threshold: number; count: number; triggered: boolean };
  chatBurst: { threshold: number; count: number; triggered: boolean };
  quarantineReason: string | null;
}): number | null {
  if (!p.shouldQuarantine) return null;
  let score = 0;
  const softSignals =
    p.softThrottleTier &&
    (p.quarantineReason === 'soft_throttle_over_limit' ||
      p.quarantineReason === 'soft_plus_burst' ||
      p.quarantineReason === 'soft_chat_burst' ||
      p.quarantineReason === 'triple_signal');
  if (softSignals && p.votes1mFromIp != null) {
    const over = Math.max(0, p.votes1mFromIp - p.softMax);
    score = Math.max(score, Math.min(100, 34 + Math.min(58, over * 12)));
  }
  if (p.ipBurst.threshold > 0 && p.ipBurst.triggered) {
    const over = Math.max(0, p.ipBurst.count - p.ipBurst.threshold + 1);
    score = Math.max(score, Math.min(100, 42 + Math.min(52, over * 8)));
  }
  if (p.chatBurst.threshold > 0 && p.chatBurst.triggered) {
    const over = Math.max(0, p.chatBurst.count - p.chatBurst.threshold + 1);
    score = Math.max(score, Math.min(100, 40 + Math.min(52, over * 8)));
  }
  if (score === 0) return 28;
  return score;
}

export async function voteOnPollService(
  req: AppRequest,
  pollId: string,
  body: VotePollBody,
): Promise<VoteOnPollResult> {
  const optionStrRaw = body.option;
  const optionIndex = body.option_index;
  const optionIndices = body.option_indices;
  const boostWeightRaw = body.boost_weight;
  const powNonce = body.pow_nonce?.trim();
  const chatChannelId = normalizeChatChannelId(body.chat_channel_id);
  const commandIdempotencyKey = normalizeIdempotencyKey(body.idempotency_key);
  const { location } = body;

  try {
    const poll = await findPollByIdOrSlug(pollId);
    if (!poll) return { kind: 'not_found' };

    const resolvedPollId = String(poll.get('id'));
    const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
    const embedToken = readEmbedReadTokenFromRequest(req);
    const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
    if (!pollEmbedReadAllowed(req, embedHash, embedToken, creatorUserId)) {
      return { kind: 'forbidden_embed_token' };
    }
    if (poll.get('archived')) return { kind: 'poll_archived' };

    const phase = resolveEffectivePollPhase(
      poll.get('phase'),
      pollPhaseScheduleFromRow(poll),
      Date.now(),
    );
    if (phase !== 'open') return { kind: 'poll_not_accepting_votes' };
    if (poll.get('votingPaused')) return { kind: 'poll_voting_paused' };

    const voteEligibility =
      String(poll.get('voteEligibility') ?? 'anonymous') === 'account' ? 'account' : 'anonymous';
    let signedInUserId: number | null = null;
    if (req.user?.id != null) {
      const n = Number(req.user.id);
      if (Number.isFinite(n) && n > 0) signedInUserId = n;
    }
    if (voteEligibility === 'account' && signedInUserId == null) {
      return { kind: 'vote_requires_sign_in' };
    }

    const validOptions = (poll.get('options') as string[] | null) || [];
    const selectionMode = String(poll.get('selectionMode') ?? 'single') === 'multi' ? 'multi' : 'single';
    const boostedVotingEnabled = !!poll.get('boostedVotingEnabled');
    const maxBoostWeight = Number(poll.get('maxBoostWeight') ?? 3);
    const voteFrictionTier = String(poll.get('voteFrictionTier') ?? 'open');
    const softThrottleMaxVotesPerMin = Number(poll.get('softThrottleMaxVotesPerMin') ?? 30);
    const powDifficulty = Number(poll.get('powDifficulty') ?? 4);
    const allowWriteIn = !!poll.get('allowWriteIn');
    const writeInMaxLength = Number(poll.get('writeInMaxLength') ?? 80);
    const writeInBlocklist = (
      (poll.get('writeInBlocklist') as string[] | null | undefined) ?? []
    ).filter((s) => typeof s === 'string' && s.trim() !== '');
    const writeInProfanityFilter = poll.get('writeInProfanityFilter') !== false;
    const boostWeight = boostWeightRaw ?? 1;

    const isMultiBody = optionIndices !== undefined && optionIndices.length > 0;

    if (selectionMode === 'multi') {
      if (!isMultiBody) {
        return {
          kind: 'vote_shape_mismatch',
          detail: 'This poll uses selection_mode=multi; send option_indices (array of 0-based indices).',
        };
      }
      if (boostWeightRaw !== undefined && boostWeight !== 1) {
        return { kind: 'boost_weight_disabled' };
      }
    } else if (isMultiBody) {
      return {
        kind: 'vote_shape_mismatch',
        detail: 'option_indices is only valid when the poll uses selection_mode=multi.',
      };
    }

    if (boostWeightRaw !== undefined && !boostedVotingEnabled) {
      return { kind: 'boost_weight_disabled' };
    }
    if (!Number.isFinite(boostWeight) || boostWeight < 1 || boostWeight > maxBoostWeight) {
      return { kind: 'invalid_boost_weight', maxBoostWeight };
    }

    const sourceIpHash = hashIp(String(req.ip || ''));
    let signalSoft = false;
    let votes1mFromIp: number | null = null;
    let burstWindowCount = 0;
    let ipBurstTriggered = false;
    let chatWindowCount = 0;
    let chatBurstTriggered = false;

    if (voteFrictionTier === 'soft_throttle') {
      votes1mFromIp = await countRecentVotesForSourceIp({ pollId: resolvedPollId, sourceIpHash });
      const c = votes1mFromIp;
      if (c >= softThrottleMaxVotesPerMin * 5) {
        return { kind: 'poll_soft_throttled', softThrottleMaxVotesPerMin };
      }
      if (c >= softThrottleMaxVotesPerMin) signalSoft = true;
    }

    const burstThreshold = appEnv.trustIpBurstVoteThreshold;
    if (burstThreshold > 0) {
      burstWindowCount = await countRecentVotesForSourceIpWindowSeconds({
        pollId: resolvedPollId,
        sourceIpHash,
        windowSec: appEnv.trustIpBurstWindowSec,
      });
      if (burstWindowCount >= burstThreshold) ipBurstTriggered = true;
    }

    const chatBurstTh = appEnv.trustChatBurstVoteThreshold;
    if (chatChannelId && chatBurstTh > 0) {
      chatWindowCount = await countRecentVotesForChatChannelWindowSeconds({
        pollId: resolvedPollId,
        chatChannelId,
        windowSec: appEnv.trustChatBurstWindowSec,
      });
      if (chatWindowCount >= chatBurstTh) chatBurstTriggered = true;
    }

    const shouldQuarantine = signalSoft || ipBurstTriggered || chatBurstTriggered;
    const quarantineReason = shouldQuarantine
      ? reasonFromTrustSignals({ soft: signalSoft, ip: ipBurstTriggered, chat: chatBurstTriggered })
      : null;

    const trustRiskScore = computeTrustRiskScore({
      shouldQuarantine,
      softThrottleTier: voteFrictionTier === 'soft_throttle',
      softMax: softThrottleMaxVotesPerMin,
      votes1mFromIp,
      ipBurst: {
        threshold: burstThreshold,
        count: burstWindowCount,
        triggered: ipBurstTriggered,
      },
      chatBurst: {
        threshold: chatBurstTh,
        count: chatWindowCount,
        triggered: chatBurstTriggered,
      },
      quarantineReason,
    });

    if (voteFrictionTier === 'proof_of_work') {
      if (!powNonce || !validatePow(resolvedPollId, powNonce, powDifficulty)) {
        return { kind: 'pow_required', pollId: resolvedPollId, powDifficulty };
      }
    }

    let singleOptionLabel: string | null = null;
    if (selectionMode === 'multi') {
      for (const idx of optionIndices!) {
        if (!Number.isInteger(idx) || idx < 0 || idx >= validOptions.length) {
          return { kind: 'invalid_option_indices' };
        }
      }
    } else {
      let optionStr: string;
      if (optionIndex !== undefined) {
        const opt = validOptions[optionIndex];
        if (opt === undefined) return { kind: 'invalid_option_index' };
        optionStr = opt;
      } else {
        optionStr = optionStrRaw as string;
      }

      if (!validOptions.includes(optionStr)) {
        const writeInCheck = validateWriteInText(optionStr, {
          allowWriteIn,
          writeInMaxLength,
          writeInBlocklist,
          writeInProfanityFilter,
        });
        if (!writeInCheck.ok) {
          return { kind: 'invalid_write_in', code: writeInCheck.code, message: writeInCheck.message };
        }
      }
      singleOptionLabel = optionStr;
    }

    if (Date.now() > Number.parseInt(String(poll.get('expiration')), 10)) {
      return { kind: 'poll_expired' };
    }

    if (chatChannelId) {
      const perChannelMax = appEnv.chatChannelVoteMaxPerMin;
      const c = await countRecentVotesForChatChannel({ pollId: resolvedPollId, chatChannelId });
      if (c >= perChannelMax) return { kind: 'channel_rate_limited', perChannelMax };
    }

    if (commandIdempotencyKey) {
      if (selectionMode === 'multi') {
        const existingAll = await findVotesByIdempotencyKey({
          pollId: resolvedPollId,
          commandIdempotencyKey,
        });
        if (existingAll.length > 0) {
          return {
            kind: 'idempotent_replay',
            vote: existingAll[0],
            ballotVotes: existingAll,
          };
        }
      } else {
        const existing = await findVoteByIdempotencyKey({
          pollId: resolvedPollId,
          commandIdempotencyKey,
        });
        if (existing) return { kind: 'idempotent_replay', vote: existing };
      }
    }

    const limitIp = !!poll.get('limit_ip');
    const ipBallotBaseId = `${req.ip}-${resolvedPollId}`;
    if (voteEligibility === 'account' && signedInUserId != null) {
      const priorUser = await countVotesByPollAndUser({
        pollId: resolvedPollId,
        userId: signedInUserId,
      });
      if (priorUser > 0) return { kind: 'duplicate_vote' };
    } else if (limitIp) {
      const prior = await countLimitIpBallotsForPoll({ pollId: resolvedPollId, baseId: ipBallotBaseId });
      if (prior > 0) return { kind: 'duplicate_vote' };
    }

    const creatorOwnerId =
      typeof creatorUserId === 'number' && Number.isFinite(creatorUserId) && creatorUserId > 0
        ? creatorUserId
        : null;
    const incomingVoteRows = selectionMode === 'multi' ? optionIndices!.length : 1;
    const voteMonthQuota = await checkMonthlyVoteQuotaForCreator({
      creatorUserId: creatorOwnerId,
      pollId: resolvedPollId,
      incomingVoteRows,
    });
    if (!voteMonthQuota.ok) {
      return {
        kind: 'usage_limit_votes_month',
        max: voteMonthQuota.max,
        current: voteMonthQuota.current,
        plan: voteMonthQuota.plan,
        incoming: voteMonthQuota.incoming,
      };
    }

    const voteGeoEnabled = await getVoteGeoEnabled();
    const lat = voteGeoEnabled ? quantizeCoordinate(location?.latitude, -90, 90) : null;
    const lon = voteGeoEnabled ? quantizeCoordinate(location?.longitude, -180, 180) : null;

    if (selectionMode === 'multi') {
      const indices = [...optionIndices!].sort((a, b) => a - b);
      const votes = await db.transaction(async (transaction) => {
        const created: unknown[] = [];
        for (const idx of indices) {
          const optionStr = validOptions[idx];
          const id = limitIp ? `${ipBallotBaseId}-${idx}` : randomId(16);
          const row = await createVoteRowInTransaction(
            {
              id,
              pollId: resolvedPollId,
              option: optionStr,
              weight: 1,
              sourceIpHash,
              userId: req.user?.id ?? null,
              commandIdempotencyKey,
              chatChannelId,
              isQuarantined: shouldQuarantine,
              quarantineReason,
              quarantineStatus: shouldQuarantine ? 'pending' : null,
              trustRiskScore: shouldQuarantine ? trustRiskScore : null,
              vote_latitude: lat,
              vote_longitude: lon,
            },
            transaction,
          );
          created.push(row);
        }
        return created;
      });

      notifyPollLive(resolvedPollId, { type: 'update' });
      queuePollWebhook(resolvedPollId, 'vote', {
        selection_mode: 'multi',
        option_indices: indices,
        options: indices.map((i) => validOptions[i]),
        weight: 1,
        chat_channel_id: chatChannelId,
        idempotency_key: commandIdempotencyKey,
      });

      return {
        kind: 'ok',
        vote: votes[0],
        ballotVotes: votes,
        optionIndices: indices,
        ...(shouldQuarantine
          ? {
              moderation: {
                quarantined: true as const,
                reason: quarantineReason,
                trust_risk_score: trustRiskScore,
              },
            }
          : {}),
      };
    }

    const optionStr = singleOptionLabel as string;

    const id = limitIp ? ipBallotBaseId : randomId(16);
    const vote = await createVoteRow({
      id,
      pollId: resolvedPollId,
      option: optionStr,
      weight: boostWeight,
      sourceIpHash,
      userId: req.user?.id ?? null,
      commandIdempotencyKey,
      chatChannelId,
      isQuarantined: shouldQuarantine,
      quarantineReason,
      quarantineStatus: shouldQuarantine ? 'pending' : null,
      trustRiskScore: shouldQuarantine ? trustRiskScore : null,
      vote_latitude: lat,
      vote_longitude: lon,
    });

    notifyPollLive(resolvedPollId, { type: 'update' });
    queuePollWebhook(resolvedPollId, 'vote', {
      option: optionStr,
      weight: boostWeight,
      chat_channel_id: chatChannelId,
      idempotency_key: commandIdempotencyKey,
    });

    return {
      kind: 'ok',
      vote,
      ...(shouldQuarantine
        ? {
            moderation: {
              quarantined: true as const,
              reason: quarantineReason,
              trust_risk_score: trustRiskScore,
            },
          }
        : {}),
    };
  } catch (err: unknown) {
    if (isPostgresUniqueViolation(err)) return { kind: 'duplicate_vote' };
    throw err;
  }
}
