import { describe, expect, it } from 'vitest';
import { parseAuditLogsQuery, parseAuditLogsSearch } from './audit-logs';

describe('parseAuditLogsSearch', () => {
  it('parses target string', () => {
    expect(parseAuditLogsSearch({ target: '42' })).toEqual(
      expect.objectContaining({ target: '42', limit: undefined }),
    );
  });

  it('drops non-string scalar fields', () => {
    expect(parseAuditLogsSearch({ target: 99 })).toEqual(
      expect.objectContaining({ target: undefined, limit: undefined }),
    );
  });

  it('parses full filter set from URL-style object', () => {
    expect(
      parseAuditLogsSearch({
        action: 'login',
        actor: 'admin',
        target: 'p1',
        start: '2024-01-01',
        end: '2024-12-31',
        limit: '50',
      }),
    ).toEqual({
      action: 'login',
      actor: 'admin',
      target: 'p1',
      start: '2024-01-01',
      end: '2024-12-31',
      limit: 50,
    });
  });

  it('rejects non-numeric limit', () => {
    expect(() => parseAuditLogsSearch({ limit: 'x' })).toThrow();
  });

  it('accepts numeric limit from router state', () => {
    expect(parseAuditLogsSearch({ limit: 50 })).toEqual(expect.objectContaining({ limit: 50 }));
  });
});

describe('parseAuditLogsQuery', () => {
  it('defaults limit to 100', () => {
    expect(parseAuditLogsQuery({})).toEqual(expect.objectContaining({ limit: 100 }));
  });
});
