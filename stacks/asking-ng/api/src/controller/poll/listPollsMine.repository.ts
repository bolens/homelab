import type { Order } from 'sequelize';
import { Op } from 'sequelize';
import { QueryTypes } from 'sequelize';
import db from '../../connections';
import Poll from '../../model/Poll';

let pollColumnCache: Set<string> | null = null;
let voteColumnCache: Set<string> | null = null;

async function getTableColumns(tableName: 'polls' | 'votes'): Promise<Set<string>> {
  if (tableName === 'polls' && pollColumnCache) return pollColumnCache;
  if (tableName === 'votes' && voteColumnCache) return voteColumnCache;
  const rows = (await db.query(
    `SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = :tableName`,
    { replacements: { tableName }, type: QueryTypes.SELECT },
  )) as Array<{ column_name?: unknown }>;
  const columns = new Set(
    rows
      .map((row) => (typeof row.column_name === 'string' ? row.column_name : ''))
      .filter((name) => name.length > 0),
  );
  if (tableName === 'polls') pollColumnCache = columns;
  else voteColumnCache = columns;
  return columns;
}

export async function getPollAndVoteColumns(): Promise<{
  pollColumns: Set<string>;
  voteColumns: Set<string>;
}> {
  const [pollColumns, voteColumns] = await Promise.all([
    getTableColumns('polls'),
    getTableColumns('votes'),
  ]);
  return { pollColumns, voteColumns };
}

export async function listPollRows(args: {
  uid: number;
  runOfShowKey?: string;
  sort: 'created_desc' | 'run_of_show';
  limit: number;
  offset: number;
  pollAttributes: string[];
}): Promise<{
  rows: Awaited<ReturnType<typeof Poll.findAndCountAll>>['rows'];
  count: number;
}> {
  const where = {
    [Op.or]: [
      { creatorUserId: args.uid },
      {
        phase: 'draft',
        sharedEditorUserIds: { [Op.contains]: [args.uid] },
      },
    ],
    ...(args.runOfShowKey ? { runOfShowKey: args.runOfShowKey } : {}),
  };
  const order: Order =
    args.sort === 'run_of_show'
      ? [
          ['runOfShowOrder', 'ASC'],
          ['createdAt', 'DESC'],
        ]
      : [['createdAt', 'DESC']];
  const { rows, count } = await Poll.findAndCountAll({
    where,
    order,
    limit: args.limit,
    offset: args.offset,
    attributes: args.pollAttributes,
  });
  return { rows, count };
}

type VoteMetricRow = {
  poll_id: string;
  total_votes: string | number;
  votes_last_5m: string | number;
  votes_last_24h: string | number;
  first_vote_at: Date | string | null;
};

type PeakHourRow = {
  poll_id: string;
  peak_hour_utc: string | number;
  peak_hour_votes: string | number;
};

type PeakDowRow = {
  poll_id: string;
  peak_dow_utc: string | number;
  peak_dow_votes: string | number;
};

type OptionFunnelRow = {
  poll_id: string;
  option_label: string;
  votes_total: string | number;
  votes_last_24h: string | number;
};

export async function listPollVoteMetrics(
  pollIds: string[],
  voteColumns: Set<string>,
): Promise<{
  voteMetricsRows: VoteMetricRow[];
  peakHourRows: PeakHourRow[];
  peakDowRows: PeakDowRow[];
  optionFunnelRows: OptionFunnelRow[];
}> {
  if (pollIds.length === 0) {
    return { voteMetricsRows: [], peakHourRows: [], peakDowRows: [], optionFunnelRows: [] };
  }

  const quarantinePredicate = voteColumns.has('isQuarantined')
    ? 'AND COALESCE("isQuarantined", false) = false'
    : '';

  const [voteMetricsRows, peakHourRows, peakDowRows, optionFunnelRows] = await Promise.all([
    db.query(
      `SELECT
        "pollId" AS poll_id,
        COUNT(*)::int AS total_votes,
        COUNT(*) FILTER (WHERE "createdAt" >= NOW() - INTERVAL '5 minutes')::int AS votes_last_5m,
        COUNT(*) FILTER (WHERE "createdAt" >= NOW() - INTERVAL '24 hours')::int AS votes_last_24h,
        MIN("createdAt") AS first_vote_at
       FROM votes
       WHERE "pollId" IN (:pollIds)
         ${quarantinePredicate}
       GROUP BY "pollId"`,
      { replacements: { pollIds }, type: QueryTypes.SELECT },
    ) as Promise<VoteMetricRow[]>,
    db.query(
      `SELECT DISTINCT ON ("pollId")
        "pollId" AS poll_id,
        peak_hour_utc,
        peak_hour_votes
       FROM (
         SELECT
           "pollId",
           EXTRACT(HOUR FROM "createdAt" AT TIME ZONE 'UTC')::int AS peak_hour_utc,
           COUNT(*)::int AS peak_hour_votes
         FROM votes
         WHERE "pollId" IN (:pollIds)
           ${quarantinePredicate}
         GROUP BY "pollId", peak_hour_utc
       ) t
       ORDER BY "pollId", peak_hour_votes DESC, peak_hour_utc ASC`,
      { replacements: { pollIds }, type: QueryTypes.SELECT },
    ) as Promise<PeakHourRow[]>,
    db.query(
      `SELECT DISTINCT ON ("pollId")
        "pollId" AS poll_id,
        peak_dow_utc,
        peak_dow_votes
       FROM (
         SELECT
           "pollId",
           EXTRACT(DOW FROM "createdAt" AT TIME ZONE 'UTC')::int AS peak_dow_utc,
           COUNT(*)::int AS peak_dow_votes
         FROM votes
         WHERE "pollId" IN (:pollIds)
           ${quarantinePredicate}
         GROUP BY "pollId", peak_dow_utc
       ) t
       ORDER BY "pollId", peak_dow_votes DESC, peak_dow_utc ASC`,
      { replacements: { pollIds }, type: QueryTypes.SELECT },
    ) as Promise<PeakDowRow[]>,
    db.query(
      `SELECT
        "pollId" AS poll_id,
        COALESCE("option", '') AS option_label,
        COUNT(*)::int AS votes_total,
        COUNT(*) FILTER (WHERE "createdAt" >= NOW() - INTERVAL '24 hours')::int AS votes_last_24h
       FROM votes
       WHERE "pollId" IN (:pollIds)
         ${quarantinePredicate}
       GROUP BY "pollId", COALESCE("option", '')`,
      { replacements: { pollIds }, type: QueryTypes.SELECT },
    ) as Promise<OptionFunnelRow[]>,
  ]);

  return { voteMetricsRows, peakHourRows, peakDowRows, optionFunnelRows };
}
