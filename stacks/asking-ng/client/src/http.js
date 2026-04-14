import { apiUrl } from './apiBase';

/**
 * @param {string} path - e.g. `poll/1`, `admin/users` (no base; query string allowed)
 * @param {RequestInit & { body?: object; adminToken?: string | false }} [options]
 * @returns {Promise<unknown>} Parsed JSON when Content-Type is JSON, else response text (or null if empty)
 */
export async function apiFetch(path, options = {}) {
  const { method = 'GET', body, adminToken, headers: extraHeaders, ...rest } = options;
  const normalizedPath = path.replace(/^\/+/, '');
  const url = path.startsWith('http') ? path : apiUrl(normalizedPath);

  const headers = new Headers(extraHeaders);

  let token;
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

  const hasJsonObjectBody =
    body != null &&
    typeof body === 'object' &&
    !(body instanceof FormData) &&
    !(body instanceof Blob) &&
    !(body instanceof ArrayBuffer);
  if (hasJsonObjectBody) {
    headers.set('Content-Type', 'application/json');
  }

  /** @type {RequestInit} */
  const init = { method, headers, ...rest };
  if (body !== undefined && method !== 'GET' && method !== 'HEAD') {
    init.body = hasJsonObjectBody ? JSON.stringify(body) : body;
  }

  const res = await fetch(url, init);
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }

  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    return res.json();
  }
  const text = await res.text();
  return text === '' ? null : text;
}
