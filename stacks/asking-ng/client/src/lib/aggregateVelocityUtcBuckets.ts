export type VoteVelocityMinuteRow = { minuteUtcIso: string; voteCount: number };

/** Sum vote counts into fixed UTC wall-clock buckets (ms-aligned) for denser charts. */
export function aggregateVelocityUtcBuckets(
  rows: VoteVelocityMinuteRow[],
  bucketMinutes: 1 | 5 | 15,
): VoteVelocityMinuteRow[] {
  if (!rows.length || bucketMinutes <= 1) return rows;
  const bucketMs = bucketMinutes * 60_000;
  const acc = new Map<number, number>();
  for (const row of rows) {
    const ms = Date.parse(row.minuteUtcIso);
    if (!Number.isFinite(ms)) continue;
    const key = Math.floor(ms / bucketMs) * bucketMs;
    acc.set(key, (acc.get(key) ?? 0) + row.voteCount);
  }
  return Array.from(acc.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([k, v]) => ({
      minuteUtcIso: new Date(k).toISOString(),
      voteCount: v,
    }));
}
