import type { IncomingHttpHeaders } from 'node:http';

/**
 * Request shape passed to route handlers (built from Fastify via {@link toAppRequest} in `server/requestAdapter.ts`).
 * Shared handler request shape; the HTTP server is Fastify (`toAppRequest` builds this from Fastify requests).
 */
export interface AppRequest {
  params: Record<string, unknown>;
  query: Record<string, unknown>;
  body?: unknown;
  headers: IncomingHttpHeaders;
  ip: string;
  /** True when the inbound request is HTTPS (Fastify `protocol` or equivalent). */
  secure?: boolean;
  requestId?: string;
  user?: { id: number; homelab-user: string; role: string; billingPlan?: string };
  /** Set by validateQuery middleware; cast to the route Zod output type. */
  validatedQuery?: unknown;
}

export type AppNextFunction = (err?: unknown) => void;

/** Minimal response surface used by handlers (invoked via Fastify reply shims in `server/poll.ts` etc.). */
export interface AppResponse {
  status(code: number): AppResponse;
  json(body: unknown): AppResponse;
  setHeader(name: string, value: string | number | readonly string[]): AppResponse;
  attachment(filename: string): AppResponse;
  send(body?: unknown): AppResponse;
}

export type AppRequestHandler = (
  req: AppRequest,
  res: AppResponse,
  next: AppNextFunction,
) => unknown;
