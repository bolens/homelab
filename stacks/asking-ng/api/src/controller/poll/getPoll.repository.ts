import { QueryTypes } from 'sequelize';
import db from '../../connections';

type PollVoteRow = {
  option: string;
  vote_count: string | number;
  weighted_vote_count: string | number;
};

type PollMetricsRow = {
  total_votes: string | number;
  total_weighted_votes: string | number;
  votes_last_5m: string | number;
  first_vote_at: Date | string | null;
};

type PollPeakHourRow = {
  peak_hour_utc: string | number;
  peak_hour_votes: string | number;
};

type PollPeakDowRow = {
  peak_dow_utc: string | number;
  peak_dow_votes: string | number;
};

type PollHourBinRow = {
  hour_utc: string | number;
  vote_count: string | number;
};

type PollDowBinRow = {
  dow_utc: string | number;
  vote_count: string | number;
};

type PollOptionHourBinRow = {
  option_label: string;
  hour_utc: string | number;
  vote_count: string | number;
};

type PollVoteMinuteBinRow = {
  minute_utc: Date | string;
  vote_count: string | number;
};

type PollOptionVoteMinuteBinRow = {
  option_label: string;
  minute_utc: Date | string;
  vote_count: string | number;
};

type PollRateCountersRow = {
  votes_last_1m: string | number;
  unique_ip_hashes_last_1m: string | number;
  unique_accounts_last_1m: string | number;
  top_ip_votes_last_1m: string | number;
  quarantined_votes_pending: string | number;
  quarantined_votes_pending_account_linked: string | number;
  votes_account_linked_last_24h: string | number;
  votes_anonymous_last_24h: string | number;
};

type PollDelayedPendingRow = {
  delayed_votes_pending: string | number;
};

export type PollVoteAnalytics = {
  voteData: PollVoteRow[];
  metricsRow: PollMetricsRow | undefined;
  peakHourRow: PollPeakHourRow | undefined;
  peakDowRow: PollPeakDowRow | undefined;
  hourBins: PollHourBinRow[];
  dowBins: PollDowBinRow[];
  /** Owner-only: vote counts per configured option label by UTC clock hour (0–23). */
  optionHourBins: PollOptionHourBinRow[];
  /** Owner-only: up to 4000 most recent UTC minutes with ≥1 vote (chronological after service normalizes). */
  voteMinuteBins: PollVoteMinuteBinRow[];
  /**
   * Owner-only: per-option counts on the same ≤120 most recent distinct UTC minutes (any option);
   * aligns with aggregate minute chart for cross-option comparison (sparse rows filled in service).
   */
  optionVoteMinuteBins: PollOptionVoteMinuteBinRow[];
  rateCountersRow: PollRateCountersRow | undefined;
  delayedVotesPending: number;
};

type GetPollVoteAnalyticsArgs = {
  pollId: string;
  resultsVisibleThroughIso: string;
  liveResultsAreDelayed: boolean;
  youOwnThisPoll: boolean;
};

export async function getPollVoteAnalytics({
  pollId,
  resultsVisibleThroughIso,
  liveResultsAreDelayed,
  youOwnThisPoll,
}: GetPollVoteAnalyticsArgs): Promise<PollVoteAnalytics> {
  const liveVoteWindowSql = liveResultsAreDelayed
    ? `AND "createdAt" <= :resultsVisibleThrough`
    : ``;

  const voteData = (await db.query(
    `SELECT option, count(option) as vote_count, COALESCE(sum(weight), count(option)) as weighted_vote_count
     FROM votes
     WHERE "pollId" = :pollId
       AND COALESCE("isQuarantined", false) = false
       ${liveVoteWindowSql}
     GROUP BY option;`,
    {
      replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
      type: QueryTypes.SELECT,
    },
  )) as PollVoteRow[];

  const [metricsRow] = (await db.query(
    `SELECT
      COUNT(*)::int AS total_votes,
      COALESCE(SUM(weight), COUNT(*))::int AS total_weighted_votes,
      COUNT(*) FILTER (WHERE "createdAt" >= NOW() - INTERVAL '5 minutes')::int AS votes_last_5m,
      MIN("createdAt") AS first_vote_at
     FROM votes
     WHERE "pollId" = :pollId
       AND COALESCE("isQuarantined", false) = false
       ${liveVoteWindowSql}`,
    {
      replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
      type: QueryTypes.SELECT,
    },
  )) as PollMetricsRow[];

  const [peakHourRow] = (await db.query(
    `SELECT
      EXTRACT(HOUR FROM "createdAt" AT TIME ZONE 'UTC')::int AS peak_hour_utc,
      COUNT(*)::int AS peak_hour_votes
     FROM votes
     WHERE "pollId" = :pollId
       AND COALESCE("isQuarantined", false) = false
       ${liveVoteWindowSql}
     GROUP BY peak_hour_utc
     ORDER BY peak_hour_votes DESC, peak_hour_utc ASC
     LIMIT 1`,
    {
      replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
      type: QueryTypes.SELECT,
    },
  )) as PollPeakHourRow[];

  const [peakDowRow] = (await db.query(
    `SELECT
      EXTRACT(DOW FROM "createdAt" AT TIME ZONE 'UTC')::int AS peak_dow_utc,
      COUNT(*)::int AS peak_dow_votes
     FROM votes
     WHERE "pollId" = :pollId
       AND COALESCE("isQuarantined", false) = false
       ${liveVoteWindowSql}
     GROUP BY peak_dow_utc
     ORDER BY peak_dow_votes DESC, peak_dow_utc ASC
     LIMIT 1`,
    {
      replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
      type: QueryTypes.SELECT,
    },
  )) as PollPeakDowRow[];

  const hourBins = (await db.query(
    `SELECT
      EXTRACT(HOUR FROM "createdAt" AT TIME ZONE 'UTC')::int AS hour_utc,
      COUNT(*)::int AS vote_count
     FROM votes
     WHERE "pollId" = :pollId
       AND COALESCE("isQuarantined", false) = false
       ${liveVoteWindowSql}
     GROUP BY hour_utc
     ORDER BY hour_utc ASC`,
    {
      replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
      type: QueryTypes.SELECT,
    },
  )) as PollHourBinRow[];

  const dowBins = (await db.query(
    `SELECT
      EXTRACT(DOW FROM "createdAt" AT TIME ZONE 'UTC')::int AS dow_utc,
      COUNT(*)::int AS vote_count
     FROM votes
     WHERE "pollId" = :pollId
       AND COALESCE("isQuarantined", false) = false
       ${liveVoteWindowSql}
     GROUP BY dow_utc
     ORDER BY dow_utc ASC`,
    {
      replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
      type: QueryTypes.SELECT,
    },
  )) as PollDowBinRow[];

  const optionHourBins = youOwnThisPoll
    ? ((await db.query(
        `SELECT
          COALESCE("option", '') AS option_label,
          EXTRACT(HOUR FROM "createdAt" AT TIME ZONE 'UTC')::int AS hour_utc,
          COUNT(*)::int AS vote_count
         FROM votes
         WHERE "pollId" = :pollId
           AND COALESCE("isQuarantined", false) = false
           ${liveVoteWindowSql}
         GROUP BY COALESCE("option", ''), EXTRACT(HOUR FROM "createdAt" AT TIME ZONE 'UTC')::int
         ORDER BY option_label ASC, hour_utc ASC`,
        {
          replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
          type: QueryTypes.SELECT,
        },
      )) as PollOptionHourBinRow[])
    : [];

  const voteMinuteBins = youOwnThisPoll
    ? ((await db.query(
        `WITH mins AS (
          SELECT
            date_trunc('minute', "createdAt" AT TIME ZONE 'UTC') AS minute_utc,
            COUNT(*)::int AS vote_count
           FROM votes
           WHERE "pollId" = :pollId
             AND COALESCE("isQuarantined", false) = false
             ${liveVoteWindowSql}
           GROUP BY 1
         )
         SELECT minute_utc, vote_count FROM mins
         ORDER BY minute_utc DESC
         LIMIT 4000`,
        {
          replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
          type: QueryTypes.SELECT,
        },
      )) as PollVoteMinuteBinRow[])
    : [];

  const liveVoteWindowSqlV = liveResultsAreDelayed
    ? `AND v."createdAt" <= :resultsVisibleThrough`
    : '';

  const optionVoteMinuteBins = youOwnThisPoll
    ? ((await db.query(
        `WITH cap_minutes AS (
          SELECT date_trunc('minute', "createdAt" AT TIME ZONE 'UTC') AS minute_utc
          FROM votes
          WHERE "pollId" = :pollId
            AND COALESCE("isQuarantined", false) = false
            ${liveVoteWindowSql}
          GROUP BY 1
          ORDER BY 1 DESC
          LIMIT 120
        )
        SELECT
          COALESCE(v."option", '') AS option_label,
          date_trunc('minute', v."createdAt" AT TIME ZONE 'UTC') AS minute_utc,
          COUNT(*)::int AS vote_count
        FROM votes v
        INNER JOIN cap_minutes m
          ON date_trunc('minute', v."createdAt" AT TIME ZONE 'UTC') = m.minute_utc
        WHERE v."pollId" = :pollId
          AND COALESCE(v."isQuarantined", false) = false
          ${liveVoteWindowSqlV}
        GROUP BY COALESCE(v."option", ''), date_trunc('minute', v."createdAt" AT TIME ZONE 'UTC')
        ORDER BY option_label ASC, minute_utc ASC`,
        {
          replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
          type: QueryTypes.SELECT,
        },
      )) as PollOptionVoteMinuteBinRow[])
    : [];

  const [rateCountersRow] = youOwnThisPoll
    ? ((await db.query(
        `SELECT
          COUNT(*) FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '1 minute' AND COALESCE("isQuarantined", false) = false
          )::int AS votes_last_1m,
          COUNT(DISTINCT "sourceIpHash") FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '1 minute'
              AND "sourceIpHash" IS NOT NULL
              AND COALESCE("isQuarantined", false) = false
          )::int AS unique_ip_hashes_last_1m,
          COUNT(DISTINCT "userId") FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '1 minute'
              AND "userId" IS NOT NULL
              AND COALESCE("isQuarantined", false) = false
          )::int AS unique_accounts_last_1m,
          COALESCE((
            SELECT MAX(c) FROM (
              SELECT COUNT(*)::int AS c
              FROM votes
              WHERE "pollId" = :pollId
                AND "createdAt" >= NOW() - INTERVAL '1 minute'
                AND "sourceIpHash" IS NOT NULL
                AND COALESCE("isQuarantined", false) = false
              GROUP BY "sourceIpHash"
            ) t
          ), 0)::int AS top_ip_votes_last_1m,
          COUNT(*) FILTER (
            WHERE COALESCE("isQuarantined", false) = true AND COALESCE("quarantineStatus", 'pending') = 'pending'
          )::int AS quarantined_votes_pending,
          COUNT(*) FILTER (
            WHERE COALESCE("isQuarantined", false) = true
              AND COALESCE("quarantineStatus", 'pending') = 'pending'
              AND "userId" IS NOT NULL
          )::int AS quarantined_votes_pending_account_linked,
          COUNT(*) FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '24 hours'
              AND "userId" IS NOT NULL
          )::int AS votes_account_linked_last_24h,
          COUNT(*) FILTER (
            WHERE "createdAt" >= NOW() - INTERVAL '24 hours'
              AND "userId" IS NULL
          )::int AS votes_anonymous_last_24h
         FROM votes
         WHERE "pollId" = :pollId`,
        { replacements: { pollId }, type: QueryTypes.SELECT },
      )) as PollRateCountersRow[])
    : [];

  const [delayedPendingRow] = liveResultsAreDelayed
    ? ((await db.query(
        `SELECT COUNT(*)::int AS delayed_votes_pending
         FROM votes
         WHERE "pollId" = :pollId
           AND COALESCE("isQuarantined", false) = false
           AND "createdAt" > :resultsVisibleThrough`,
        {
          replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
          type: QueryTypes.SELECT,
        },
      )) as PollDelayedPendingRow[])
    : [];

  return {
    voteData,
    metricsRow,
    peakHourRow,
    peakDowRow,
    hourBins,
    dowBins,
    optionHourBins,
    voteMinuteBins,
    optionVoteMinuteBins,
    rateCountersRow,
    delayedVotesPending: Number(delayedPendingRow?.delayed_votes_pending ?? 0) || 0,
  };
}
