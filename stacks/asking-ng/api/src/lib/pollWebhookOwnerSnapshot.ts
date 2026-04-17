import { QueryTypes } from 'sequelize';
import db from '../connections';
import { computePollWebhookPublicDelayWindow } from './pollWebhookDelayWindow';
import { trustChatBurstOwnerSummary, trustIpBurstOwnerSummary } from './trustStackSignals';

type PollRateCountersRow = {
  votes_last_1m: string | number;
  unique_ip_hashes_last_1m: string | number;
  unique_accounts_last_1m: string | number;
  top_ip_votes_last_1m: string | number;
  quarantined_votes_pending: string | number;
  quarantined_votes_pending_account_linked: string | number;
  votes_account_linked_last_24h: string | number;
  votes_anonymous_last_24h: string | number;
};

type PollDelayedPendingRow = { delayed_votes_pending: string | number };

/**
 * Owner-style moderation / rate counters (same SQL shape as owner `GET /poll/:id` metrics).
 * Sensitive: send only to webhook URLs the poll owner trusts (HMAC secret); opt-in per `webhook_targets[].include_owner_snapshot`.
 */
export async function fetchPollWebhookOwnerSnapshot(args: {
  pollId: string;
  poll: { get(key: string): unknown };
}): Promise<Record<string, unknown>> {
  const { pollId, poll } = args;
  const delay = computePollWebhookPublicDelayWindow(poll);

  const [rateCountersRow] = (await db.query(
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
      ), 0)::int AS top_ip_votes_last_1m,
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
  )) as PollRateCountersRow[];

  let delayedVotesPending = 0;
  if (delay.liveResultsAreDelayed) {
    const [delayedPendingRow] = (await db.query(
      `SELECT COUNT(*)::int AS delayed_votes_pending
       FROM votes
       WHERE "pollId" = :pollId
         AND COALESCE("isQuarantined", false) = false
         AND "createdAt" > :resultsVisibleThrough`,
      {
        replacements: { pollId, resultsVisibleThrough: delay.resultsVisibleThroughIso },
        type: QueryTypes.SELECT,
      },
    )) as PollDelayedPendingRow[];
    delayedVotesPending = Number(delayedPendingRow?.delayed_votes_pending ?? 0) || 0;
  }

  return {
    captured_at_ms: delay.now,
    effective_phase: delay.effectivePhase,
    results_delay_applied: delay.liveResultsAreDelayed,
    moderation_counters: {
      votes_last_1m: Number(rateCountersRow?.votes_last_1m ?? 0) || 0,
      unique_ip_hashes_last_1m: Number(rateCountersRow?.unique_ip_hashes_last_1m ?? 0) || 0,
      unique_accounts_last_1m: Number(rateCountersRow?.unique_accounts_last_1m ?? 0) || 0,
      top_ip_votes_last_1m: Number(rateCountersRow?.top_ip_votes_last_1m ?? 0) || 0,
      quarantined_votes_pending: Number(rateCountersRow?.quarantined_votes_pending ?? 0) || 0,
      quarantined_votes_pending_account_linked:
        Number(rateCountersRow?.quarantined_votes_pending_account_linked ?? 0) || 0,
      votes_account_linked_last_24h:
        Number(rateCountersRow?.votes_account_linked_last_24h ?? 0) || 0,
      votes_anonymous_last_24h: Number(rateCountersRow?.votes_anonymous_last_24h ?? 0) || 0,
      trust_ip_burst: trustIpBurstOwnerSummary(),
      trust_chat_burst: trustChatBurstOwnerSummary(),
    },
    delayed_votes_pending: delayedVotesPending,
  };
}
