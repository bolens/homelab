import { describe, expect, it } from 'vitest';
import { relativePathFromLocation } from './routerPath';

describe('relativePathFromLocation', () => {
  it('returns / for root pathname when base empty', () => {
    expect(relativePathFromLocation('/', '/')).toBe('/');
    expect(relativePathFromLocation('/about', '/')).toBe('/about');
  });

  it('strips base path prefix', () => {
    expect(relativePathFromLocation('/app/', '/app/')).toBe('/');
    expect(relativePathFromLocation('/app/about', '/app/')).toBe('/about');
  });
});
