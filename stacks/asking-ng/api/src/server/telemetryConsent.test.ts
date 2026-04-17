import fastify, { type FastifyInstance } from 'fastify';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

describe('POST /telemetry/consent', () => {
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

  it('accepts valid simple consent payload (explicit mode)', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/telemetry/consent',
      payload: {
        mode: 'simple',
        choice: 'rejected',
        source: 'banner',
        clientTs: new Date().toISOString(),
      },
    });

    expect(response.statusCode).toBe(202);
    expect(response.json()).toEqual({ status: 'accepted' });
  });

  it('accepts legacy simple payload without mode', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/telemetry/consent',
      payload: {
        choice: 'accepted',
        source: 'settings',
        clientTs: new Date().toISOString(),
      },
    });

    expect(response.statusCode).toBe(202);
    expect(response.json()).toEqual({ status: 'accepted' });
  });

  it('accepts granular consent payload', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/telemetry/consent',
      payload: {
        mode: 'granular',
        necessary: true,
        functional: false,
        analytics: true,
        marketing: false,
        consentRegion: 'eu',
        source: 'banner',
        clientTs: new Date().toISOString(),
      },
    });

    expect(response.statusCode).toBe(202);
    expect(response.json()).toEqual({ status: 'accepted' });
  });

  it('rejects invalid choice', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/telemetry/consent',
      payload: { mode: 'simple', choice: 'maybe' },
    });

    expect(response.statusCode).toBe(400);
    expect(response.json()).toMatchObject({
      error: { code: 'VALIDATION_ERROR', message: 'Invalid request' },
      requestId: expect.any(String),
    });
  });
});

describe('GET /telemetry/consent-region', () => {
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

  it('returns unknown without geo header', async () => {
    const response = await app.inject({
      method: 'GET',
      url: '/telemetry/consent-region',
    });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({
      region: 'unknown',
      source: 'unknown',
    });
  });

  it('returns eu when cf-ipcountry is an EU member', async () => {
    const response = await app.inject({
      method: 'GET',
      url: '/telemetry/consent-region',
      headers: { 'cf-ipcountry': 'DE' },
    });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({
      region: 'eu',
      source: 'header',
    });
  });
});

describe('POST /auth/register validation', () => {
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

  it('rejects body without acceptTermsAndPrivacy', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/auth/register',
      payload: { homelab-user: 'newuser_e2e_val', password: 'abcdefgh' },
    });

    expect(response.statusCode).toBe(400);
    expect(response.json()).toMatchObject({
      error: { code: 'VALIDATION_ERROR' },
      requestId: expect.any(String),
    });
  });
});
