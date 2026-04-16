import type { AppRequest } from '../types/http';

export function firstQueryParam(value: AppRequest['query'][string]): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (Array.isArray(value)) {
    const x = value[0];
    return typeof x === 'string' ? x : undefined;
  }
  if (typeof value === 'string') return value;
  return undefined;
}

export function normalizeQueryParams(
  query: AppRequest['query'],
): Record<string, string | undefined> {
  const out: Record<string, string | undefined> = {};
  for (const key of Object.keys(query)) {
    out[key] = firstQueryParam(query[key]);
  }
  return out;
}

export function parseBoundedInt(
  raw: string | undefined,
  opts: { min: number; max: number; defaultValue: number },
): number {
  const n = Number.parseInt(raw ?? '', 10);
  if (!Number.isFinite(n) || n < opts.min) return opts.defaultValue;
  return Math.min(opts.max, n);
}
