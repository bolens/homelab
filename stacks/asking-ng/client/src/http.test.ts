import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { apiFetch, apiFetchErrorFromText, isApiFetchError, summaryFromApiErrorBody } from './http';
import { mswServer } from './test/mswServer';

describe('apiFetch error payloads', () => {
  it('reads nested API error message, code, and requestId', async () => {
    mswServer.use(
      http.post(/\/poll$/, () =>
        HttpResponse.json(
          {
            error: { code: 'VALIDATION_ERROR', message: 'Invalid request' },
            requestId: 'req-xyz',
          },
          { status: 400 },
        ),
      ),
    );
    try {
      await apiFetch('poll', { method: 'POST', body: { x: 1 } });
      expect.fail('expected throw');
    } catch (e: unknown) {
      expect(e).toBeInstanceOf(Error);
      expect(isApiFetchError(e)).toBe(true);
      if (!isApiFetchError(e)) throw new Error('narrow');
      expect(e.message).toBe('Invalid request');
      expect(e.requestId).toBe('req-xyz');
      expect(e.errorCode).toBe('VALIDATION_ERROR');
    }
  });

  it('apiFetchErrorFromText attaches details from nested error', () => {
    const raw = JSON.stringify({
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Invalid request',
        details: { fieldErrors: { limit: ['bad'] } },
      },
      requestId: 'r1',
    });
    const e = apiFetchErrorFromText(400, raw);
    expect(e.errorCode).toBe('VALIDATION_ERROR');
    expect(e.details).toEqual({ fieldErrors: { limit: ['bad'] } });
    expect(e.requestId).toBe('r1');
  });

  it('apiFetchErrorFromText replaces CDN/proxy HTML bodies with a short hint', () => {
    const raw = '<!DOCTYPE html><html><title>502 Bad Gateway</title></html>';
    const e = apiFetchErrorFromText(502, raw);
    expect(e.message).toContain('HTTP 502');
    expect(e.message).toContain('HTML error page');
    expect(e.message).not.toContain('<!DOCTYPE');
  });

  it('summaryFromApiErrorBody formats ready-style SERVICE_UNAVAILABLE', () => {
    const s = summaryFromApiErrorBody(
      {
        error: {
          code: 'SERVICE_UNAVAILABLE',
          message: 'Database is not accepting connections',
        },
        requestId: 'rid-1',
      },
      503,
    );
    expect(s).toContain('Database is not accepting connections');
    expect(s).toContain('[SERVICE_UNAVAILABLE]');
    expect(s).toContain('(request rid-1)');
  });

  it('summaryFromApiErrorBody falls back to HTTP status when body is empty', () => {
    expect(summaryFromApiErrorBody({}, 503)).toBe('HTTP 503');
  });

  it('sets api_key header when pollApiKey is provided', async () => {
    let sawKey: string | null = null;
    mswServer.use(
      http.put(/\/poll\/x$/, ({ request }) => {
        sawKey = request.headers.get('api_key');
        return HttpResponse.json({ status: 'success' });
      }),
    );
    await apiFetch('poll/x', {
      method: 'PUT',
      body: { phase: 'open' },
      pollApiKey: 'abc123',
      adminToken: false,
    });
    expect(sawKey).toBe('abc123');
  });

  it('supports legacy string error field', async () => {
    mswServer.use(
      http.get(/\/legacy$/, () => HttpResponse.json({ error: 'nope' }, { status: 500 })),
    );
    try {
      await apiFetch('legacy', { adminToken: false });
      expect.fail('expected throw');
    } catch (e: unknown) {
      expect((e as Error).message).toBe('nope');
    }
  });
});
