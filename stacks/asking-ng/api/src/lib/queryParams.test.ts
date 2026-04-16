import { describe, expect, it } from 'vitest';
import { firstQueryParam, normalizeQueryParams, parseBoundedInt } from './queryParams';

describe('firstQueryParam', () => {
  it('returns first string from array', () => {
    expect(firstQueryParam(['a', 'b'])).toBe('a');
  });

  it('returns undefined for non-string values', () => {
    expect(firstQueryParam(undefined)).toBeUndefined();
    expect(firstQueryParam(null as unknown as string)).toBeUndefined();
    expect(firstQueryParam([1] as unknown as string[])).toBeUndefined();
  });
});

describe('normalizeQueryParams', () => {
  it('normalizes object values into first-string map', () => {
    const query = {
      one: '1',
      two: ['2', '3'],
      three: undefined,
    } as unknown as Record<string, string | string[] | undefined>;
    expect(normalizeQueryParams(query)).toEqual({
      one: '1',
      two: '2',
      three: undefined,
    });
  });
});

describe('parseBoundedInt', () => {
  it('uses default for invalid values', () => {
    expect(parseBoundedInt(undefined, { min: 1, max: 10, defaultValue: 5 })).toBe(5);
    expect(parseBoundedInt('x', { min: 1, max: 10, defaultValue: 5 })).toBe(5);
    expect(parseBoundedInt('0', { min: 1, max: 10, defaultValue: 5 })).toBe(5);
  });

  it('clamps values above max', () => {
    expect(parseBoundedInt('99', { min: 1, max: 10, defaultValue: 5 })).toBe(10);
  });
});
