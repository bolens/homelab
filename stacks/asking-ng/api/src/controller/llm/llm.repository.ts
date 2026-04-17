import { appEnv } from '../../lib/env';
import {
  assertLlmUpstreamUrlAllowed,
  lmStudioBaseUrl,
  ollamaBaseUrl,
} from '../../lib/llmProviders';

function llmUpstreamTimeoutMs(): number {
  return appEnv.llmUpstreamTimeoutMs;
}

async function fetchWithLlmTimeout(url: string, init?: RequestInit): Promise<Response> {
  assertLlmUpstreamUrlAllowed(url);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort(new Error('LLM upstream timeout'));
  }, llmUpstreamTimeoutMs());
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function fetchOllamaTags(headers: Record<string, string>) {
  return fetchWithLlmTimeout(`${ollamaBaseUrl()}/api/tags`, { headers });
}

export async function fetchLmStudioModels(headers: Record<string, string>) {
  return fetchWithLlmTimeout(`${lmStudioBaseUrl()}/v1/models`, { headers });
}

export async function postOllamaChat(headers: Record<string, string>, body: string) {
  return fetchWithLlmTimeout(`${ollamaBaseUrl()}/api/chat`, {
    method: 'POST',
    headers,
    body,
  });
}

export async function postLmStudioChat(headers: Record<string, string>, body: string) {
  return fetchWithLlmTimeout(`${lmStudioBaseUrl()}/v1/chat/completions`, {
    method: 'POST',
    headers,
    body,
  });
}
