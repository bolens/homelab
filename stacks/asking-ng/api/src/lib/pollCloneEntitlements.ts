import { findBillingPlanAndRoleForVoteQuota } from '../controller/self/self.repository';
import {
  hasExtendedRetentionForBillingPlan,
  hasWebhookAutomationForBillingPlan,
} from './billingLimits';
import { appEnv } from './env';
import { selfhostProLicenseExpiredDetailsForPlan } from './selfhostProLicense';

type PollLike = { get(key: string): unknown };

export type NormalizedClonePremiumFields = {
  webhookTargets: Array<{
    url: string;
    secret: string;
    hint_locale?: 'en' | 'en-gb' | 'es';
    include_results_snapshot?: boolean;
    include_owner_snapshot?: boolean;
    include_owner_events?: boolean;
  }>;
  retentionTtlDays: number | null;
  retentionLegalHold: boolean;
};

export type ClonePremiumEntitlementBlock =
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

export function normalizeClonePremiumFields(source: PollLike): NormalizedClonePremiumFields {
  const webhookTargets = (
    (source.get('webhookTargets') as
      | Array<{
          url?: string;
          secret?: string;
          hint_locale?: unknown;
          include_results_snapshot?: unknown;
          include_owner_snapshot?: unknown;
          include_owner_events?: unknown;
        }>
      | null
      | undefined) ?? []
  )
    .filter(
      (
        t,
      ): t is {
        url: string;
        secret: string;
        hint_locale?: unknown;
        include_results_snapshot?: unknown;
        include_owner_snapshot?: unknown;
        include_owner_events?: unknown;
      } =>
        typeof t?.url === 'string' &&
        t.url.trim() !== '' &&
        typeof t?.secret === 'string' &&
        t.secret.trim() !== '',
    )
    .map((t) => {
      const base: {
        url: string;
        secret: string;
        hint_locale?: 'en' | 'en-gb' | 'es';
        include_results_snapshot?: boolean;
        include_owner_snapshot?: boolean;
        include_owner_events?: boolean;
      } = { url: t.url.trim(), secret: t.secret.trim() };
      const hl = typeof t.hint_locale === 'string' ? t.hint_locale.trim().toLowerCase() : '';
      if (hl === 'en' || hl === 'en-gb' || hl === 'es')
        base.hint_locale = hl as 'en' | 'en-gb' | 'es';
      if (t.include_results_snapshot === true) base.include_results_snapshot = true;
      if (t.include_owner_snapshot === true) base.include_owner_snapshot = true;
      if (t.include_owner_events === true) base.include_owner_events = true;
      return base;
    });

  return {
    webhookTargets,
    retentionTtlDays: (source.get('retentionTtlDays') as number | null | undefined) ?? null,
    retentionLegalHold: source.get('retentionLegalHold') === true,
  };
}

export async function checkClonePremiumEntitlements(args: {
  pollId: string;
  ownerId: number | null | undefined;
  source: PollLike;
}): Promise<ClonePremiumEntitlementBlock | null> {
  const premiumFields = normalizeClonePremiumFields(args.source);
  const cloneNeedsAutomationEntitlement = premiumFields.webhookTargets.length > 0;
  const cloneNeedsRetentionEntitlement =
    premiumFields.retentionTtlDays != null || premiumFields.retentionLegalHold;
  if (
    !appEnv.billingEnforceLimits ||
    (!cloneNeedsAutomationEntitlement && !cloneNeedsRetentionEntitlement)
  ) {
    return null;
  }

  const ownerUserId =
    args.ownerId != null && Number.isFinite(Number(args.ownerId)) ? Number(args.ownerId) : null;
  const { billingPlan, role } =
    ownerUserId != null
      ? await findBillingPlanAndRoleForVoteQuota({
          pollId: args.pollId,
          creatorUserId: ownerUserId,
        })
      : { billingPlan: 'free', role: null };
  const licenseExpired =
    role !== 'superadmin' ? selfhostProLicenseExpiredDetailsForPlan(billingPlan) : null;
  if (licenseExpired) {
    return { kind: 'billing_license_expired', details: licenseExpired };
  }

  if (
    cloneNeedsAutomationEntitlement &&
    role !== 'superadmin' &&
    !hasWebhookAutomationForBillingPlan(billingPlan)
  ) {
    return { kind: 'plan_limit_automation', plan: billingPlan, requiredPlan: 'cloud-team' };
  }
  if (
    cloneNeedsRetentionEntitlement &&
    role !== 'superadmin' &&
    !hasExtendedRetentionForBillingPlan(billingPlan)
  ) {
    return { kind: 'plan_limit_retention', plan: billingPlan, requiredPlan: 'cloud-team' };
  }
  return null;
}
