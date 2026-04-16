import { QueryTypes } from 'sequelize';
import db from '../connections';

let lastReadModelRefreshAtMs = 0;
const lastPollReadModelRefreshAtMs = new Map<string, number>();

export type PollVoteRollupRow = {
  poll_id: string;
  total_votes: string | number;
  votes_last_1m: string | number;
  votes_last_24h: string | number;
  quarantined_votes_pending: string | number;
  updated_at: Date | string;
};

export type PollVoteGeoBinRow = {
  latitude_bucket: string | number;
  longitude_bucket: string | number;
  votes_count: string | number;
};

export type PollVoteReplayEventRow = {
  option_label: string;
  offset_ms: string | number;
};

export async function refreshPollVoteRollupsIfStale(minIntervalMs = 30_000): Promise<void> {
  const now = Date.now();
  if (now - lastReadModelRefreshAtMs < minIntervalMs) return;
  await db.query(`
    INSERT INTO poll_vote_rollups (
      poll_id,
      total_votes,
      votes_last_1m,
      votes_last_24h,
      quarantined_votes_pending,
      updated_at
    )
    SELECT
      p.id AS poll_id,
      COUNT(v.*) FILTER (WHERE COALESCE(v."isQuarantined", false) = false)::int AS total_votes,
      COUNT(v.*) FILTER (
        WHERE v."createdAt" >= NOW() - INTERVAL '1 minute'
          AND COALESCE(v."isQuarantined", false) = false
      )::int AS votes_last_1m,
      COUNT(v.*) FILTER (
        WHERE v."createdAt" >= NOW() - INTERVAL '24 hours'
          AND COALESCE(v."isQuarantined", false) = false
      )::int AS votes_last_24h,
      COUNT(v.*) FILTER (
        WHERE COALESCE(v."isQuarantined", false) = true
          AND COALESCE(v."quarantineStatus", 'pending') = 'pending'
      )::int AS quarantined_votes_pending,
      NOW() AS updated_at
    FROM polls p
    LEFT JOIN votes v ON v."pollId" = p.id
    GROUP BY p.id
    ON CONFLICT (poll_id) DO UPDATE SET
      total_votes = EXCLUDED.total_votes,
      votes_last_1m = EXCLUDED.votes_last_1m,
      votes_last_24h = EXCLUDED.votes_last_24h,
      quarantined_votes_pending = EXCLUDED.quarantined_votes_pending,
      updated_at = EXCLUDED.updated_at;
  `);
  await db.query(`
    DELETE FROM poll_vote_replay_events;
  `);
  await db.query(`
    INSERT INTO poll_vote_replay_events (
      poll_id,
      sequence_no,
      option_label,
      offset_ms,
      updated_at
    )
    SELECT
      t.poll_id,
      t.sequence_no,
      t.option_label,
      t.offset_ms,
      NOW() AS updated_at
    FROM (
      SELECT
        v."pollId" AS poll_id,
        ROW_NUMBER() OVER (
          PARTITION BY v."pollId"
          ORDER BY v."createdAt" ASC, v.id ASC
        )::int AS sequence_no,
        v.option AS option_label,
        GREATEST(
          0,
          FLOOR(
            EXTRACT(
              EPOCH FROM (
                v."createdAt" - FIRST_VALUE(v."createdAt") OVER (
                  PARTITION BY v."pollId"
                  ORDER BY v."createdAt" ASC, v.id ASC
                )
              )
            ) * 1000
          )
        )::bigint AS offset_ms
      FROM votes v
      WHERE COALESCE(v."isQuarantined", false) = false
    ) t
    ON CONFLICT (poll_id, sequence_no) DO UPDATE SET
      option_label = EXCLUDED.option_label,
      offset_ms = EXCLUDED.offset_ms,
      updated_at = EXCLUDED.updated_at;
  `);
  await db.query(`
    DELETE FROM poll_vote_geo_bins;
  `);
  await db.query(`
    INSERT INTO poll_vote_geo_bins (
      poll_id,
      latitude_bucket,
      longitude_bucket,
      vote_count,
      updated_at
    )
    SELECT
      v."pollId" AS poll_id,
      v.vote_latitude::numeric(4,1) AS latitude_bucket,
      v.vote_longitude::numeric(4,1) AS longitude_bucket,
      COUNT(*)::int AS vote_count,
      NOW() AS updated_at
    FROM votes v
    WHERE COALESCE(v."isQuarantined", false) = false
      AND v.vote_latitude IS NOT NULL
      AND v.vote_longitude IS NOT NULL
    GROUP BY
      v."pollId",
      v.vote_latitude::numeric(4,1),
      v.vote_longitude::numeric(4,1)
    ON CONFLICT (poll_id, latitude_bucket, longitude_bucket) DO UPDATE SET
      vote_count = EXCLUDED.vote_count,
      updated_at = EXCLUDED.updated_at;
  `);
  await db.query(`
    DELETE FROM poll_vote_time_bins_hourly;
  `);
  await db.query(`
    INSERT INTO poll_vote_time_bins_hourly (
      poll_id,
      hour_bucket_utc,
      vote_count,
      updated_at
    )
    SELECT
      v."pollId" AS poll_id,
      date_trunc('hour', v."createdAt" AT TIME ZONE 'UTC') AS hour_bucket_utc,
      COUNT(*)::int AS vote_count,
      NOW() AS updated_at
    FROM votes v
    WHERE COALESCE(v."isQuarantined", false) = false
    GROUP BY v."pollId", date_trunc('hour', v."createdAt" AT TIME ZONE 'UTC')
    ON CONFLICT (poll_id, hour_bucket_utc) DO UPDATE SET
      vote_count = EXCLUDED.vote_count,
      updated_at = EXCLUDED.updated_at;
  `);
  lastReadModelRefreshAtMs = now;
}

export async function refreshPollReadModelsForPollIds(
  pollIds: string[],
  minIntervalMs = 10_000,
): Promise<void> {
  const uniquePollIds = [...new Set(pollIds.map((id) => id.trim()).filter(Boolean))];
  if (uniquePollIds.length === 0) return;
  const now = Date.now();
  const stalePollIds = uniquePollIds.filter((pollId) => {
    const last = lastPollReadModelRefreshAtMs.get(pollId) ?? 0;
    return now - last >= minIntervalMs;
  });
  if (stalePollIds.length === 0) return;

  await db.query(
    `DELETE FROM poll_vote_replay_events
     WHERE poll_id IN (:pollIds)`,
    { replacements: { pollIds: stalePollIds } },
  );
  await db.query(
    `DELETE FROM poll_vote_geo_bins
     WHERE poll_id IN (:pollIds)`,
    { replacements: { pollIds: stalePollIds } },
  );
  await db.query(
    `DELETE FROM poll_vote_time_bins_hourly
     WHERE poll_id IN (:pollIds)`,
    { replacements: { pollIds: stalePollIds } },
  );

  await db.query(
    `
    INSERT INTO poll_vote_rollups (
      poll_id,
      total_votes,
      votes_last_1m,
      votes_last_24h,
      quarantined_votes_pending,
      updated_at
    )
    SELECT
      p.id AS poll_id,
      COUNT(v.*) FILTER (WHERE COALESCE(v."isQuarantined", false) = false)::int AS total_votes,
      COUNT(v.*) FILTER (
        WHERE v."createdAt" >= NOW() - INTERVAL '1 minute'
          AND COALESCE(v."isQuarantined", false) = false
      )::int AS votes_last_1m,
      COUNT(v.*) FILTER (
        WHERE v."createdAt" >= NOW() - INTERVAL '24 hours'
          AND COALESCE(v."isQuarantined", false) = false
      )::int AS votes_last_24h,
      COUNT(v.*) FILTER (
        WHERE COALESCE(v."isQuarantined", false) = true
          AND COALESCE(v."quarantineStatus", 'pending') = 'pending'
      )::int AS quarantined_votes_pending,
      NOW() AS updated_at
    FROM polls p
    LEFT JOIN votes v ON v."pollId" = p.id
    WHERE p.id IN (:pollIds)
    GROUP BY p.id
    ON CONFLICT (poll_id) DO UPDATE SET
      total_votes = EXCLUDED.total_votes,
      votes_last_1m = EXCLUDED.votes_last_1m,
      votes_last_24h = EXCLUDED.votes_last_24h,
      quarantined_votes_pending = EXCLUDED.quarantined_votes_pending,
      updated_at = EXCLUDED.updated_at;
    `,
    { replacements: { pollIds: stalePollIds } },
  );

  await db.query(
    `
    INSERT INTO poll_vote_replay_events (
      poll_id,
      sequence_no,
      option_label,
      offset_ms,
      updated_at
    )
    SELECT
      t.poll_id,
      t.sequence_no,
      t.option_label,
      t.offset_ms,
      NOW() AS updated_at
    FROM (
      SELECT
        v."pollId" AS poll_id,
        ROW_NUMBER() OVER (
          PARTITION BY v."pollId"
          ORDER BY v."createdAt" ASC, v.id ASC
        )::int AS sequence_no,
        v.option AS option_label,
        GREATEST(
          0,
          FLOOR(
            EXTRACT(
              EPOCH FROM (
                v."createdAt" - FIRST_VALUE(v."createdAt") OVER (
                  PARTITION BY v."pollId"
                  ORDER BY v."createdAt" ASC, v.id ASC
                )
              )
            ) * 1000
          )
        )::bigint AS offset_ms
      FROM votes v
      WHERE COALESCE(v."isQuarantined", false) = false
        AND v."pollId" IN (:pollIds)
    ) t
    ON CONFLICT (poll_id, sequence_no) DO UPDATE SET
      option_label = EXCLUDED.option_label,
      offset_ms = EXCLUDED.offset_ms,
      updated_at = EXCLUDED.updated_at;
    `,
    { replacements: { pollIds: stalePollIds } },
  );

  await db.query(
    `
    INSERT INTO poll_vote_geo_bins (
      poll_id,
      latitude_bucket,
      longitude_bucket,
      vote_count,
      updated_at
    )
    SELECT
      v."pollId" AS poll_id,
      v.vote_latitude::numeric(4,1) AS latitude_bucket,
      v.vote_longitude::numeric(4,1) AS longitude_bucket,
      COUNT(*)::int AS vote_count,
      NOW() AS updated_at
    FROM votes v
    WHERE COALESCE(v."isQuarantined", false) = false
      AND v.vote_latitude IS NOT NULL
      AND v.vote_longitude IS NOT NULL
      AND v."pollId" IN (:pollIds)
    GROUP BY
      v."pollId",
      v.vote_latitude::numeric(4,1),
      v.vote_longitude::numeric(4,1)
    ON CONFLICT (poll_id, latitude_bucket, longitude_bucket) DO UPDATE SET
      vote_count = EXCLUDED.vote_count,
      updated_at = EXCLUDED.updated_at;
    `,
    { replacements: { pollIds: stalePollIds } },
  );

  await db.query(
    `
    INSERT INTO poll_vote_time_bins_hourly (
      poll_id,
      hour_bucket_utc,
      vote_count,
      updated_at
    )
    SELECT
      v."pollId" AS poll_id,
      date_trunc('hour', v."createdAt" AT TIME ZONE 'UTC') AS hour_bucket_utc,
      COUNT(*)::int AS vote_count,
      NOW() AS updated_at
    FROM votes v
    WHERE COALESCE(v."isQuarantined", false) = false
      AND v."pollId" IN (:pollIds)
    GROUP BY v."pollId", date_trunc('hour', v."createdAt" AT TIME ZONE 'UTC')
    ON CONFLICT (poll_id, hour_bucket_utc) DO UPDATE SET
      vote_count = EXCLUDED.vote_count,
      updated_at = EXCLUDED.updated_at;
    `,
    { replacements: { pollIds: stalePollIds } },
  );

  for (const pollId of stalePollIds) lastPollReadModelRefreshAtMs.set(pollId, now);
}

export async function refreshPollVoteRollupsNow(): Promise<void> {
  await refreshPollVoteRollupsIfStale(0);
}

export async function getGlobalVoteRollups(): Promise<{
  total_votes: string | number;
  votes_last_24h: string | number;
}> {
  const [row] = (await db.query(
    `SELECT
      COALESCE(SUM(total_votes), 0)::int AS total_votes,
      COALESCE(SUM(votes_last_24h), 0)::int AS votes_last_24h
     FROM poll_vote_rollups`,
    { type: QueryTypes.SELECT },
  )) as Array<{ total_votes: string | number; votes_last_24h: string | number }>;
  return row ?? { total_votes: 0, votes_last_24h: 0 };
}

export async function getPollVoteRollup(pollId: string): Promise<PollVoteRollupRow | null> {
  const [row] = (await db.query(
    `SELECT
      poll_id,
      total_votes,
      votes_last_1m,
      votes_last_24h,
      quarantined_votes_pending,
      updated_at
     FROM poll_vote_rollups
     WHERE poll_id = :pollId
     LIMIT 1`,
    { replacements: { pollId }, type: QueryTypes.SELECT },
  )) as PollVoteRollupRow[];
  return row ?? null;
}

export async function getPollGeoBinsFromRollups(args: {
  pollId: string;
  minCount: number;
}): Promise<PollVoteGeoBinRow[]> {
  const rows = (await db.query(
    `SELECT
      latitude_bucket,
      longitude_bucket,
      vote_count AS votes_count
     FROM poll_vote_geo_bins
     WHERE poll_id = :pollId
       AND vote_count >= :minCount
     ORDER BY vote_count DESC
     LIMIT 1000`,
    {
      replacements: { pollId: args.pollId, minCount: args.minCount },
      type: QueryTypes.SELECT,
    },
  )) as PollVoteGeoBinRow[];
  return rows;
}

export async function getPollReplayEventsFromRollups(args: {
  pollId: string;
  limit: number;
}): Promise<PollVoteReplayEventRow[]> {
  const rows = (await db.query(
    `SELECT
      option_label,
      offset_ms
     FROM poll_vote_replay_events
     WHERE poll_id = :pollId
     ORDER BY sequence_no ASC
     LIMIT :limit`,
    {
      replacements: { pollId: args.pollId, limit: args.limit },
      type: QueryTypes.SELECT,
    },
  )) as PollVoteReplayEventRow[];
  return rows;
}

export async function getGlobalTimeBinsFromRollups(): Promise<{
  hourBins: Array<{ hour_utc: string | number; vote_count: string | number }>;
  dowBins: Array<{ dow_utc: string | number; vote_count: string | number }>;
  peakHour: { peak_hour_utc: string | number; peak_hour_votes: string | number } | null;
  peakDow: { peak_dow_utc: string | number; peak_dow_votes: string | number } | null;
}> {
  const hourBins = (await db.query(
    `SELECT
      EXTRACT(HOUR FROM hour_bucket_utc)::int AS hour_utc,
      SUM(vote_count)::int AS vote_count
     FROM poll_vote_time_bins_hourly
     GROUP BY EXTRACT(HOUR FROM hour_bucket_utc)
     ORDER BY hour_utc ASC`,
    { type: QueryTypes.SELECT },
  )) as Array<{ hour_utc: string | number; vote_count: string | number }>;

  const dowBins = (await db.query(
    `SELECT
      EXTRACT(DOW FROM hour_bucket_utc)::int AS dow_utc,
      SUM(vote_count)::int AS vote_count
     FROM poll_vote_time_bins_hourly
     GROUP BY EXTRACT(DOW FROM hour_bucket_utc)
     ORDER BY dow_utc ASC`,
    { type: QueryTypes.SELECT },
  )) as Array<{ dow_utc: string | number; vote_count: string | number }>;

  const [peakHour] = (await db.query(
    `SELECT
      EXTRACT(HOUR FROM hour_bucket_utc)::int AS peak_hour_utc,
      SUM(vote_count)::int AS peak_hour_votes
     FROM poll_vote_time_bins_hourly
     GROUP BY EXTRACT(HOUR FROM hour_bucket_utc)
     ORDER BY peak_hour_votes DESC, peak_hour_utc ASC
     LIMIT 1`,
    { type: QueryTypes.SELECT },
  )) as Array<{ peak_hour_utc: string | number; peak_hour_votes: string | number }>;

  const [peakDow] = (await db.query(
    `SELECT
      EXTRACT(DOW FROM hour_bucket_utc)::int AS peak_dow_utc,
      SUM(vote_count)::int AS peak_dow_votes
     FROM poll_vote_time_bins_hourly
     GROUP BY EXTRACT(DOW FROM hour_bucket_utc)
     ORDER BY peak_dow_votes DESC, peak_dow_utc ASC
     LIMIT 1`,
    { type: QueryTypes.SELECT },
  )) as Array<{ peak_dow_utc: string | number; peak_dow_votes: string | number }>;

  return { hourBins, dowBins, peakHour: peakHour ?? null, peakDow: peakDow ?? null };
}

export type PollVoteRollupReconcileRow = {
  poll_id: string;
  canonical_total_votes: string | number;
  rollup_total_votes: string | number;
  canonical_votes_last_1m: string | number;
  rollup_votes_last_1m: string | number;
  canonical_votes_last_24h: string | number;
  rollup_votes_last_24h: string | number;
  canonical_quarantined_votes_pending: string | number;
  rollup_quarantined_votes_pending: string | number;
};

export async function reconcilePollVoteRollups(args?: {
  limit?: number;
  diffThreshold?: number;
}): Promise<PollVoteRollupReconcileRow[]> {
  const limit = Math.max(1, Math.min(500, Math.floor(args?.limit ?? 50)));
  const diffThreshold = Math.max(0, Math.floor(args?.diffThreshold ?? 0));
  const rows = (await db.query(
    `WITH canonical AS (
      SELECT
        p.id AS poll_id,
        COUNT(v.*) FILTER (WHERE COALESCE(v."isQuarantined", false) = false)::int AS total_votes,
        COUNT(v.*) FILTER (
          WHERE v."createdAt" >= NOW() - INTERVAL '1 minute'
            AND COALESCE(v."isQuarantined", false) = false
        )::int AS votes_last_1m,
        COUNT(v.*) FILTER (
          WHERE v."createdAt" >= NOW() - INTERVAL '24 hours'
            AND COALESCE(v."isQuarantined", false) = false
        )::int AS votes_last_24h,
        COUNT(v.*) FILTER (
          WHERE COALESCE(v."isQuarantined", false) = true
            AND COALESCE(v."quarantineStatus", 'pending') = 'pending'
        )::int AS quarantined_votes_pending
      FROM polls p
      LEFT JOIN votes v ON v."pollId" = p.id
      GROUP BY p.id
    )
    SELECT
      c.poll_id,
      c.total_votes AS canonical_total_votes,
      COALESCE(r.total_votes, 0)::int AS rollup_total_votes,
      c.votes_last_1m AS canonical_votes_last_1m,
      COALESCE(r.votes_last_1m, 0)::int AS rollup_votes_last_1m,
      c.votes_last_24h AS canonical_votes_last_24h,
      COALESCE(r.votes_last_24h, 0)::int AS rollup_votes_last_24h,
      c.quarantined_votes_pending AS canonical_quarantined_votes_pending,
      COALESCE(r.quarantined_votes_pending, 0)::int AS rollup_quarantined_votes_pending
    FROM canonical c
    LEFT JOIN poll_vote_rollups r ON r.poll_id = c.poll_id
    WHERE
      ABS(COALESCE(r.total_votes, 0) - c.total_votes) > :diffThreshold
      OR ABS(COALESCE(r.votes_last_1m, 0) - c.votes_last_1m) > :diffThreshold
      OR ABS(COALESCE(r.votes_last_24h, 0) - c.votes_last_24h) > :diffThreshold
      OR ABS(COALESCE(r.quarantined_votes_pending, 0) - c.quarantined_votes_pending) > :diffThreshold
    ORDER BY
      GREATEST(
        ABS(COALESCE(r.total_votes, 0) - c.total_votes),
        ABS(COALESCE(r.votes_last_1m, 0) - c.votes_last_1m),
        ABS(COALESCE(r.votes_last_24h, 0) - c.votes_last_24h),
        ABS(COALESCE(r.quarantined_votes_pending, 0) - c.quarantined_votes_pending)
      ) DESC,
      c.poll_id ASC
    LIMIT :limit`,
    { replacements: { limit, diffThreshold }, type: QueryTypes.SELECT },
  )) as PollVoteRollupReconcileRow[];
  return rows;
}
