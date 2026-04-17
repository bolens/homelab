import { describe, expect, it } from 'vitest';
import type { ApiFetchError } from '../http';
import { errMsg } from './errMsg';

function makeApiError(
  status: number,
  message: string,
  opts?: { errorCode?: string; requestId?: string },
): ApiFetchError {
  const e = new Error(message) as ApiFetchError;
  e.status = status;
  e.body = {};
  if (opts?.errorCode) e.errorCode = opts.errorCode;
  if (opts?.requestId) e.requestId = opts.requestId;
  return e;
}

describe('errMsg', () => {
  it('appends try-again hint for 429 responses', () => {
    const m = errMsg(makeApiError(429, 'Too many requests'), 'fallback');
    expect(m).toContain('Too many requests');
    expect(m.toLowerCase()).toContain('try again');
  });

  it('does not duplicate try-again when message already includes it', () => {
    const m = errMsg(makeApiError(429, 'Please try again later'), 'fallback');
    expect(m.match(/try again/gi)?.length).toBe(1);
  });

  it('appends error code when not already in the message', () => {
    const m = errMsg(
      makeApiError(409, 'Username must be unique', { errorCode: 'DUPLICATE_KEY' }),
      'fallback',
    );
    expect(m).toContain('Username must be unique');
    expect(m).toContain('[DUPLICATE_KEY]');
  });

  it('does not duplicate error code in the message', () => {
    const m = errMsg(
      makeApiError(400, 'Bad [VALIDATION_ERROR]', { errorCode: 'VALIDATION_ERROR' }),
      'fallback',
    );
    expect(m.split('VALIDATION_ERROR').length - 1).toBe(1);
  });

  it('appends retry hint for 503 API errors', () => {
    const m = errMsg(
      makeApiError(503, 'Database connection failed', { errorCode: 'DATABASE_UNAVAILABLE' }),
      'fallback',
    );
    expect(m.toLowerCase()).toContain('shortly');
    expect(m).toContain('[DATABASE_UNAVAILABLE]');
  });

  it('appends active poll counts for USAGE_LIMIT_ACTIVE_POLLS', () => {
    const e = makeApiError(403, 'Active poll limit reached.', {
      errorCode: 'USAGE_LIMIT_ACTIVE_POLLS',
    });
    (e as { details?: unknown }).details = { max: 20, current: 20, plan: 'free' };
    const m = errMsg(e, 'fallback');
    expect(m).toContain('20/20');
    expect(m).toContain('[USAGE_LIMIT_ACTIVE_POLLS]');
  });

  it('appends export day counts for USAGE_LIMIT_EXPORTS', () => {
    const e = makeApiError(403, 'Daily export limit reached.', {
      errorCode: 'USAGE_LIMIT_EXPORTS',
    });
    (e as { details?: unknown }).details = { max: 3, current: 3, plan: 'free' };
    const m = errMsg(e, 'fallback');
    expect(m).toContain('3/3');
    expect(m).toContain('[USAGE_LIMIT_EXPORTS]');
  });

  it('appends vote month counts for USAGE_LIMIT_VOTES', () => {
    const e = makeApiError(403, 'Monthly vote limit reached.', {
      errorCode: 'USAGE_LIMIT_VOTES',
    });
    (e as { details?: unknown }).details = { max: 50_000, current: 50_000, plan: 'free', incoming: 3 };
    const m = errMsg(e, 'fallback');
    expect(m).toContain('50000/50000');
    expect(m).toContain('+3 this request');
    expect(m).toContain('[USAGE_LIMIT_VOTES]');
  });

  it('appends upgrade hint for PLAN_LIMIT_* errors', () => {
    const e = makeApiError(403, 'Custom retention is not available on this billing plan.', {
      errorCode: 'PLAN_LIMIT_RETENTION',
    });
    (e as { details?: unknown }).details = {
      plan: 'free',
      required_plan: 'cloud-team',
      upgrade_hint: 'Custom retention policy requires cloud-team or higher.',
    };
    const m = errMsg(e, 'fallback');
    expect(m).toContain('Custom retention policy requires cloud-team or higher.');
    expect(m).toContain('[PLAN_LIMIT_RETENTION]');
  });

  it('appends upgrade hint for BILLING_LICENSE_EXPIRED', () => {
    const e = makeApiError(403, 'Self-host Pro license is expired for premium feature use.', {
      errorCode: 'BILLING_LICENSE_EXPIRED',
    });
    (e as { details?: unknown }).details = {
      plan: 'selfhost-pro',
      license_status: 'expired',
      upgrade_hint: 'Self-host Pro license has expired. Renew license to continue premium features.',
    };
    const m = errMsg(e, 'fallback');
    expect(m).toContain('Renew license to continue premium features.');
    expect(m).toContain('[BILLING_LICENSE_EXPIRED]');
  });
});
