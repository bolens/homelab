import { describe, expect, it } from 'vitest';
import { aggregateVelocityUtcBuckets } from './aggregateVelocityUtcBuckets';

describe('aggregateVelocityUtcBuckets', () => {
  it('returns rows unchanged for 1-minute buckets', () => {
    const rows = [
      { minuteUtcIso: '2026-01-01T00:01:00.000Z', voteCount: 2 },
      { minuteUtcIso: '2026-01-01T00:02:00.000Z', voteCount: 3 },
    ];
    expect(aggregateVelocityUtcBuckets(rows, 1)).toEqual(rows);
  });

  it('merges into 5-minute UTC buckets', () => {
    const rows = [
      { minuteUtcIso: '2026-01-01T00:01:00.000Z', voteCount: 2 },
      { minuteUtcIso: '2026-01-01T00:03:00.000Z', voteCount: 3 },
      { minuteUtcIso: '2026-01-01T00:04:00.000Z', voteCount: 1 },
    ];
    const out = aggregateVelocityUtcBuckets(rows, 5);
    expect(out).toHaveLength(1);
    const first = out[0];
    expect(first?.minuteUtcIso).toBe('2026-01-01T00:00:00.000Z');
    expect(first?.voteCount).toBe(6);
  });
});
