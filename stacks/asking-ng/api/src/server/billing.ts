import { createHash } from 'node:crypto';
import { validateEvent, WebhookVerificationError } from '@polar-sh/sdk/webhooks';
import type { FastifyPluginAsync } from 'fastify';
import { UniqueConstraintError } from 'sequelize';
import { appEnv } from '../lib/env';
import { observeIntegrationEvent } from '../lib/metrics';
import PolarWebhookDelivery from '../models/polarWebhookDelivery.sequelize';
import { replyJsonError } from './requestAdapter';

function normalizeHeaders(raw: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (typeof value === 'string' && value.length > 0) {
      out[key] = value;
    } else if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'string') {
      out[key] = value[0];
    }
  }
  return out;
}

/**
 * Polar / Standard Webhooks need the **raw** JSON body for signature verification.
 * This plugin runs in an encapsulated Fastify context so only routes here use a Buffer JSON parser.
 */
export const fastifyBillingRoutes: FastifyPluginAsync = async (app) => {
  app.removeAllContentTypeParsers();
  app.addContentTypeParser(
    'application/json',
    { parseAs: 'buffer' },
    (_req, body: Buffer, done) => {
      done(null, body);
    },
  );

  app.get('/billing/webhooks/info', async (request, reply) => {
    if (!appEnv.enablePolarWebhooks) {
      const err = replyJsonError(
        request.id,
        404,
        'NOT_FOUND',
        'Polar webhooks are disabled. Set ENABLE_POLAR_WEBHOOKS=true to enable.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const [lastDelivery, deliveriesStoredCount] = await Promise.all([
      PolarWebhookDelivery.findOne({
        order: [['createdAt', 'DESC']],
        attributes: ['eventType', 'createdAt'],
      }),
      PolarWebhookDelivery.count(),
    ]);
    const lastStoredDelivery =
      lastDelivery &&
      (lastDelivery.get('createdAt') != null || lastDelivery.get('eventType') != null)
        ? {
            eventType: String(lastDelivery.get('eventType') ?? ''),
            receivedAt:
              lastDelivery.get('createdAt') instanceof Date
                ? (lastDelivery.get('createdAt') as Date).toISOString()
                : null,
          }
        : null;

    reply.send({
      enabled: true,
      path: 'POST /billing/webhooks/polar',
      verification: 'Standard Webhooks (@polar-sh/sdk validateEvent)',
      deliveriesStoredCount,
      lastStoredDelivery,
    });
  });

  app.post('/billing/webhooks/polar', async (request, reply) => {
    if (!appEnv.enablePolarWebhooks) {
      const err = replyJsonError(
        request.id,
        404,
        'NOT_FOUND',
        'Polar webhooks are disabled. Set ENABLE_POLAR_WEBHOOKS=true to enable.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const secret = appEnv.polarWebhookSecret;
    if (!secret) {
      const err = replyJsonError(
        request.id,
        503,
        'SERVICE_UNAVAILABLE',
        'Polar webhooks are enabled but POLAR_WEBHOOK_SECRET is unset.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const raw = request.body;
    if (!Buffer.isBuffer(raw)) {
      const err = replyJsonError(
        request.id,
        400,
        'BAD_REQUEST',
        'Expected raw JSON body for Polar webhook verification.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const headers = normalizeHeaders(request.headers as Record<string, unknown>);
    let polarType: string;
    let verifiedEvent: { type: string; data: unknown };
    try {
      verifiedEvent = validateEvent(raw, headers, secret);
      polarType = typeof verifiedEvent.type === 'string' ? verifiedEvent.type : 'unknown';
    } catch (e: unknown) {
      if (e instanceof WebhookVerificationError) {
        const err = replyJsonError(
          request.id,
          403,
          'FORBIDDEN',
          'Invalid Polar webhook signature.',
        );
        reply.code(err.statusCode).send(err.body);
        observeIntegrationEvent('polar_webhook_signature_invalid');
        return;
      }
      throw e;
    }

    const headerId = headers['webhook-id']?.trim();
    const deliveryId =
      headerId && headerId.length > 0
        ? headerId.slice(0, 128)
        : `sha256:${createHash('sha256').update(raw).digest('hex')}`.slice(0, 128);

    try {
      await PolarWebhookDelivery.create({
        webhookId: deliveryId,
        eventType: polarType.slice(0, 128),
      });
      request.log.info(
        {
          event: 'polar.webhook.stored',
          polar_type: polarType,
          webhook_id: deliveryId,
          requestId: request.id,
        },
        'polar webhook stored',
      );
      observeIntegrationEvent('polar_webhook_stored');
      try {
        const { applyPolarSubscriptionWebhookEvent } = await import(
          '../lib/polarSubscriptionApply.js'
        );
        await applyPolarSubscriptionWebhookEvent(verifiedEvent, request.log);
      } catch (err: unknown) {
        request.log.error(
          {
            event: 'polar.webhook.entitlements_failed',
            err,
            polar_type: polarType,
            webhook_id: deliveryId,
            requestId: request.id,
          },
          'polar subscription entitlements apply failed',
        );
      }
    } catch (e: unknown) {
      if (e instanceof UniqueConstraintError) {
        request.log.info(
          {
            event: 'polar.webhook.duplicate',
            webhook_id: deliveryId,
            polar_type: polarType,
            requestId: request.id,
          },
          'polar webhook duplicate delivery ignored',
        );
        observeIntegrationEvent('polar_webhook_duplicate');
        reply.code(204).send();
        return;
      }
      throw e;
    }

    reply.code(204).send();
  });
};
