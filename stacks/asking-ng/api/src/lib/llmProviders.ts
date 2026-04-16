import { appEnv } from './env';

type LlmProviderKind = 'ollama' | 'lmstudio';

export function resolveLlmProvider(): LlmProviderKind | null {
  const v = appEnv.llmProvider;
  if (v === 'ollama') return 'ollama';
  if (v === 'lmstudio' || v === 'lm_studio') return 'lmstudio';
  return null;
}

export function ollamaBaseUrl(): string {
  return appEnv.ollamaBaseUrl;
}

export function ollamaApiKey(): string | undefined {
  return appEnv.ollamaApiKey;
}

export function lmStudioBaseUrl(): string {
  return appEnv.lmStudioBaseUrl;
}

export function allowedLlmUpstreamHosts(): Set<string> {
  const raw = appEnv.llmAllowedUpstreamHostsRaw;
  if (!raw) return new Set<string>();
  return new Set(
    raw
      .split(',')
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean),
  );
}

export function assertLlmUpstreamUrlAllowed(url: string): void {
  const allowedHosts = allowedLlmUpstreamHosts();
  if (allowedHosts.size === 0) return;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error(`Invalid LLM upstream URL: ${url}`);
  }
  const host = parsed.hostname.trim().toLowerCase();
  if (!allowedHosts.has(host)) {
    throw new Error(`LLM upstream host "${host}" is not in LLM_ALLOWED_UPSTREAM_HOSTS`);
  }
}
