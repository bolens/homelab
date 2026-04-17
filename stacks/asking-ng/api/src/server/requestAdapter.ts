import type { IncomingHttpHeaders } from 'node:http';
import type { AppRequest } from '../types/http';

export function toAppRequest(
  request: {
    params?: unknown;
    query?: unknown;
    body?: unknown;
    headers?: unknown;
    ip: string;
    id: string;
    protocol?: string;
    user?: { id: number; homelab-user: string; role: string; billingPlan?: string } | null;
  },
  validatedQuery?: unknown,
): AppRequest {
  const protocol = typeof request.protocol === 'string' ? request.protocol : '';
  return {
    params: (request.params ?? {}) as Record<string, unknown>,
    query: (request.query ?? {}) as Record<string, unknown>,
    body: request.body,
    headers: (request.headers ?? {}) as IncomingHttpHeaders,
    ip: request.ip,
    secure: protocol === 'https',
    requestId: request.id,
    ...(request.user ? { user: request.user } : {}),
    validatedQuery,
  };
}

export function replyJsonError(
  requestId: string,
  statusCode: number,
  code: string,
  message: string,
  details?: unknown,
) {
  return {
    statusCode,
    body: {
      error: {
        code,
        message,
        ...(details !== undefined ? { details } : {}),
      },
      requestId,
    },
  };
}
