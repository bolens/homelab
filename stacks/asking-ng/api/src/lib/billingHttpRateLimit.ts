import type { FastifyRequest } from 'fastify';
import {
  maxAuthenticatedRestBurstPerMinuteForBillingPlan,
  maxAuthenticatedRestSustainedPerMinuteForBillingPlan,
} from './billingLimits';
import { appEnv } from './env';

function clientIp(req: FastifyRequest): string {
  const raw = typeof req.ip === 'string' && req.ip.trim() !== '' ? req.ip.trim() : 'unknown';
  return raw;
}

/**
 * Global HTTP rate limit key. When {@link appEnv.billingEnforceLimits} is on and the caller is
 * authenticated, keys per user so tier caps apply; otherwise keys per IP (existing behavior).
 */
export function billingHttpRateLimitKey(req: FastifyRequest): string {
  if (appEnv.billingEnforceLimits && req.user?.id != null) {
    return `auth:${req.user.id}`;
  }
  return `ip:${clientIp(req)}`;
}

export function billingHttpRateLimitMax(req: FastifyRequest): number {
  if (!appEnv.billingEnforceLimits) {
    return appEnv.httpRateLimitMax;
  }
  if (req.user?.id != null) {
    return maxAuthenticatedRestBurstPerMinuteForBillingPlan(req.user.billingPlan ?? 'free');
  }
  return appEnv.httpRateLimitMax;
}

/** One-minute window for authenticated tier caps; otherwise env window. */
export function billingHttpRateLimitWindowMs(req: FastifyRequest): number {
  if (!appEnv.billingEnforceLimits) {
    return appEnv.httpRateLimitWindowMs;
  }
  if (req.user?.id != null) {
    return 60_000;
  }
  return appEnv.httpRateLimitWindowMs;
}

export function billingApiRateLimitErrorBody(
  req: FastifyRequest,
  max: number,
): Record<string, unknown> {
  const plan = req.user?.billingPlan?.trim() || 'free';
  const sustained = maxAuthenticatedRestSustainedPerMinuteForBillingPlan(plan);
  return {
    error: {
      code: 'USAGE_LIMIT_API_RATE',
      message: 'Too many requests for this billing tier.',
      details: {
        max,
        plan,
        sustainedPerMinute: sustained,
        windowMs: billingHttpRateLimitWindowMs(req),
      },
    },
    requestId: req.id,
  };
}
