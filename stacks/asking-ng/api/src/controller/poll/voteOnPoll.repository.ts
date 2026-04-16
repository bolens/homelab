import { QueryTypes } from 'sequelize';
import type { Transaction } from 'sequelize';
import db from '../../connections';
import Poll from '../../model/Poll';
import Vote from '../../model/Vote';

export async function findPollByIdOrSlug(pollId: string) {
  let poll = await Poll.findByPk(pollId);
  if (!poll) {
    poll = await Poll.findOne({ where: { vanitySlug: pollId.trim().toLowerCase() } });
  }
  return poll;
}

export async function countRecentVotesForSourceIp(args: {
  pollId: string;
  sourceIpHash: string;
}): Promise<number> {
  const [r] = (await db.query(
    `SELECT COUNT(*)::int AS c
     FROM votes
     WHERE "pollId" = :pollId
       AND "sourceIpHash" = :sourceIpHash
       AND "createdAt" >= NOW() - INTERVAL '1 minute'`,
    {
      replacements: { pollId: args.pollId, sourceIpHash: args.sourceIpHash },
      type: QueryTypes.SELECT,
    },
  )) as Array<{ c: string | number }>;
  return Number(r?.c ?? 0) || 0;
}

/** Votes in the rolling window from the same hashed IP (trust / burst detection). */
export async function countRecentVotesForSourceIpWindowSeconds(args: {
  pollId: string;
  sourceIpHash: string;
  windowSec: number;
}): Promise<number> {
  const windowSec = Math.max(1, Math.min(600, Math.floor(args.windowSec)));
  const [r] = (await db.query(
    `SELECT COUNT(*)::int AS c
     FROM votes
     WHERE "pollId" = :pollId
       AND "sourceIpHash" = :sourceIpHash
       AND "createdAt" >= NOW() - (INTERVAL '1 second' * :windowSec)`,
    {
      replacements: { pollId: args.pollId, sourceIpHash: args.sourceIpHash, windowSec },
      type: QueryTypes.SELECT,
    },
  )) as Array<{ c: string | number }>;
  return Number(r?.c ?? 0) || 0;
}

export async function countRecentVotesForChatChannel(args: {
  pollId: string;
  chatChannelId: string;
}): Promise<number> {
  const [r] = (await db.query(
    `SELECT COUNT(*)::int AS c
     FROM votes
     WHERE "pollId" = :pollId
       AND "chatChannelId" = :chatChannelId
       AND "createdAt" >= NOW() - INTERVAL '1 minute'`,
    {
      replacements: { pollId: args.pollId, chatChannelId: args.chatChannelId },
      type: QueryTypes.SELECT,
    },
  )) as Array<{ c: string | number }>;
  return Number(r?.c ?? 0) || 0;
}

/** Votes in the rolling window for the same chat channel id (trust / burst detection). */
export async function countRecentVotesForChatChannelWindowSeconds(args: {
  pollId: string;
  chatChannelId: string;
  windowSec: number;
}): Promise<number> {
  const windowSec = Math.max(1, Math.min(600, Math.floor(args.windowSec)));
  const [r] = (await db.query(
    `SELECT COUNT(*)::int AS c
     FROM votes
     WHERE "pollId" = :pollId
       AND "chatChannelId" = :chatChannelId
       AND "createdAt" >= NOW() - (INTERVAL '1 second' * :windowSec)`,
    {
      replacements: { pollId: args.pollId, chatChannelId: args.chatChannelId, windowSec },
      type: QueryTypes.SELECT,
    },
  )) as Array<{ c: string | number }>;
  return Number(r?.c ?? 0) || 0;
}

export async function findVoteByIdempotencyKey(args: {
  pollId: string;
  commandIdempotencyKey: string;
}) {
  return Vote.findOne({
    where: { pollId: args.pollId, commandIdempotencyKey: args.commandIdempotencyKey },
  });
}

export async function findVotesByIdempotencyKey(args: {
  pollId: string;
  commandIdempotencyKey: string;
}) {
  return Vote.findAll({
    where: { pollId: args.pollId, commandIdempotencyKey: args.commandIdempotencyKey },
    order: [['createdAt', 'ASC']],
  });
}

/** limit_ip ballots use id `baseId` (single) or `baseId-<optionIndex>` (multi). */
export async function countVotesByPollAndUser(args: { pollId: string; userId: number }): Promise<number> {
  const [r] = (await db.query(
    `SELECT COUNT(*)::int AS c
     FROM votes
     WHERE "pollId" = :pollId
       AND "userId" = :userId`,
    {
      replacements: { pollId: args.pollId, userId: args.userId },
      type: QueryTypes.SELECT,
    },
  )) as Array<{ c: string | number }>;
  return Number(r?.c ?? 0) || 0;
}

export async function countLimitIpBallotsForPoll(args: { pollId: string; baseId: string }): Promise<number> {
  const [r] = (await db.query(
    `SELECT COUNT(*)::int AS c
     FROM votes
     WHERE "pollId" = :pollId
       AND (id = :baseId OR id LIKE :prefix)`,
    {
      replacements: { pollId: args.pollId, baseId: args.baseId, prefix: `${args.baseId}-%` },
      type: QueryTypes.SELECT,
    },
  )) as Array<{ c: string | number }>;
  return Number(r?.c ?? 0) || 0;
}

/** Billable vote rows this UTC month for polls where `creator_user_id` matches (non-quarantined only). */
export async function countBillableVotesForCreatorUtcMonth(args: {
  creatorUserId: number;
  monthStart: Date;
  monthEndExclusive: Date;
}): Promise<number> {
  const [r] = (await db.query(
    `SELECT COUNT(*)::int AS c
     FROM votes v
     INNER JOIN polls p ON p.id = v."pollId"
     WHERE p."creatorUserId" = :creatorUserId
       AND v."createdAt" >= :monthStart
       AND v."createdAt" < :monthEndExclusive
       AND v."isQuarantined" = false`,
    {
      replacements: {
        creatorUserId: args.creatorUserId,
        monthStart: args.monthStart,
        monthEndExclusive: args.monthEndExclusive,
      },
      type: QueryTypes.SELECT,
    },
  )) as Array<{ c: string | number }>;
  return Number(r?.c ?? 0) || 0;
}

export async function createVoteRow(payload: Record<string, unknown>) {
  await db.sync();
  return Vote.create(payload);
}

export async function createVoteRowInTransaction(
  payload: Record<string, unknown>,
  transaction: Transaction,
) {
  return Vote.create(payload, { transaction });
}
