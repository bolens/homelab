/** Base path for API calls (e.g. `/api` when behind Caddy). */
function apiBase(): string {
  const raw = import.meta.env.VITE_API_BASE;
  // In local Vite dev, the proxy is mounted at `/api`; default to it when unset.
  if (raw === undefined || raw === null || raw === '') {
    return import.meta.env.DEV ? '/api' : '';
  }
  return String(raw).replace(/\/$/, '');
}

export function apiUrl(path: string): string {
  const base = apiBase();
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${base}${p}`;
}

/**
 * WebSocket URL for live poll updates (`GET /ws/poll/:id` on the API).
 * Mirrors {@link apiUrl} base rules: relative `/api`, absolute `http(s):`, or same-origin when base is empty.
 */
export function pollWsUrl(
  pollId: string,
  opts?: { embedToken?: string; wsBearer?: string },
): string {
  const enc = encodeURIComponent(pollId);
  const path = `/ws/poll/${enc}`;
  const base = apiBase();
  const params = new URLSearchParams();
  const et = opts?.embedToken?.trim();
  if (et) params.set('embed_token', et);
  const wb = opts?.wsBearer?.trim();
  if (wb) params.set('ws_bearer', wb);
  const qs = params.toString() ? `?${params.toString()}` : '';

  if (!base) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Dev: Vite proxies `/ws` to the API (see `vite.config.ts`). Prod usually sets `VITE_API_BASE=/api`.
    return `${proto}//${window.location.host}/ws${path}${qs}`;
  }
  if (base.startsWith('http://') || base.startsWith('https://')) {
    const u = new URL(base);
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    u.pathname = `${u.pathname.replace(/\/$/, '')}${path}`;
    u.search = qs.startsWith('?') ? qs.slice(1) : '';
    u.hash = '';
    return u.toString();
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${base.replace(/\/$/, '')}${path}${qs}`;
}
