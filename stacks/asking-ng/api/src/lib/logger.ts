import pino from 'pino';
import { sharedLoggerOptions } from './logConfig';

export const logger = pino({
  ...sharedLoggerOptions,
});

type RequestLikeForLogging = {
  requestId?: unknown;
  id?: unknown;
  method?: unknown;
  originalUrl?: unknown;
  path?: unknown;
};

/**
 * Best-effort request-scoped logger for non-Fastify handlers.
 * Adds request correlation fields when available.
 */
export function loggerForRequest(req: RequestLikeForLogging) {
  const requestId =
    typeof req.requestId === 'string' && req.requestId.trim() !== ''
      ? req.requestId.trim()
      : typeof req.id === 'string' && req.id.trim() !== ''
        ? req.id.trim()
        : undefined;
  const method = typeof req.method === 'string' && req.method.trim() !== '' ? req.method : undefined;
  const path =
    typeof req.originalUrl === 'string' && req.originalUrl.trim() !== ''
      ? req.originalUrl
      : typeof req.path === 'string' && req.path.trim() !== ''
        ? req.path
        : undefined;

  if (!requestId && !method && !path) return logger;
  return logger.child({
    ...(requestId ? { requestId } : {}),
    ...(method ? { method } : {}),
    ...(path ? { path } : {}),
  });
}
