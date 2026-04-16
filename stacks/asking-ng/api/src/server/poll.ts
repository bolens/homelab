import {
  formatAllowedPhasesList,
  isPollPhaseTransitionAllowed,
  normalizePollPhase,
  type ModerateVoteBatchBody,
  type UpdatePollBody,
  createPollBodySchema,
  decideQuarantinedVoteBodySchema,
  editWriteInVoteBodySchema,
  exportPollQuerySchema,
  listPollsMineQuerySchema,
  listQuarantinedVotesQuerySchema,
  moderateVoteBatchBodySchema,
  pollReplayQuerySchema,
  pollVoteHeatmapQuerySchema,
  updatePollBodySchema,
  votePollBodySchema,
} from '@asking-ng/contracts/poll';
import type { FastifyPluginAsync } from 'fastify';
import { Op, QueryTypes } from 'sequelize';
import { presentCreatePollResponse } from '../controller/poll/createPoll.presenter';
import { createPollService } from '../controller/poll/createPoll.service';
import {
  issueSignedEmbedReadGrant,
  pollEmbedViewAllowed,
  pollSignedReadGrantAllowed,
  readEmbedReadTokenFromRequest,
  verifyEmbedReadToken,
} from '../lib/embedReadToken';
import { presentPollResponse } from '../controller/poll/getPoll.presenter';
import { getPollView } from '../controller/poll/getPoll.service';
import { presentPollsMineResponse } from '../controller/poll/listPollsMine.presenter';
import { buildPollsMineView } from '../controller/poll/listPollsMine.service';
import {
  checkDailyDataExportQuotaForWorkspace,
  recordDataExportJob,
} from '../lib/billingExportQuota';
import { checkActivePollQuotaForUser } from '../lib/billingPollQuota';
import { resolveWorkspaceIdForCreatorUserId } from '../lib/workspaceBootstrap';
import db from '../connections';
import { getVoteGeoEnabled } from '../lib/appSettings';
import { notifyPollLive } from '../lib/pollLive';
import {
  trustChatBurstOwnerSummary,
  trustIpBurstOwnerSummary,
  trustStackSafeguardTags,
} from '../lib/trustStackSignals';
import { listPollPhaseHistory } from '../lib/pollPhaseHistory';
import { pollPhaseScheduleFromRow, resolveEffectivePollPhase } from '../lib/pollPhaseSchedule';
import { queuePollWebhook } from '../lib/pollWebhooks';
import { normalizeMediaAttachment, normalizeMediaModeration } from '../lib/mediaPolicy';
import {
  getPollGeoBinsFromRollups,
  getPollReplayEventsFromRollups,
  getPollVoteRollup,
  refreshPollReadModelsForPollIds,
} from '../lib/readModelRollups';
import { publicPollPageUrl, publicPollResultsUrl, publicSiteRoot } from '../lib/sitePublicUrl';
import { validateWriteInText } from '../lib/writeInHygiene';
import {
  presentVoteIdempotentReplay,
  presentVoteSuccess,
} from '../controller/poll/voteOnPoll.presenter';
import { voteOnPollService } from '../controller/poll/voteOnPoll.service';
import { moderateVoteBatchService } from '../controller/poll/moderateVoteBatch.service';
import { presentModerateVoteBatch } from '../controller/poll/moderateVoteBatch.presenter';
import type { ListPollsMineQuery, VotePollBody } from '@asking-ng/contracts/poll';
import Poll from '../model/Poll';
import Vote from '../model/Vote';
import AuditLog from '../models/auditlog.sequelize';
import { replyJsonError, toAppRequest } from './requestAdapter';
import { Parser } from 'json2csv';
import randomId from '../helpers/randomId';
import { recordPollPhaseTransition } from '../lib/pollPhaseHistory';
import { validatePollPhaseScheduleWindow } from '../lib/pollPhaseSchedule';
import { generateEmbedReadToken, hashEmbedReadToken } from '../lib/embedReadToken';
import { sendCompressedJson } from './compression';
import { appEnv } from '../lib/env';

export const fastifyPollRoutes: FastifyPluginAsync = async (app) => {
  const pollSharedEditorIds = (poll: { get: (field: string) => unknown }): number[] => {
    const raw = (poll.get('sharedEditorUserIds') as unknown) ?? [];
    if (!Array.isArray(raw)) return [];
    return raw
      .map((id) => Number(id))
      .filter((id) => Number.isInteger(id) && id > 0);
  };

  const canEditDraftViaJwt = (
    poll: { get: (field: string) => unknown },
    user: { id: number } | null | undefined,
  ): boolean => {
    if (!user) return false;
    const ownerId = poll.get('creatorUserId') as number | null | undefined;
    if (ownerId != null && Number(ownerId) === Number(user.id)) return true;
    const phase = String(poll.get('phase') ?? 'open');
    if (phase !== 'draft') return false;
    return pollSharedEditorIds(poll).includes(Number(user.id));
  };

  const apiKeyFrom = (request: { headers?: unknown }): string | undefined => {
    const headers = (request.headers ?? {}) as Record<string, unknown>;
    const v = headers.api_key;
    if (typeof v === 'string') return v;
    if (Array.isArray(v) && typeof v[0] === 'string') return v[0];
    return undefined;
  };

  app.get('/mine', async (request, reply) => {
    if (!request.user) {
      const err = replyJsonError(
        request.id,
        401,
        'MISSING_AUTHORIZATION',
        'Missing Authorization header',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const parsed = listPollsMineQuerySchema.safeParse(request.query);
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

    const reqLike = toAppRequest(request, parsed.data);
    const view = await buildPollsMineView(reqLike, parsed.data as ListPollsMineQuery);
    reply.send(presentPollsMineResponse(view));
  });

  app.get<{ Params: { id: string } }>('/:id', async (request, reply) => {
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const result = await getPollView(toAppRequest(request), pollId);
    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'forbidden_embed_token') {
      const err = replyJsonError(
        request.id,
        403,
        'POLL_EMBED_TOKEN_REQUIRED',
        'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    sendCompressedJson(request, reply, 200, presentPollResponse(result.data));
  });

  app.post('/', async (request, reply) => {
    const parsed = createPollBodySchema.safeParse(request.body);
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

    const result = await createPollService(toAppRequest(request), parsed.data);
    if (result.kind === 'invalid_webhook_url') {
      const err = replyJsonError(
        request.id,
        400,
        'BAD_REQUEST',
        `Invalid webhook target URL: ${result.url}`,
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'webhook_url_blocked') {
      const err = replyJsonError(
        request.id,
        400,
        'WEBHOOK_URL_BLOCKED',
        `Blocked webhook target URL: ${result.url}`,
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_next_poll_requires_signed_in') {
      const err = replyJsonError(
        request.id,
        400,
        'INVALID_NEXT_POLL',
        'next_poll_id requires a signed-in creator-owned poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_next_poll_requires_next_poll_id') {
      const err = replyJsonError(
        request.id,
        400,
        'INVALID_NEXT_POLL',
        'auto_advance_on_close requires next_poll_id.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_next_poll_missing_target') {
      const err = replyJsonError(
        request.id,
        400,
        'INVALID_NEXT_POLL',
        'next_poll_id does not exist.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_next_poll_wrong_owner') {
      const err = replyJsonError(
        request.id,
        400,
        'INVALID_NEXT_POLL',
        'next_poll_id must belong to the same signed-in creator.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_vanity_slug_in_use') {
      const err = replyJsonError(
        request.id,
        400,
        'INVALID_VANITY_SLUG',
        'vanity_slug is already in use.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'usage_limit_active_polls') {
      const err = replyJsonError(
        request.id,
        403,
        'USAGE_LIMIT_ACTIVE_POLLS',
        'Active poll limit reached for this billing plan.',
        { max: result.max, current: result.current, plan: result.plan },
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    reply.code(200).send(presentCreatePollResponse(result.data));
  });

  app.put<{ Params: { id: string } }>('/:id/vote', async (request, reply) => {
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const parsed = votePollBodySchema.safeParse(request.body);
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

    const reqLike = toAppRequest(request);
    const result = await voteOnPollService(reqLike, pollId, parsed.data as VotePollBody);

    if (result.kind === 'not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'forbidden_embed_token') {
      const err = replyJsonError(
        request.id,
        403,
        'POLL_EMBED_TOKEN_REQUIRED',
        'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'poll_archived') {
      const err = replyJsonError(request.id, 400, 'POLL_ARCHIVED', 'Poll is archived.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'poll_not_accepting_votes') {
      const err = replyJsonError(
        request.id,
        400,
        'POLL_NOT_ACCEPTING_VOTES',
        'This poll is not accepting votes right now.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'poll_voting_paused') {
      const err = replyJsonError(
        request.id,
        400,
        'POLL_VOTING_PAUSED',
        'Voting is temporarily paused for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'vote_requires_sign_in') {
      const err = replyJsonError(
        request.id,
        401,
        'VOTE_REQUIRES_SIGN_IN',
        'This poll only accepts votes from signed-in users. Send Authorization: Bearer with a valid user JWT.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'boost_weight_disabled') {
      const err = replyJsonError(
        request.id,
        400,
        'BOOST_WEIGHT_DISABLED',
        'boost_weight is only allowed when boosted voting is enabled for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_boost_weight') {
      const err = replyJsonError(
        request.id,
        400,
        'INVALID_BOOST_WEIGHT',
        `boost_weight must be between 1 and ${result.maxBoostWeight}.`,
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'poll_soft_throttled') {
      const err = replyJsonError(
        request.id,
        429,
        'POLL_SOFT_THROTTLED',
        `Too many recent votes from your source. Limit is ${result.softThrottleMaxVotesPerMin}/min for this poll.`,
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'pow_required') {
      const err = replyJsonError(
        request.id,
        400,
        'POW_REQUIRED',
        `pow_nonce is required and must satisfy SHA-256(${result.pollId}:nonce) starting with ${'0'.repeat(result.powDifficulty)}.`,
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_option_index') {
      const err = replyJsonError(
        request.id,
        400,
        'INVALID_OPTION_INDEX',
        'option_index is out of range for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_option_indices') {
      const err = replyJsonError(
        request.id,
        400,
        'INVALID_OPTION_INDICES',
        'One or more option_indices are out of range for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'vote_shape_mismatch') {
      const err = replyJsonError(request.id, 400, 'VOTE_SHAPE_MISMATCH', result.detail);
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'invalid_write_in') {
      const err = replyJsonError(request.id, 400, result.code, result.message);
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'poll_expired') {
      const err = replyJsonError(request.id, 400, 'POLL_EXPIRED', 'Poll has expired.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'channel_rate_limited') {
      const err = replyJsonError(
        request.id,
        429,
        'CHANNEL_RATE_LIMITED',
        `Too many chat votes for this channel. Limit is ${result.perChannelMax}/min.`,
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'idempotent_replay') {
      reply.code(200).send(presentVoteIdempotentReplay(result.vote, result.ballotVotes));
      return;
    }
    if (result.kind === 'duplicate_vote') {
      const err = replyJsonError(request.id, 409, 'DUPLICATE_VOTE', 'You already voted on this poll.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'usage_limit_votes_month') {
      const err = replyJsonError(
        request.id,
        403,
        'USAGE_LIMIT_VOTES',
        'Monthly vote limit reached for this poll owner billing plan.',
        {
          max: result.max,
          current: result.current,
          plan: result.plan,
          incoming: result.incoming,
        },
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    reply.code(200).send(
      presentVoteSuccess({
        vote: result.vote,
        ballot_votes: result.ballotVotes,
        option_indices: result.optionIndices,
        moderation: result.moderation,
      }),
    );
  });

  app.get<{ Params: { id: string } }>('/:id/embed', async (request, reply) => {
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const reqLike = toAppRequest(request);
    const poll = await Poll.findByPk(pollId, {
      attributes: ['id', 'title', 'archived', 'embedReadTokenHash'],
    });
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
    const embedToken = readEmbedReadTokenFromRequest(reqLike);
    if (!verifyEmbedReadToken(embedHash, embedToken) && !pollSignedReadGrantAllowed(reqLike, pollId)) {
      const err = replyJsonError(
        request.id,
        403,
        'POLL_EMBED_TOKEN_REQUIRED',
        'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const title = poll.get('title') as string;
    const archived = !!poll.get('archived');
    const pageUrl = publicPollPageUrl(reqLike, pollId);
    const provider = appEnv.serviceName;
    const providerSite = publicSiteRoot(reqLike);
    const esc = (s: string) =>
      s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    const html = `<a href="${esc(pageUrl)}">${esc(title)}</a>`;

    reply
      .header('Content-Type', 'application/json; charset=utf-8')
      .header('Access-Control-Allow-Origin', '*')
      .code(200)
      .send({
        version: '1.0',
        type: 'link',
        title: archived ? `${title} (archived)` : title,
        provider_name: provider,
        provider_url: providerSite || pageUrl,
        cache_age: 30,
        html,
        url: pageUrl,
      });
  });

  app.post<{ Params: { id: string } }>('/:id/embed-read-url', async (request, reply) => {
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findByPk(pollId, {
      attributes: ['id', 'api_key', 'creatorUserId', 'embedReadTokenHash'],
    });
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const apiKey = apiKeyFrom(request);
    const targetApiKey = poll.get('api_key') as string | undefined;
    const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
    const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
    const ownerId = poll.get('creatorUserId') as number | null | undefined;
    const jwtOk = request.user != null && ownerId != null && Number(ownerId) === Number(request.user.id);
    if (!apiKeyOk && !jwtOk) {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
    if (!embedHash || embedHash.trim() === '') {
      const err = replyJsonError(
        request.id,
        409,
        'EMBED_GATE_DISABLED',
        'This poll has no embed read token configured. Rotate/embed-enable first.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const query = (request.query ?? {}) as Record<string, unknown>;
    const ttlRaw = query.ttl_seconds;
    const ttlSeconds =
      typeof ttlRaw === 'string'
        ? Number.parseInt(ttlRaw, 10)
        : typeof ttlRaw === 'number'
          ? Math.floor(ttlRaw)
          : 30 * 60;
    const signed = issueSignedEmbedReadGrant(pollId, Number.isFinite(ttlSeconds) ? ttlSeconds : 30 * 60);
    if (!signed) {
      const err = replyJsonError(
        request.id,
        503,
        'EMBED_SIGNING_UNAVAILABLE',
        'Embed URL signing is unavailable because JWT_SECRET is not configured.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const reqLike = toAppRequest(request);
    const pageUrl = new URL(publicPollPageUrl(reqLike, pollId));
    const resultsUrl = new URL(publicPollResultsUrl(reqLike, pollId));
    const publicOrigin = `${publicSiteRoot(reqLike).replace(/\/$/, '')}/`;
    const wsProto = pageUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = new URL(`/ws/poll/${encodeURIComponent(pollId)}`, `${wsProto}//${pageUrl.host}`);
    const metaUrl = new URL(`/poll/${encodeURIComponent(pollId)}/meta`, publicOrigin);
    const oembedUrl = new URL(`/poll/${encodeURIComponent(pollId)}/embed`, publicOrigin);
    for (const url of [pageUrl, resultsUrl, wsUrl, metaUrl, oembedUrl]) {
      url.searchParams.set('embed_exp', String(signed.embed_exp));
      url.searchParams.set('embed_sig', signed.embed_sig);
    }
    reply.code(200).send({
      status: 'success',
      data: {
        ttl_seconds: Math.max(30, signed.embed_exp - Math.floor(Date.now() / 1000)),
        expires_at: new Date(signed.embed_exp * 1000).toISOString(),
        embed_exp: signed.embed_exp,
        embed_sig: signed.embed_sig,
        poll_url: pageUrl.toString(),
        results_url: resultsUrl.toString(),
        ws_url: wsUrl.toString(),
        meta_url: metaUrl.toString(),
        oembed_url: oembedUrl.toString(),
      },
    });
  });

  app.get<{ Params: { id: string } }>('/:id/meta', async (request, reply) => {
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const reqLike = toAppRequest(request);
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
    const embedToken = readEmbedReadTokenFromRequest(reqLike);
    const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
    if (!pollEmbedViewAllowed(reqLike, pollId, embedHash, embedToken, creatorUserId)) {
      const err = replyJsonError(
        request.id,
        403,
        'POLL_EMBED_TOKEN_REQUIRED',
        'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const title = poll.get('title') as string;
    const options = (poll.get('options') as string[]) || [];
    const expiration = Number.parseInt(String(poll.get('expiration')), 10);
    const archived = !!poll.get('archived');
    const now = Date.now();
    const schedule = pollPhaseScheduleFromRow(poll);
    const phase = resolveEffectivePollPhase(poll.get('phase'), schedule, now);
    const votingPaused = !!poll.get('votingPaused');
    const pauseMessage = (poll.get('pauseMessage') as string | null) ?? null;
    const embedGate = typeof embedHash === 'string' && embedHash.trim() !== '';
    const boostedVotingEnabled = !!poll.get('boostedVotingEnabled');
    const showUnweightedValues = !!poll.get('showUnweightedValues');
    const maxBoostWeight = Number(poll.get('maxBoostWeight') ?? 3);
    const runOfShowKey = (poll.get('runOfShowKey') as string | null | undefined) ?? null;
    const runOfShowOrder = (poll.get('runOfShowOrder') as number | null | undefined) ?? null;
    const vanitySlug = (poll.get('vanitySlug') as string | null | undefined) ?? null;
    const nextPollId = (poll.get('nextPollId') as string | null | undefined) ?? null;
    const autoAdvanceOnClose = !!poll.get('autoAdvanceOnClose');
    const voteFrictionTier = String(poll.get('voteFrictionTier') ?? 'open');
    const softThrottleMaxVotesPerMin = Number(poll.get('softThrottleMaxVotesPerMin') ?? 30);
    const powDifficulty = Number(poll.get('powDifficulty') ?? 4);
    const allowWriteIn = !!poll.get('allowWriteIn');
    const writeInMaxLength = Number(poll.get('writeInMaxLength') ?? 80);
    const writeInBlocklist = (
      (poll.get('writeInBlocklist') as string[] | null | undefined) ?? []
    ).filter((s) => typeof s === 'string' && s.trim() !== '');
    const writeInProfanityFilter = poll.get('writeInProfanityFilter') !== false;
    const resultsDelaySeconds = Math.max(0, Number(poll.get('resultsDelaySeconds') ?? 0) || 0);
    const mediaAttachment = normalizeMediaAttachment(poll.get('mediaAttachment'));
    const mediaModeration = normalizeMediaModeration(poll.get('mediaModeration'));
    const mediaBlurByDefault = poll.get('mediaBlurByDefault') !== false;
    const themePreset = String(poll.get('themePreset') ?? 'default');
    const selectionMode = String(poll.get('selectionMode') ?? 'single') === 'multi' ? 'multi' : 'single';
    const voteEligibility =
      String(poll.get('voteEligibility') ?? 'anonymous') === 'account' ? 'account' : 'anonymous';
    const expired = Number.isFinite(expiration) && expiration > 0 && now > expiration;
    const signedInOk =
      request.user != null &&
      Number.isFinite(Number(request.user.id)) &&
      Number(request.user.id) > 0;
    const canVote =
      !archived &&
      !votingPaused &&
      !expired &&
      phase === 'open' &&
      options.length >= 2 &&
      (voteEligibility !== 'account' || signedInOk);

    const votePath = `poll/${encodeURIComponent(pollId)}/vote`;
    const phaseHistory = await listPollPhaseHistory(pollId, { limit: 50 });
    const youOwnThisPoll =
      request.user != null && creatorUserId != null && Number(request.user.id) === Number(creatorUserId);
    const [rateCountersRow] = youOwnThisPoll
      ? ((await db.query(
          `SELECT
            COUNT(DISTINCT "sourceIpHash") FILTER (
              WHERE "createdAt" >= NOW() - INTERVAL '1 minute'
                AND "sourceIpHash" IS NOT NULL
                AND COALESCE("isQuarantined", false) = false
            )::int AS unique_ip_hashes_last_1m,
            COUNT(DISTINCT "userId") FILTER (
              WHERE "createdAt" >= NOW() - INTERVAL '1 minute'
                AND "userId" IS NOT NULL
                AND COALESCE("isQuarantined", false) = false
            )::int AS unique_accounts_last_1m,
            COALESCE((
              SELECT MAX(c) FROM (
                SELECT COUNT(*)::int AS c
                FROM votes
                WHERE "pollId" = :pollId
                  AND "createdAt" >= NOW() - INTERVAL '1 minute'
                  AND "sourceIpHash" IS NOT NULL
                  AND COALESCE("isQuarantined", false) = false
                GROUP BY "sourceIpHash"
              ) t
            ), 0)::int AS top_ip_votes_last_1m
           FROM votes
           WHERE "pollId" = :pollId`,
          { replacements: { pollId }, type: QueryTypes.SELECT },
        )) as Array<{
          unique_ip_hashes_last_1m: string | number;
          unique_accounts_last_1m: string | number;
          top_ip_votes_last_1m: string | number;
        }>)
      : [];
    let votesLast1m = 0;
    let quarantinedVotesPending = 0;
    let rollupLoaded = false;
    if (youOwnThisPoll) {
      if (appEnv.readModelEnabled) {
        try {
          await refreshPollReadModelsForPollIds([pollId]);
          const rollup = await getPollVoteRollup(pollId);
          votesLast1m = Number(rollup?.votes_last_1m ?? 0) || 0;
          quarantinedVotesPending = Number(rollup?.quarantined_votes_pending ?? 0) || 0;
          rollupLoaded = rollup != null;
        } catch (err) {
          request.log.warn(
            { event: 'poll.read_model.rollup_fallback', err, pollId },
            'poll read model unavailable, falling back to canonical counters',
          );
        }
      }
      if (!appEnv.readModelEnabled || !rollupLoaded) {
        const [fallbackCounters] = (await db.query(
          `SELECT
            COUNT(*) FILTER (
              WHERE "createdAt" >= NOW() - INTERVAL '1 minute'
                AND COALESCE("isQuarantined", false) = false
            )::int AS votes_last_1m,
            COUNT(*) FILTER (
              WHERE COALESCE("isQuarantined", false) = true
                AND COALESCE("quarantineStatus", 'pending') = 'pending'
            )::int AS quarantined_votes_pending
           FROM votes
           WHERE "pollId" = :pollId`,
          { replacements: { pollId }, type: QueryTypes.SELECT },
        )) as Array<{ votes_last_1m: string | number; quarantined_votes_pending: string | number }>;
        votesLast1m = Number(fallbackCounters?.votes_last_1m ?? 0) || 0;
        quarantinedVotesPending = Number(fallbackCounters?.quarantined_votes_pending ?? 0) || 0;
      }
    }

    sendCompressedJson(request, reply, 200, {
      status: 'success',
      data: {
        id: pollId,
        title,
        phase,
        phase_schedule: schedule,
        archived,
        voting_paused: votingPaused,
        pause_message: pauseMessage,
        boosted_voting_enabled: boostedVotingEnabled,
        show_unweighted_values: showUnweightedValues,
        max_boost_weight: maxBoostWeight,
        run_of_show_key: runOfShowKey,
        run_of_show_order: runOfShowOrder,
        vanity_slug: vanitySlug,
        next_poll_id: nextPollId,
        auto_advance_on_close: autoAdvanceOnClose,
        vote_friction_tier: voteFrictionTier,
        soft_throttle_max_votes_per_min: softThrottleMaxVotesPerMin,
        pow_difficulty: powDifficulty,
        allow_write_in: allowWriteIn,
        write_in_max_length: writeInMaxLength,
        write_in_blocklist: writeInBlocklist,
        write_in_profanity_filter: writeInProfanityFilter,
        results_delay_seconds: resultsDelaySeconds,
        media:
          mediaAttachment != null
            ? {
                ...mediaAttachment,
                blur_by_default: mediaBlurByDefault,
                moderation_status: mediaModeration.status,
              }
            : null,
        theme_preset: themePreset,
        selection_mode: selectionMode,
        vote_eligibility: voteEligibility,
        expiration,
        embed_gate: embedGate,
        public_poll_url: publicPollPageUrl(reqLike, pollId),
        public_results_url: publicPollResultsUrl(reqLike, pollId),
        vote_path: votePath,
        vote_http_method: 'PUT',
        timestamps_timezone: 'UTC',
        server_now_ms: now,
        phase_history: phaseHistory,
        integrity_panel: {
          safeguards_applied: [
            embedGate ? 'embed_gate' : null,
            boostedVotingEnabled ? 'boosted_voting' : null,
            selectionMode === 'multi' ? 'selection_mode:multi' : null,
            voteEligibility === 'account' ? 'vote_eligibility:account' : null,
            voteFrictionTier !== 'open' ? `vote_friction:${voteFrictionTier}` : null,
            resultsDelaySeconds > 0 ? `results_delay:${resultsDelaySeconds}s` : null,
            ...trustStackSafeguardTags(),
          ].filter((v): v is string => v != null),
          vote_friction_tier: voteFrictionTier,
          rate_limits: {
            soft_throttle_max_votes_per_min:
              voteFrictionTier === 'soft_throttle' ? softThrottleMaxVotesPerMin : null,
            pow_difficulty: voteFrictionTier === 'proof_of_work' ? powDifficulty : null,
          },
          moderation: {
            quarantined_votes_pending: quarantinedVotesPending,
          },
        },
        options: options.map((label, index) => ({ index, label })),
        can_vote: canVote,
        ...(youOwnThisPoll
          ? {
              moderation_counters: {
                votes_last_1m: votesLast1m,
                unique_ip_hashes_last_1m: Number(rateCountersRow?.unique_ip_hashes_last_1m ?? 0) || 0,
                unique_accounts_last_1m: Number(rateCountersRow?.unique_accounts_last_1m ?? 0) || 0,
                top_ip_votes_last_1m: Number(rateCountersRow?.top_ip_votes_last_1m ?? 0) || 0,
                quarantined_votes_pending: quarantinedVotesPending,
                trust_ip_burst: trustIpBurstOwnerSummary(),
                trust_chat_burst: trustChatBurstOwnerSummary(),
              },
            }
          : {}),
      },
    });
  });

  app.post<{ Params: { id: string } }>('/:id/media/report', async (request, reply) => {
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const reqLike = toAppRequest(request);
    const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
    const embedToken = readEmbedReadTokenFromRequest(reqLike);
    const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
    if (!pollEmbedViewAllowed(reqLike, pollId, embedHash, embedToken, creatorUserId)) {
      const err = replyJsonError(
        request.id,
        403,
        'POLL_EMBED_TOKEN_REQUIRED',
        'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const mediaAttachment = normalizeMediaAttachment(poll.get('mediaAttachment'));
    if (!mediaAttachment) {
      const err = replyJsonError(request.id, 409, 'MEDIA_NOT_CONFIGURED', 'This poll has no media attachment.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const body = (request.body ?? {}) as Record<string, unknown>;
    const reasonRaw = typeof body.reason === 'string' ? body.reason.trim() : '';
    const current = normalizeMediaModeration(poll.get('mediaModeration'));
    const next =
      current.status === 'takedown'
        ? current
        : {
            status: 'reported' as const,
            reported_reason: reasonRaw ? reasonRaw.slice(0, 500) : current.reported_reason ?? null,
            last_action_at: new Date().toISOString(),
            last_actor: 'public_report',
          };
    await Poll.update({ mediaModeration: next }, { where: { id: pollId } });
    await AuditLog.create({
      action: 'poll_media_report',
      actor: request.user?.homelab-user ?? 'public',
      target: String(pollId),
      details: {
        reason: reasonRaw ? reasonRaw.slice(0, 500) : null,
        by_user_id: request.user?.id ?? null,
      },
    });
    reply.send({ status: 'success', reported: true });
  });

  app.get<{ Params: { id: string } }>('/:id/quarantine', async (request, reply) => {
    const parsed = listQuarantinedVotesQuerySchema.safeParse(request.query);
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
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const apiKey = apiKeyFrom(request);
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const targetApiKey = poll.get('api_key') as string | undefined;
    const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
    const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
    const ownerId = poll.get('creatorUserId') as number | null | undefined;
    const jwtOk = request.user != null && ownerId != null && Number(ownerId) === Number(request.user.id);
    if (!apiKeyOk && !jwtOk) {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const status = parsed.data.status;
    const limit = parsed.data.limit;
    const offset = parsed.data.offset;
    const statusFilter = status === 'all' ? { [Op.in]: ['pending', 'approved', 'rejected'] } : status;
    const rows = await Vote.findAll({
      where: {
        pollId,
        [Op.or]: [{ isQuarantined: true }, { quarantineStatus: { [Op.ne]: null } }],
        quarantineStatus: statusFilter,
      },
      attributes: [
        'id',
        'option',
        'weight',
        'sourceIpHash',
        'userId',
        'createdAt',
        'isQuarantined',
        'quarantineReason',
        'quarantineStatus',
        'quarantineDecidedAt',
        'quarantineDecidedBy',
        'quarantineNote',
        'trustRiskScore',
      ],
      order: [['createdAt', 'DESC']],
      limit,
      offset,
    });
    reply.code(200).send({
      status: 'success',
      data: rows.map((row) => ({
        id: row.get('id'),
        option: row.get('option'),
        weight: Number(row.get('weight') ?? 1) || 1,
        source_ip_hash: row.get('sourceIpHash') ?? null,
        user_id: row.get('userId') ?? null,
        created_at: row.get('createdAt'),
        is_quarantined: !!row.get('isQuarantined'),
        quarantine_reason: row.get('quarantineReason') ?? null,
        quarantine_status: row.get('quarantineStatus') ?? null,
        quarantine_decided_at: row.get('quarantineDecidedAt') ?? null,
        quarantine_decided_by: row.get('quarantineDecidedBy') ?? null,
        quarantine_note: row.get('quarantineNote') ?? null,
        trust_risk_score:
          row.get('trustRiskScore') == null ? null : Number(row.get('trustRiskScore')) || null,
      })),
    });
  });

  app.put<{ Params: { id: string; voteId: string } }>('/:id/quarantine/:voteId', async (request, reply) => {
    const parsed = decideQuarantinedVoteBodySchema.safeParse(request.body);
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
    const pollId = request.params.id?.trim();
    const voteId = request.params.voteId?.trim();
    if (!pollId || !voteId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id and vote id are required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const apiKey = apiKeyFrom(request);
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const targetApiKey = poll.get('api_key') as string | undefined;
    const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
    const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
    const ownerId = poll.get('creatorUserId') as number | null | undefined;
    const jwtOk = request.user != null && ownerId != null && Number(ownerId) === Number(request.user.id);
    if (!apiKeyOk && !jwtOk) {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const vote = await Vote.findByPk(voteId);
    if (!vote || String(vote.get('pollId')) !== pollId) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Quarantined vote not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const body = parsed.data;
    const action = body.action;
    const currentStatus = String(vote.get('quarantineStatus') ?? 'pending');
    const isQuarantined = !!vote.get('isQuarantined');
    if (action === 'revert' && currentStatus !== 'approved' && currentStatus !== 'rejected') {
      const err = replyJsonError(
        request.id,
        400,
        'VOTE_REVERT_NOT_ALLOWED',
        'Only approved or rejected votes can be reverted to pending.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (action !== 'revert' && !(isQuarantined || currentStatus === 'pending')) {
      const err = replyJsonError(
        request.id,
        400,
        'VOTE_NOT_QUARANTINED',
        'Vote is not pending quarantine review.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    let quarantineStatus: 'pending' | 'approved' | 'rejected';
    let nextIsQuarantined: boolean;
    if (action === 'approve') {
      quarantineStatus = 'approved';
      nextIsQuarantined = false;
    } else if (action === 'reject') {
      quarantineStatus = 'rejected';
      nextIsQuarantined = true;
    } else {
      quarantineStatus = 'pending';
      nextIsQuarantined = true;
    }
    await Vote.update(
      {
        quarantineStatus,
        isQuarantined: nextIsQuarantined,
        quarantineDecidedAt: new Date(),
        quarantineDecidedBy: request.user?.homelab-user ?? 'api_key',
        quarantineNote: body.note ?? null,
      },
      { where: { id: voteId, pollId } },
    );
    reply.code(200).send({
      status: 'success',
      data: {
        vote_id: voteId,
        quarantine_status: quarantineStatus,
        is_quarantined: nextIsQuarantined,
      },
    });
  });

  app.put<{ Params: { id: string; voteId: string } }>('/:id/votes/:voteId/text', async (request, reply) => {
    const parsed = editWriteInVoteBodySchema.safeParse(request.body);
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
    const pollId = request.params.id?.trim();
    const voteId = request.params.voteId?.trim();
    if (!pollId || !voteId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id and vote id are required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const apiKey = apiKeyFrom(request);
    const targetApiKey = poll.get('api_key') as string | undefined;
    const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
    const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
    const ownerId = poll.get('creatorUserId') as number | null | undefined;
    const jwtOk = request.user != null && ownerId != null && Number(ownerId) === Number(request.user.id);
    if (!apiKeyOk && !jwtOk) {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const vote = await Vote.findByPk(voteId);
    if (!vote || String(vote.get('pollId')) !== pollId) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Vote not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const nextOption = parsed.data.option.trim();
    const validOptions = ((poll.get('options') as string[] | null | undefined) ?? []).filter(Boolean);
    if (!validOptions.includes(nextOption)) {
      const writeInCheck = validateWriteInText(nextOption, {
        allowWriteIn: !!poll.get('allowWriteIn'),
        writeInMaxLength: Number(poll.get('writeInMaxLength') ?? 80),
        writeInBlocklist: (
          (poll.get('writeInBlocklist') as string[] | null | undefined) ?? []
        ).filter((s) => typeof s === 'string' && s.trim() !== ''),
        writeInProfanityFilter: poll.get('writeInProfanityFilter') !== false,
      });
      if (!writeInCheck.ok) {
        const err = replyJsonError(request.id, 400, writeInCheck.code, writeInCheck.message);
        reply.code(err.statusCode).send(err.body);
        return;
      }
    }
    const prevOption = String(vote.get('option') ?? '');
    await Vote.update({ option: nextOption }, { where: { id: voteId, pollId } });
    await AuditLog.create({
      action: 'moderation.write_in.edit',
      actor: request.user?.homelab-user ?? 'api_key',
      target: `poll:${pollId}:vote:${voteId}`,
      details: {
        poll_id: pollId,
        vote_id: voteId,
        previous_option: prevOption,
        new_option: nextOption,
        note: parsed.data.note?.trim() || null,
      },
    });
    notifyPollLive(pollId, { type: 'update' });
    queuePollWebhook(pollId, 'poll_updated', {
      moderation_vote_id: voteId,
      moderation_action: 'write_in_edit',
    });
    reply.code(200).send({
      status: 'success',
      data: {
        vote_id: voteId,
        option: nextOption,
      },
    });
  });

  app.put<{ Params: { id: string } }>('/:id/moderation/batch', async (request, reply) => {
    const parsed = moderateVoteBatchBodySchema.safeParse(request.body);
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
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const result = await moderateVoteBatchService({
      pollId,
      body: parsed.data as ModerateVoteBatchBody,
      apiKey: apiKeyFrom(request),
      actorUserId: request.user?.id ?? null,
      actorUsername: request.user?.homelab-user ?? null,
    });
    if (result.kind === 'poll_not_found') {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'unauthorized') {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.code(200).send(
      presentModerateVoteBatch({
        action: result.action,
        selector: result.selector,
        selectorValue: result.selectorValue,
        reasonCode: result.reasonCode,
        affectedCount: result.affectedCount,
      }),
    );
  });

  app.get<{ Params: { id: string } }>('/:id/export', async (request, reply) => {
    const parsed = exportPollQuerySchema.safeParse(request.query);
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
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const reqLike = toAppRequest(request, parsed.data);
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
    const embedToken = readEmbedReadTokenFromRequest(reqLike);
    const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
    if (!pollEmbedViewAllowed(reqLike, pollId, embedHash, embedToken, creatorUserId)) {
      const err = replyJsonError(
        request.id,
        403,
        'POLL_EMBED_TOKEN_REQUIRED',
        'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const apiKeyHeader = request.headers.api_key;
    const apiKey =
      typeof apiKeyHeader === 'string'
        ? apiKeyHeader
        : Array.isArray(apiKeyHeader)
          ? apiKeyHeader[0]
          : undefined;
    const storedKey = poll.get('api_key') as string | undefined;
    const ownerJwt = request.user && creatorUserId != null && request.user.id === creatorUserId;
    const ownerKey = apiKey !== undefined && apiKey !== '' && apiKey === storedKey;
    if (!ownerJwt && !ownerKey) {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Provide api_key header or sign in as the poll owner.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const workspaceMeterId =
      typeof creatorUserId === 'number' && Number.isFinite(creatorUserId) && creatorUserId > 0
        ? creatorUserId
        : null;
    const exportQuotaCheck = await checkDailyDataExportQuotaForWorkspace({
      workspaceUserId: workspaceMeterId,
    });
    if (!exportQuotaCheck.ok) {
      const err = replyJsonError(
        request.id,
        403,
        'USAGE_LIMIT_EXPORTS',
        'Daily data export limit reached for this billing plan.',
        {
          max: exportQuotaCheck.max,
          current: exportQuotaCheck.current,
          plan: exportQuotaCheck.plan,
        },
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const format = parsed.data.format;
    const include = parsed.data.include;
    const title = poll.get('title') as string;
    const options = (poll.get('options') as string[]) || [];
    const phase = (poll.get('phase') as string) || 'open';
    const votingPaused = !!poll.get('votingPaused');
    const impressionCount = Number(poll.get('impressionCount')) || 0;
    const expiration = Number.parseInt(String(poll.get('expiration')), 10);
    const boostedVotingEnabled = !!poll.get('boostedVotingEnabled');
    const showUnweightedValues = !!poll.get('showUnweightedValues');
    const maxBoostWeight = Number(poll.get('maxBoostWeight') ?? 3);
    const jsonExportProvenance = () => ({
      exported_at: new Date().toISOString(),
      timestamps_timezone: 'UTC' as const,
    });

    const voteData = (await db.query(
      `SELECT option, count(option) as vote_count, COALESCE(sum(weight), count(option)) as weighted_vote_count
       FROM votes
       WHERE "pollId" = :pollId
         AND COALESCE("isQuarantined", false) = false
       GROUP BY option;`,
      { replacements: { pollId }, type: QueryTypes.SELECT },
    )) as Array<{ option: string; vote_count: string | number; weighted_vote_count: string | number }>;
    const rows = options.map((opt) => {
      const row = voteData.find((v) => v.option === opt);
      const n = row ? Number.parseInt(String(row.vote_count), 10) || 0 : 0;
      const weighted = row ? Number.parseInt(String(row.weighted_vote_count), 10) || n : 0;
      return { option: opt, votes: boostedVotingEnabled ? weighted : n, weighted_votes: weighted, unweighted_votes: n };
    });
    const velocityRows = (await db.query(
      `SELECT
        date_trunc('minute', "createdAt" AT TIME ZONE 'UTC') AS minute_utc,
        COUNT(*)::int AS vote_count
       FROM votes
       WHERE "pollId" = :pollId
         AND COALESCE("isQuarantined", false) = false
       GROUP BY minute_utc
       ORDER BY minute_utc ASC`,
      { replacements: { pollId }, type: QueryTypes.SELECT },
    )) as Array<{ minute_utc: Date | string; vote_count: string | number }>;
    const voteVelocity = velocityRows.map((r) => ({
      minute_utc: r.minute_utc instanceof Date ? r.minute_utc.toISOString() : new Date(String(r.minute_utc)).toISOString(),
      vote_count: Number(r.vote_count ?? 0) || 0,
    }));
    const phaseHistory = await listPollPhaseHistory(pollId, { limit: 200 });
    const safeName = `poll-${pollId}`.replace(/[^a-zA-Z0-9._-]+/g, '_');

    if (include === 'votes') {
      const rawVotes = (await db.query(
        `SELECT option, "createdAt" AS voted_at, weight
         FROM votes
         WHERE "pollId" = :pollId
           AND COALESCE("isQuarantined", false) = false
         ORDER BY "createdAt" ASC`,
        { replacements: { pollId }, type: QueryTypes.SELECT },
      )) as Array<{ option: string; voted_at: Date; weight?: number }>;
      if (format === 'csv') {
        const parser = new Parser({ fields: ['option', 'voted_at', 'weight'] });
        const csv = parser.parse(
          rawVotes.map((r) => ({
            option: r.option,
            voted_at: r.voted_at instanceof Date ? r.voted_at.toISOString() : String(r.voted_at),
            weight: Number(r.weight ?? 1) || 1,
          })),
        );
        if (workspaceMeterId != null) {
          await recordDataExportJob({ workspaceUserId: workspaceMeterId, kind: 'poll', pollId });
        }
        reply
          .header('Content-Type', 'text/csv; charset=utf-8')
          .header('Content-Disposition', `attachment; filename="${safeName}-votes.csv"`)
          .code(200)
          .send(csv);
        return;
      }
      const payload = {
        ...jsonExportProvenance(),
        id: pollId,
        title,
        expiration,
        archived: !!poll.get('archived'),
        phase,
        voting_paused: votingPaused,
        impression_count: impressionCount,
        boosted_voting_enabled: boostedVotingEnabled,
        max_boost_weight: maxBoostWeight,
        show_unweighted_values: showUnweightedValues,
        vote_velocity_by_minute_utc: voteVelocity,
        phase_history: phaseHistory,
        votes: rawVotes.map((r) => ({
          option: r.option,
          voted_at: r.voted_at instanceof Date ? r.voted_at.toISOString() : r.voted_at,
          weight: Number(r.weight ?? 1) || 1,
        })),
      };
      if (workspaceMeterId != null) {
        await recordDataExportJob({ workspaceUserId: workspaceMeterId, kind: 'poll', pollId });
      }
      reply
        .header('Content-Type', 'application/json; charset=utf-8')
        .header('Content-Disposition', `attachment; filename="${safeName}-votes.json"`)
        .code(200)
        .send(JSON.stringify(payload, null, 2));
      return;
    }

    const payload = {
      ...jsonExportProvenance(),
      id: pollId,
      title,
      expiration,
      archived: !!poll.get('archived'),
      phase,
      voting_paused: votingPaused,
      impression_count: impressionCount,
      boosted_voting_enabled: boostedVotingEnabled,
      max_boost_weight: maxBoostWeight,
      show_unweighted_values: showUnweightedValues,
      vote_velocity_by_minute_utc: voteVelocity,
      phase_history: phaseHistory,
      options: rows.map((r) => ({
        option: r.option,
        votes: r.votes,
        ...(boostedVotingEnabled ? { weighted_votes: r.weighted_votes } : {}),
        ...(boostedVotingEnabled && showUnweightedValues ? { unweighted_votes: r.unweighted_votes } : {}),
      })),
      totalVotes: rows.reduce((a, r) => a + r.votes, 0),
    };
    if (format === 'csv') {
      const flat = rows.map((r) => ({
        option: r.option,
        votes: r.votes,
        ...(boostedVotingEnabled ? { weighted_votes: r.weighted_votes } : {}),
        ...(boostedVotingEnabled && showUnweightedValues ? { unweighted_votes: r.unweighted_votes } : {}),
      }));
      const parser = new Parser({
        fields: [
          'option',
          'votes',
          ...(boostedVotingEnabled ? ['weighted_votes'] : []),
          ...(boostedVotingEnabled && showUnweightedValues ? ['unweighted_votes'] : []),
        ],
      });
      const csv = parser.parse(flat);
      if (workspaceMeterId != null) {
        await recordDataExportJob({ workspaceUserId: workspaceMeterId, kind: 'poll', pollId });
      }
      reply
        .header('Content-Type', 'text/csv; charset=utf-8')
        .header('Content-Disposition', `attachment; filename="${safeName}.csv"`)
        .code(200)
        .send(csv);
      return;
    }
    if (workspaceMeterId != null) {
      await recordDataExportJob({ workspaceUserId: workspaceMeterId, kind: 'poll', pollId });
    }
    reply
      .header('Content-Type', 'application/json; charset=utf-8')
      .header('Content-Disposition', `attachment; filename="${safeName}.json"`)
      .code(200)
      .send(JSON.stringify(payload, null, 2));
  });

  app.get<{ Params: { id: string } }>('/:id/replay', async (request, reply) => {
    const parsed = pollReplayQuerySchema.safeParse(request.query);
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
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const reqLike = toAppRequest(request, parsed.data);
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
    const embedToken = readEmbedReadTokenFromRequest(reqLike);
    const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
    if (!pollEmbedViewAllowed(reqLike, pollId, embedHash, embedToken, creatorUserId)) {
      const err = replyJsonError(
        request.id,
        403,
        'POLL_EMBED_TOKEN_REQUIRED',
        'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const expiration = Number(poll.get('expiration'));
    const archived = !!poll.get('archived');
    const phase = String(poll.get('phase') ?? 'open');
    const expired = Number.isFinite(expiration) && expiration > 0 && Date.now() > expiration;
    const completed = archived || expired || phase !== 'open';
    if (!completed) {
      const err = replyJsonError(
        request.id,
        409,
        'POLL_NOT_COMPLETED',
        'Replay is available only after poll completion.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const options = ((poll.get('options') as string[]) || []).map((opt) => String(opt));
    const optionIndexByLabel = new Map<string, number>();
    options.forEach((label, idx) => optionIndexByLabel.set(label, idx));
    const limit = Number(parsed.data.limit ?? 5000);
    let events: Array<{ option_index: number; offset_ms: number }> | null = null;
    if (appEnv.readModelEnabled) {
      try {
        await refreshPollReadModelsForPollIds([pollId]);
        const replayRows = await getPollReplayEventsFromRollups({ pollId, limit });
        events = replayRows
          .map((row) => {
            const optionIndex = optionIndexByLabel.get(String(row.option_label));
            if (optionIndex === undefined) return null;
            return {
              option_index: optionIndex,
              offset_ms: Math.max(0, Number(row.offset_ms ?? 0) || 0),
            };
          })
          .filter((e): e is { option_index: number; offset_ms: number } => e !== null);
      } catch (err) {
        request.log.warn(
          { event: 'poll.read_model.replay_fallback', err, pollId },
          'poll replay read model unavailable, falling back to canonical query',
        );
      }
    }
    if (events == null) {
      const rows = await db.query<{
        option: string;
        created_at: Date | string;
      }>(
        `
          SELECT option, "createdAt" AS created_at
          FROM votes
          WHERE "pollId" = :pollId
            AND COALESCE("isQuarantined", false) = false
          ORDER BY "createdAt" ASC, id ASC
          LIMIT :limit;
        `,
        {
          replacements: { pollId, limit },
          type: QueryTypes.SELECT,
        },
      );
      const firstTsMs = rows.length ? new Date(rows[0].created_at).getTime() : null;
      events = rows
        .map((row) => {
          const optionIndex = optionIndexByLabel.get(String(row.option));
          if (optionIndex === undefined) return null;
          const ts = new Date(row.created_at).getTime();
          if (!Number.isFinite(ts)) return null;
          return {
            option_index: optionIndex,
            offset_ms: firstTsMs === null ? 0 : Math.max(0, ts - firstTsMs),
          };
        })
        .filter((e): e is { option_index: number; offset_ms: number } => e !== null);
    }

    reply.code(200).send({
      status: 'success',
      data: {
        options,
        total_votes: events.length,
        completed,
        events,
      },
    });
  });

  app.get<{ Params: { id: string } }>('/:id/heatmap', async (request, reply) => {
    const parsed = pollVoteHeatmapQuerySchema.safeParse(request.query);
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
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const reqLike = toAppRequest(request, parsed.data);
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
    const embedToken = readEmbedReadTokenFromRequest(reqLike);
    const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
    if (!pollEmbedViewAllowed(reqLike, pollId, embedHash, embedToken, creatorUserId)) {
      const err = replyJsonError(
        request.id,
        403,
        'POLL_EMBED_TOKEN_REQUIRED',
        'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (!(await getVoteGeoEnabled())) {
      const err = replyJsonError(
        request.id,
        403,
        'FEATURE_DISABLED',
        'Vote location heatmap is disabled by admin.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const minCount = Number(parsed.data.minCount ?? 2);
    let rows:
      | Array<{ latitude_bucket: string | number; longitude_bucket: string | number; votes_count: string | number }>
      | null = null;
    if (appEnv.readModelEnabled) {
      try {
        await refreshPollReadModelsForPollIds([pollId]);
        rows = await getPollGeoBinsFromRollups({ pollId, minCount });
      } catch (err) {
        request.log.warn(
          { event: 'poll.read_model.heatmap_fallback', err, pollId },
          'poll heatmap read model unavailable, falling back to canonical query',
        );
      }
    }
    if (rows == null) {
      rows = (await db.query(
        `
          SELECT
            vote_latitude AS latitude_bucket,
            vote_longitude AS longitude_bucket,
            count(*) AS votes_count
          FROM votes
          WHERE "pollId" = :pollId
            AND COALESCE("isQuarantined", false) = false
            AND vote_latitude IS NOT NULL
            AND vote_longitude IS NOT NULL
          GROUP BY vote_latitude, vote_longitude
          HAVING count(*) >= :minCount
          ORDER BY votes_count DESC
          LIMIT 1000;
        `,
        {
          replacements: { pollId, minCount },
          type: QueryTypes.SELECT,
        },
      )) as Array<{ latitude_bucket: string | number; longitude_bucket: string | number; votes_count: string | number }>;
    }
    const points = rows
      .map((row) => ({
        latitude: Number(row.latitude_bucket),
        longitude: Number(row.longitude_bucket),
        intensity: Number(row.votes_count),
      }))
      .filter(
        (row) =>
          Number.isFinite(row.latitude) &&
          Number.isFinite(row.longitude) &&
          Number.isFinite(row.intensity),
      );
    reply.code(200).send({
      status: 'success',
      data: {
        points,
        minCount,
        geo_collection_mode: 'opt_in_coarse',
        coordinate_precision_decimals: 1,
        note: 'Coordinates are intentionally coarse and aggregated for privacy.',
      },
    });
  });

  app.post<{ Params: { id: string } }>('/:id/clone', async (request, reply) => {
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const source = await Poll.findByPk(pollId);
    if (!source) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const apiKey = apiKeyFrom(request);
    const targetApiKey = source.get('api_key') as string | undefined;
    const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
    const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
    const ownerId = source.get('creatorUserId') as number | null | undefined;
    const jwtOk = canEditDraftViaJwt(source, request.user ?? null);
    if (!apiKeyOk && !jwtOk) {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const now = Date.now();
    const existingExpiration = Number(source.get('expiration')) || now + 7 * 24 * 3600 * 1000;
    const safeExpiration = existingExpiration <= now + 60_000 ? now + 7 * 24 * 3600 * 1000 : existingExpiration;
    const sourceTitle = String(source.get('title') ?? 'Untitled poll');
    const copiedTitle = sourceTitle.includes('(copy)') ? sourceTitle : `${sourceTitle} (copy)`;
    const newCreatorId =
      ownerId != null && Number.isInteger(Number(ownerId)) && Number(ownerId) > 0 ? Number(ownerId) : null;
    const quota = await checkActivePollQuotaForUser({
      creatorUserId: newCreatorId,
      sessionUserRole: jwtOk ? request.user?.role ?? null : null,
    });
    if (!quota.ok) {
      const err = replyJsonError(
        request.id,
        403,
        'USAGE_LIMIT_ACTIVE_POLLS',
        'Active poll limit reached for this billing plan.',
        { max: quota.max, current: quota.current, plan: quota.plan },
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const workspaceId = await resolveWorkspaceIdForCreatorUserId(newCreatorId);

    await db.sync();
    const clone = await Poll.create({
      id: randomId(16),
      api_key: randomId(16),
      title: copiedTitle,
      options: (source.get('options') as string[]) ?? [],
      expiration: safeExpiration,
      limit_ip: !!source.get('limit_ip'),
      creatorUserId: ownerId ?? null,
      workspaceId,
      webhookTargets: (
        (source.get('webhookTargets') as Array<{ url?: string; secret?: string }> | null | undefined) ?? []
      )
        .filter(
          (t): t is { url: string; secret: string } =>
            typeof t?.url === 'string' &&
            t.url.trim() !== '' &&
            typeof t?.secret === 'string' &&
            t.secret.trim() !== '',
        )
        .map((t) => ({ url: t.url.trim(), secret: t.secret.trim() })),
      phase: 'draft',
      votingPaused: false,
      pauseMessage: null,
      showNotes: source.get('showNotes') ?? null,
      embedReadTokenHash: source.get('embedReadTokenHash') ?? null,
      openAt: source.get('openAt') ?? null,
      lockAt: source.get('lockAt') ?? null,
      revealAt: source.get('revealAt') ?? null,
      boostedVotingEnabled: !!source.get('boostedVotingEnabled'),
      maxBoostWeight: Number(source.get('maxBoostWeight') ?? 3),
      showUnweightedValues: !!source.get('showUnweightedValues'),
      runOfShowKey: source.get('runOfShowKey') ?? null,
      runOfShowOrder: source.get('runOfShowOrder') ?? null,
      nextPollId: null,
      autoAdvanceOnClose: false,
      voteFrictionTier: String(source.get('voteFrictionTier') ?? 'open'),
      softThrottleMaxVotesPerMin: Number(source.get('softThrottleMaxVotesPerMin') ?? 30),
      powDifficulty: Number(source.get('powDifficulty') ?? 4),
      allowWriteIn: !!source.get('allowWriteIn'),
      writeInMaxLength: Number(source.get('writeInMaxLength') ?? 80),
      writeInBlocklist: (
        (source.get('writeInBlocklist') as string[] | null | undefined) ?? []
      ).filter((s) => typeof s === 'string' && s.trim() !== ''),
      writeInProfanityFilter: source.get('writeInProfanityFilter') !== false,
      resultsDelaySeconds: Number(source.get('resultsDelaySeconds') ?? 0),
      sharedEditorUserIds: pollSharedEditorIds(source),
      mediaAttachment: normalizeMediaAttachment(source.get('mediaAttachment')),
      mediaBlurByDefault: source.get('mediaBlurByDefault') !== false,
      mediaModeration: normalizeMediaModeration(source.get('mediaModeration')),
      themePreset: String(source.get('themePreset') ?? 'default'),
      selectionMode: String(source.get('selectionMode') ?? 'single'),
      voteEligibility:
        String(source.get('voteEligibility') ?? 'anonymous') === 'account' ? 'account' : 'anonymous',
    });
    const clonedId = clone.get('id') as string;
    await recordPollPhaseTransition({
      pollId: clonedId,
      fromPhase: null,
      toPhase: 'draft',
      actorType: jwtOk ? 'owner_jwt' : 'api_key',
      actorUserId: request.user?.id ?? null,
      source: 'poll_clone',
    });
    notifyPollLive(clonedId, { type: 'update' });
    reply.code(200).send({
      status: 'success',
      message: 'Poll cloned as draft.',
      data: {
        id: clonedId,
        api_key: clone.get('api_key') as string,
        source_poll_id: pollId,
      },
    });
  });

  app.put<{ Params: { id: string } }>('/:id', async (request, reply) => {
    const parsed = updatePollBodySchema.safeParse(request.body);
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
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const apiKey = apiKeyFrom(request);
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const body = parsed.data as UpdatePollBody;
    const bodyRecord = body as Record<string, unknown>;
    const targetApiKey = poll.get('api_key') as string | undefined;
    const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
    const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
    const jwtOk = canEditDraftViaJwt(poll, request.user ?? null);
    if (!apiKeyOk && !jwtOk) {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const patch: Record<string, unknown> = {};
    if (body.expiration !== undefined) patch.expiration = body.expiration;
    if (body.phase !== undefined) patch.phase = body.phase;
    if (body.voting_paused !== undefined) patch.votingPaused = body.voting_paused;
    if (body.pause_message !== undefined) patch.pauseMessage = body.pause_message;
    if (body.show_notes !== undefined) patch.showNotes = body.show_notes;
    if (body.open_at !== undefined) patch.openAt = body.open_at;
    if (body.lock_at !== undefined) patch.lockAt = body.lock_at;
    if (body.reveal_at !== undefined) patch.revealAt = body.reveal_at;
    if (body.boosted_voting_enabled !== undefined) patch.boostedVotingEnabled = body.boosted_voting_enabled;
    if (body.max_boost_weight !== undefined) patch.maxBoostWeight = body.max_boost_weight ?? 3;
    if (body.show_unweighted_values !== undefined) patch.showUnweightedValues = body.show_unweighted_values;
    if (body.run_of_show_key !== undefined) patch.runOfShowKey = body.run_of_show_key;
    if (body.run_of_show_order !== undefined) patch.runOfShowOrder = body.run_of_show_order;
    if (body.next_poll_id !== undefined) patch.nextPollId = body.next_poll_id;
    if (body.auto_advance_on_close !== undefined) patch.autoAdvanceOnClose = body.auto_advance_on_close;
    if (body.vanity_slug !== undefined) patch.vanitySlug = body.vanity_slug;
    if (body.vote_friction_tier !== undefined) patch.voteFrictionTier = body.vote_friction_tier;
    if (body.soft_throttle_max_votes_per_min !== undefined) {
      patch.softThrottleMaxVotesPerMin = body.soft_throttle_max_votes_per_min ?? 30;
    }
    if (body.pow_difficulty !== undefined) patch.powDifficulty = body.pow_difficulty ?? 4;
    if (body.results_delay_seconds !== undefined) patch.resultsDelaySeconds = body.results_delay_seconds ?? 0;
    if (body.allow_write_in !== undefined) patch.allowWriteIn = body.allow_write_in;
    if (body.write_in_max_length !== undefined) patch.writeInMaxLength = body.write_in_max_length ?? 80;
    if (body.write_in_blocklist !== undefined) patch.writeInBlocklist = body.write_in_blocklist ?? [];
    if (body.write_in_profanity_filter !== undefined) patch.writeInProfanityFilter = body.write_in_profanity_filter;
    if (body.shared_editor_user_ids !== undefined) {
      const ownerUserId = (poll.get('creatorUserId') as number | null | undefined) ?? null;
      const ids = body.shared_editor_user_ids ?? [];
      patch.sharedEditorUserIds = Array.from(
        new Set(
          ids
            .map((id: number) => Number(id))
            .filter(
              (id: number) =>
                Number.isInteger(id) && id > 0 && (ownerUserId == null || id !== ownerUserId),
            ),
        ),
      );
    }
    if (bodyRecord.media_attachment !== undefined) {
      patch.mediaAttachment = bodyRecord.media_attachment ?? null;
      if (bodyRecord.media_attachment === null) {
        patch.mediaModeration = { status: 'active' };
      }
    }
    if (bodyRecord.media_blur_by_default !== undefined) {
      patch.mediaBlurByDefault = Boolean(bodyRecord.media_blur_by_default);
    }
    if (bodyRecord.theme_preset !== undefined) {
      patch.themePreset =
        typeof bodyRecord.theme_preset === 'string' && bodyRecord.theme_preset.trim() !== ''
          ? bodyRecord.theme_preset
          : 'default';
    }
    if (body.selection_mode !== undefined) {
      patch.selectionMode =
        body.selection_mode === null ? 'single' : (body.selection_mode as 'single' | 'multi');
    }
    if (body.vote_eligibility !== undefined) {
      patch.voteEligibility =
        body.vote_eligibility === null ? 'anonymous' : (body.vote_eligibility as 'anonymous' | 'account');
    }
    if (body.webhook_targets !== undefined) patch.webhookTargets = body.webhook_targets ?? [];
    let embedReadToken: string | undefined;
    if (body.generate_embed_read_token === true) {
      embedReadToken = generateEmbedReadToken();
      patch.embedReadTokenHash = hashEmbedReadToken(embedReadToken);
    }
    const nextPhaseRaw = patch.phase;
    if (typeof nextPhaseRaw === 'string') {
      const fromPhase = normalizePollPhase(poll.get('phase'));
      const toPhase = nextPhaseRaw as typeof fromPhase;
      if (!isPollPhaseTransitionAllowed(fromPhase, toPhase, { panic: false })) {
        const err = replyJsonError(
          request.id,
          400,
          'INVALID_PHASE_TRANSITION',
          `Cannot change poll phase from ${fromPhase} to ${toPhase}. Allowed targets: ${formatAllowedPhasesList(fromPhase)}.`,
        );
        reply.code(err.statusCode).send(err.body);
        return;
      }
    }
    const currentSchedule = pollPhaseScheduleFromRow(poll);
    const mergedSchedule = {
      open_at:
        patch.openAt !== undefined ? (patch.openAt === null ? null : Number(patch.openAt)) : currentSchedule.open_at,
      lock_at:
        patch.lockAt !== undefined ? (patch.lockAt === null ? null : Number(patch.lockAt)) : currentSchedule.lock_at,
      reveal_at:
        patch.revealAt !== undefined
          ? patch.revealAt === null
            ? null
            : Number(patch.revealAt)
          : currentSchedule.reveal_at,
    };
    const scheduleErr = validatePollPhaseScheduleWindow(mergedSchedule);
    if (scheduleErr) {
      const err = replyJsonError(request.id, 400, 'INVALID_PHASE_SCHEDULE', scheduleErr);
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (patch.selectionMode !== undefined) {
      const currentPhase = normalizePollPhase(poll.get('phase'));
      if (currentPhase !== 'draft') {
        const err = replyJsonError(
          request.id,
          400,
          'SELECTION_MODE_LOCKED',
          'selection_mode can only be changed while the poll is in draft phase.',
        );
        reply.code(err.statusCode).send(err.body);
        return;
      }
      const nextMode = String(patch.selectionMode) === 'multi' ? 'multi' : 'single';
      const nextBoosted =
        patch.boostedVotingEnabled !== undefined
          ? !!patch.boostedVotingEnabled
          : !!poll.get('boostedVotingEnabled');
      const nextWriteIn =
        patch.allowWriteIn !== undefined ? !!patch.allowWriteIn : !!poll.get('allowWriteIn');
      if (nextMode === 'multi' && (nextBoosted || nextWriteIn)) {
        const err = replyJsonError(
          request.id,
          400,
          'INCOMPATIBLE_SELECTION_MODE',
          'selection_mode=multi cannot be combined with boosted voting or write-ins.',
        );
        reply.code(err.statusCode).send(err.body);
        return;
      }
    }
    if (patch.voteEligibility !== undefined) {
      const currentPhase = normalizePollPhase(poll.get('phase'));
      if (currentPhase !== 'draft') {
        const err = replyJsonError(
          request.id,
          400,
          'VOTE_ELIGIBILITY_LOCKED',
          'vote_eligibility can only be changed while the poll is in draft phase.',
        );
        reply.code(err.statusCode).send(err.body);
        return;
      }
    }
    if (patch.boostedVotingEnabled === true || patch.allowWriteIn === true) {
      const mode = String(
        patch.selectionMode !== undefined ? patch.selectionMode : poll.get('selectionMode') ?? 'single',
      );
      if (mode === 'multi') {
        const err = replyJsonError(
          request.id,
          400,
          'INCOMPATIBLE_SELECTION_MODE',
          'Turn off selection_mode=multi before enabling boosted voting or write-ins.',
        );
        reply.code(err.statusCode).send(err.body);
        return;
      }
    }
    await Poll.update(patch, { where: { id: pollId } });
    const fromPhase = normalizePollPhase(poll.get('phase'));
    const toPhase = typeof patch.phase === 'string' ? normalizePollPhase(patch.phase) : fromPhase;
    if (fromPhase !== toPhase) {
      await recordPollPhaseTransition({
        pollId,
        fromPhase,
        toPhase,
        actorType: jwtOk ? 'owner_jwt' : 'api_key',
        actorUserId: jwtOk ? Number(request.user?.id) : null,
        source: 'poll_update',
      });
    }
    notifyPollLive(pollId, { type: 'update' });
    queuePollWebhook(pollId, 'poll_updated', {
      phase: body.phase,
      voting_paused: body.voting_paused,
      pause_message: body.pause_message,
      show_notes: body.show_notes === undefined ? undefined : body.show_notes === null ? null : '[redacted]',
      embed_read_token_rotated: body.generate_embed_read_token === true,
    });
    const payload: {
      status: string;
      message: string;
      data?: { embed_read_token?: string };
    } = {
      status: 'success',
      message: 'Poll successfully updated.',
    };
    if (embedReadToken) {
      payload.data = { embed_read_token: embedReadToken };
    }
    reply.code(200).send(payload);
  });

  app.delete<{ Params: { id: string } }>('/:id', async (request, reply) => {
    const pollId = request.params.id?.trim();
    if (!pollId) {
      const err = replyJsonError(request.id, 400, 'BAD_REQUEST', 'Poll id is required.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const poll = await Poll.findByPk(pollId);
    if (!poll) {
      const err = replyJsonError(request.id, 404, 'NOT_FOUND', 'Poll not found.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    const apiKey = apiKeyFrom(request);
    const targetApiKey = poll.get('api_key') as string | undefined;
    const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
    const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
    const ownerId = poll.get('creatorUserId') as number | null | undefined;
    const jwtOk = request.user != null && ownerId != null && Number(ownerId) === Number(request.user.id);
    if (!apiKeyOk && !jwtOk) {
      const err = replyJsonError(
        request.id,
        401,
        'UNAUTHORIZED',
        'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    notifyPollLive(pollId, { type: 'deleted' });
    queuePollWebhook(pollId, 'poll_deleted', {});
    await Poll.destroy({ where: { id: pollId } });
    reply.code(200).send({
      status: 'success',
      message: 'Poll successfully destroyed.',
    });
  });
};
