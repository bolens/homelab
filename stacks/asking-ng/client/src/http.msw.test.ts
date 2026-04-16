import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { apiFetch } from './http';
import { mswServer } from './test/mswServer';

describe('apiFetch (msw)', () => {
  it('returns mocked JSON', async () => {
    mswServer.use(
      http.get(/\/poll\/msw-test$/, () =>
        HttpResponse.json({ status: 'success', data: { id: 'msw-test' } }),
      ),
    );

    const json = (await apiFetch('poll/msw-test')) as {
      status: string;
      data: { id: string };
    };
    expect(json.status).toBe('success');
    expect(json.data.id).toBe('msw-test');
  });
});
