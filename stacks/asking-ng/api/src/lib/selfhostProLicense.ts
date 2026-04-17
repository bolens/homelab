import { appEnv } from './env';

export type SelfhostProLicenseStatus = 'unknown' | 'active' | 'grace' | 'expired';

export type SelfhostProLicenseState = {
  status: SelfhostProLicenseStatus;
  validUntilMs: number | null;
  lastVerifiedMs: number | null;
  graceUntilMs: number | null;
};

export type SelfhostProLicenseExpiredDetails = {
  plan: 'selfhost-pro';
  license_status: 'expired';
  license_valid_until_ms: number | null;
  license_last_verified_ms: number | null;
  license_grace_until_ms: number | null;
  upgrade_hint: string;
};

export const BILLING_LICENSE_EXPIRED_CODE = 'BILLING_LICENSE_EXPIRED' as const;
export const BILLING_LICENSE_EXPIRED_MESSAGE =
  'Self-host Pro license is expired for premium feature use.' as const;

function normalizePositiveMs(value: number): number | null {
  return Number.isFinite(value) && value > 0 ? Math.trunc(value) : null;
}

export function evaluateSelfhostProLicenseState(nowMs = Date.now()): SelfhostProLicenseState {
  const validUntilMs = normalizePositiveMs(appEnv.selfhostProLicenseValidUntilMs);
  const lastVerifiedMs = normalizePositiveMs(appEnv.selfhostProLicenseLastVerifiedMs);
  const graceMs = Math.max(0, Math.trunc(appEnv.selfhostProLicenseOfflineGraceHours)) * 60 * 60 * 1000;

  if (validUntilMs == null) {
    return {
      status: 'unknown',
      validUntilMs: null,
      lastVerifiedMs,
      graceUntilMs: null,
    };
  }
  if (nowMs <= validUntilMs) {
    return {
      status: 'active',
      validUntilMs,
      lastVerifiedMs,
      graceUntilMs: null,
    };
  }

  const graceUntilMs = lastVerifiedMs != null && graceMs > 0 ? lastVerifiedMs + graceMs : null;
  if (graceUntilMs != null && nowMs <= graceUntilMs) {
    return {
      status: 'grace',
      validUntilMs,
      lastVerifiedMs,
      graceUntilMs,
    };
  }
  return {
    status: 'expired',
    validUntilMs,
    lastVerifiedMs,
    graceUntilMs,
  };
}

/**
 * Premium-only capabilities should block when a selfhost-pro license is expired.
 * Unknown/active/grace states remain allowed in phase-1 enforcement.
 */
export function selfhostProLicenseExpiredDetailsForPlan(
  billingPlan: string,
): SelfhostProLicenseExpiredDetails | null {
  if (billingPlan !== 'selfhost-pro') return null;
  const state = evaluateSelfhostProLicenseState();
  if (state.status !== 'expired') return null;
  return {
    plan: 'selfhost-pro',
    license_status: 'expired',
    license_valid_until_ms: state.validUntilMs,
    license_last_verified_ms: state.lastVerifiedMs,
    license_grace_until_ms: state.graceUntilMs,
    upgrade_hint: 'Self-host Pro license has expired. Renew license to continue premium features.',
  };
}
