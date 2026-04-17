import { adminPollWriteBodySchema } from '@asking-ng/contracts/admin';
import type { FastifyPluginAsync } from 'fastify';
import { Op, QueryTypes } from 'sequelize';
import sequelize from '../connections';
import randomId from '../helpers/randomId';
import { timingSafeAdminTokenEqual } from '../lib/adminToken';
import {
  getRetentionPolicySettings,
  getSignupsEnabled,
  getVoteGeoEnabled,
  setRetentionPolicySettings,
  setSignupsEnabled,
  setVoteGeoEnabled,
} from '../lib/appSettings';
import { countCompletedDataExportsForWorkspaceUtcDay } from '../lib/billingExportQuota';
import {
  hasExtendedRetentionForBillingPlan,
  hasWebhookAutomationForBillingPlan,
  type KnownBillingPlan,
  maxActivePollsForBillingPlan,
  maxDataExportsPerDayForBillingPlan,
  maxVotesPerMonthForBillingPlan,
  normalizeBillingPlan,
  utcCalendarMonthBounds,
} from '../lib/billingLimits';
import { appEnv } from '../lib/env';
import { notifyWebhook, sinkAuditLog } from '../lib/integrationWebhooks';
import { reconcilePolarSubscriptionsFromApi } from '../lib/polarSubscriptionReconcile';
import { notifyPollLive } from '../lib/pollLive';
import { readPollWebhookDeliveryTelemetry } from '../lib/pollWebhookDeliveryTelemetry';
import { queuePollWebhook } from '../lib/pollWebhooks';
import {
  getGlobalTimeBinsFromRollups,
  getGlobalVoteRollups,
  reconcilePollVoteRollups,
  refreshPollVoteRollupsIfStale,
  refreshPollVoteRollupsNow,
} from '../lib/readModelRollups';
import { resolveWorkspaceIdForCreatorUserId } from '../lib/workspaceBootstrap';
import { authenticateBearer, isJwtAdminRole } from '../middleware/requireSession';
import Poll from '../model/Poll';
import Vote from '../model/Vote';
import AuditLog from '../models/auditlog.sequelize';
import User from '../models/user.sequelize';
import { replyJsonError, toAppRequest } from './requestAdapter';

const adminOperatorRoles = ['mod', 'admin', 'superadmin'] as const;
const adminElevatedRoles = ['admin', 'superadmin'] as const;

function isAllowedJwtRole(
  role: string,
  allowedRoles: ReadonlyArray<(typeof adminOperatorRoles)[number]>,
): boolean {
  return allowedRoles.includes(role as (typeof adminOperatorRoles)[number]);
}

async function requireAdminAuth(
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
  allowedRoles: ReadonlyArray<(typeof adminOperatorRoles)[number]> = adminElevatedRoles,
): Promise<boolean> {
  const token =
    typeof request.headers?.['x-admin-token' as never] === 'string'
      ? (request.headers?.['x-admin-token' as never] as string)
      : undefined;
  if (timingSafeAdminTokenEqual(token, appEnv.adminToken || 'changeme')) return true;

  const reqLike = toAppRequest(request);
  const bearerOk = await authenticateBearer(reqLike, null);
  if (bearerOk && reqLike.user && isAllowedJwtRole(reqLike.user.role, allowedRoles)) {
    request.user = reqLike.user;
    if (request.context) {
      request.context.userId = reqLike.user.id;
      request.context.homelab-user = reqLike.user.homelab-user;
      request.context.role = reqLike.user.role;
    }
    return true;
  }
  if (bearerOk && reqLike.user && !isJwtAdminRole(reqLike.user.role)) {
    const allowedList = allowedRoles.join(', ');
    const err = replyJsonError(
      request.id,
      403,
      'FORBIDDEN',
      `Admin API requires one of roles: ${allowedList}, or a valid admin token.`,
    );
    reply.code(err.statusCode).send(err.body);
    return false;
  }
  const err = replyJsonError(
    request.id,
    401,
    'UNAUTHORIZED',
    'Invalid or missing admin token or admin session.',
  );
  reply.code(err.statusCode).send(err.body);
  return false;
}

async function logAdminAction(
  action: string,
  actor: string,
  target: string | number | null,
  details: unknown,
) {
  const entry = {
    action,
    actor,
    target: target === null || target === undefined ? null : String(target),
    details,
  };
  await AuditLog.create(entry);
  sinkAuditLog(entry as Record<string, unknown>);
  notifyWebhook('admin.action', entry as Record<string, unknown>);
}

export const fastifyAdminRoutes: FastifyPluginAsync = async (app) => {
  app.get('/bootstrap-status', async (_request, reply) => {
    const adminCount = await User.count({ where: { role: { [Op.in]: ['admin', 'superadmin'] } } });
    const adminTokenIsDefault = !appEnv.adminToken || appEnv.adminToken === 'changeme';
    reply.send({
      noAdminExists: adminCount === 0,
      adminTokenIsDefault,
    });
  });

  app.get('/me', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    if (request.user && isAllowedJwtRole(request.user.role, adminOperatorRoles)) {
      reply.send({
        admin: {
          id: request.user.id,
          homelab-user: request.user.homelab-user,
          role: request.user.role,
        },
      });
      return;
    }

    const superuser = await User.findOne({
      where: { role: 'superadmin' },
      attributes: ['id', 'homelab-user', 'role'],
    });
    const adminUser =
      superuser ??
      (await User.findOne({
        where: { role: 'admin' },
        attributes: ['id', 'homelab-user', 'role'],
      }));
    if (!adminUser) {
      const err = replyJsonError(
        request.id,
        404,
        'NOT_FOUND',
        'No user with role admin or superadmin. Create one before using the admin UI.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.send({
      admin: {
        id: adminUser.get('id') as number,
        homelab-user: adminUser.get('homelab-user') as string,
        role: adminUser.get('role') as string,
      },
    });
  });

  app.get('/status', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const userCount = await User.count();
    const activeUserCount = await User.count({ where: { active: true } });
    const pollCount = await Poll.count();
    const archivedPollCount = await Poll.count({ where: { archived: true } });
    const recentAuditCount = await AuditLog.count({
      where: { createdAt: { [Op.gte]: new Date(Date.now() - 24 * 60 * 60 * 1000) } },
    });
    let pollMetrics: { total_votes: string | number; votes_last_24h: string | number } | undefined;
    if (appEnv.readModelEnabled) {
      try {
        await refreshPollVoteRollupsIfStale();
        pollMetrics = await getGlobalVoteRollups();
      } catch (err) {
        request.log.warn(
          { event: 'admin.read_model.global_votes_fallback', err },
          'read model unavailable, falling back to votes table',
        );
      }
    }
    if (!pollMetrics) {
      const [fallbackMetrics] = (await sequelize.query(
        `SELECT
          COUNT(*)::int AS total_votes,
          COUNT(*) FILTER (WHERE "createdAt" >= NOW() - INTERVAL '24 hours')::int AS votes_last_24h
         FROM votes`,
        { type: QueryTypes.SELECT },
      )) as Array<{ total_votes: string | number; votes_last_24h: string | number }>;
      pollMetrics = fallbackMetrics;
    }
    let peakHourMetrics: {
      peak_hour_utc: string | number;
      peak_hour_votes: string | number;
    } | null = null;
    let peakDowMetrics: { peak_dow_utc: string | number; peak_dow_votes: string | number } | null =
      null;
    let hourBins: Array<{ hour_utc: string | number; vote_count: string | number }> = [];
    let dowBins: Array<{ dow_utc: string | number; vote_count: string | number }> = [];
    if (appEnv.readModelEnabled) {
      try {
        await refreshPollVoteRollupsIfStale();
        const rollupBins = await getGlobalTimeBinsFromRollups();
        peakHourMetrics = rollupBins.peakHour;
        peakDowMetrics = rollupBins.peakDow;
        hourBins = rollupBins.hourBins;
        dowBins = rollupBins.dowBins;
      } catch (err) {
        request.log.warn(
          { event: 'admin.read_model.time_bins_fallback', err },
          'read model time bins unavailable, falling back to votes table',
        );
      }
    }
    if (hourBins.length === 0 && dowBins.length === 0) {
      const [peakHourRows] = (await sequelize.query(
        `SELECT
          EXTRACT(HOUR FROM "createdAt" AT TIME ZONE 'UTC')::int AS peak_hour_utc,
          COUNT(*)::int AS peak_hour_votes
         FROM votes
         GROUP BY peak_hour_utc
         ORDER BY peak_hour_votes DESC, peak_hour_utc ASC
         LIMIT 1`,
        { type: QueryTypes.SELECT },
      )) as Array<{ peak_hour_utc: string | number; peak_hour_votes: string | number }>;
      peakHourMetrics = peakHourRows ?? null;
      const [peakDowRows] = (await sequelize.query(
        `SELECT
          EXTRACT(DOW FROM "createdAt" AT TIME ZONE 'UTC')::int AS peak_dow_utc,
          COUNT(*)::int AS peak_dow_votes
         FROM votes
         GROUP BY peak_dow_utc
         ORDER BY peak_dow_votes DESC, peak_dow_utc ASC
         LIMIT 1`,
        { type: QueryTypes.SELECT },
      )) as Array<{ peak_dow_utc: string | number; peak_dow_votes: string | number }>;
      peakDowMetrics = peakDowRows ?? null;
      hourBins = (await sequelize.query(
        `SELECT
          EXTRACT(HOUR FROM "createdAt" AT TIME ZONE 'UTC')::int AS hour_utc,
          COUNT(*)::int AS vote_count
         FROM votes
         GROUP BY hour_utc
         ORDER BY hour_utc ASC`,
        { type: QueryTypes.SELECT },
      )) as Array<{ hour_utc: string | number; vote_count: string | number }>;
      dowBins = (await sequelize.query(
        `SELECT
          EXTRACT(DOW FROM "createdAt" AT TIME ZONE 'UTC')::int AS dow_utc,
          COUNT(*)::int AS vote_count
         FROM votes
         GROUP BY dow_utc
         ORDER BY dow_utc ASC`,
        { type: QueryTypes.SELECT },
      )) as Array<{ dow_utc: string | number; vote_count: string | number }>;
    }
    const [firstResponseMetrics] = (await sequelize.query(
      `SELECT AVG(EXTRACT(EPOCH FROM (v.first_vote_at - p."createdAt")) * 1000)::float8 AS avg_time_to_first_vote_ms
       FROM polls p
       JOIN (
         SELECT "pollId", MIN("createdAt") AS first_vote_at
         FROM votes
         GROUP BY "pollId"
       ) v
       ON v."pollId" = p.id`,
      { type: QueryTypes.SELECT },
    )) as Array<{ avg_time_to_first_vote_ms: number | null }>;
    const totalVotes = Number(pollMetrics?.total_votes ?? 0) || 0;
    const votesLast24h = Number(pollMetrics?.votes_last_24h ?? 0) || 0;
    const completionRatePct = pollCount > 0 ? (activeUserCount / pollCount) * 100 : null;
    const avgTimeToFirstVoteMs =
      firstResponseMetrics?.avg_time_to_first_vote_ms != null &&
      Number.isFinite(firstResponseMetrics.avg_time_to_first_vote_ms)
        ? Number(firstResponseMetrics.avg_time_to_first_vote_ms)
        : null;
    const peakHourUtc =
      peakHourMetrics != null && peakHourMetrics.peak_hour_utc !== undefined
        ? Number(peakHourMetrics.peak_hour_utc)
        : null;
    const peakHourVotes =
      peakHourMetrics != null ? Number(peakHourMetrics.peak_hour_votes ?? 0) || 0 : 0;
    const peakDowUtc =
      peakDowMetrics != null && peakDowMetrics.peak_dow_utc !== undefined
        ? Number(peakDowMetrics.peak_dow_utc)
        : null;
    const peakDowVotes =
      peakDowMetrics != null ? Number(peakDowMetrics.peak_dow_votes ?? 0) || 0 : 0;
    const hourlyVotesByHourUtc = Array.from({ length: 24 }, () => 0);
    for (const row of hourBins) {
      const h = Number(row.hour_utc);
      if (!Number.isInteger(h) || h < 0 || h > 23) continue;
      hourlyVotesByHourUtc[h] = Number(row.vote_count) || 0;
    }
    const weekdayVotesByDowUtc = Array.from({ length: 7 }, () => 0);
    for (const row of dowBins) {
      const d = Number(row.dow_utc);
      if (!Number.isInteger(d) || d < 0 || d > 6) continue;
      weekdayVotesByDowUtc[d] = Number(row.vote_count) || 0;
    }
    const [trustTotalsRow] = (await sequelize.query(
      `SELECT
        COUNT(*) FILTER (
          WHERE COALESCE("isQuarantined", false) = true
            AND COALESCE("quarantineStatus", 'pending') = 'pending'
        )::int AS quarantine_pending_total,
        COUNT(DISTINCT "pollId") FILTER (
          WHERE COALESCE("isQuarantined", false) = true
            AND COALESCE("quarantineStatus", 'pending') = 'pending'
        )::int AS quarantine_pending_polls,
        COUNT(*) FILTER (
          WHERE COALESCE("isQuarantined", false) = true
            AND "quarantineStatus" = 'approved'
            AND "quarantineDecidedAt" >= NOW() - INTERVAL '24 hours'
        )::int AS quarantine_approved_last_24h,
        COUNT(*) FILTER (
          WHERE COALESCE("isQuarantined", false) = true
            AND "quarantineStatus" = 'rejected'
            AND "quarantineDecidedAt" >= NOW() - INTERVAL '24 hours'
        )::int AS quarantine_rejected_last_24h,
        AVG("trustRiskScore") FILTER (
          WHERE COALESCE("isQuarantined", false) = true
            AND COALESCE("quarantineStatus", 'pending') = 'pending'
            AND "trustRiskScore" IS NOT NULL
        )::float8 AS trust_risk_avg_pending,
        COUNT(*) FILTER (
          WHERE COALESCE("isQuarantined", false) = true
            AND COALESCE("quarantineStatus", 'pending') = 'pending'
            AND "userId" IS NOT NULL
        )::int AS quarantine_pending_account_linked,
        COUNT(*) FILTER (
          WHERE "createdAt" >= NOW() - INTERVAL '24 hours'
            AND "userId" IS NOT NULL
        )::int AS votes_account_linked_last_24h,
        COUNT(*) FILTER (
          WHERE "createdAt" >= NOW() - INTERVAL '24 hours'
            AND "userId" IS NULL
        )::int AS votes_anonymous_last_24h
       FROM votes`,
      { type: QueryTypes.SELECT },
    )) as Array<{
      quarantine_pending_total: string | number;
      quarantine_pending_polls: string | number;
      quarantine_approved_last_24h: string | number;
      quarantine_rejected_last_24h: string | number;
      trust_risk_avg_pending: number | null;
      quarantine_pending_account_linked: string | number;
      votes_account_linked_last_24h: string | number;
      votes_anonymous_last_24h: string | number;
    }>;
    const reasonRows = (await sequelize.query(
      `SELECT
        COALESCE(NULLIF(TRIM("quarantineReason"), ''), '_unknown') AS reason,
        COUNT(*)::int AS c
       FROM votes
       WHERE COALESCE("isQuarantined", false) = true
         AND COALESCE("quarantineStatus", 'pending') = 'pending'
       GROUP BY 1
       ORDER BY c DESC`,
      { type: QueryTypes.SELECT },
    )) as Array<{ reason: string; c: string | number }>;
    const quarantine_pending_by_reason: Record<string, number> = {};
    for (const row of reasonRows) {
      quarantine_pending_by_reason[String(row.reason)] = Number(row.c) || 0;
    }
    const trustAvgRaw = trustTotalsRow?.trust_risk_avg_pending;
    const trust_risk_avg_pending =
      trustAvgRaw != null && Number.isFinite(trustAvgRaw)
        ? Math.round(Number(trustAvgRaw) * 10) / 10
        : null;
    const retentionPolicy = await getRetentionPolicySettings();
    const webhookDeliveryTelemetry = readPollWebhookDeliveryTelemetry(15);
    reply.send({
      users: { total: userCount, active: activeUserCount },
      polls: { total: pollCount, archived: archivedPollCount },
      auditLogs: { last24h: recentAuditCount },
      creatorMetrics: {
        total_votes: totalVotes,
        votes_last_24h: votesLast24h,
        avg_time_to_first_vote_ms: avgTimeToFirstVoteMs,
        polls_per_active_user_pct: completionRatePct,
        peak_hour_utc: Number.isInteger(peakHourUtc) ? peakHourUtc : null,
        peak_hour_votes: peakHourVotes,
        peak_dow_utc: Number.isInteger(peakDowUtc) ? peakDowUtc : null,
        peak_dow_votes: peakDowVotes,
        hourly_votes_by_hour_utc: hourlyVotesByHourUtc,
        weekday_votes_by_dow_utc: weekdayVotesByDowUtc,
      },
      trustMetrics: {
        quarantine_pending_total: Number(trustTotalsRow?.quarantine_pending_total ?? 0) || 0,
        quarantine_pending_polls: Number(trustTotalsRow?.quarantine_pending_polls ?? 0) || 0,
        quarantine_pending_by_reason,
        quarantine_approved_last_24h:
          Number(trustTotalsRow?.quarantine_approved_last_24h ?? 0) || 0,
        quarantine_rejected_last_24h:
          Number(trustTotalsRow?.quarantine_rejected_last_24h ?? 0) || 0,
        trust_risk_avg_pending,
        quarantine_pending_account_linked:
          Number(trustTotalsRow?.quarantine_pending_account_linked ?? 0) || 0,
        votes_account_linked_last_24h:
          Number(trustTotalsRow?.votes_account_linked_last_24h ?? 0) || 0,
        votes_anonymous_last_24h: Number(trustTotalsRow?.votes_anonymous_last_24h ?? 0) || 0,
      },
      retentionPolicy,
      webhookDeliveryTelemetry,
      timestamp: new Date().toISOString(),
    });
  });

  app.get('/polls', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const polls = await Poll.findAll({
      attributes: ['id', 'title', 'options', 'archived', 'votingPaused', 'mediaModeration'],
      order: [['createdAt', 'DESC']],
    });
    reply.send({
      polls: polls.map((poll) => ({
        id: String(poll.get('id')),
        question: String(poll.get('title') ?? ''),
        options: ((poll.get('options') as string[] | null | undefined) ?? []).map((opt) =>
          String(opt),
        ),
        archived: !!poll.get('archived'),
        voting_paused: !!poll.get('votingPaused'),
        media_moderation_status:
          (poll.get('mediaModeration') as { status?: string } | null | undefined)?.status ??
          'active',
      })),
    });
  });

  app.post('/polls', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const parsed = adminPollWriteBodySchema.safeParse(request.body);
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
    const now = Date.now();
    const workspaceId = await resolveWorkspaceIdForCreatorUserId(request.user?.id ?? null);
    const poll = await Poll.create({
      id: randomId(16),
      api_key: randomId(16),
      title: parsed.data.question,
      options: parsed.data.options,
      expiration: now + 7 * 24 * 60 * 60 * 1000,
      phase: 'open',
      archived: false,
      votingPaused: false,
      creatorUserId: request.user?.id ?? null,
      workspaceId,
    });
    const pollId = String(poll.get('id'));
    notifyPollLive(pollId, { type: 'update' });
    queuePollWebhook(pollId, 'poll_updated', { source: 'admin', created_via_admin: true });
    await logAdminAction('poll_create', request.user?.homelab-user ?? 'admin_token', pollId, {
      role: request.user?.role ?? 'token',
    });
    reply.code(201).send({
      poll: {
        id: pollId,
        question: String(poll.get('title') ?? ''),
        options: ((poll.get('options') as string[] | null | undefined) ?? []).map((opt) =>
          String(opt),
        ),
        archived: !!poll.get('archived'),
        voting_paused: !!poll.get('votingPaused'),
      },
    });
  });

  app.get<{ Params: { id: string } }>('/polls/:id', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findByPk(pollId, {
      attributes: ['id', 'title', 'options', 'archived', 'votingPaused'],
    });
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const options = ((poll.get('options') as string[] | null | undefined) ?? []).map((opt) =>
      String(opt),
    );
    const rows = (await sequelize.query(
      `SELECT option, COUNT(*)::int AS vote_count
       FROM votes
       WHERE "pollId" = :pollId
         AND COALESCE("isQuarantined", false) = false
       GROUP BY option`,
      {
        replacements: { pollId },
        type: QueryTypes.SELECT,
      },
    )) as Array<{ option: string; vote_count: string | number }>;
    const countByOption = new Map<string, number>();
    for (const row of rows) countByOption.set(String(row.option), Number(row.vote_count) || 0);
    reply.send({
      poll: {
        id: String(poll.get('id')),
        question: String(poll.get('title') ?? ''),
        options,
        archived: !!poll.get('archived'),
        voting_paused: !!poll.get('votingPaused'),
        votes: options.map((opt) => countByOption.get(opt) ?? 0),
      },
    });
  });

  app.patch<{ Params: { id: string } }>('/polls/:id', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const parsed = adminPollWriteBodySchema.safeParse(request.body);
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
    const [updatedCount] = await Poll.update(
      {
        title: parsed.data.question,
        options: parsed.data.options,
      },
      { where: { id: pollId } },
    );
    if (!updatedCount) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    notifyPollLive(pollId, { type: 'update' });
    queuePollWebhook(pollId, 'poll_updated', { source: 'admin' });
    await logAdminAction('poll_update', request.user?.homelab-user ?? 'admin_token', pollId, null);
    reply.send({ ok: true });
  });

  app.delete<{ Params: { id: string } }>('/polls/:id', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const deleted = await Poll.destroy({ where: { id: pollId } });
    if (!deleted) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    notifyPollLive(pollId, { type: 'deleted' });
    queuePollWebhook(pollId, 'poll_deleted', { source: 'admin' });
    await logAdminAction('poll_delete', request.user?.homelab-user ?? 'admin_token', pollId, null);
    reply.send({ ok: true });
  });

  app.patch<{ Params: { id: string } }>('/polls/:id/archive', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const [updatedCount] = await Poll.update({ archived: true }, { where: { id: pollId } });
    if (!updatedCount) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    notifyPollLive(pollId, { type: 'update' });
    await logAdminAction('poll_archive', request.user?.homelab-user ?? 'admin_token', pollId, null);
    reply.send({ ok: true });
  });

  app.patch<{ Params: { id: string } }>('/polls/:id/unarchive', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const [updatedCount] = await Poll.update({ archived: false }, { where: { id: pollId } });
    if (!updatedCount) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    notifyPollLive(pollId, { type: 'update' });
    await logAdminAction('poll_unarchive', request.user?.homelab-user ?? 'admin_token', pollId, null);
    reply.send({ ok: true });
  });

  app.post<{ Params: { id: string } }>('/polls/:id/reset-votes', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findByPk(pollId, { attributes: ['id'] });
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    await Vote.destroy({ where: { pollId } });
    notifyPollLive(pollId, { type: 'update' });
    await logAdminAction('poll_reset_votes', request.user?.homelab-user ?? 'admin_token', pollId, null);
    reply.send({ ok: true });
  });

  app.patch<{ Params: { id: string } }>('/polls/:id/pause', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findByPk(pollId, { attributes: ['id', 'archived'] });
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (poll.get('archived')) {
      const err = replyJsonError(
        request.id,
        400,
        'POLL_ARCHIVED',
        'Cannot pause an archived poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const pauseMessageRaw = (request.body as { pause_message?: unknown } | null | undefined)
      ?.pause_message;
    const pauseMessage =
      typeof pauseMessageRaw === 'string' && pauseMessageRaw.trim() !== ''
        ? pauseMessageRaw.trim().slice(0, 280)
        : appEnv.panicPauseMessage || 'Voting is temporarily paused.';
    await Poll.update({ votingPaused: true, pauseMessage }, { where: { id: pollId } });
    notifyPollLive(pollId, { type: 'update' });
    await logAdminAction('poll_pause_voting', request.user?.homelab-user ?? 'admin_token', pollId, {
      pause_message: pauseMessage,
    });
    reply.send({ ok: true, voting_paused: true, pause_message: pauseMessage });
  });

  app.patch<{ Params: { id: string } }>('/polls/:id/unpause', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const [updatedCount] = await Poll.update(
      { votingPaused: false, pauseMessage: null },
      { where: { id: pollId } },
    );
    if (!updatedCount) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    notifyPollLive(pollId, { type: 'update' });
    await logAdminAction(
      'poll_unpause_voting',
      request.user?.homelab-user ?? 'admin_token',
      pollId,
      null,
    );
    reply.send({ ok: true, voting_paused: false });
  });

  app.post<{ Params: { id: string } }>('/polls/:id/media/takedown', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findByPk(pollId, {
      attributes: ['id', 'mediaAttachment', 'mediaModeration'],
    });
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (!poll.get('mediaAttachment')) {
      const err = replyJsonError(
        request.id,
        409,
        'MEDIA_NOT_CONFIGURED',
        'This poll has no media attachment.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const body = (request.body ?? {}) as Record<string, unknown>;
    const reason =
      typeof body['reason'] === 'string' && body['reason'].trim()
        ? body['reason'].trim().slice(0, 500)
        : null;
    const moderation = {
      status: 'takedown',
      reported_reason: reason,
      last_action_at: new Date().toISOString(),
      last_actor: request.user?.homelab-user ?? 'admin_token',
    };
    await Poll.update({ mediaModeration: moderation }, { where: { id: pollId } });
    await logAdminAction('poll_media_takedown', request.user?.homelab-user ?? 'admin_token', pollId, {
      reason,
    });
    reply.send({ ok: true, moderation_status: 'takedown' });
  });

  app.post<{ Params: { id: string } }>('/polls/:id/media/restore', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminOperatorRoles))) return;
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findByPk(pollId, { attributes: ['id'] });
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const moderation = {
      status: 'active',
      reported_reason: null,
      last_action_at: new Date().toISOString(),
      last_actor: request.user?.homelab-user ?? 'admin_token',
    };
    await Poll.update({ mediaModeration: moderation }, { where: { id: pollId } });
    await logAdminAction(
      'poll_media_restore',
      request.user?.homelab-user ?? 'admin_token',
      pollId,
      null,
    );
    reply.send({ ok: true, moderation_status: 'active' });
  });

  app.post('/read-model/refresh', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply))) return;
    if (!appEnv.readModelEnabled) {
      const err = replyJsonError(
        request.id,
        400,
        'READ_MODEL_DISABLED',
        'Set READ_MODEL_ENABLED=true to use read-model endpoints.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    await refreshPollVoteRollupsNow();
    reply.send({ status: 'success', refreshed: true, at: new Date().toISOString() });
  });

  app.get('/read-model/reconcile', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply))) return;
    if (!appEnv.readModelEnabled) {
      const err = replyJsonError(
        request.id,
        400,
        'READ_MODEL_DISABLED',
        'Set READ_MODEL_ENABLED=true to use read-model endpoints.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const query = (request.query ?? {}) as Record<string, unknown>;
    const limitRaw =
      typeof query['limit'] === 'string' ? Number.parseInt(query['limit'], 10) : undefined;
    const thresholdRaw =
      typeof query['diff_threshold'] === 'string'
        ? Number.parseInt(query['diff_threshold'], 10)
        : undefined;
    const limit = typeof limitRaw === 'number' && Number.isFinite(limitRaw) ? limitRaw : 50;
    const diffThreshold =
      typeof thresholdRaw === 'number' && Number.isFinite(thresholdRaw) ? thresholdRaw : 0;
    const rows = await reconcilePollVoteRollups({ limit, diffThreshold });
    const maxDiffs = rows.reduce(
      (acc, row) => {
        const totalVotesDiff = Math.abs(
          (Number(row.rollup_total_votes) || 0) - (Number(row.canonical_total_votes) || 0),
        );
        const votesLast1mDiff = Math.abs(
          (Number(row.rollup_votes_last_1m) || 0) - (Number(row.canonical_votes_last_1m) || 0),
        );
        const votesLast24hDiff = Math.abs(
          (Number(row.rollup_votes_last_24h) || 0) - (Number(row.canonical_votes_last_24h) || 0),
        );
        const quarantinedVotesPendingDiff = Math.abs(
          (Number(row.rollup_quarantined_votes_pending) || 0) -
            (Number(row.canonical_quarantined_votes_pending) || 0),
        );
        return {
          total_votes: Math.max(acc.total_votes, totalVotesDiff),
          votes_last_1m: Math.max(acc.votes_last_1m, votesLast1mDiff),
          votes_last_24h: Math.max(acc.votes_last_24h, votesLast24hDiff),
          quarantined_votes_pending: Math.max(
            acc.quarantined_votes_pending,
            quarantinedVotesPendingDiff,
          ),
        };
      },
      { total_votes: 0, votes_last_1m: 0, votes_last_24h: 0, quarantined_votes_pending: 0 },
    );
    const alertMismatchCountThreshold = appEnv.readModelReconcileAlertMismatchCount;
    const alertDiffThreshold = appEnv.readModelReconcileAlertDiffThreshold;
    const shouldAlert =
      (alertMismatchCountThreshold > 0 && rows.length >= alertMismatchCountThreshold) ||
      (alertDiffThreshold > 0 &&
        rows.some(
          (row) =>
            Math.abs(
              (Number(row.rollup_total_votes) || 0) - (Number(row.canonical_total_votes) || 0),
            ) >= alertDiffThreshold ||
            Math.abs(
              (Number(row.rollup_votes_last_24h) || 0) -
                (Number(row.canonical_votes_last_24h) || 0),
            ) >= alertDiffThreshold,
        ));
    request.log.info(
      {
        event: 'read_model.reconcile.summary',
        mismatchCount: rows.length,
        diffThreshold,
        alert: shouldAlert,
        maxDiffTotalVotes: maxDiffs.total_votes,
        maxDiffVotesLast1m: maxDiffs.votes_last_1m,
        maxDiffVotesLast24h: maxDiffs.votes_last_24h,
        maxDiffQuarantinedVotesPending: maxDiffs.quarantined_votes_pending,
      },
      'read model reconciliation summary',
    );
    if (shouldAlert) {
      request.log.warn(
        {
          event: 'read_model.reconcile.alert',
          mismatchCount: rows.length,
          alertMismatchCountThreshold,
          alertDiffThreshold,
        },
        'read model reconciliation exceeded alert thresholds',
      );
    }
    const payload = {
      status: 'success',
      data: {
        mismatches: rows,
        mismatch_count: rows.length,
        diff_threshold: Math.max(0, Math.floor(diffThreshold)),
        limit: Math.max(1, Math.min(500, Math.floor(limit))),
        alert: shouldAlert,
        max_diffs: maxDiffs,
        alert_thresholds: {
          mismatch_count: alertMismatchCountThreshold,
          diff_threshold: alertDiffThreshold,
        },
      },
    };
    const failOnAlertRaw = typeof query['fail_on_alert'] === 'string' ? query['fail_on_alert'] : '';
    const failOnAlert = ['1', 'true', 'yes'].includes(failOnAlertRaw.trim().toLowerCase());
    if (shouldAlert && failOnAlert) {
      reply.code(503).send(payload);
      return;
    }
    reply.send(payload);
  });

  app.get('/signups', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply))) return;
    reply.send({ enabled: await getSignupsEnabled() });
  });

  app.post('/signups/enable', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply))) return;
    await setSignupsEnabled(true);
    await logAdminAction('enable_signups', 'admin', null, null);
    reply.send({ enabled: true });
  });

  app.post('/signups/disable', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply))) return;
    await setSignupsEnabled(false);
    await logAdminAction('disable_signups', 'admin', null, null);
    reply.send({ enabled: false });
  });

  app.get('/vote-geo', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply))) return;
    reply.send({ enabled: await getVoteGeoEnabled() });
  });

  app.post('/vote-geo/enable', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply))) return;
    await setVoteGeoEnabled(true);
    await logAdminAction('enable_vote_geo', 'admin', null, null);
    reply.send({ enabled: true });
  });

  app.post('/vote-geo/disable', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply))) return;
    await setVoteGeoEnabled(false);
    await logAdminAction('disable_vote_geo', 'admin', null, null);
    reply.send({ enabled: false });
  });

  app.get('/retention-policy', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminElevatedRoles))) return;
    reply.send(await getRetentionPolicySettings());
  });

  app.post('/retention-policy', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminElevatedRoles))) return;
    const body = (request.body ?? {}) as Record<string, unknown>;
    const parseIntField = (key: string): number | null => {
      const raw = body[key];
      const n =
        typeof raw === 'number'
          ? raw
          : typeof raw === 'string'
            ? Number.parseInt(raw.trim(), 10)
            : Number.NaN;
      return Number.isFinite(n) ? Math.floor(n) : null;
    };
    const next = {
      poll_retention_ttl_days_default: parseIntField('poll_retention_ttl_days_default'),
      poll_retention_sweep_interval_sec: parseIntField('poll_retention_sweep_interval_sec'),
      poll_retention_sweep_batch_size: parseIntField('poll_retention_sweep_batch_size'),
      audit_log_retention_days: parseIntField('audit_log_retention_days'),
      moderation_rejected_vote_retention_days: parseIntField(
        'moderation_rejected_vote_retention_days',
      ),
      audit_log_retention_legal_hold:
        body['audit_log_retention_legal_hold'] === true ||
        String(body['audit_log_retention_legal_hold'] ?? '')
          .trim()
          .toLowerCase() === 'true',
      moderation_rejected_vote_retention_legal_hold:
        body['moderation_rejected_vote_retention_legal_hold'] === true ||
        String(body['moderation_rejected_vote_retention_legal_hold'] ?? '')
          .trim()
          .toLowerCase() === 'true',
    };
    if (
      next.poll_retention_ttl_days_default == null ||
      next.poll_retention_sweep_interval_sec == null ||
      next.poll_retention_sweep_batch_size == null ||
      next.audit_log_retention_days == null ||
      next.moderation_rejected_vote_retention_days == null
    ) {
      const err = replyJsonError(
        request.id,
        400,
        'BAD_REQUEST',
        'Retention policy fields must be finite integers.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    await setRetentionPolicySettings({
      poll_retention_ttl_days_default: next.poll_retention_ttl_days_default,
      poll_retention_sweep_interval_sec: next.poll_retention_sweep_interval_sec,
      poll_retention_sweep_batch_size: next.poll_retention_sweep_batch_size,
      audit_log_retention_days: next.audit_log_retention_days,
      moderation_rejected_vote_retention_days: next.moderation_rejected_vote_retention_days,
      audit_log_retention_legal_hold: next.audit_log_retention_legal_hold,
      moderation_rejected_vote_retention_legal_hold:
        next.moderation_rejected_vote_retention_legal_hold,
    });
    await logAdminAction('set_retention_policy', 'admin', null, next);
    reply.send(await getRetentionPolicySettings());
  });

  /**
   * Fetch each workspace's Polar subscription by `polar_subscription_id` and align `workspaces.billing_plan`
   * (mirrored on the owner user) with the same rules as webhooks (drift repair when webhooks were missed).
   */
  app.post('/billing/reconcile-polar', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply))) return;
    if (!appEnv.polarAccessToken) {
      const err = replyJsonError(
        request.id,
        503,
        'SERVICE_UNAVAILABLE',
        'Set POLAR_ACCESS_TOKEN (Organization Access Token) to reconcile from the Polar API.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const body = (request.body ?? {}) as Record<string, unknown>;
    const dryRun =
      body['dryRun'] === true ||
      body['dry_run'] === true ||
      (typeof body['dryRun'] === 'string' &&
        ['1', 'true', 'yes'].includes(body['dryRun'].trim().toLowerCase()));
    const limitRaw = body['limit'];
    const limitParsed =
      typeof limitRaw === 'number' && Number.isFinite(limitRaw)
        ? Math.floor(limitRaw)
        : typeof limitRaw === 'string'
          ? Number.parseInt(limitRaw, 10)
          : 50;
    const limit = Number.isFinite(limitParsed) ? limitParsed : 50;
    try {
      const summary = await reconcilePolarSubscriptionsFromApi({
        log: request.log,
        limit,
        dryRun,
      });
      await logAdminAction('polar_reconcile', request.user?.homelab-user ?? 'admin_token', null, {
        dry_run: dryRun,
        scanned: summary.scanned,
        polar_fetch_errors: summary.polarFetchErrors,
        drift_detected: summary.driftDetected,
        rows_updated: summary.rowsUpdated,
      });
      reply.send({ ok: true, ...summary });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      request.log.error(
        { event: 'polar.reconcile.route_error', err: msg },
        'polar reconcile failed',
      );
      const err = replyJsonError(request.id, 500, 'INTERNAL_ERROR', 'Polar reconcile failed.');
      reply.code(err.statusCode).send(err.body);
    }
  });

  app.post('/billing/downgrade-simulate', async (request, reply) => {
    if (!(await requireAdminAuth(request, reply, adminElevatedRoles))) return;
    const body = (request.body ?? {}) as Record<string, unknown>;
    const userIdRaw = body['userId'] ?? body['user_id'];
    const userId =
      typeof userIdRaw === 'number' && Number.isFinite(userIdRaw)
        ? Math.floor(userIdRaw)
        : typeof userIdRaw === 'string'
          ? Number.parseInt(userIdRaw, 10)
          : Number.NaN;
    if (!Number.isFinite(userId) || userId <= 0) {
      const err = replyJsonError(
        request.id,
        400,
        'BAD_REQUEST',
        'userId must be a positive integer.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const targetPlanRaw =
      typeof body['targetPlan'] === 'string'
        ? body['targetPlan']
        : typeof body['target_plan'] === 'string'
          ? body['target_plan']
          : '';
    const targetPlan = normalizeBillingPlan(targetPlanRaw);
    const allowedPlans = new Set<KnownBillingPlan>([
      'free',
      'cloud-team',
      'cloud-pro',
      'selfhost-pro',
      'enterprise-custom',
    ]);
    if (!allowedPlans.has(targetPlan)) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'targetPlan is invalid.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const owner = await User.findByPk(userId, {
      attributes: ['id', 'homelab-user', 'defaultWorkspaceId', 'billingPlan'],
    });
    if (!owner) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'User not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const currentPlan = normalizeBillingPlan(
      (owner.get('billingPlan') as string | null | undefined) ?? 'free',
    );
    const workspaceId = await resolveWorkspaceIdForCreatorUserId(userId);
    const month = utcCalendarMonthBounds();
    const [activePolls, votesThisMonth, exportsToday, ownedPolls] = await Promise.all([
      Poll.count({ where: { creatorUserId: userId, archived: false } }),
      Vote.count({
        include: [
          {
            model: Poll,
            as: 'poll',
            required: true,
            attributes: [],
            where: { creatorUserId: userId },
          },
        ],
        where: {
          isQuarantined: false,
          createdAt: { [Op.gte]: month.start, [Op.lt]: month.endExclusive },
        },
      }),
      countCompletedDataExportsForWorkspaceUtcDay(userId),
      Poll.findAll({
        where: { creatorUserId: userId, archived: false },
        attributes: ['id', 'webhookTargets', 'retentionTtlDays', 'retentionLegalHold'],
      }),
    ]);

    let pollsWithWebhookAutomation = 0;
    let pollsWithExtendedRetention = 0;
    for (const p of ownedPolls) {
      const webhooks =
        (p.get('webhookTargets') as Array<{ url?: string; secret?: string }> | null | undefined) ??
        [];
      if (
        Array.isArray(webhooks) &&
        webhooks.some((w) => typeof w?.url === 'string' && w.url.trim() !== '')
      ) {
        pollsWithWebhookAutomation += 1;
      }
      const ttl = p.get('retentionTtlDays') as number | null | undefined;
      const hold = p.get('retentionLegalHold') as boolean | null | undefined;
      if ((typeof ttl === 'number' && Number.isFinite(ttl) && ttl > 0) || hold === true) {
        pollsWithExtendedRetention += 1;
      }
    }

    const limits = {
      activePolls: maxActivePollsForBillingPlan(targetPlan),
      votesPerMonth: maxVotesPerMonthForBillingPlan(targetPlan),
      exportsPerDay: maxDataExportsPerDayForBillingPlan(targetPlan),
    };
    const usage = {
      activePolls,
      votesThisMonth,
      exportsToday,
      pollsWithWebhookAutomation,
      pollsWithExtendedRetention,
    };
    const flags = {
      webhookAutomationAllowed: hasWebhookAutomationForBillingPlan(targetPlan),
      extendedRetentionAllowed: hasExtendedRetentionForBillingPlan(targetPlan),
    };
    const violations = [
      ...(usage.activePolls > limits.activePolls
        ? [
            {
              code: 'USAGE_LIMIT_ACTIVE_POLLS',
              current: usage.activePolls,
              max: limits.activePolls,
            },
          ]
        : []),
      ...(usage.votesThisMonth > limits.votesPerMonth
        ? [{ code: 'USAGE_LIMIT_VOTES', current: usage.votesThisMonth, max: limits.votesPerMonth }]
        : []),
      ...(usage.exportsToday > limits.exportsPerDay
        ? [{ code: 'USAGE_LIMIT_EXPORTS', current: usage.exportsToday, max: limits.exportsPerDay }]
        : []),
      ...(!flags.webhookAutomationAllowed && usage.pollsWithWebhookAutomation > 0
        ? [{ code: 'PLAN_LIMIT_AUTOMATION', affectedPolls: usage.pollsWithWebhookAutomation }]
        : []),
      ...(!flags.extendedRetentionAllowed && usage.pollsWithExtendedRetention > 0
        ? [{ code: 'PLAN_LIMIT_RETENTION', affectedPolls: usage.pollsWithExtendedRetention }]
        : []),
    ];

    await logAdminAction(
      'billing_downgrade_simulate',
      request.user?.homelab-user ?? 'admin_token',
      userId,
      {
        workspace_id: workspaceId,
        current_plan: currentPlan,
        target_plan: targetPlan,
        violations: violations.map((v) => v.code),
      },
    );
    reply.send({
      ok: true,
      user: {
        id: Number(owner.get('id')),
        homelab-user: String(owner.get('homelab-user') ?? ''),
        workspaceId,
      },
      currentPlan,
      targetPlan,
      usage,
      limits,
      flags,
      violations,
      wouldBlock: violations.length > 0,
      generatedAt: new Date().toISOString(),
    });
  });
};
