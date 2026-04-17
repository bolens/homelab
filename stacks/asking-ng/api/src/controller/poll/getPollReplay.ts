import { QueryTypes } from 'sequelize';
import db from '../../connections';
import { pollEmbedViewAllowed, readEmbedReadTokenFromRequest } from '../../lib/embedReadToken';
import { jsonError } from '../../lib/jsonError';
import Poll from '../../model/Poll';
import type { AppRequestHandler } from '../../types/http';
import { singleString } from '../../utils/http';

type ReplayVoteRow = {
  option: string;
  created_at: Date | string;
};

const getPollReplay: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params['id']);
  const limit =
    typeof req.query['limit'] === 'number'
      ? req.query['limit']
      : Number.parseInt(String(req.query['limit'] ?? ''), 10) || 5000;
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

  const expiration = Number(poll.get('expiration'));
  const archived = !!poll.get('archived');
  const phase = String(poll.get('phase') ?? 'open');
  const expired = Number.isFinite(expiration) && expiration > 0 && Date.now() > expiration;
  const completed = archived || expired || phase !== 'open';
  if (!completed) {
    jsonError(
      res,
      req,
      409,
      'POLL_NOT_COMPLETED',
      'Replay is available only after poll completion.',
    );
    return;
  }

  const options = ((poll.get('options') as string[]) || []).map((opt) => String(opt));
  const optionIndexByLabel = new Map<string, number>();
  options.forEach((label, idx) => optionIndexByLabel.set(label, idx));

  const rows = await db.query<ReplayVoteRow>(
    `
      SELECT option, "createdAt" AS created_at
      FROM votes
      WHERE "pollId" = :pollId
        AND COALESCE("isQuarantined", false) = false
      ORDER BY "createdAt" ASC, id ASC
      LIMIT :limit;
    `,
    {
      replacements: { pollId, limit },
      type: QueryTypes.SELECT,
    },
  );

  const firstRow = rows[0];
  const firstTsMs = firstRow ? new Date(firstRow.created_at).getTime() : null;
  const events = rows
    .map((row) => {
      const optionIndex = optionIndexByLabel.get(String(row.option));
      if (optionIndex === undefined) return null;
      const ts = new Date(row.created_at).getTime();
      if (!Number.isFinite(ts)) return null;
      return {
        option_index: optionIndex,
        offset_ms: firstTsMs === null ? 0 : Math.max(0, ts - firstTsMs),
      };
    })
    .filter((e): e is { option_index: number; offset_ms: number } => e !== null);

  res.status(200).json({
    status: 'success',
    data: {
      options,
      total_votes: events.length,
      completed,
      events,
    },
  });
};

export default getPollReplay;
