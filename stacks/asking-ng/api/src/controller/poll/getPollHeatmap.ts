import type { AppRequestHandler } from '../../types/http';
import { QueryTypes } from 'sequelize';
import db from '../../connections';
import { getVoteGeoEnabled } from '../../lib/appSettings';
import { pollEmbedViewAllowed, readEmbedReadTokenFromRequest } from '../../lib/embedReadToken';
import { jsonError } from '../../lib/jsonError';
import Poll from '../../model/Poll';
import { singleString } from '../../utils/http';

type HeatPointRow = {
  latitude_bucket: string | number;
  longitude_bucket: string | number;
  votes_count: string | number;
};

const getPollHeatmap: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params.id);
  const minCount =
    typeof req.query.minCount === 'string' ? Number.parseInt(req.query.minCount, 10) || 2 : 2;
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

  if (!(await getVoteGeoEnabled())) {
    jsonError(res, req, 403, 'FEATURE_DISABLED', 'Vote location heatmap is disabled by admin.');
    return;
  }

  const rows = await db.query<HeatPointRow>(
    `
      SELECT
        vote_latitude AS latitude_bucket,
        vote_longitude AS longitude_bucket,
        count(*) AS votes_count
      FROM votes
      WHERE "pollId" = :pollId
        AND COALESCE("isQuarantined", false) = false
        AND vote_latitude IS NOT NULL
        AND vote_longitude IS NOT NULL
      GROUP BY vote_latitude, vote_longitude
      HAVING count(*) >= :minCount
      ORDER BY votes_count DESC
      LIMIT 1000;
    `,
    {
      replacements: { pollId, minCount },
      type: QueryTypes.SELECT,
    },
  );

  const points = rows
    .map((row) => ({
      latitude: Number(row.latitude_bucket),
      longitude: Number(row.longitude_bucket),
      intensity: Number(row.votes_count),
    }))
    .filter(
      (row) =>
        Number.isFinite(row.latitude) &&
        Number.isFinite(row.longitude) &&
        Number.isFinite(row.intensity),
    );

  res.status(200).json({
    status: 'success',
    data: {
      points,
      minCount,
      geo_collection_mode: 'opt_in_coarse',
      coordinate_precision_decimals: 1,
      note: 'Coordinates are intentionally coarse and aggregated for privacy.',
    },
  });
};

export default getPollHeatmap;
