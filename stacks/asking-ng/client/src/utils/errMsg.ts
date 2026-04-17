import { type ApiFetchError, isApiFetchError } from '../http';

/** Human-readable message; appends `requestId` when present on {@link ApiFetchError}. */
export function errMsg(err: unknown, fallback: string): string {
  if (!(err instanceof Error)) return fallback;
  let m = err.message;
  const ae = err as Partial<ApiFetchError>;
  if (isApiFetchError(err) && err.status === 429 && !m.toLowerCase().includes('try again')) {
    m = `${m} Try again in a moment.`;
  }
  if (
    isApiFetchError(err) &&
    err.status === 503 &&
    !/\btry again\b/i.test(m) &&
    !/\bshortly\b/i.test(m)
  ) {
    m = `${m} Retry shortly if the database is still starting or unreachable.`;
  }
  if (
    isApiFetchError(err) &&
    err.errorCode === 'USAGE_LIMIT_ACTIVE_POLLS' &&
    err.details &&
    typeof err.details === 'object' &&
    !Array.isArray(err.details)
  ) {
    const d = err.details as Record<string, unknown>;
    const cur = d.current;
    const max = d.max;
    if (typeof cur === 'number' && typeof max === 'number' && max < Number.MAX_SAFE_INTEGER / 2) {
      m = `${m} (${cur}/${max} active polls).`;
    }
  }
  if (
    isApiFetchError(err) &&
    err.errorCode === 'USAGE_LIMIT_EXPORTS' &&
    err.details &&
    typeof err.details === 'object' &&
    !Array.isArray(err.details)
  ) {
    const d = err.details as Record<string, unknown>;
    const cur = d.current;
    const max = d.max;
    if (typeof cur === 'number' && typeof max === 'number' && max < Number.MAX_SAFE_INTEGER / 2) {
      m = `${m} (${cur}/${max} exports today UTC).`;
    }
  }
  if (
    isApiFetchError(err) &&
    err.errorCode === 'USAGE_LIMIT_VOTES' &&
    err.details &&
    typeof err.details === 'object' &&
    !Array.isArray(err.details)
  ) {
    const d = err.details as Record<string, unknown>;
    const cur = d.current;
    const max = d.max;
    const incoming = d.incoming;
    if (typeof cur === 'number' && typeof max === 'number' && max < Number.MAX_SAFE_INTEGER / 2) {
      const inc =
        typeof incoming === 'number' && incoming > 1 ? ` (+${incoming} this request)` : '';
      m = `${m} (${cur}/${max} votes this UTC month${inc}).`;
    }
  }
  if (
    isApiFetchError(err) &&
    typeof err.errorCode === 'string' &&
    (err.errorCode.startsWith('PLAN_LIMIT_') || err.errorCode === 'BILLING_LICENSE_EXPIRED') &&
    err.details &&
    typeof err.details === 'object' &&
    !Array.isArray(err.details)
  ) {
    const d = err.details as Record<string, unknown>;
    const hint = d.upgrade_hint;
    if (typeof hint === 'string' && hint.trim() !== '' && !m.includes(hint.trim())) {
      m = `${m} ${hint.trim()}`;
    }
  }
  if (
    isApiFetchError(err) &&
    typeof ae.errorCode === 'string' &&
    ae.errorCode.trim() !== '' &&
    !m.includes(ae.errorCode)
  ) {
    m = `${m} [${ae.errorCode}]`;
  }
  if (ae.requestId) m = `${m} (request ${ae.requestId})`;
  return m;
}
