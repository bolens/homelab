/** Upstream project the UI nods to in the default footer link. */
export const DEFAULT_ATTRIBUTION_HREF = 'https://github.com/jdleo/asking';

type SiteFooterMode = { kind: 'hidden' } | { kind: 'default' } | { kind: 'custom'; text: string };

function readEnv(env: Record<string, string | undefined>, key: string): string | undefined {
  const v = env[key];
  if (v === undefined || v === null) return undefined;
  const s = String(v).trim();
  return s === '' ? undefined : s;
}

export function parseSiteFooterFromEnv(env: Record<string, string | undefined>): SiteFooterMode {
  const raw = readEnv(env, 'VITE_SITE_FOOTER');
  if (!raw || raw.toLowerCase() === 'default') return { kind: 'default' };
  const lower = raw.toLowerCase();
  if (lower === 'hidden' || lower === 'none' || lower === 'off') return { kind: 'hidden' };
  return { kind: 'custom', text: raw.slice(0, 280) };
}

export function parseSiteFooter(): SiteFooterMode {
  return parseSiteFooterFromEnv(import.meta.env as unknown as Record<string, string | undefined>);
}

/** Safe href for the default “Powered by” link (https only, or http localhost). */
export function parseAttributionUrlFromEnv(env: Record<string, string | undefined>): string {
  const raw = readEnv(env, 'VITE_ATTRIBUTION_URL');
  if (!raw) return DEFAULT_ATTRIBUTION_HREF;
  try {
    const u = new URL(raw);
    if (u.protocol === 'https:') return u.toString();
    if (u.protocol === 'http:' && u.hostname === 'localhost') return u.toString();
  } catch {
    /* ignore */
  }
  return DEFAULT_ATTRIBUTION_HREF;
}

export function parseAttributionUrl(): string {
  return parseAttributionUrlFromEnv(
    import.meta.env as unknown as Record<string, string | undefined>,
  );
}
