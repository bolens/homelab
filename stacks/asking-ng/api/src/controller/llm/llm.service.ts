import { appEnv } from '../../lib/env';
import { ollamaResponseToOpenAI, toOllamaChatPayload } from '../../lib/llmOpenAiFormat';
import {
  lmStudioBaseUrl,
  ollamaApiKey,
  ollamaBaseUrl,
  resolveLlmProvider,
} from '../../lib/llmProviders';
import type { ChatCompletionBody } from '../../schemas/llm';
import {
  fetchLmStudioModels,
  fetchOllamaTags,
  postLmStudioChat,
  postOllamaChat,
} from './llm.repository';

function parseJsonOrNull(text: string): unknown | null {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export function exposeLlmPublicDetails(): boolean {
  return appEnv.llmExposePublicDetails;
}

export function buildLlmStatus() {
  const provider = resolveLlmProvider();
  const base = {
    provider: provider ?? 'none',
    gatewayAuth: Boolean(appEnv.llmGatewayToken),
    ...(provider === 'ollama' ? { ollamaAuth: Boolean(ollamaApiKey()) } : {}),
  };
  if (!exposeLlmPublicDetails()) return base;
  return {
    ...base,
    ...(provider === 'ollama' ? { ollamaBaseUrl: ollamaBaseUrl() } : {}),
    ...(provider === 'lmstudio' ? { lmStudioBaseUrl: lmStudioBaseUrl() } : {}),
  };
}

export type ListModelsResult =
  | { kind: 'not_configured' }
  | { kind: 'ollama_upstream_error'; status: number }
  | { kind: 'ollama_upstream_invalid_json' }
  | { kind: 'lmstudio_upstream_error'; status: number; details: unknown }
  | { kind: 'lmstudio_upstream_invalid_json' }
  | { kind: 'upstream_error'; message: string }
  | { kind: 'ollama_ok'; models: Array<{ name: string }> }
  | { kind: 'lmstudio_ok'; data: unknown };

export async function listLlmModelsService(): Promise<ListModelsResult> {
  const provider = resolveLlmProvider();
  if (!provider) return { kind: 'not_configured' };

  try {
    if (provider === 'ollama') {
      const key = ollamaApiKey();
      const r = await fetchOllamaTags(key ? { Authorization: `Bearer ${key}` } : {});
      const data = (await r.json()) as { models?: { name: string }[] };
      if (!r.ok) return { kind: 'ollama_upstream_error', status: r.status };
      return { kind: 'ollama_ok', models: data.models ?? [] };
    }

    const key = appEnv.lmStudioApiKey;
    const r = await fetchLmStudioModels(key ? { Authorization: `Bearer ${key}` } : {});
    const text = await r.text();
    const data = parseJsonOrNull(text);
    if (data == null) return { kind: 'lmstudio_upstream_invalid_json' };
    if (!r.ok) return { kind: 'lmstudio_upstream_error', status: r.status, details: data };
    return { kind: 'lmstudio_ok', data };
  } catch (err: unknown) {
    return { kind: 'upstream_error', message: err instanceof Error ? err.message : String(err) };
  }
}

export type ChatCompletionsResult =
  | { kind: 'not_configured' }
  | { kind: 'ollama_upstream_error'; status: number; details: unknown }
  | { kind: 'ollama_upstream_invalid_json' }
  | { kind: 'lmstudio_upstream_error'; status: number; details: unknown }
  | { kind: 'lmstudio_upstream_invalid_json' }
  | { kind: 'upstream_error'; message: string }
  | { kind: 'ok'; data: unknown };

export async function createChatCompletionsService(
  body: ChatCompletionBody,
): Promise<ChatCompletionsResult> {
  const provider = resolveLlmProvider();
  if (!provider) return { kind: 'not_configured' };

  const payload = {
    model: body.model,
    messages: body.messages,
    stream: false as const,
    ...(typeof body.temperature === 'number' ? { temperature: body.temperature } : {}),
    ...(typeof body.max_tokens === 'number' ? { max_tokens: body.max_tokens } : {}),
  };

  try {
    if (provider === 'ollama') {
      const key = ollamaApiKey();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (key) headers.Authorization = `Bearer ${key}`;
      const ollamaBody = toOllamaChatPayload(payload);
      const r = await postOllamaChat(headers, JSON.stringify(ollamaBody));
      const text = await r.text();
      const data = parseJsonOrNull(text);
      if (data == null) return { kind: 'ollama_upstream_invalid_json' };
      if (!r.ok) return { kind: 'ollama_upstream_error', status: r.status, details: data };
      return {
        kind: 'ok',
        data: ollamaResponseToOpenAI(data as Parameters<typeof ollamaResponseToOpenAI>[0]),
      };
    }

    const key = appEnv.lmStudioApiKey;
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (key) headers.Authorization = `Bearer ${key}`;
    const r = await postLmStudioChat(headers, JSON.stringify(payload));
    const text = await r.text();
    const data = parseJsonOrNull(text);
    if (data == null) return { kind: 'lmstudio_upstream_invalid_json' };
    if (!r.ok) return { kind: 'lmstudio_upstream_error', status: r.status, details: data };
    return { kind: 'ok', data };
  } catch (err: unknown) {
    return { kind: 'upstream_error', message: err instanceof Error ? err.message : String(err) };
  }
}
