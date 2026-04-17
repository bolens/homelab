import { countBillableVotesForCreatorUtcMonth } from '../controller/poll/voteOnPoll.repository';
import { findBillingPlanAndRoleForVoteQuota } from '../controller/self/self.repository';
import { maxVotesPerMonthForBillingPlan, utcCalendarMonthBounds } from './billingLimits';
import { appEnv } from './env';

export type MonthlyVoteQuotaDenied = {
  ok: false;
  max: number;
  current: number;
  plan: string;
  incoming: number;
};
export type MonthlyVoteQuotaOk = { ok: true };

/**
 * When {@link appEnv.billingEnforceLimits} is on, blocks new vote rows if the poll owner's workspace
 * would exceed the monthly non-quarantined vote cap for their billing plan (UTC calendar month).
 */
export async function checkMonthlyVoteQuotaForCreator(args: {
  creatorUserId: number | null;
  /** When set, plan tier is taken from this poll’s `workspace_id` (if present), not only the creator’s default workspace. */
  pollId?: string | null;
  incomingVoteRows: number;
}): Promise<MonthlyVoteQuotaOk | MonthlyVoteQuotaDenied> {
  if (!appEnv.billingEnforceLimits) return { ok: true };
  const uid = args.creatorUserId;
  if (uid == null) return { ok: true };
  const incoming = Math.max(0, Math.floor(args.incomingVoteRows));
  if (incoming < 1) return { ok: true };

  const { billingPlan, role } = await findBillingPlanAndRoleForVoteQuota({
    pollId: args.pollId,
    creatorUserId: uid,
  });
  if (role === 'superadmin') return { ok: true };

  const maxVotes = maxVotesPerMonthForBillingPlan(billingPlan);
  if (maxVotes >= Number.MAX_SAFE_INTEGER / 2) return { ok: true };

  const { start, endExclusive } = utcCalendarMonthBounds();
  const current = await countBillableVotesForCreatorUtcMonth({
    creatorUserId: uid,
    monthStart: start,
    monthEndExclusive: endExclusive,
  });
  if (current + incoming > maxVotes) {
    return { ok: false, max: maxVotes, current, plan: billingPlan, incoming };
  }
  return { ok: true };
}
