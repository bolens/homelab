import type { FastifyInstance } from 'fastify';
import { ConnectionError, ForeignKeyConstraintError } from 'sequelize';
import { appEnv } from '../lib/env';
import { reportErrorToSentryCompat } from '../lib/integrationWebhooks';
import { errorToAppError } from '../middleware/errorToAppError';

export function registerFastifyErrorHandling(app: FastifyInstance): void {
  app.setNotFoundHandler((request, reply) => {
    reply.code(404).send({
      error: { code: 'NOT_FOUND', message: 'Not found' },
      requestId: request.id,
    });
  });

  app.setErrorHandler((err, request, reply) => {
    const appError = errorToAppError(err);
    const logMeta = { requestId: request.id, code: appError.code, event: 'http.error' };
    const redact = appEnv.incidentMode;
    const messageForClient =
      redact && appError.statusCode >= 500 ? 'Service temporarily degraded.' : appError.message;

    if (appError.statusCode >= 500) {
      if (redact) request.log.error(logMeta, 'incident mode server error');
      else request.log.error({ err, ...logMeta }, appError.message);
      void reportErrorToSentryCompat({
        requestId: request.id,
        code: appError.code,
        message: messageForClient,
        method: request.method,
        url: request.url,
      });
    } else if (
      err instanceof ConnectionError ||
      err instanceof ForeignKeyConstraintError ||
      appError.statusCode >= 400
    ) {
      request.log.warn({ err, ...logMeta }, appError.message);
    } else {
      request.log.info({ ...logMeta }, appError.message);
    }

    reply.code(appError.statusCode).send({
      error: {
        code: appError.code,
        message: messageForClient,
        ...(!redact && appError.details !== undefined ? { details: appError.details } : {}),
      },
      requestId: request.id,
    });
  });
}
