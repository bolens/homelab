import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiUrl, pollWsUrl } from './apiBase';

describe('apiUrl', () => {
  it('prefixes /api in dev when VITE_API_BASE is unset', () => {
    expect(apiUrl('poll/1')).toBe('/api/poll/1');
  });
});

describe('pollWsUrl', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('adds embed_token and ws_bearer to websocket URL', () => {
    vi.stubGlobal('window', {
      location: { protocol: 'https:', host: 'example.com' },
    });
    const u = pollWsUrl('p1', { embedToken: 'e', wsBearer: 'jwt' });
    expect(u.startsWith('wss://example.com/')).toBe(true);
    expect(u).toContain('/ws/poll/p1');
    expect(u).toContain('embed_token=e');
    expect(u).toContain('ws_bearer=jwt');
  });
});
