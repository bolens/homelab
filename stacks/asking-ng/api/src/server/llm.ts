import { createHash } from 'node:crypto';
import type { FastifyPluginAsync } from 'fastify';
import { presentLlmStatus, presentOpenAiModelList } from '../controller/llm/llm.presenter';
import { appEnv } from '../lib/env';
import {
  buildLlmStatus,
  createChatCompletionsService,
  listLlmModelsService,
} from '../controller/llm/llm.service';
import { chatCompletionBodySchema } from '../schemas/llm';
import { replyJsonError } from './requestAdapter';

function authHeader(request: { headers?: unknown }): string | null {
  const h = (request.headers ?? {}) as Record<string, unknown>;
  return typeof h.authorization === 'string' ? h.authorization : null;
}

function bearerToken(request: { headers?: unknown }): string | null {
  const auth = authHeader(request);
  if (!auth?.startsWith('Bearer ')) return null;
  return auth.slice(7).trim() || null;
}

function callerRateLimitKey(request: { headers?: unknown; ip: string }): string {
  const bearer = bearerToken(request) ?? '';
  const callerMaterial = bearer || request.ip || 'unknown';
  return createHash('sha256').update(callerMaterial).digest('hex');
}

export const fastifyLlmRoutes: FastifyPluginAsync = async (app) => {
  const windowMs = appEnv.llmRateLimitWindowMs;
  const maxPerWindow = appEnv.llmRateLimitMaxPerWindow;
  const buckets = new Map<string, { count: number; resetAt: number }>();

  app.addHook('preHandler', async (request, reply) => {
    if (appEnv.incidentMode) {
      const err = replyJsonError(request.id, 503, 'LLM_DISABLED', 'LLM gateway disabled (INCIDENT_MODE).');
      reply.code(err.statusCode).send(err.body);
      return;
    }

    const expected = appEnv.llmGatewayToken;
    if (expected) {
      const token = bearerToken(request);
      if (!token) {
        const err = replyJsonError(
          request.id,
          401,
          'UNAUTHORIZED',
          'Missing Authorization: Bearer token',
        );
        reply.code(err.statusCode).send(err.body);
        return;
      }
      if (token !== expected) {
        const err = replyJsonError(request.id, 401, 'UNAUTHORIZED', 'Invalid LLM gateway token');
        reply.code(err.statusCode).send(err.body);
        return;
      }
    }

    const key = callerRateLimitKey(request);
    const now = Date.now();
    const bucket = buckets.get(key);
    if (!bucket || now >= bucket.resetAt) {
      buckets.set(key, { count: 1, resetAt: now + windowMs });
      return;
    }
    if (bucket.count >= maxPerWindow) {
      const err = replyJsonError(request.id, 429, 'RATE_LIMIT_LLM', 'Too many LLM requests.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    bucket.count += 1;
  });

  app.get('/status', async (request, reply) => {
    reply.send(presentLlmStatus(buildLlmStatus()));
  });

  app.get('/v1/models', async (request, reply) => {
    const result = await listLlmModelsService();
    if (result.kind === 'not_configured') {
      const err = replyJsonError(
        request.id,
        503,
        'LLM_NOT_CONFIGURED',
        'Set LLM_PROVIDER to ollama or lmstudio (and base URLs if not default).',
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'ollama_upstream_error') {
      const err = replyJsonError(request.id, result.status, 'OLLAMA_UPSTREAM', 'Ollama tags request failed');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'lmstudio_upstream_invalid_json') {
      const err = replyJsonError(request.id, 502, 'LMSTUDIO_UPSTREAM', 'Invalid JSON from LM Studio');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'lmstudio_upstream_error') {
      const err = replyJsonError(
        request.id,
        result.status,
        'LMSTUDIO_UPSTREAM',
        'LM Studio models request failed',
        result.details,
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'upstream_error') {
      request.log.error({ event: 'llm.models.upstream_error', err: result.message }, 'llm list models');
      const err = replyJsonError(request.id, 502, 'LLM_UPSTREAM', result.message);
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'ollama_upstream_invalid_json') {
      const err = replyJsonError(request.id, 502, 'OLLAMA_UPSTREAM', 'Invalid JSON from Ollama');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'ollama_ok') {
      reply.send(presentOpenAiModelList({ models: result.models }));
      return;
    }
    reply.send(result.data);
  });

  app.post('/v1/chat/completions', async (request, reply) => {
    const parsed = chatCompletionBodySchema.safeParse(request.body);
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
    const result = await createChatCompletionsService(parsed.data);
    if (result.kind === 'not_configured') {
      const err = replyJsonError(request.id, 503, 'LLM_NOT_CONFIGURED', 'Set LLM_PROVIDER to ollama or lmstudio.');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'ollama_upstream_invalid_json') {
      const err = replyJsonError(request.id, 502, 'OLLAMA_UPSTREAM', 'Invalid JSON from Ollama');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'ollama_upstream_error') {
      const err = replyJsonError(request.id, result.status, 'OLLAMA_UPSTREAM', 'Ollama chat failed', result.details);
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'lmstudio_upstream_invalid_json') {
      const err = replyJsonError(request.id, 502, 'LMSTUDIO_UPSTREAM', 'Invalid JSON from LM Studio');
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'lmstudio_upstream_error') {
      const err = replyJsonError(
        request.id,
        result.status,
        'LMSTUDIO_UPSTREAM',
        'LM Studio chat failed',
        result.details,
      );
      reply.code(err.statusCode).send(err.body);
      return;
    }
    if (result.kind === 'upstream_error') {
      request.log.error({ event: 'llm.chat.upstream_error', err: result.message }, 'llm chat');
      const err = replyJsonError(request.id, 502, 'LLM_UPSTREAM', result.message);
      reply.code(err.statusCode).send(err.body);
      return;
    }
    reply.send(result.data);
  });
};
