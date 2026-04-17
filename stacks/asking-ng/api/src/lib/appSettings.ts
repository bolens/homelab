import AppSetting from '../models/appsettings.sequelize';
import { appEnv } from './env';

const SIGNUPS_ENABLED_KEY = 'signups_enabled';
const VOTE_GEO_ENABLED_KEY = 'vote_geo_enabled';
const POLL_RETENTION_TTL_DAYS_DEFAULT_KEY = 'poll_retention_ttl_days_default';
const POLL_RETENTION_SWEEP_INTERVAL_SEC_KEY = 'poll_retention_sweep_interval_sec';
const POLL_RETENTION_SWEEP_BATCH_SIZE_KEY = 'poll_retention_sweep_batch_size';
const AUDIT_LOG_RETENTION_DAYS_KEY = 'audit_log_retention_days';
const MODERATION_REJECTED_VOTE_RETENTION_DAYS_KEY = 'moderation_rejected_vote_retention_days';
const AUDIT_LOG_RETENTION_LEGAL_HOLD_KEY = 'audit_log_retention_legal_hold';
const MODERATION_REJECTED_VOTE_RETENTION_LEGAL_HOLD_KEY =
  'moderation_rejected_vote_retention_legal_hold';

/** When the row is missing (e.g. mid-migration), signups stay allowed so existing installs are not locked out. */
export async function getSignupsEnabled(): Promise<boolean> {
  const row = await AppSetting.findByPk(SIGNUPS_ENABLED_KEY);
  if (!row) return true;
  return (row.get('value') as string) === 'true';
}

export async function setSignupsEnabled(enabled: boolean): Promise<void> {
  const now = new Date();
  await AppSetting.upsert({
    key: SIGNUPS_ENABLED_KEY,
    value: enabled ? 'true' : 'false',
    updatedAt: now,
  });
}

/** Missing row defaults to enabled for backward-compatible rollout. */
export async function getVoteGeoEnabled(): Promise<boolean> {
  const row = await AppSetting.findByPk(VOTE_GEO_ENABLED_KEY);
  if (!row) return true;
  return (row.get('value') as string) === 'true';
}

export async function setVoteGeoEnabled(enabled: boolean): Promise<void> {
  const now = new Date();
  await AppSetting.upsert({
    key: VOTE_GEO_ENABLED_KEY,
    value: enabled ? 'true' : 'false',
    updatedAt: now,
  });
}

function parseClampedInt(raw: unknown, min: number, max: number): number | null {
  const n =
    typeof raw === 'number'
      ? raw
      : typeof raw === 'string'
        ? Number.parseInt(raw.trim(), 10)
        : Number.NaN;
  if (!Number.isFinite(n)) return null;
  return Math.max(min, Math.min(max, Math.floor(n)));
}

async function getNumericAppSetting(key: string): Promise<number | null> {
  const row = await AppSetting.findByPk(key);
  if (!row) return null;
  return parseClampedInt(row.get('value'), 0, 1_000_000);
}

async function upsertNumericAppSetting(key: string, value: number): Promise<void> {
  const now = new Date();
  await AppSetting.upsert({
    key,
    value: String(value),
    updatedAt: now,
  });
}

async function getBoolAppSetting(key: string): Promise<boolean | null> {
  const row = await AppSetting.findByPk(key);
  if (!row) return null;
  const raw = String(row.get('value') ?? '')
    .trim()
    .toLowerCase();
  if (raw === 'true' || raw === '1' || raw === 'yes') return true;
  if (raw === 'false' || raw === '0' || raw === 'no') return false;
  return null;
}

async function upsertBoolAppSetting(key: string, value: boolean): Promise<void> {
  const now = new Date();
  await AppSetting.upsert({
    key,
    value: value ? 'true' : 'false',
    updatedAt: now,
  });
}

export type RetentionPolicySettings = {
  poll_retention_ttl_days_default: number;
  poll_retention_sweep_interval_sec: number;
  poll_retention_sweep_batch_size: number;
  audit_log_retention_days: number;
  moderation_rejected_vote_retention_days: number;
  audit_log_retention_legal_hold: boolean;
  moderation_rejected_vote_retention_legal_hold: boolean;
};

export async function getRetentionPolicySettings(): Promise<RetentionPolicySettings> {
  const ttlRaw = await getNumericAppSetting(POLL_RETENTION_TTL_DAYS_DEFAULT_KEY);
  const intervalRaw = await getNumericAppSetting(POLL_RETENTION_SWEEP_INTERVAL_SEC_KEY);
  const batchRaw = await getNumericAppSetting(POLL_RETENTION_SWEEP_BATCH_SIZE_KEY);
  const auditRaw = await getNumericAppSetting(AUDIT_LOG_RETENTION_DAYS_KEY);
  const rejectedRaw = await getNumericAppSetting(MODERATION_REJECTED_VOTE_RETENTION_DAYS_KEY);
  const auditHold = await getBoolAppSetting(AUDIT_LOG_RETENTION_LEGAL_HOLD_KEY);
  const rejectedHold = await getBoolAppSetting(MODERATION_REJECTED_VOTE_RETENTION_LEGAL_HOLD_KEY);
  return {
    poll_retention_ttl_days_default:
      ttlRaw == null ? appEnv.pollRetentionTtlDaysDefault : Math.max(0, Math.min(3650, ttlRaw)),
    poll_retention_sweep_interval_sec:
      intervalRaw == null
        ? appEnv.pollRetentionSweepIntervalSec
        : Math.max(30, Math.min(86_400, intervalRaw)),
    poll_retention_sweep_batch_size:
      batchRaw == null
        ? appEnv.pollRetentionSweepBatchSize
        : Math.max(10, Math.min(5_000, batchRaw)),
    audit_log_retention_days:
      auditRaw == null ? appEnv.auditLogRetentionDays : Math.max(0, Math.min(3650, auditRaw)),
    moderation_rejected_vote_retention_days:
      rejectedRaw == null
        ? appEnv.moderationRejectedVoteRetentionDays
        : Math.max(0, Math.min(3650, rejectedRaw)),
    audit_log_retention_legal_hold: auditHold === true,
    moderation_rejected_vote_retention_legal_hold: rejectedHold === true,
  };
}

export async function setRetentionPolicySettings(next: RetentionPolicySettings): Promise<void> {
  await upsertNumericAppSetting(
    POLL_RETENTION_TTL_DAYS_DEFAULT_KEY,
    Math.max(0, Math.min(3650, Math.floor(next.poll_retention_ttl_days_default))),
  );
  await upsertNumericAppSetting(
    POLL_RETENTION_SWEEP_INTERVAL_SEC_KEY,
    Math.max(30, Math.min(86_400, Math.floor(next.poll_retention_sweep_interval_sec))),
  );
  await upsertNumericAppSetting(
    POLL_RETENTION_SWEEP_BATCH_SIZE_KEY,
    Math.max(10, Math.min(5_000, Math.floor(next.poll_retention_sweep_batch_size))),
  );
  await upsertNumericAppSetting(
    AUDIT_LOG_RETENTION_DAYS_KEY,
    Math.max(0, Math.min(3650, Math.floor(next.audit_log_retention_days))),
  );
  await upsertNumericAppSetting(
    MODERATION_REJECTED_VOTE_RETENTION_DAYS_KEY,
    Math.max(0, Math.min(3650, Math.floor(next.moderation_rejected_vote_retention_days))),
  );
  await upsertBoolAppSetting(
    AUDIT_LOG_RETENTION_LEGAL_HOLD_KEY,
    next.audit_log_retention_legal_hold === true,
  );
  await upsertBoolAppSetting(
    MODERATION_REJECTED_VOTE_RETENTION_LEGAL_HOLD_KEY,
    next.moderation_rejected_vote_retention_legal_hold === true,
  );
}
