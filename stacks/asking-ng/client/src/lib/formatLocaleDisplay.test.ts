import { describe, expect, it } from 'vitest';
import { formatLocaleDateTime, formatLocaleInteger } from './formatLocaleDisplay';

describe('formatLocaleInteger', () => {
  it('formats with grouping for en-US', () => {
    expect(formatLocaleInteger(12345, 'en-US')).toBe('12,345');
  });

  it('handles non-finite', () => {
    expect(formatLocaleInteger(Number.NaN, 'en-US')).toBe('NaN');
  });
});

describe('formatLocaleDateTime', () => {
  it('formats ISO string with en-US', () => {
    const s = formatLocaleDateTime('2024-06-15T14:30:00.000Z', 'en-US');
    expect(s.length).toBeGreaterThan(4);
    expect(s).toMatch(/2024/);
  });

  it('returns original-looking string for invalid input', () => {
    expect(formatLocaleDateTime('not-a-date', 'en-US')).toBe('not-a-date');
  });
});
