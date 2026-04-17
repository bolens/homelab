import { jsonError } from '../../lib/jsonError';
import type { AppRequestHandler } from '../../types/http';
import { singleString } from '../../utils/http';
import { presentPollResponse } from './getPoll.presenter';
import { getPollView } from './getPoll.service';

const getPoll: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params['id']);

  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  const result = await getPollView(req, pollId);
  if (result.kind === 'not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
    return;
  }
  if (result.kind === 'forbidden_embed_token') {
    jsonError(
      res,
      req,
      403,
      'POLL_EMBED_TOKEN_REQUIRED',
      'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
    );
    return;
  }

  res.status(200).json(presentPollResponse(result.data));
};

export default getPoll;
