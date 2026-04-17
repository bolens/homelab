import fastify, { type FastifyInstance } from 'fastify';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

describe('POST /telemetry/web-vitals', () => {
  let app: FastifyInstance;
  let fastifyBaseRoutes: typeof import('./base')['fastifyBaseRoutes'];

  beforeAll(async () => {
    process.env.DATABASE_URI ??= 'postgres://asking:asking@127.0.0.1:5432/asking';
    ({ fastifyBaseRoutes } = await import('./base'));
    app = fastify();
    await app.register(fastifyBaseRoutes);
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  it('accepts valid web-vitals payload', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/telemetry/web-vitals',
      payload: {
        metric: {
          id: 'v4-123',
          name: 'LCP',
          value: 2134.25,
          delta: 125.5,
          rating: 'good',
          navigationType: 'navigate',
        },
        page: {
          path: '/poll/demo',
          href: 'https://asking-ng.example.com/poll/demo',
        },
        capturedAt: new Date().toISOString(),
      },
    });

    expect(response.statusCode).toBe(202);
    expect(response.json()).toEqual({ status: 'accepted' });
  });

  it('rejects invalid payload with validation error', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/telemetry/web-vitals',
      payload: {
        metric: {
          id: '',
          name: 'NOT_A_METRIC',
          value: 'oops',
        },
      },
    });

    expect(response.statusCode).toBe(400);
    expect(response.json()).toMatchObject({
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Invalid request',
      },
      requestId: expect.any(String),
    });
  });
});
