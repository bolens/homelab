import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiUrl, pollWsUrl } from './apiBase';

describe('apiUrl', () => {
  it('joins path with leading slash when base is empty', () => {
    expect(apiUrl('poll/1')).toBe('/poll/1');
  });
});

describe('pollWsUrl', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('adds embed_token and ws_bearer when base is empty (same-origin ws)', () => {
    vi.stubGlobal('window', {
      location: { protocol: 'https:', host: 'example.com' },
    });
    const u = pollWsUrl('p1', { embedToken: 'e', wsBearer: 'jwt' });
    expect(u.startsWith('wss://example.com/ws/ws/poll/p1?')).toBe(true);
    expect(u).toContain('embed_token=e');
    expect(u).toContain('ws_bearer=jwt');
  });
});
