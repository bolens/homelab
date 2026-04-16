import { describe, expect, it } from 'vitest';
import { pollPathForId, shareUrlForPoll } from './pollUrl';

describe('pollPathForId', () => {
  it('ends with the poll id', () => {
    expect(pollPathForId('my-poll')).toMatch(/my-poll$/);
  });
});

describe('shareUrlForPoll', () => {
  it('prefixes origin and includes poll path', () => {
    const u = shareUrlForPoll('xyz');
    expect(u.startsWith(window.location.origin)).toBe(true);
    expect(u).toContain('xyz');
  });
});
