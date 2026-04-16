import { maxActivePollsForBillingPlan } from './billingLimits';
import { appEnv } from './env';
import { countNonArchivedPollsOwnedByUser, findBillingPlanByUserId } from '../controller/self/self.repository';

export type ActivePollQuotaDenied = { ok: false; max: number; current: number; plan: string };
export type ActivePollQuotaOk = { ok: true };

/**
 * When {@link appEnv.billingEnforceLimits} is on, blocks creating another non-archived poll
 * for the same creator once they reach the cap for their billing plan.
 */
export async function checkActivePollQuotaForUser(args: {
  creatorUserId: number | null;
  sessionUserRole?: string | null;
}): Promise<ActivePollQuotaOk | ActivePollQuotaDenied> {
  if (!appEnv.billingEnforceLimits) return { ok: true };
  const uid = args.creatorUserId;
  if (uid == null) return { ok: true };
  if (args.sessionUserRole === 'superadmin') return { ok: true };
  const plan = await findBillingPlanByUserId(uid);
  const maxPolls = maxActivePollsForBillingPlan(plan);
  const current = await countNonArchivedPollsOwnedByUser(uid);
  if (current >= maxPolls) {
    return { ok: false, max: maxPolls, current, plan };
  }
  return { ok: true };
}
