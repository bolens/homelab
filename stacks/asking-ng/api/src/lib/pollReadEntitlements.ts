import { findBillingPlanAndRoleForVoteQuota } from '../controller/self/self.repository';
import { hasForensicReplayForBillingPlan, hasVoteHeatmapForBillingPlan } from './billingLimits';
import { appEnv } from './env';
import { selfhostProLicenseExpiredDetailsForPlan } from './selfhostProLicense';

export type PollReadPremiumFeature = 'forensic_replay' | 'vote_heatmap';

export type PollReadEntitlementBlock =
  | {
      kind: 'billing_license_expired';
      details: ReturnType<typeof selfhostProLicenseExpiredDetailsForPlan> extends infer T
        ? Exclude<T, null>
        : never;
    }
  | {
      kind: 'plan_limit_forensic';
      plan: string;
      requiredPlan: 'cloud-team';
    }
  | {
      kind: 'plan_limit_heatmap';
      plan: string;
      requiredPlan: 'cloud-team';
    };

export async function checkPollReadEntitlements(args: {
  pollId: string;
  ownerUserId: number | null | undefined;
  feature: PollReadPremiumFeature;
}): Promise<PollReadEntitlementBlock | null> {
  if (!appEnv.billingEnforceLimits) return null;
  const ownerUserId =
    args.ownerUserId != null && Number.isFinite(Number(args.ownerUserId)) && Number(args.ownerUserId) > 0
      ? Number(args.ownerUserId)
      : null;
  const { billingPlan, role } =
    ownerUserId != null
      ? await findBillingPlanAndRoleForVoteQuota({ pollId: args.pollId, creatorUserId: ownerUserId })
      : { billingPlan: 'free', role: null };
  const licenseExpired = role !== 'superadmin' ? selfhostProLicenseExpiredDetailsForPlan(billingPlan) : null;
  if (licenseExpired) {
    return { kind: 'billing_license_expired', details: licenseExpired };
  }
  if (args.feature === 'forensic_replay' && role !== 'superadmin' && !hasForensicReplayForBillingPlan(billingPlan)) {
    return { kind: 'plan_limit_forensic', plan: billingPlan, requiredPlan: 'cloud-team' };
  }
  if (args.feature === 'vote_heatmap' && role !== 'superadmin' && !hasVoteHeatmapForBillingPlan(billingPlan)) {
    return { kind: 'plan_limit_heatmap', plan: billingPlan, requiredPlan: 'cloud-team' };
  }
  return null;
}
