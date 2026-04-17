import { pollPhaseScheduleFromRow, resolveEffectivePollPhase } from './pollPhaseSchedule';

/** Same “public viewer” delay semantics as anonymous `GET /poll/:id` for open, non-expired polls. */
export type PollWebhookPublicDelayWindow = {
  now: number;
  effectivePhase: string;
  liveResultsAreDelayed: boolean;
  resultsVisibleThroughMs: number;
  resultsVisibleThroughIso: string;
};

export function computePollWebhookPublicDelayWindow(poll: {
  get(key: string): unknown;
}): PollWebhookPublicDelayWindow {
  const now = Date.now();
  const archived = Boolean(poll.get('archived'));
  const expiration = poll.get('expiration');
  const expired =
    Number.isFinite(Number(expiration)) && Number(expiration) > 0 && now > Number(expiration);
  const schedule = pollPhaseScheduleFromRow(poll);
  const effectivePhase = resolveEffectivePollPhase(poll.get('phase'), schedule, now);
  const resultsDelaySeconds = Math.max(0, Number(poll.get('resultsDelaySeconds') ?? 0) || 0);
  const liveResultsAreDelayed =
    !archived && !expired && effectivePhase === 'open' && resultsDelaySeconds > 0;
  const resultsVisibleThroughMs = liveResultsAreDelayed
    ? Math.max(0, now - resultsDelaySeconds * 1000)
    : now;
  const resultsVisibleThroughIso = new Date(resultsVisibleThroughMs).toISOString();
  return {
    now,
    effectivePhase,
    liveResultsAreDelayed,
    resultsVisibleThroughMs,
    resultsVisibleThroughIso,
  };
}
