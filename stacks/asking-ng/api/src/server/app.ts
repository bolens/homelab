import { randomUUID } from 'node:crypto';
import fastify, { type FastifyInstance } from 'fastify';
import fastifyCompress from '@fastify/compress';
import fastifyCors from '@fastify/cors';
import fastifyHelmet from '@fastify/helmet';
import fastifyRateLimit from '@fastify/rate-limit';
import fastifyUnderPressure from '@fastify/under-pressure';
import pkg from '../../package.json';
import { appEnv } from '../lib/env';
import { billingApiRateLimitErrorBody, billingHttpRateLimitKey, billingHttpRateLimitMax, billingHttpRateLimitWindowMs } from '../lib/billingHttpRateLimit';
import { recordBillingApiRateLimited } from '../lib/billingApiRateLimitLedger';
import { observeHttpRequest, observeIntegrationEvent, renderPrometheusMetrics } from '../lib/metrics';
import { sharedLoggerOptions } from '../lib/logConfig';
import sequelize from '../models';
import { fastifyAdminRoutes } from './admin';
import { fastifyBillingRoutes } from './billing';
import { fastifyBaseRoutes } from './base';
import { registerFastifyErrorHandling } from './errorHandling';
import { fastifyLlmRoutes } from './llm';
import { fastifyPollRoutes } from './poll';
import { requestContextPlugin } from './requestContext';
import { registerFastifySwagger } from './swagger';

type BuildFastifyAppOptions = {
  trustProxy?: boolean;
};

function normalizeRouteForMetrics(route: string): string {
  if (!route) return 'unknown';
  const [pathOnly] = route.split('?');
  if (!pathOnly) return 'unknown';
  const normalized = pathOnly
    .split('/')
    .filter(Boolean)
    .map((segment) => {
      if (segment.startsWith(':')) return segment;
      if (/^[0-9]+$/.test(segment)) return ':id';
      if (/^[0-9a-f]{24,}$/i.test(segment)) return ':id';
      if (/^[0-9a-f-]{36}$/i.test(segment)) return ':uuid';
      return segment;
    })
    .join('/');
  return `/${normalized}`;
}

export async function buildFastifyApp(
  options: BuildFastifyAppOptions = {},
): Promise<FastifyInstance> {
  const app = fastify({
    logger: sharedLoggerOptions,
    trustProxy: options.trustProxy ?? true,
    disableRequestLogging: true,
    requestIdHeader: 'x-request-id',
    requestIdLogLabel: 'requestId',
    genReqId: () => randomUUID(),
  });

  await app.register(fastifyHelmet);
  await app.register(fastifyCompress);
  await app.register(fastifyUnderPressure, {
    exposeStatusRoute: false,
    maxEventLoopDelay: appEnv.pressureMaxEventLoopDelayMs,
    ...(appEnv.pressureMaxHeapUsedBytes
      ? { maxHeapUsedBytes: appEnv.pressureMaxHeapUsedBytes }
      : {}),
    ...(appEnv.pressureMaxRssBytes ? { maxRssBytes: appEnv.pressureMaxRssBytes } : {}),
    retryAfter: 30,
    message: 'Server is under pressure',
  });
  await app.register(requestContextPlugin);
  await app.register(fastifyRateLimit, {
    global: true,
    max: (req) => billingHttpRateLimitMax(req),
    timeWindow: (req) => billingHttpRateLimitWindowMs(req),
    keyGenerator: (req) => billingHttpRateLimitKey(req),
    skipOnError: true,
    errorResponseBuilder: (req, ctx) => billingApiRateLimitErrorBody(req, ctx.max),
    onExceeded: (req) => {
      if (appEnv.billingEnforceLimits && req.user?.id != null) {
        observeIntegrationEvent('billing_api_rate_limited');
        void recordBillingApiRateLimited({
          userId: req.user.id,
          billingPlan: req.user.billingPlan?.trim() || 'free',
          max: billingHttpRateLimitMax(req),
          route: req.routeOptions?.url ?? req.url,
        });
      }
    },
  });
  await app.register(
    fastifyCors,
    appEnv.corsOrigins.length > 0 ? { origin: appEnv.corsOrigins } : {},
  );
  await registerFastifySwagger(app);
  await app.register(fastifyBillingRoutes);
  await app.register(fastifyBaseRoutes);
  await app.register(fastifyAdminRoutes, { prefix: '/admin' });
  await app.register(fastifyLlmRoutes, { prefix: '/llm' });

  app.addHook('onResponse', async (request, reply) => {
    observeHttpRequest({
      route: normalizeRouteForMetrics(request.routeOptions.url || request.url || 'unknown'),
      method: request.method,
      statusCode: reply.statusCode,
    });
  });

  app.get('/healthcheck', async () => ({ status: 'ok', message: 'API is healthy' }));

  app.get('/ready', async (request, reply) => {
    try {
      await sequelize.authenticate();
      return { status: 'ok', ready: true };
    } catch (err: unknown) {
      request.log.warn({ event: 'db.readiness.failed', err }, 'database not ready');
      reply.code(503);
      return {
        error: {
          code: 'SERVICE_UNAVAILABLE',
          message: 'Database is not accepting connections',
        },
        requestId: request.id,
      };
    }
  });

  app.get('/info', async () => {
    const service = appEnv.serviceName;
    if (appEnv.nodeEnv === 'production' && !appEnv.exposeServiceInfoDetails) {
      return { service };
    }
    return {
      service,
      version: pkg.version,
      node: process.version,
      environment: appEnv.nodeEnv,
      ...(appEnv.commit ? { commit: appEnv.commit } : {}),
    };
  });

  app.get('/metrics', async (request, reply) => {
    if (!appEnv.enablePrometheusMetrics) {
      reply.code(404).send({
        error: { code: 'NOT_FOUND', message: 'Not found' },
        requestId: request.id,
      });
      return;
    }
    reply.type('text/plain; version=0.0.4').send(renderPrometheusMetrics());
  });

  await app.register(fastifyPollRoutes, { prefix: '/poll' });
  registerFastifyErrorHandling(app);

  return app;
}
