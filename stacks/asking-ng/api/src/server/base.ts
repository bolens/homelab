import {
  authLoginBodySchema,
  authRegisterBodySchema,
} from '@asking-ng/contracts/auth';
import { createHash, randomBytes } from 'node:crypto';
import type { IncomingHttpHeaders } from 'node:http';
import type { FastifyPluginAsync } from 'fastify';
import { z } from 'zod';
import {
  countCompletedDataExportsForWorkspaceUtcDay,
  checkDailyDataExportQuotaForWorkspace,
  recordDataExportJob,
} from '../lib/billingExportQuota';
import { buildBillingUsageWarnings, type BillingUsageWarnings } from '../lib/billingUsageWarnings';
import {
  countBillingUsageActionsForWorkspaceUtcDay,
  listDailyBillingUsageRollupsForWorkspace,
  listRecentBillingUsageLedgerForWorkspace,
  type BillingUsageLedgerDailyRollupEntry,
  type BillingUsageLedgerEntry,
} from '../lib/billingUsageLedger';
import { evaluateSelfhostProLicenseState } from '../lib/selfhostProLicense';
import { readCampaignAttributionDayMeter } from '../lib/billingCampaignAttributionQuota';
import {
  readPollWebhookDeliveryMeterForScope,
  resolveWebhookDeliveryScopeKeyForSignedInUser,
} from '../lib/billingPollWebhookDelivery';
import { effectiveWsFanoutMessagesPerSecondForWorkspace } from '../lib/billingWsFanout';
import {
  maxActivePollsForBillingPlan,
  maxDataExportsPerDayForBillingPlan,
  maxVotesPerMonthForBillingPlan,
  utcCalendarMonthBounds,
} from '../lib/billingLimits';
import { resolveEffectivePollLiveRoomCap } from '../lib/billingWsQuota';
import { appEnv } from '../lib/env';
import { resolvePublicConsentRegion } from '../lib/consentRegion';
import { notifyWebhook, sinkAuditLog } from '../lib/integrationWebhooks';
import { observeIntegrationEvent } from '../lib/metrics';
import {
  createUserService,
  deleteUserService,
  getUserService,
  listUsersService,
  patchUserRoleService,
  resetUserPasswordService,
} from '../controller/admin/users.service';
import {
  presentDeletedUserMessage,
  presentPasswordResetMessage,
  presentUser,
  presentUsersList,
} from '../controller/admin/users.presenter';
import { presentAuthSuccess } from '../controller/auth/auth.presenter';
import { loginUser, registerUser } from '../controller/auth/auth.service';
import {
  getProfileService,
  deleteSelfService,
  exportSelfDataService,
  updateProfileService,
  updateSelfPasswordService,
} from '../controller/self/self.service';
import {
  presentPasswordUpdated,
  presentPolarBillingLinks,
  presentProfile,
  presentSelfDeleted,
} from '../controller/self/self.presenter';
import { countBillableVotesForCreatorUtcMonth } from '../controller/poll/voteOnPoll.repository';
import {
  countNonArchivedPollsOwnedByUser,
  findWorkspacePolarSubscriptionFields,
} from '../controller/self/self.repository';
import { invalidateSessionUserCache } from '../lib/sessionUserCache';
import { authenticateBearer } from '../middleware/requireSession';
import Poll from '../model/Poll';
import sequelize from '../models';
import AuditLog from '../models/auditlog.sequelize';
import User from '../models/user.sequelize';
import { ensureDefaultWorkspaceForUser } from '../lib/workspaceBootstrap';
import { generateToken, hashPassword } from '../utils/auth';
import {
  createUserBodySchema,
  rolePatchBodySchema,
  setPasswordBodySchema,
} from '../schemas/admin';
import { profileUpdateBodySchema } from '../schemas/profile';
import { selfDeleteBodySchema, selfPasswordChangeBodySchema } from '../schemas/userSelf';
import { singleString } from '../utils/http';
import {
  isPlatformProvider,
  platformProviders,
  platformWebhookSharedSecret,
  platformWebhooksEnabled,
} from '../lib/platformWebhooks';
import { firstQueryParam, parseBoundedInt } from '../lib/queryParams';
import { publicPollPageUrl } from '../lib/sitePublicUrl';
import { replyJsonError, toAppRequest } from './requestAdapter';

const webVitalsPayloadSchema = z.object({
  metric: z.object({
    id: z.string().min(1),
    name: z.enum(['CLS', 'FCP', 'INP', 'LCP', 'TTFB']),
    value: z.number().finite(),
    delta: z.number().finite(),
    rating: z.enum(['good', 'needs-improvement', 'poor']),
    navigationType: z.string().min(1).max(64),
  }),
  page: z.object({
    path: z.string().min(1).max(2048),
    href: z.string().min(1).max(4096),
  }),
  capturedAt: z.string().datetime(),
});

const telemetryConsentSourceSchema = z.enum(['banner', 'settings', 'browser_signal']).optional();
const telemetryClientTsSchema = z.string().datetime().optional();

const telemetryConsentBodyDiscriminated = z.discriminatedUnion('mode', [
  z.object({
    mode: z.literal('simple'),
    choice: z.enum(['accepted', 'rejected']),
    source: telemetryConsentSourceSchema,
    clientTs: telemetryClientTsSchema,
  }),
  z.object({
    mode: z.literal('granular'),
    necessary: z.literal(true),
    functional: z.boolean(),
    analytics: z.boolean(),
    marketing: z.boolean(),
    consentRegion: z.enum(['eu', 'non-eu', 'unknown']).optional(),
    source: telemetryConsentSourceSchema,
    clientTs: telemetryClientTsSchema,
  }),
]);

/** Older clients sent `{ choice, source?, clientTs? }` without `mode`. */
const telemetryConsentBodySchema = z.preprocess((raw: unknown) => {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return raw;
  const o = raw as Record<string, unknown>;
  if (!('mode' in o) && (o.choice === 'accepted' || o.choice === 'rejected')) {
    return {
      mode: 'simple' as const,
      choice: o.choice,
      source: o.source,
      clientTs: o.clientTs,
    };
  }
  return raw;
}, telemetryConsentBodyDiscriminated);

async function requireSession(
  request: {
    params?: unknown;
    query?: unknown;
    body?: unknown;
    headers?: unknown;
    ip: string;
    id: string;
    user?: { id: number; homelab-user: string; role: string } | null;
    context?: {
      requestId: string;
      userId: number | null;
      homelab-user: string | null;
      role: string | null;
      ip: string | null;
    };
  },
  reply: { code: (statusCode: number) => { send: (payload?: unknown) => void } },
): Promise<boolean> {
  const reqLike = toAppRequest(request);
  let responseStatusCode: number | undefined;
  let responseBody: unknown;
  const resLike = {
    status(code: number) {
      return {
        json(payload: unknown) {
          responseStatusCode = code;
          responseBody = payload;
        },
      };
    },
  };

  const ok = await authenticateBearer(reqLike, resLike as never);
  if (!ok) {
    if (responseStatusCode !== undefined) {
      reply.code(responseStatusCode).send(responseBody);
    } else {
      const err = replyJsonError(request.id, 401, 'INVALID_TOKEN', 'Invalid or expired token');
      reply.code(err.statusCode).send(err.body);
    }
    return false;
  }

  request.user = reqLike.user ?? null;
  if (request.context) {
    request.context.userId = request.user?.id ?? null;
    request.context.homelab-user = request.user?.homelab-user ?? null;
    request.context.role = request.user?.role ?? null;
  }
  return true;
}

function roleFromProxy(raw: unknown): 'user' | 'admin' | 'superadmin' {
  const normalized = typeof raw === 'string' ? raw.trim().toLowerCase() : '';
  if (
    (normalized === 'user' || normalized === 'admin' || normalized === 'superadmin') &&
    appEnv.authProxyAllowedRoles.includes(normalized)
  ) {
    return normalized;
  }
  return appEnv.authProxyDefaultRole;
}

function clampAllowedRole(role: 'user' | 'admin' | 'superadmin'): 'user' | 'admin' | 'superadmin' {
  if (appEnv.authProxyAllowedRoles.includes(role)) return role;
  if (appEnv.authProxyAllowedRoles.includes(appEnv.authProxyDefaultRole)) {
    return appEnv.authProxyDefaultRole;
  }
  return 'user';
}

function proxyHeader(
  request: { headers: Record<string, string | string[] | undefined> },
  name: string,
): string {
  const value = request.headers[name];
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value) && typeof value[0] === 'string') return value[0].trim();
  return '';
}

function roleFromGroups(raw: string): 'user' | 'admin' | 'superadmin' {
  const groups = raw
    .split(/[,\s;]+/)
    .map((v) => v.trim().toLowerCase())
    .filter(Boolean);
  if (groups.some((g) => g === 'superadmin' || g === 'admins:super')) return 'superadmin';
  if (groups.some((g) => g === 'admin' || g === 'admins' || g === 'operators')) return 'admin';
  return 'user';
}

function normalizeProxyUsername(raw: string): string {
  const value = raw.trim();
  if (!value) return '';
  if (value.includes('@')) return value.toLowerCase();
  return value;
}

function normalizeIp(raw: string): string {
  const trimmed = raw.trim();
  if (trimmed.startsWith('::ffff:')) return trimmed.slice('::ffff:'.length);
  return trimmed;
}

function ipv4ToInt(ip: string): number | null {
  const parts = ip.split('.');
  if (parts.length !== 4) return null;
  let result = 0;
  for (const part of parts) {
    if (!/^\d+$/.test(part)) return null;
    const value = Number(part);
    if (!Number.isInteger(value) || value < 0 || value > 255) return null;
    result = (result << 8) + value;
  }
  return result >>> 0;
}

function matchesCidr(ip: string, cidr: string): boolean {
  const [base, bitsRaw] = cidr.split('/');
  if (!base || bitsRaw === undefined) return false;
  const ipInt = ipv4ToInt(ip);
  const baseInt = ipv4ToInt(base);
  const bits = Number(bitsRaw);
  if (ipInt === null || baseInt === null || !Number.isInteger(bits) || bits < 0 || bits > 32) {
    return false;
  }
  const mask = bits === 0 ? 0 : ((0xffffffff << (32 - bits)) >>> 0);
  return (ipInt & mask) === (baseInt & mask);
}

function isTrustedProxyIp(ipRaw: string): boolean {
  const trusted = appEnv.authProxyTrustedIps;
  if (trusted.length === 0) return true;
  const ip = normalizeIp(ipRaw);
  if (!ip) return false;
  for (const rule of trusted) {
    const normalizedRule = normalizeIp(rule);
    if (!normalizedRule) continue;
    if (normalizedRule.includes('/')) {
      if (matchesCidr(ip, normalizedRule)) return true;
      continue;
    }
    if (ip === normalizedRule) return true;
  }
  return false;
}

function proxyPrincipal(request: {
  headers: Record<string, string | string[] | undefined>;
}): { homelab-user: string; role: 'user' | 'admin' | 'superadmin' } {
  const provider = appEnv.authProxyProvider;
  if (provider === 'authentik') {
    const homelab-user =
      proxyHeader(request, 'x-authentik-homelab-user') ||
      proxyHeader(request, 'x-authentik-email') ||
      proxyHeader(request, appEnv.authProxyUserHeader);
    const groups = proxyHeader(request, 'x-authentik-groups');
    return {
      homelab-user: normalizeProxyUsername(homelab-user),
      role: clampAllowedRole(groups ? roleFromGroups(groups) : appEnv.authProxyDefaultRole),
    };
  }
  if (provider === 'authelia') {
    const homelab-user =
      proxyHeader(request, 'remote-user') ||
      proxyHeader(request, 'remote-email') ||
      proxyHeader(request, appEnv.authProxyUserHeader);
    const groups = proxyHeader(request, 'remote-groups');
    return {
      homelab-user: normalizeProxyUsername(homelab-user),
      role: clampAllowedRole(groups ? roleFromGroups(groups) : appEnv.authProxyDefaultRole),
    };
  }
  if (provider === 'oauth2-proxy') {
    const homelab-user =
      proxyHeader(request, 'x-forwarded-user') ||
      proxyHeader(request, 'x-forwarded-email') ||
      proxyHeader(request, appEnv.authProxyUserHeader);
    const groups = proxyHeader(request, 'x-forwarded-groups');
    return {
      homelab-user: normalizeProxyUsername(homelab-user),
      role: clampAllowedRole(groups ? roleFromGroups(groups) : appEnv.authProxyDefaultRole),
    };
  }
  if (provider === 'traefik-forward-auth' || provider === 'traefik' || provider === 'keycloak') {
    const homelab-user =
      proxyHeader(request, 'x-forwarded-preferred-homelab-user') ||
      proxyHeader(request, 'x-forwarded-user') ||
      proxyHeader(request, appEnv.authProxyUserHeader);
    const groups = proxyHeader(request, 'x-forwarded-groups');
    return {
      homelab-user: normalizeProxyUsername(homelab-user),
      role: clampAllowedRole(groups ? roleFromGroups(groups) : appEnv.authProxyDefaultRole),
    };
  }
  const homelab-user =
    proxyHeader(request, appEnv.authProxyUserHeader) ||
    proxyHeader(request, appEnv.authProxyEmailHeader);
  const groups = proxyHeader(request, appEnv.authProxyGroupsHeader);
  const roleRaw = proxyHeader(request, appEnv.authProxyRoleHeader);
  return {
    homelab-user: normalizeProxyUsername(homelab-user),
    role: clampAllowedRole(groups ? roleFromGroups(groups) : roleFromProxy(roleRaw)),
  };
}

const supportedProxyProviders = [
  'generic',
  'authentik',
  'authelia',
  'oauth2-proxy',
  'traefik-forward-auth',
  'keycloak',
] as const;

const proxyProvidersResponse = {
  enabled: true,
  configured_provider: appEnv.authProxyProvider,
  supported_providers: [...supportedProxyProviders],
} as const;

export const fastifyBaseRoutes: FastifyPluginAsync = async (app) => {
  app.post('/telemetry/web-vitals', async (request, reply) => {
    const parsed = webVitalsPayloadSchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    request.log.info({
      event: 'telemetry.web_vitals.accepted',
      telemetry_type: 'web_vitals',
      request_id: request.id,
      metric_name: parsed.data.metric.name,
      metric_rating: parsed.data.metric.rating,
      metric_value: parsed.data.metric.value,
      metric_delta: parsed.data.metric.delta,
      navigation_type: parsed.data.metric.navigationType,
      page_path: parsed.data.page.path,
      page_href: parsed.data.page.href,
      captured_at: parsed.data.capturedAt,
    });
    reply.code(202).send({ status: 'accepted' });
  });

  app.get('/telemetry/consent-region', async (request, reply) => {
    const headers = (request.headers ?? {}) as IncomingHttpHeaders;
    const { region, source } = resolvePublicConsentRegion(headers, {
      force: appEnv.forceConsentRegion,
      countryHeaderLower: appEnv.consentCountryHeader,
    });
    reply.send({ region, source });
  });

  app.post(
    '/telemetry/consent',
    {
      config: {
        rateLimit: {
          max: 60,
          timeWindow: '1 minute',
        },
      },
    },
    async (request, reply) => {
    const parsed = telemetryConsentBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const baseLog = {
      event: 'telemetry.cookie_consent' as const,
      telemetry_type: 'cookie_consent' as const,
      request_id: request.id,
      source: parsed.data.source ?? 'unknown',
      client_ts: parsed.data.clientTs ?? null,
    };
    if (parsed.data.mode === 'simple') {
      request.log.info({
        ...baseLog,
        consent_mode: 'simple',
        choice: parsed.data.choice,
      });
    } else {
      request.log.info({
        ...baseLog,
        consent_mode: 'granular',
        necessary: parsed.data.necessary,
        functional: parsed.data.functional,
        analytics: parsed.data.analytics,
        marketing: parsed.data.marketing,
        consent_region: parsed.data.consentRegion ?? null,
      });
    }
    reply.code(202).send({ status: 'accepted' });
  },
  );

  app.get('/platform/webhooks/info', async (request, reply) => {
    if (!platformWebhooksEnabled()) {
      const err = replyJsonError(
        request.id,
        404,
        'NOT_FOUND',
        'Platform webhooks are disabled. Set ENABLE_PLATFORM_WEBHOOKS=true to enable.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.send({
      enabled: true,
      providers: platformProviders(),
      auth: 'x-platform-webhook-token',
      stored_fields: ['provider', 'event_type', 'delivery_id', 'subject_id_hash', 'received_at'],
    });
  });

  app.post<{ Params: { provider: string } }>('/platform/webhooks/:provider', async (request, reply) => {
    if (!platformWebhooksEnabled()) {
      const err = replyJsonError(
        request.id,
        404,
        'NOT_FOUND',
        'Platform webhooks are disabled. Set ENABLE_PLATFORM_WEBHOOKS=true to enable.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const provider = singleString(request.params.provider)?.trim().toLowerCase() ?? '';
    if (!isPlatformProvider(provider)) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Unknown platform webhook provider.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const expectedToken = platformWebhookSharedSecret();
    if (!expectedToken) {
      const err = replyJsonError(
        request.id,
        503,
        'SERVICE_UNAVAILABLE',
        'Platform webhooks are enabled but PLATFORM_WEBHOOK_SHARED_SECRET is unset.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const supplied =
      typeof request.headers['x-platform-webhook-token'] === 'string'
        ? request.headers['x-platform-webhook-token'].trim()
        : '';
    if (!supplied || supplied !== expectedToken) {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Missing or invalid x-platform-webhook-token.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const body = (request.body ?? {}) as Record<string, unknown>;
    const challenge =
      typeof body.challenge === 'string' && body.challenge.trim() !== '' ? body.challenge : null;
    const eventType =
      typeof body.type === 'string'
        ? body.type
        : typeof body.event_type === 'string'
          ? body.event_type
          : typeof body.subscription === 'object' &&
              body.subscription != null &&
              typeof (body.subscription as { type?: unknown }).type === 'string'
            ? ((body.subscription as { type: string }).type ?? '')
            : 'unknown';
    const deliveryId =
      (typeof request.headers['x-delivery-id'] === 'string' ? request.headers['x-delivery-id'] : '') ||
      (typeof body.id === 'string' ? body.id : '');
    const eventObj =
      typeof body.event === 'object' && body.event != null
        ? (body.event as Record<string, unknown>)
        : null;
    const subjectRaw =
      eventObj != null && typeof eventObj.user_id === 'string'
        ? eventObj.user_id
        : eventObj != null && typeof eventObj.channel_id === 'string'
          ? eventObj.channel_id
          : null;
    const salt = appEnv.platformWebhookIdHashSalt;
    const subjectHash =
      typeof subjectRaw === 'string' && subjectRaw.trim() !== ''
        ? createHash('sha256').update(`${salt}:${subjectRaw.trim()}`).digest('hex')
        : null;

    const auditEntry = {
      action: `platform.webhook.${provider}`,
      actor: 'platform_webhook',
      target: provider,
      details: {
        provider,
        event_type: eventType || 'unknown',
        delivery_id: deliveryId || null,
        subject_id_hash: subjectHash,
        received_at: new Date().toISOString(),
      },
    };
    await AuditLog.create(auditEntry);
    observeIntegrationEvent(`platform_webhook_${provider}`);
    sinkAuditLog(auditEntry as Record<string, unknown>);
    notifyWebhook('platform.webhook.accepted', auditEntry as Record<string, unknown>);
    if (challenge) {
      reply.code(200).type('text/plain').send(challenge);
      return;
    }
    reply.code(202).send({ status: 'accepted' });
  });

  app.get('/s/:slug', async (request, reply) => {
    const slugParam = (request.params as { slug?: unknown }).slug;
    const slugRaw =
      singleString(
        typeof slugParam === 'string' || Array.isArray(slugParam) ? slugParam : undefined,
      )
        ?.trim()
        .toLowerCase();
    if (!slugRaw) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Slug is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findOne({ where: { vanitySlug: slugRaw }, attributes: ['id'] });
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Slug not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const pollId = String(poll.get('id'));
    reply.redirect(publicPollPageUrl(toAppRequest(request), pollId), 302);
  });

  app.get('/status/history', async (request, reply) => {
    const query = (request.query ?? {}) as Record<string, unknown>;
    const windowHoursRaw = query.windowHours;
    const windowHours = parseBoundedInt(
      firstQueryParam(
        typeof windowHoursRaw === 'string' || Array.isArray(windowHoursRaw)
          ? windowHoursRaw
          : undefined,
      ),
      {
      min: 1,
      max: 24 * 30,
      defaultValue: 24,
      },
    );
    let rows: Array<{ readiness_ok: boolean; createdAt: string }> = [];
    try {
      const [rowsRaw] = await sequelize.query(
        `
        SELECT readiness_ok, "createdAt"
        FROM status_probe_snapshots
        WHERE "createdAt" >= NOW() - (:windowHours * INTERVAL '1 hour')
        ORDER BY "createdAt" ASC
        `,
        { replacements: { windowHours } },
      );
      rows = rowsRaw as Array<{ readiness_ok: boolean; createdAt: string }>;
    } catch (err: unknown) {
      if (!appEnv.incidentMode) throw err;
      request.log.warn(
        { event: 'status.history.fallback_incident_mode', requestId: request.id },
        'status history fallback',
      );
      reply.send({
        windowHours,
        generatedAt: new Date().toISOString(),
        sampleCount: 0,
        uptimePct: null,
        incidents: [
          {
            startedAt: new Date().toISOString(),
            endedAt: null,
            summary: 'Incident mode is active; live history backend is bypassed.',
            status: 'investigating',
            durationMinutes: null,
          },
        ],
      });
      return;
    }
    const total = rows.length;
    const readyCount = rows.reduce((acc, row) => acc + (row.readiness_ok ? 1 : 0), 0);
    const uptimePct = total > 0 ? Number(((readyCount / total) * 100).toFixed(2)) : null;
    const incidents: Array<{
      startedAt: string;
      endedAt: string | null;
      summary: string;
      status: 'investigating' | 'resolved';
      durationMinutes: number | null;
    }> = [];
    let activeStartMs: number | null = null;
    for (const row of rows) {
      const ts = Date.parse(row.createdAt);
      if (!Number.isFinite(ts)) continue;
      if (!row.readiness_ok && activeStartMs == null) {
        activeStartMs = ts;
        continue;
      }
      if (row.readiness_ok && activeStartMs != null) {
        const durationMs = Math.max(0, ts - activeStartMs);
        incidents.push({
          startedAt: new Date(activeStartMs).toISOString(),
          endedAt: new Date(ts).toISOString(),
          summary: 'Readiness degraded (database unavailable) and then recovered.',
          status: 'resolved',
          durationMinutes: Math.max(1, Math.round(durationMs / 60_000)),
        });
        activeStartMs = null;
      }
    }
    if (activeStartMs != null) {
      incidents.push({
        startedAt: new Date(activeStartMs).toISOString(),
        endedAt: null,
        summary: 'Readiness is currently degraded (database unavailable).',
        status: 'investigating',
        durationMinutes: Math.max(1, Math.round((Date.now() - activeStartMs) / 60_000)),
      });
    }
    reply.send({
      windowHours,
      generatedAt: new Date().toISOString(),
      sampleCount: total,
      uptimePct,
      incidents: incidents.reverse(),
    });
  });

  app.post('/auth/register', async (request, reply) => {
    const parsed = authRegisterBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const { homelab-user, password } = parsed.data;
    const result = await registerUser({ homelab-user, password });
    if (result.kind === 'signups_disabled') {
      const err = replyJsonError(request.id, 403, 'SIGNUPS_DISABLED', 'New registrations are disabled.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.code(201).send(presentAuthSuccess(result));
  });

  app.post('/auth/proxy-login', async (request, reply) => {
    if (!appEnv.authProxyEnabled) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (!isTrustedProxyIp(request.ip)) {
      observeIntegrationEvent('auth_proxy_untrusted_ip');
      const err = replyJsonError(
        request.id,
        403,
        'FORBIDDEN',
        'Auth proxy login denied: request IP is not in AUTH_PROXY_TRUSTED_IPS.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const principal = proxyPrincipal(request);
    const homelab-user = principal.homelab-user;
    if (!homelab-user) {
      observeIntegrationEvent('auth_proxy_header_missing');
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Missing auth proxy identity headers for configured provider.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const role = principal.role;
    let user = await User.findOne({ where: { homelab-user } });
    if (!user && !appEnv.authProxyAutoProvision) {
      observeIntegrationEvent('auth_proxy_provision_denied');
      const err = replyJsonError(
        request.id,
        403,
        'FORBIDDEN',
        'Auth proxy user is not provisioned and AUTH_PROXY_AUTO_PROVISION=false.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (!user) {
      const generatedPassword = `proxy-${randomBytes(24).toString('hex')}`;
      user = await User.create({
        homelab-user,
        password: hashPassword(generatedPassword),
        role,
        active: true,
      });
      await ensureDefaultWorkspaceForUser(user);
      observeIntegrationEvent('auth_proxy_auto_provision');
    } else if ((user.get('role') as string) !== role && appEnv.authProxyAllowedRoles.includes(role)) {
      user.set('role', role);
      await user.save();
      observeIntegrationEvent('auth_proxy_role_sync');
    }
    const responsePayload = {
      user: {
        id: user.get('id') as number,
        homelab-user: user.get('homelab-user') as string,
        role: user.get('role') as string,
      },
      token: generateToken({
        id: user.get('id') as number,
        homelab-user: user.get('homelab-user') as string,
        role: user.get('role') as string,
      }),
    };
    observeIntegrationEvent('auth_proxy_login');
    reply.send(presentAuthSuccess(responsePayload));
  });

  app.get('/auth/proxy/providers', async (request, reply) => {
    if (!appEnv.authProxyEnabled) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.send(proxyProvidersResponse);
  });

  app.post('/auth/login', async (request, reply) => {
    const parsed = authLoginBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const { homelab-user, password } = parsed.data;
    const result = await loginUser({ homelab-user, password });
    if (result.kind === 'invalid_credentials') {
      const err = replyJsonError(request.id, 401, 'UNAUTHORIZED', 'Invalid credentials');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'account_disabled') {
      const err = replyJsonError(request.id, 403, 'ACCOUNT_DISABLED', 'Account is suspended.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.send(presentAuthSuccess(result));
  });

  app.get('/profile', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const result = await getProfileService({ userId: request.user?.id ?? null });
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.send(presentProfile({ user: result.user }));
  });

  app.get('/profile/billing', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const portal = appEnv.polarCustomerPortalUrl || null;
    const team = appEnv.polarCheckoutCloudTeamUrl || null;
    const pro = appEnv.polarCheckoutCloudProUrl || null;
    const profile = await getProfileService({ userId: request.user?.id ?? null });
    const billingPlan = profile.kind === 'ok' ? profile.user.billingPlan : 'free';
    const uid = request.user?.id ?? null;
    const polarWorkspace =
      uid != null ? await findWorkspacePolarSubscriptionFields(uid) : { polarSubscriptionId: null, polarSubscriptionStatus: null };
    const subscription =
      polarWorkspace.polarSubscriptionId != null
        ? {
            polarStatus: polarWorkspace.polarSubscriptionStatus,
            pastDue: polarWorkspace.polarSubscriptionStatus === 'past_due',
          }
        : undefined;
    const selfhostProLicense = billingPlan === 'selfhost-pro' ? evaluateSelfhostProLicenseState() : undefined;
    let usage:
      | {
          limitsEnforced: false;
          usageLedger?: BillingUsageLedgerEntry[];
          usageLedgerDaily?: BillingUsageLedgerDailyRollupEntry[];
          usageReconcile?: {
            generatedAt: string;
            checks: Array<{
              meter:
                | 'data_exports'
                | 'campaign_attribution'
                | 'poll_webhook_delivery'
                | 'api_rate_limit'
                | 'ws_fanout';
              window: 'utc_day';
              derived: number | null;
              raw: number | null;
              status: 'ok' | 'mismatch' | 'unavailable';
            }>;
          };
        }
      | {
          limitsEnforced: true;
          usageLedger?: BillingUsageLedgerEntry[];
          usageLedgerDaily?: BillingUsageLedgerDailyRollupEntry[];
          usageReconcile?: {
            generatedAt: string;
            checks: Array<{
              meter:
                | 'data_exports'
                | 'campaign_attribution'
                | 'poll_webhook_delivery'
                | 'api_rate_limit'
                | 'ws_fanout';
              window: 'utc_day';
              derived: number | null;
              raw: number | null;
              status: 'ok' | 'mismatch' | 'unavailable';
            }>;
          };
          activePolls: number;
          maxActivePolls: number;
          votesThisMonth: number;
          maxVotesPerMonth: number;
          maxWsSubscribersPerPoll: number;
          exportsToday: number;
          maxExportsPerDay: number;
          maxPollLiveFanoutPerSec: number;
          /** In-process counter for this UTC minute; omits when plan has no finite webhook cap. */
          webhookDeliveriesThisUtcMinute?: number;
          maxWebhookDeliveriesPerUtcMinute?: number;
          campaignAttributionIncrementsToday?: number;
          maxCampaignAttributionPerUtcDay?: number;
          warnings?: BillingUsageWarnings;
        };
    const usageLedger =
      uid != null ? await listRecentBillingUsageLedgerForWorkspace({ workspaceUserId: uid, limit: 25 }) : [];
    const usageLedgerDaily =
      uid != null ? await listDailyBillingUsageRollupsForWorkspace({ workspaceUserId: uid, days: 14 }) : [];
    if (appEnv.billingEnforceLimits && uid != null) {
      const month = utcCalendarMonthBounds();
      const maxActivePolls = maxActivePollsForBillingPlan(billingPlan);
      const maxVotesPerMonth = maxVotesPerMonthForBillingPlan(billingPlan);
      const maxExportsPerDay = maxDataExportsPerDayForBillingPlan(billingPlan);
      const [activePolls, votesThisMonth, maxWsSubscribersPerPoll, exportsToday, webhookScopeKey] =
        await Promise.all([
          countNonArchivedPollsOwnedByUser(uid),
          countBillableVotesForCreatorUtcMonth({
            creatorUserId: uid,
            monthStart: month.start,
            monthEndExclusive: month.endExclusive,
          }),
          resolveEffectivePollLiveRoomCap(uid),
          countCompletedDataExportsForWorkspaceUtcDay(uid),
          resolveWebhookDeliveryScopeKeyForSignedInUser(uid),
        ]);
      const hookMeter =
        webhookScopeKey != null
          ? readPollWebhookDeliveryMeterForScope(webhookScopeKey, billingPlan)
          : { current: 0, max: 0, metered: false };
      const attrMeter =
        webhookScopeKey != null
          ? readCampaignAttributionDayMeter(webhookScopeKey, billingPlan)
          : { current: 0, max: 0, metered: false };
      const warnings = buildBillingUsageWarnings({
        activePolls,
        maxActivePolls,
        votesThisMonth,
        maxVotesPerMonth,
        exportsToday,
        maxExportsPerDay,
        ...(hookMeter.metered
          ? {
              pollWebhookDeliveriesThisUtcMinute: hookMeter.current,
              maxPollWebhookDeliveriesPerUtcMinute: hookMeter.max,
            }
          : {}),
        ...(attrMeter.metered
          ? {
              campaignAttributionIncrementsToday: attrMeter.current,
              maxCampaignAttributionPerUtcDay: attrMeter.max,
            }
          : {}),
      });
      const todayUtc = new Date().toISOString().slice(0, 10);
      const exportDerivedToday =
        usageLedgerDaily.find((r) => r.dayUtc === todayUtc && r.action === 'usage.data_export')?.amount ?? 0;
      const campaignShedDerivedToday =
        usageLedgerDaily.find((r) => r.dayUtc === todayUtc && r.action === 'usage.campaign_attribution_shed')
          ?.amount ?? 0;
      const pollWebhookShedDerivedToday =
        usageLedgerDaily.find((r) => r.dayUtc === todayUtc && r.action === 'usage.poll_webhook_delivery_shed')
          ?.amount ?? 0;
      const apiRateDerivedToday =
        usageLedgerDaily.find((r) => r.dayUtc === todayUtc && r.action === 'usage.api_rate_limited')?.amount ?? 0;
      const wsFanoutDerivedToday =
        usageLedgerDaily.find((r) => r.dayUtc === todayUtc && r.action === 'usage.ws_fanout_shed')?.amount ?? 0;
      const rawUsageToday = await countBillingUsageActionsForWorkspaceUtcDay({ workspaceUserId: uid });
      const usageReconcile = {
        generatedAt: new Date().toISOString(),
        checks: [
          {
            meter: 'data_exports' as const,
            window: 'utc_day' as const,
            derived: exportDerivedToday,
            raw: rawUsageToday.dataExport,
            status: exportDerivedToday === rawUsageToday.dataExport ? ('ok' as const) : ('mismatch' as const),
          },
          {
            meter: 'campaign_attribution' as const,
            window: 'utc_day' as const,
            derived: campaignShedDerivedToday,
            raw: rawUsageToday.campaignAttributionShed,
            status:
              campaignShedDerivedToday === rawUsageToday.campaignAttributionShed
                ? ('ok' as const)
                : ('mismatch' as const),
          },
          {
            meter: 'poll_webhook_delivery' as const,
            window: 'utc_day' as const,
            derived: pollWebhookShedDerivedToday,
            raw: rawUsageToday.pollWebhookDeliveryShed,
            status:
              pollWebhookShedDerivedToday === rawUsageToday.pollWebhookDeliveryShed
                ? ('ok' as const)
                : ('mismatch' as const),
          },
          {
            meter: 'api_rate_limit' as const,
            window: 'utc_day' as const,
            derived: apiRateDerivedToday,
            raw: rawUsageToday.apiRateLimited,
            status:
              apiRateDerivedToday === rawUsageToday.apiRateLimited ? ('ok' as const) : ('mismatch' as const),
          },
          {
            meter: 'ws_fanout' as const,
            window: 'utc_day' as const,
            derived: wsFanoutDerivedToday,
            raw: rawUsageToday.wsFanoutShed,
            status:
              wsFanoutDerivedToday === rawUsageToday.wsFanoutShed ? ('ok' as const) : ('mismatch' as const),
          },
        ],
      };
      usage = {
        limitsEnforced: true,
        usageLedger,
        ...(usageLedgerDaily.length > 0 ? { usageLedgerDaily } : {}),
        usageReconcile,
        activePolls,
        maxActivePolls,
        votesThisMonth,
        maxVotesPerMonth,
        maxWsSubscribersPerPoll,
        exportsToday,
        maxExportsPerDay,
        maxPollLiveFanoutPerSec: effectiveWsFanoutMessagesPerSecondForWorkspace(uid),
        ...(hookMeter.metered
          ? {
              webhookDeliveriesThisUtcMinute: hookMeter.current,
              maxWebhookDeliveriesPerUtcMinute: hookMeter.max,
            }
          : {}),
        ...(attrMeter.metered
          ? {
              campaignAttributionIncrementsToday: attrMeter.current,
              maxCampaignAttributionPerUtcDay: attrMeter.max,
            }
          : {}),
        ...(warnings ? { warnings } : {}),
      };
    } else {
      usage = {
        limitsEnforced: false,
        ...(usageLedger.length > 0 ? { usageLedger } : {}),
        ...(usageLedgerDaily.length > 0 ? { usageLedgerDaily } : {}),
        usageReconcile: {
          generatedAt: new Date().toISOString(),
          checks: [
            { meter: 'data_exports', window: 'utc_day', derived: null, raw: null, status: 'unavailable' },
            { meter: 'campaign_attribution', window: 'utc_day', derived: null, raw: null, status: 'unavailable' },
            { meter: 'poll_webhook_delivery', window: 'utc_day', derived: null, raw: null, status: 'unavailable' },
            { meter: 'api_rate_limit', window: 'utc_day', derived: null, raw: null, status: 'unavailable' },
            { meter: 'ws_fanout', window: 'utc_day', derived: null, raw: null, status: 'unavailable' },
          ],
        },
      };
    }
    reply.send(
      presentPolarBillingLinks({
        customerPortalUrl: portal,
        checkoutCloudTeamUrl: team,
        checkoutCloudProUrl: pro,
        billingPlan,
        usage,
        subscription,
        ...(selfhostProLicense ? { selfhostProLicense } : {}),
      }),
    );
  });

  app.get('/profile/export', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const sessionUserId = request.user?.id ?? null;
    if (sessionUserId != null) {
      const exportQuota = await checkDailyDataExportQuotaForWorkspace({
        workspaceUserId: sessionUserId,
      });
      if (!exportQuota.ok) {
        const err = replyJsonError(
          request.id,
          403,
          'USAGE_LIMIT_EXPORTS',
          'Daily data export limit reached for this billing plan.',
          {
            max: exportQuota.max,
            current: exportQuota.current,
            plan: exportQuota.plan,
          },
        );
        reply.code(err.statusCode).send(err.body);
        return;
      }
    }
    const result = await exportSelfDataService({ userId: request.user?.id ?? null });
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (sessionUserId != null) {
      await recordDataExportJob({ workspaceUserId: sessionUserId, kind: 'self' });
    }
    const uid = request.user?.id ?? 'user';
    const filename = `asking-ng-data-export-${uid}.json`;
    reply
      .header('Content-Type', 'application/json; charset=utf-8')
      .header('Content-Disposition', `attachment; filename="${filename}"`)
      .send(JSON.stringify(result.payload, null, 2));
  });

  app.put('/profile', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const parsed = profileUpdateBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const userId = request.user?.id ?? null;
    const result = await updateProfileService({
      userId,
      body: parsed.data,
    });
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (userId != null) invalidateSessionUserCache(userId);
    reply.send(presentProfile({ user: result.user }));
  });

  app.post('/users/reset-password', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const parsed = selfPasswordChangeBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const userId = request.user?.id ?? null;
    const result = await updateSelfPasswordService({
      userId,
      body: parsed.data,
    });
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_credentials') {
      const err = replyJsonError(request.id, 401, 'UNAUTHORIZED', 'Invalid credentials');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (userId != null) invalidateSessionUserCache(userId);
    reply.send(presentPasswordUpdated());
  });

  app.delete('/profile', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const parsed = selfDeleteBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const userId = request.user?.id ?? null;
    const result = await deleteSelfService({
      userId,
      body: parsed.data,
    });
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_credentials') {
      const err = replyJsonError(request.id, 401, 'UNAUTHORIZED', 'Invalid credentials');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (userId != null) invalidateSessionUserCache(userId);
    reply.send(presentSelfDeleted());
  });

  app.get('/users', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const result = await listUsersService({ actorRole: request.user?.role ?? null });
    if (result.kind === 'forbidden') {
      const err = replyJsonError(request.id, 403, 'FORBIDDEN', 'Admin only');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.send(presentUsersList({ users: result.users }));
  });

  app.get<{ Params: { id: string } }>('/users/:id', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const result = await getUserService({
      actorRole: request.user?.role ?? null,
      actorUserId: request.user?.id ?? null,
      userIdRaw: singleString(request.params.id) ?? null,
    });
    if (result.kind === 'invalid_id') {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Invalid user id');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'forbidden') {
      const err = replyJsonError(request.id, 403, 'FORBIDDEN', 'You can only view your own user record');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.send(result.user);
  });

  app.post('/users', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const parsed = createUserBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const result = await createUserService({
      actorRole: request.user?.role ?? null,
      body: parsed.data,
    });
    if (result.kind === 'forbidden') {
      const err = replyJsonError(request.id, 403, 'FORBIDDEN', 'Admin only');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'forbidden_superadmin') {
      const err = replyJsonError(
        request.id,
        403,
        'FORBIDDEN',
        'Only superadmin can create users with the superadmin role',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.code(201).send(presentUser({ user: result.user }));
  });

  app.delete<{ Params: { id: string } }>('/users/:id', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const result = await deleteUserService({
      actorRole: request.user?.role ?? null,
      userIdRaw: singleString(request.params.id) ?? null,
    });
    if (result.kind === 'forbidden') {
      const err = replyJsonError(request.id, 403, 'FORBIDDEN', 'Admin only');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_id') {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Invalid user id');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    invalidateSessionUserCache(result.deletedId);
    reply.send(presentDeletedUserMessage(result.deletedId));
  });

  app.patch<{ Params: { id: string } }>('/users/:id/role', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const parsed = rolePatchBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const result = await patchUserRoleService({
      actorRole: request.user?.role ?? null,
      userIdRaw: singleString(request.params.id) ?? null,
      body: parsed.data,
    });
    if (result.kind === 'forbidden') {
      const err = replyJsonError(request.id, 403, 'FORBIDDEN', 'Admin only');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_id') {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Invalid user id');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'forbidden_modify_superadmin') {
      const err = replyJsonError(request.id, 403, 'FORBIDDEN', 'Only superadmin can modify a superadmin account');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'forbidden_assign_superadmin') {
      const err = replyJsonError(request.id, 403, 'FORBIDDEN', 'Only superadmin can assign the superadmin role');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    invalidateSessionUserCache(result.updatedId);
    reply.send(presentUser({ user: result.user }));
  });

  app.post<{ Params: { id: string } }>('/users/:id/reset-password', async (request, reply) => {
    if (!(await requireSession(request, reply))) return;
    const parsed = setPasswordBodySchema.safeParse(request.body);
    if (!parsed.success) {
      const err = replyJsonError(
        request.id,
        400,
        'VALIDATION_ERROR',
        'Invalid request',
        parsed.error.flatten(),
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const result = await resetUserPasswordService({
      actorRole: request.user?.role ?? null,
      userIdRaw: singleString(request.params.id) ?? null,
      body: parsed.data,
    });
    if (result.kind === 'forbidden') {
      const err = replyJsonError(request.id, 403, 'FORBIDDEN', 'Admin only');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_id') {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Invalid user id');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    invalidateSessionUserCache(result.updatedId);
    reply.send(presentPasswordResetMessage());
  });
};
