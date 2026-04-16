import type { LoggerOptions } from 'pino';
import { appEnv } from './env';

const level = appEnv.logLevel || (appEnv.nodeEnv === 'production' ? 'info' : 'debug');

/**
 * Shared logger options for both Fastify request logging and standalone pino usage.
 * Redaction keeps auth/session tokens out of logs by default.
 */
export const sharedLoggerOptions: LoggerOptions = {
  level,
  base: { service: 'asking-ng-api' },
  redact: {
    paths: [
      'req.headers.authorization',
      'req.headers.cookie',
      'req.headers.x-admin-token',
      'req.headers.api_key',
      'req.headers.x-platform-webhook-token',
      'req.headers.x-poll-embed-token',
      'headers.authorization',
      'headers.cookie',
      'headers.x-admin-token',
      'headers.api_key',
      'headers.x-platform-webhook-token',
      'headers.x-poll-embed-token',
      'authorization',
      'cookie',
      'adminToken',
      'bearerToken',
      'pollApiKey',
      'embedToken',
      'token',
      'secret',
      '*.token',
      '*.secret',
    ],
    censor: '[REDACTED]',
  },
};
