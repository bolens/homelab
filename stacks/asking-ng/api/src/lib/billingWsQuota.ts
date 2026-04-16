import { findBillingPlanAndRoleByUserId } from '../controller/self/self.repository';
import { maxWsSubscribersPerPollForBillingPlan } from './billingLimits';
import { appEnv } from './env';

/**
 * Effective cap for the poll-live WebSocket room: always bounded by {@link appEnv.wsMaxSubscribersPerPoll}.
 * When {@link appEnv.billingEnforceLimits} is on, also bounded by the poll owner's plan (orphan polls use `free`).
 */
export async function resolveEffectivePollLiveRoomCap(
  creatorUserId: number | null | undefined,
): Promise<number> {
  const envCap = appEnv.wsMaxSubscribersPerPoll;
  if (!appEnv.billingEnforceLimits) return envCap;

  const uid =
    typeof creatorUserId === 'number' && Number.isFinite(creatorUserId) && creatorUserId > 0
      ? creatorUserId
      : null;

  if (uid == null) {
    return Math.min(envCap, maxWsSubscribersPerPollForBillingPlan('free'));
  }

  const { billingPlan, role } = await findBillingPlanAndRoleByUserId(uid);
  if (role === 'superadmin') return envCap;

  const tierMax = maxWsSubscribersPerPollForBillingPlan(billingPlan);
  if (tierMax >= Number.MAX_SAFE_INTEGER / 2) return envCap;
  return Math.min(envCap, tierMax);
}
