import { QueryTypes } from 'sequelize';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockQuery, mockTransaction, mockInfo } = vi.hoisted(() => ({
  mockQuery: vi.fn(),
  mockTransaction: vi.fn(),
  mockInfo: vi.fn(),
}));
const { mockGetRetentionPolicySettings } = vi.hoisted(() => ({
  mockGetRetentionPolicySettings: vi.fn(),
}));

vi.mock('../connections', () => ({
  default: {
    query: mockQuery,
    transaction: mockTransaction,
  },
}));

vi.mock('./env', () => ({
  appEnv: {
    pollRetentionTtlDaysDefault: 30,
    pollRetentionSweepBatchSize: 100,
    pollRetentionSweepIntervalSec: 60,
    auditLogRetentionDays: 90,
    moderationRejectedVoteRetentionDays: 30,
  },
}));

vi.mock('./logger', () => ({
  logger: {
    info: mockInfo,
    error: vi.fn(),
  },
}));
vi.mock('./appSettings', () => ({
  getRetentionPolicySettings: mockGetRetentionPolicySettings,
}));

import {
  sweepExpiredAuditLogs,
  sweepExpiredPollRetention,
  sweepExpiredRejectedModerationVotes,
} from './pollRetention';

describe('pollRetention', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTransaction.mockImplementation(async (fn: (tx: unknown) => Promise<void>) => fn({}));
    mockGetRetentionPolicySettings.mockResolvedValue({
      poll_retention_ttl_days_default: 30,
      poll_retention_sweep_interval_sec: 60,
      poll_retention_sweep_batch_size: 100,
      audit_log_retention_days: 90,
      moderation_rejected_vote_retention_days: 30,
      audit_log_retention_legal_hold: false,
      moderation_rejected_vote_retention_legal_hold: false,
    });
  });

  it('returns zero when no expired polls are found', async () => {
    mockQuery.mockResolvedValueOnce([]);
    const n = await sweepExpiredPollRetention({ nowMs: 1_700_000_000_000 });
    expect(n).toBe(0);
    expect(mockQuery).toHaveBeenCalledTimes(1);
    expect(mockInfo).not.toHaveBeenCalled();
  });

  it('deletes poll-related rows in one transaction', async () => {
    mockQuery.mockResolvedValueOnce([{ id: 'p1' }, { id: 'p2' }]);
    mockQuery.mockResolvedValue([]);

    const n = await sweepExpiredPollRetention({ nowMs: 1_700_000_000_000 });
    expect(n).toBe(2);
    expect(mockTransaction).toHaveBeenCalledTimes(1);
    expect(mockQuery).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('SELECT id'),
      expect.objectContaining({ type: QueryTypes.SELECT }),
    );
    expect(mockQuery.mock.calls[0]?.[0]).toContain('COALESCE("retentionLegalHold", false) = false');
    expect(mockQuery).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('DELETE FROM poll_phase_events'),
      expect.objectContaining({ type: QueryTypes.DELETE }),
    );
    expect(mockQuery).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining('DELETE FROM votes'),
      expect.objectContaining({ type: QueryTypes.DELETE }),
    );
    expect(mockQuery).toHaveBeenNthCalledWith(
      4,
      expect.stringContaining('DELETE FROM polls'),
      expect.objectContaining({ type: QueryTypes.DELETE }),
    );
    expect(mockInfo).toHaveBeenCalledWith(
      expect.objectContaining({ event: 'poll.retention.auto_delete', deletedCount: 2 }),
      expect.any(String),
    );
  });

  it('deletes expired audit logs in batches', async () => {
    mockQuery.mockResolvedValueOnce([{ id: 'a1' }]);
    mockQuery.mockResolvedValueOnce([]);
    const n = await sweepExpiredAuditLogs({ nowMs: 1_700_000_000_000 });
    expect(n).toBe(1);
    expect(mockQuery).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('FROM audit_logs'),
      expect.objectContaining({ type: QueryTypes.SELECT }),
    );
    expect(mockQuery).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('DELETE FROM audit_logs'),
      expect.objectContaining({ type: QueryTypes.DELETE }),
    );
  });

  it('deletes expired rejected moderation votes in batches', async () => {
    mockQuery.mockResolvedValueOnce([{ id: 'v1' }, { id: 'v2' }]);
    mockQuery.mockResolvedValueOnce([]);
    const n = await sweepExpiredRejectedModerationVotes({ nowMs: 1_700_000_000_000 });
    expect(n).toBe(2);
    expect(mockQuery).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining(`"quarantineStatus", 'pending') = 'rejected'`),
      expect.objectContaining({ type: QueryTypes.SELECT }),
    );
    expect(mockQuery).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('DELETE FROM votes'),
      expect.objectContaining({ type: QueryTypes.DELETE }),
    );
  });

  it('skips audit-log retention deletes when legal hold is enabled', async () => {
    mockGetRetentionPolicySettings.mockResolvedValueOnce({
      poll_retention_ttl_days_default: 30,
      poll_retention_sweep_interval_sec: 60,
      poll_retention_sweep_batch_size: 100,
      audit_log_retention_days: 90,
      moderation_rejected_vote_retention_days: 30,
      audit_log_retention_legal_hold: true,
      moderation_rejected_vote_retention_legal_hold: false,
    });
    const n = await sweepExpiredAuditLogs({ nowMs: 1_700_000_000_000 });
    expect(n).toBe(0);
    expect(mockQuery).not.toHaveBeenCalled();
  });

  it('skips rejected-vote retention deletes when legal hold is enabled', async () => {
    mockGetRetentionPolicySettings.mockResolvedValueOnce({
      poll_retention_ttl_days_default: 30,
      poll_retention_sweep_interval_sec: 60,
      poll_retention_sweep_batch_size: 100,
      audit_log_retention_days: 90,
      moderation_rejected_vote_retention_days: 30,
      audit_log_retention_legal_hold: false,
      moderation_rejected_vote_retention_legal_hold: true,
    });
    const n = await sweepExpiredRejectedModerationVotes({ nowMs: 1_700_000_000_000 });
    expect(n).toBe(0);
    expect(mockQuery).not.toHaveBeenCalled();
  });
});
