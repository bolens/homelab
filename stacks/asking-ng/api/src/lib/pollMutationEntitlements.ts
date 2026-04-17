import { findBillingPlanAndRoleByUserId } from '../controller/self/self.repository';
import { hasExtendedRetentionForBillingPlan, hasWebhookAutomationForBillingPlan } from './billingLimits';
import { appEnv } from './env';
import { selfhostProLicenseExpiredDetailsForPlan } from './selfhostProLicense';

export type PollMutationEntitlementBlock =
  | {
      kind: 'billing_license_expired';
      details: ReturnType<typeof selfhostProLicenseExpiredDetailsForPlan> extends infer T
        ? Exclude<T, null>
        : never;
    }
  | {
      kind: 'plan_limit_automation';
      plan: string;
      requiredPlan: 'cloud-team';
    }
  | {
      kind: 'plan_limit_retention';
      plan: string;
      requiredPlan: 'cloud-team';
    };

export async function checkPollMutationEntitlements(args: {
  ownerUserId: number | null | undefined;
  requiresAutomation: boolean;
  requiresRetention: boolean;
}): Promise<PollMutationEntitlementBlock | null> {
  if (!appEnv.billingEnforceLimits || (!args.requiresAutomation && !args.requiresRetention)) return null;
  const ownerUserId =
    args.ownerUserId != null && Number.isFinite(Number(args.ownerUserId)) && Number(args.ownerUserId) > 0
      ? Number(args.ownerUserId)
      : null;
  const { billingPlan, role } =
    ownerUserId != null
      ? await findBillingPlanAndRoleByUserId(ownerUserId)
      : { billingPlan: 'free', role: null };
  const licenseExpired = role !== 'superadmin' ? selfhostProLicenseExpiredDetailsForPlan(billingPlan) : null;
  if (licenseExpired) {
    return { kind: 'billing_license_expired', details: licenseExpired };
  }
  if (args.requiresAutomation && role !== 'superadmin' && !hasWebhookAutomationForBillingPlan(billingPlan)) {
    return { kind: 'plan_limit_automation', plan: billingPlan, requiredPlan: 'cloud-team' };
  }
  if (args.requiresRetention && role !== 'superadmin' && !hasExtendedRetentionForBillingPlan(billingPlan)) {
    return { kind: 'plan_limit_retention', plan: billingPlan, requiredPlan: 'cloud-team' };
  }
  return null;
}
