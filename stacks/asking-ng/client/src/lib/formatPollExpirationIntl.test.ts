import { describe, expect, it } from 'vitest';
import { formatPollExpiryAbsolute, formatPollExpiryRelative } from './formatPollExpirationIntl';

describe('formatPollExpiryRelative', () => {
  it('returns expired when end is in the past', () => {
    const now = 1_700_000_000_000;
    expect(formatPollExpiryRelative('en', now - 60_000, now)).toEqual({
      state: 'expired',
      text: '',
    });
  });

  it('returns never for far-future expirations', () => {
    const now = 1_700_000_000_000;
    const far = now + 864_001 * 3600 * 1000;
    expect(formatPollExpiryRelative('en', far, now).state).toBe('never');
  });

  it('returns relative string for a few minutes ahead', () => {
    const now = Date.UTC(2026, 3, 14, 12, 0, 0);
    const exp = Date.UTC(2026, 3, 14, 12, 5, 0);
    const r = formatPollExpiryRelative('en', exp, now);
    expect(r.state).toBe('relative');
    expect(r.text.length).toBeGreaterThan(0);
    expect(r.text.toLowerCase()).toMatch(/minute|min/);
  });

  it('returns invalid for non-finite expiration', () => {
    expect(formatPollExpiryRelative('en', Number.NaN, 0).state).toBe('invalid');
  });
});

describe('formatPollExpiryAbsolute', () => {
  it('formats a fixed instant', () => {
    const s = formatPollExpiryAbsolute('en-US', Date.UTC(2026, 3, 14, 15, 30, 0));
    expect(s).toMatch(/2026/);
    expect(s.length).toBeGreaterThan(6);
  });
});
