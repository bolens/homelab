import { QueryTypes } from 'sequelize';
import db from '../connections';
import { getRetentionPolicySettings } from './appSettings';
import { appEnv } from './env';
import { logger } from './logger';

const DAY_MS = 24 * 60 * 60 * 1000;

type ExpiredPollRow = { id: string };
type IdRow = { id: string };

export async function sweepExpiredPollRetention(opts?: { nowMs?: number }): Promise<number> {
  const policy = await getRetentionPolicySettings();
  const defaultTtl = policy.poll_retention_ttl_days_default;
  if (defaultTtl <= 0) return 0;
  const nowMs = opts?.nowMs ?? Date.now();
  const batch = policy.poll_retention_sweep_batch_size;
  const expired = await db.query<ExpiredPollRow>(
    `SELECT id
     FROM polls
     WHERE expiration IS NOT NULL
       AND expiration > 0
       AND COALESCE("retentionLegalHold", false) = false
       AND (
         expiration + (
           COALESCE("retentionTtlDays", :defaultTtl) * :dayMs
         )
       ) <= :nowMs
     ORDER BY expiration ASC
     LIMIT :batch`,
    {
      replacements: { defaultTtl, dayMs: DAY_MS, nowMs, batch },
      type: QueryTypes.SELECT,
    },
  );
  if (!expired.length) return 0;
  const ids = expired.map((r) => r.id);
  await db.transaction(async (tx) => {
    await db.query(`DELETE FROM poll_phase_events WHERE "pollId" IN (:ids)`, {
      replacements: { ids },
      type: QueryTypes.DELETE,
      transaction: tx,
    });
    await db.query(`DELETE FROM votes WHERE "pollId" IN (:ids)`, {
      replacements: { ids },
      type: QueryTypes.DELETE,
      transaction: tx,
    });
    await db.query(`DELETE FROM polls WHERE id IN (:ids)`, {
      replacements: { ids },
      type: QueryTypes.DELETE,
      transaction: tx,
    });
  });
  logger.info(
    { event: 'poll.retention.auto_delete', deletedCount: ids.length },
    'deleted expired polls by retention policy',
  );
  return ids.length;
}

export async function sweepExpiredAuditLogs(opts?: { nowMs?: number }): Promise<number> {
  const policy = await getRetentionPolicySettings();
  if (policy.audit_log_retention_legal_hold) return 0;
  const days = policy.audit_log_retention_days;
  if (days <= 0) return 0;
  const nowMs = opts?.nowMs ?? Date.now();
  const cutoffIso = new Date(nowMs - days * DAY_MS).toISOString();
  const batch = policy.poll_retention_sweep_batch_size;
  const rows = await db.query<IdRow>(
    `SELECT id
     FROM audit_logs
     WHERE "createdAt" <= :cutoffIso
     ORDER BY "createdAt" ASC
     LIMIT :batch`,
    { replacements: { cutoffIso, batch }, type: QueryTypes.SELECT },
  );
  if (!rows.length) return 0;
  const ids = rows.map((r) => r.id);
  await db.query(`DELETE FROM audit_logs WHERE id IN (:ids)`, {
    replacements: { ids },
    type: QueryTypes.DELETE,
  });
  logger.info(
    { event: 'poll.retention.audit_log_delete', deletedCount: ids.length },
    'deleted expired audit logs by retention policy',
  );
  return ids.length;
}

export async function sweepExpiredRejectedModerationVotes(opts?: {
  nowMs?: number;
}): Promise<number> {
  const policy = await getRetentionPolicySettings();
  if (policy.moderation_rejected_vote_retention_legal_hold) return 0;
  const days = policy.moderation_rejected_vote_retention_days;
  if (days <= 0) return 0;
  const nowMs = opts?.nowMs ?? Date.now();
  const cutoffIso = new Date(nowMs - days * DAY_MS).toISOString();
  const batch = policy.poll_retention_sweep_batch_size;
  const rows = await db.query<IdRow>(
    `SELECT id
     FROM votes
     WHERE COALESCE("isQuarantined", false) = true
       AND COALESCE("quarantineStatus", 'pending') = 'rejected'
       AND "quarantineDecidedAt" IS NOT NULL
       AND "quarantineDecidedAt" <= :cutoffIso
     ORDER BY "quarantineDecidedAt" ASC
     LIMIT :batch`,
    { replacements: { cutoffIso, batch }, type: QueryTypes.SELECT },
  );
  if (!rows.length) return 0;
  const ids = rows.map((r) => r.id);
  await db.query(`DELETE FROM votes WHERE id IN (:ids)`, {
    replacements: { ids },
    type: QueryTypes.DELETE,
  });
  logger.info(
    { event: 'poll.retention.rejected_vote_delete', deletedCount: ids.length },
    'deleted expired rejected moderation votes by retention policy',
  );
  return ids.length;
}

let retentionTimer: NodeJS.Timeout | undefined;
let retentionWorkerRunning = false;

export function startPollRetentionWorker(): void {
  if (retentionWorkerRunning) return;
  retentionWorkerRunning = true;
  const runOnce = async () => {
    try {
      await sweepExpiredPollRetention();
      await sweepExpiredAuditLogs();
      await sweepExpiredRejectedModerationVotes();
    } catch (err: unknown) {
      logger.error({ event: 'poll.retention.sweep_failed', err }, 'poll retention sweep failed');
    } finally {
      if (!retentionWorkerRunning) return;
      const policy = await getRetentionPolicySettings().catch(() => null);
      const intervalSec = Math.max(
        30,
        Math.min(
          86_400,
          Math.floor(
            policy?.poll_retention_sweep_interval_sec ?? appEnv.pollRetentionSweepIntervalSec,
          ),
        ),
      );
      retentionTimer = setTimeout(() => {
        void runOnce();
      }, intervalSec * 1000);
      if (retentionTimer && typeof retentionTimer.unref === 'function') retentionTimer.unref();
    }
  };
  void runOnce();
}

export function stopPollRetentionWorker(): void {
  retentionWorkerRunning = false;
  if (!retentionTimer) return;
  clearTimeout(retentionTimer);
  retentionTimer = undefined;
}
