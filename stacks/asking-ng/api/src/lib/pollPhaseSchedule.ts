import { normalizePollPhase, type PollPhase } from '@asking-ng/contracts/poll';

export type PollPhaseSchedule = {
  open_at: number | null;
  lock_at: number | null;
  reveal_at: number | null;
};

export function pollPhaseScheduleFromRow(row: { get: (k: string) => unknown }): PollPhaseSchedule {
  const toNum = (v: unknown): number | null => {
    if (v == null) return null;
    const n = Number.parseInt(String(v), 10);
    return Number.isFinite(n) ? n : null;
  };
  return {
    open_at: toNum(row.get('openAt')),
    lock_at: toNum(row.get('lockAt')),
    reveal_at: toNum(row.get('revealAt')),
  };
}

export function validatePollPhaseScheduleWindow(s: PollPhaseSchedule): string | null {
  const { open_at, lock_at, reveal_at } = s;
  if (open_at != null && lock_at != null && lock_at < open_at) {
    return 'lock_at must be greater than or equal to open_at';
  }
  if (open_at != null && reveal_at != null && reveal_at < open_at) {
    return 'reveal_at must be greater than or equal to open_at';
  }
  if (lock_at != null && reveal_at != null && reveal_at < lock_at) {
    return 'reveal_at must be greater than or equal to lock_at';
  }
  return null;
}

export function resolveEffectivePollPhase(
  configuredPhaseRaw: unknown,
  schedule: PollPhaseSchedule,
  nowMs: number,
): PollPhase {
  const configured = normalizePollPhase(configuredPhaseRaw);
  if (schedule.reveal_at != null && nowMs >= schedule.reveal_at) return 'revealed';
  if (schedule.lock_at != null && nowMs >= schedule.lock_at) return 'locked';
  if (schedule.open_at != null) {
    if (nowMs >= schedule.open_at) return 'open';
    return 'draft';
  }
  return configured;
}
