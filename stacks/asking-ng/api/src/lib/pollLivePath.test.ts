import { describe, expect, it } from 'vitest';
import { matchPollLivePath } from './pollLivePath';

describe('matchPollLivePath', () => {
  it('parses poll id from path', () => {
    expect(matchPollLivePath('/ws/poll/abc123')).toBe('abc123');
  });

  it('decodes encoded id', () => {
    expect(matchPollLivePath('/ws/poll/hello%20world')).toBe('hello world');
  });

  it('returns null for other paths', () => {
    expect(matchPollLivePath('/poll/x')).toBeNull();
    expect(matchPollLivePath('/ws/poll/')).toBeNull();
  });
});
