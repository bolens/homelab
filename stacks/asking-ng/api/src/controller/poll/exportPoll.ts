import type { ExportPollQuery } from '@asking-ng/contracts/poll';
import { Parser } from 'json2csv';
import { QueryTypes } from 'sequelize';
import db from '../../connections';
import { pollEmbedViewAllowed, readEmbedReadTokenFromRequest } from '../../lib/embedReadToken';
import { jsonError } from '../../lib/jsonError';
import { listPollPhaseHistory } from '../../lib/pollPhaseHistory';
import Poll from '../../model/Poll';
import type { AppRequestHandler } from '../../types/http';
import { singleString } from '../../utils/http';

function apiKeyFrom(req: Parameters<AppRequestHandler>[0]): string | undefined {
  const v = req.headers['api_key'];
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v[0];
  return undefined;
}

type VoteRow = { option: string; voted_at: Date; weight?: number };
type VelocityRow = { minute_utc: Date | string; vote_count: string | number };

const exportPoll: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params['id']);
  const { format, include } = req.validatedQuery as ExportPollQuery;

  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  const poll = await Poll.findByPk(pollId);
  if (!poll) {
    jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
    return;
  }

  const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
  const embedToken = readEmbedReadTokenFromRequest(req);
  const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
  if (!pollEmbedViewAllowed(req, pollId, embedHash, embedToken, creatorUserId)) {
    jsonError(
      res,
      req,
      403,
      'POLL_EMBED_TOKEN_REQUIRED',
      'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
    );
    return;
  }

  const apiKey = apiKeyFrom(req);
  const storedKey = poll.get('api_key') as string | undefined;
  const creatorId = creatorUserId;
  const ownerJwt = req.user && creatorId != null && req.user.id === creatorId;
  const ownerKey = apiKey !== undefined && apiKey !== '' && apiKey === storedKey;

  if (!ownerJwt && !ownerKey) {
    jsonError(
      res,
      req,
      401,
      'UNAUTHORIZED',
      'Provide api_key header or sign in as the poll owner.',
    );
    return;
  }

  const title = poll.get('title') as string;
  const options = (poll.get('options') as string[]) || [];
  const phase = (poll.get('phase') as string) || 'open';
  const votingPaused = !!poll.get('votingPaused');
  const impressionCount = Number(poll.get('impressionCount')) || 0;
  const expiration = Number.parseInt(String(poll.get('expiration')), 10);
  const boostedVotingEnabled = !!poll.get('boostedVotingEnabled');
  const showUnweightedValues = !!poll.get('showUnweightedValues');
  const maxBoostWeight = Number(poll.get('maxBoostWeight') ?? 3);

  const jsonExportProvenance = (): { exported_at: string; timestamps_timezone: 'UTC' } => ({
    exported_at: new Date().toISOString(),
    timestamps_timezone: 'UTC',
  });

  const query = `
    SELECT option, count(option) as vote_count, COALESCE(sum(weight), count(option)) as weighted_vote_count
    FROM votes
    WHERE "pollId" = :pollId
      AND COALESCE("isQuarantined", false) = false
    GROUP BY option;
  `;
  const voteData = (await db.query(query, {
    replacements: { pollId },
    type: QueryTypes.SELECT,
  })) as { option: string; vote_count: string | number; weighted_vote_count: string | number }[];

  const rows = options.map((opt) => {
    const row = voteData.find((v) => v.option === opt);
    const n = row ? Number.parseInt(String(row.vote_count), 10) || 0 : 0;
    const weighted = row ? Number.parseInt(String(row.weighted_vote_count), 10) || n : 0;
    return {
      option: opt,
      votes: boostedVotingEnabled ? weighted : n,
      weighted_votes: weighted,
      unweighted_votes: n,
    };
  });
  const velocityRows = (await db.query(
    `SELECT
      date_trunc('minute', "createdAt" AT TIME ZONE 'UTC') AS minute_utc,
      COUNT(*)::int AS vote_count
     FROM votes
     WHERE "pollId" = :pollId
       AND COALESCE("isQuarantined", false) = false
     GROUP BY minute_utc
     ORDER BY minute_utc ASC`,
    { replacements: { pollId }, type: QueryTypes.SELECT },
  )) as VelocityRow[];
  const voteVelocity = velocityRows.map((r) => ({
    minute_utc:
      r.minute_utc instanceof Date
        ? r.minute_utc.toISOString()
        : new Date(String(r.minute_utc)).toISOString(),
    vote_count: Number(r.vote_count ?? 0) || 0,
  }));
  const phaseHistory = await listPollPhaseHistory(pollId, { limit: 200 });

  const safeName = `poll-${pollId}`.replace(/[^a-zA-Z0-9._-]+/g, '_');

  if (include === 'votes') {
    const rawVotes = (await db.query(
      `SELECT option, "createdAt" AS voted_at, weight
       FROM votes
       WHERE "pollId" = :pollId
         AND COALESCE("isQuarantined", false) = false
       ORDER BY "createdAt" ASC`,
      { replacements: { pollId }, type: QueryTypes.SELECT },
    )) as VoteRow[];

    if (format === 'csv') {
      const parser = new Parser({ fields: ['option', 'voted_at', 'weight'] });
      const csv = parser.parse(
        rawVotes.map((r) => ({
          option: r.option,
          voted_at: r.voted_at instanceof Date ? r.voted_at.toISOString() : String(r.voted_at),
          weight: Number(r.weight ?? 1) || 1,
        })),
      );
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.attachment(`${safeName}-votes.csv`);
      res.send(csv);
      return;
    }

    const payload = {
      ...jsonExportProvenance(),
      id: pollId,
      title,
      expiration,
      archived: !!poll.get('archived'),
      phase,
      voting_paused: votingPaused,
      impression_count: impressionCount,
      boosted_voting_enabled: boostedVotingEnabled,
      max_boost_weight: maxBoostWeight,
      show_unweighted_values: showUnweightedValues,
      vote_velocity_by_minute_utc: voteVelocity,
      phase_history: phaseHistory,
      votes: rawVotes.map((r) => ({
        option: r.option,
        voted_at: r.voted_at instanceof Date ? r.voted_at.toISOString() : r.voted_at,
        weight: Number(r.weight ?? 1) || 1,
      })),
    };
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.attachment(`${safeName}-votes.json`);
    res.send(JSON.stringify(payload, null, 2));
    return;
  }

  const payload = {
    ...jsonExportProvenance(),
    id: pollId,
    title,
    expiration,
    archived: !!poll.get('archived'),
    phase,
    voting_paused: votingPaused,
    impression_count: impressionCount,
    boosted_voting_enabled: boostedVotingEnabled,
    max_boost_weight: maxBoostWeight,
    show_unweighted_values: showUnweightedValues,
    vote_velocity_by_minute_utc: voteVelocity,
    phase_history: phaseHistory,
    options: rows.map((r) => ({
      option: r.option,
      votes: r.votes,
      ...(boostedVotingEnabled ? { weighted_votes: r.weighted_votes } : {}),
      ...(boostedVotingEnabled && showUnweightedValues
        ? { unweighted_votes: r.unweighted_votes }
        : {}),
    })),
    totalVotes: rows.reduce((a, r) => a + r.votes, 0),
  };

  if (format === 'csv') {
    const flat = rows.map((r) => ({
      option: r.option,
      votes: r.votes,
      ...(boostedVotingEnabled ? { weighted_votes: r.weighted_votes } : {}),
      ...(boostedVotingEnabled && showUnweightedValues
        ? { unweighted_votes: r.unweighted_votes }
        : {}),
    }));
    const parser = new Parser({
      fields: [
        'option',
        'votes',
        ...(boostedVotingEnabled ? ['weighted_votes'] : []),
        ...(boostedVotingEnabled && showUnweightedValues ? ['unweighted_votes'] : []),
      ],
    });
    const csv = parser.parse(flat);
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.attachment(`${safeName}.csv`);
    res.send(csv);
    return;
  }

  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.attachment(`${safeName}.json`);
  res.send(JSON.stringify(payload, null, 2));
};

export default exportPoll;
