import { apiUrl } from './apiBase';
import { getStoredUserJwt } from './lib/userSession';

type ApiFetchOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
  adminToken?: string | false;
  /** Sent as `Authorization: Bearer …` (e.g. optional `LLM_GATEWAY_TOKEN` on `/llm/*`). */
  bearerToken?: string | undefined;
  /** Poll creator secret for `PUT`/`DELETE /poll/:id` when not using owner JWT. */
  pollApiKey?: string | undefined;
  /** For gated polls: sent as `X-Poll-Embed-Token` (matches `embed_token` query on the API). */
  embedToken?: string | undefined;
};

export interface ApiFetchError extends Error {
  status: number;
  body: unknown;
  requestId?: string | undefined;
  errorCode?: string | undefined;
  /** Present for Zod `VALIDATION_ERROR` responses from the API. */
  details?: unknown;
}

export function isApiFetchError(err: unknown): err is ApiFetchError {
  return err instanceof Error && typeof (err as ApiFetchError).status === 'number';
}

function messageFromErrorPayload(parsed: Record<string, unknown>): string {
  const nested = parsed['error'];
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    const msg = (nested as { message?: unknown }).message;
    if (typeof msg === 'string' && msg.trim() !== '') return msg;
  }
  if (typeof nested === 'string' && nested.trim() !== '') return nested;
  if (typeof parsed['message'] === 'string' && parsed['message'].trim() !== '') return parsed['message'];
  return '';
}

function errorCodeFromPayload(parsed: Record<string, unknown>): string | undefined {
  const nested = parsed['error'];
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    const code = (nested as { code?: unknown }).code;
    if (typeof code === 'string' && code.trim() !== '') return code;
  }
  return undefined;
}

function detailsFromPayload(parsed: Record<string, unknown>): unknown {
  const nested = parsed['error'];
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    return (nested as { details?: unknown }).details;
  }
  return undefined;
}

/**
 * One-line summary from API JSON error bodies (for raw `fetch` probes such as `GET /ready`
 * when the API returns **503** `{ error, requestId }`).
 */
function looksLikeHtmlErrorPage(raw: string): boolean {
  const head = raw.slice(0, 800).trimStart().toLowerCase();
  return head.startsWith('<!doctype') || head.startsWith('<html');
}

export function summaryFromApiErrorBody(body: unknown, httpStatus: number): string {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return `HTTP ${httpStatus}`;
  }
  const parsed = body as Record<string, unknown>;
  const msg = messageFromErrorPayload(parsed);
  if (!msg.trim()) return `HTTP ${httpStatus}`;
  const code = errorCodeFromPayload(parsed);
  const rid = parsed['requestId'];
  const codePart =
    typeof code === 'string' && code.trim() !== '' && !msg.includes(code) ? ` [${code}]` : '';
  const ridPart = typeof rid === 'string' && rid.trim() !== '' ? ` (request ${rid.trim()})` : '';
  return `${msg}${codePart}${ridPart}`;
}

/** Parse a failed HTTP body into {@link ApiFetchError} (same shape as `apiFetch` throws). */
export function apiFetchErrorFromText(status: number, raw: string): ApiFetchError {
  let parsed: Record<string, unknown>;
  try {
    parsed = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
  } catch {
    if (looksLikeHtmlErrorPage(raw)) {
      parsed = {
        message: `HTTP ${status}: the server returned an HTML error page (often a reverse proxy or CDN gateway failure). Confirm the API container is healthy, Caddy can reach asking-api, and LLM base URLs are reachable from inside the API container (not 127.0.0.1 unless Ollama/LM Studio runs in that same container).`,
      };
    } else {
      const trimmed = raw.trim();
      const cap = 2000;
      parsed = {
        message:
          trimmed.length > cap
            ? `${trimmed.slice(0, cap)}… (truncated, HTTP ${status})`
            : trimmed || `HTTP ${status}`,
      };
    }
  }
  const msg = messageFromErrorPayload(parsed) || `HTTP ${status}`;
  const err = new Error(msg) as ApiFetchError;
  err.status = status;
  err.body = parsed;
  const rid = parsed['requestId'];
  err.requestId = typeof rid === 'string' ? rid : undefined;
  err.errorCode = errorCodeFromPayload(parsed);
  const det = detailsFromPayload(parsed);
  if (det !== undefined) err.details = det;
  return err;
}

export async function apiFetch(path: string, options?: ApiFetchOptions): Promise<unknown> {
  const {
    method = 'GET',
    body,
    adminToken,
    bearerToken,
    pollApiKey,
    embedToken,
    headers: extraHeaders,
    ...rest
  } = options ?? {};
  const normalizedPath = path.replace(/^\/+/, '');
  const url = path.startsWith('http') ? path : apiUrl(normalizedPath);

  const headers = new Headers(extraHeaders);

  let token: string | null;
  if (adminToken === false) {
    token = null;
  } else if (typeof adminToken === 'string') {
    token = adminToken;
  } else if (normalizedPath.startsWith('admin/')) {
    token = localStorage.getItem('adminToken');
  } else {
    token = null;
  }
  if (token) {
    headers.set('x-admin-token', token);
  }

  let bearer = bearerToken?.trim();
  if (!bearer && normalizedPath.startsWith('admin/') && adminToken !== false) {
    const sessionJwt = getStoredUserJwt()?.trim();
    if (sessionJwt) bearer = sessionJwt;
  }
  if (bearer) {
    headers.set('Authorization', `Bearer ${bearer}`);
  }

  const embed = embedToken?.trim();
  if (embed) {
    headers.set('X-Poll-Embed-Token', embed);
  }

  const pKey = pollApiKey?.trim();
  if (pKey) {
    headers.set('api_key', pKey);
  }

  const hasJsonObjectBody =
    body != null &&
    typeof body === 'object' &&
    !(body instanceof FormData) &&
    !(body instanceof Blob) &&
    !(body instanceof ArrayBuffer);
  if (hasJsonObjectBody) {
    headers.set('Content-Type', 'application/json');
  }

  const init: RequestInit = { method, headers, ...rest };
  if (body !== undefined && method !== 'GET' && method !== 'HEAD') {
    init.body = hasJsonObjectBody ? JSON.stringify(body) : (body as BodyInit);
  }

  const res = await fetch(url, init);
  if (!res.ok) {
    const raw = await res.text();
    throw apiFetchErrorFromText(res.status, raw);
  }

  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    return res.json();
  }
  const text = await res.text();
  return text === '' ? null : text;
}

/** Headers for raw `fetch` to `admin/*` (e.g. file download) matching {@link apiFetch} auth rules. */
export function buildAdminBrowserAuthHeaders(): Record<string, string> {
  const out: Record<string, string> = {};
  try {
    const t = localStorage.getItem('adminToken')?.trim();
    if (t) out['x-admin-token'] = t;
  } catch {
    /* private mode */
  }
  const j = getStoredUserJwt()?.trim();
  if (j) out['Authorization'] = `Bearer ${j}`;
  return out;
}
