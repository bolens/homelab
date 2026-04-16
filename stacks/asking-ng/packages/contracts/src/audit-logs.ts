import { z } from 'zod';

const optionalTrimmed = (max: number) =>
  z
    .string()
    .max(max)
    .optional()
    .transform((s) => (s === undefined || s.trim() === '' ? undefined : s.trim()));

const limitStringField = z
  .string()
  .max(10)
  .optional()
  .transform((s) => (s === undefined || s.trim() === '' ? undefined : s.trim()));

const auditLogsFiltersObject = z.object({
  action: optionalTrimmed(128),
  actor: optionalTrimmed(128),
  target: optionalTrimmed(256),
  start: optionalTrimmed(64),
  end: optionalTrimmed(64),
  limit: limitStringField,
});

function refineLimitDigits(val: { limit?: string }, ctx: z.RefinementCtx) {
  if (val.limit !== undefined && !/^\d+$/.test(val.limit)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'limit must be a positive integer',
      path: ['limit'],
    });
  }
}

/** TanStack Router search: same field rules as the API, but `limit` is optional (API defaults when absent). */
export const auditLogsRouteSearchSchema = auditLogsFiltersObject
  .superRefine(refineLimitDigits)
  .transform(({ limit, ...rest }) => ({
    ...rest,
    limit: limit === undefined ? undefined : Math.min(500, Math.max(1, Number.parseInt(limit, 10))),
  }));

export type AuditLogsRouteSearch = z.infer<typeof auditLogsRouteSearchSchema>;

/** API query validation: applies default `limit` 100 when omitted. */
export const auditLogsQuerySchema = auditLogsFiltersObject
  .superRefine(refineLimitDigits)
  .transform(({ limit, ...rest }) => ({
    ...rest,
    limit: limit === undefined ? 100 : Math.min(500, Math.max(1, Number.parseInt(limit, 10))),
  }));

export type AuditLogsQuery = z.infer<typeof auditLogsQuerySchema>;

function pickString(v: unknown): string | undefined {
  if (typeof v === 'string') return v;
  return undefined;
}

/** Accept string or finite number (e.g. TanStack Router after programmatic navigate). */
function pickLimitInput(v: unknown): string | undefined {
  if (typeof v === 'string') return v;
  if (typeof v === 'number' && Number.isFinite(v)) return String(Math.trunc(v));
  return undefined;
}

function pickAuditLogFields(raw: unknown) {
  const o = raw && typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {};
  return {
    action: pickString(o.action),
    actor: pickString(o.actor),
    target: pickString(o.target),
    start: pickString(o.start),
    end: pickString(o.end),
    limit: pickLimitInput(o.limit),
  };
}

/**
 * Parse audit-log filters for the admin UI URL (optional `limit`; same trim/max rules as the API).
 */
export function parseAuditLogsSearch(raw: unknown): AuditLogsRouteSearch {
  return auditLogsRouteSearchSchema.parse(pickAuditLogFields(raw));
}

/** Parse audit-log filters for the HTTP API (default `limit` 100). */
export function parseAuditLogsQuery(raw: unknown): AuditLogsQuery {
  return auditLogsQuerySchema.parse(pickAuditLogFields(raw));
}
