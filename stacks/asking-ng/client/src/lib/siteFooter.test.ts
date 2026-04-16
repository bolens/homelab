import { describe, expect, it } from 'vitest';
import {
  DEFAULT_ATTRIBUTION_HREF,
  parseAttributionUrlFromEnv,
  parseSiteFooterFromEnv,
} from './siteFooter';

describe('siteFooter', () => {
  it('parseSiteFooterFromEnv', () => {
    expect(parseSiteFooterFromEnv({}).kind).toBe('default');
    expect(parseSiteFooterFromEnv({ VITE_SITE_FOOTER: '  default  ' }).kind).toBe('default');
    expect(parseSiteFooterFromEnv({ VITE_SITE_FOOTER: 'hidden' }).kind).toBe('hidden');
    expect(parseSiteFooterFromEnv({ VITE_SITE_FOOTER: 'NONE' }).kind).toBe('hidden');
    expect(parseSiteFooterFromEnv({ VITE_SITE_FOOTER: '  Hello stream  ' })).toEqual({
      kind: 'custom',
      text: 'Hello stream',
    });
  });

  it('parseAttributionUrlFromEnv', () => {
    expect(parseAttributionUrlFromEnv({})).toBe(DEFAULT_ATTRIBUTION_HREF);
    expect(parseAttributionUrlFromEnv({ VITE_ATTRIBUTION_URL: 'https://example.com/x' })).toBe(
      'https://example.com/x',
    );
    expect(parseAttributionUrlFromEnv({ VITE_ATTRIBUTION_URL: 'http://evil.com' })).toBe(
      DEFAULT_ATTRIBUTION_HREF,
    );
    expect(parseAttributionUrlFromEnv({ VITE_ATTRIBUTION_URL: 'http://localhost:5173/' })).toBe(
      'http://localhost:5173/',
    );
  });
});
