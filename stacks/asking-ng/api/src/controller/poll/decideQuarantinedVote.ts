import type { DecideQuarantinedVoteBody } from '@asking-ng/contracts/poll';
import { jsonError } from '../../lib/jsonError';
import type { AppRequestHandler } from '../../types/http';
import { singleString } from '../../utils/http';
import { presentDecideQuarantinedVote } from './decideQuarantinedVote.presenter';
import { decideQuarantinedVoteService } from './decideQuarantinedVote.service';

function apiKeyFrom(req: Parameters<AppRequestHandler>[0]): string | undefined {
  const v = req.headers['api_key'];
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v[0];
  return undefined;
}

const decideQuarantinedVote: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params['id']);
  const voteId = singleString(req.params['voteId']);
  const apiKey = apiKeyFrom(req);

  if (!pollId || !voteId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id and vote id are required.');
    return;
  }

  const result = await decideQuarantinedVoteService({
    pollId,
    voteId,
    body: req.body as DecideQuarantinedVoteBody,
    apiKey,
    actorUserId: req.user?.id ?? null,
    actorUsername: req.user?.homelab-user ?? null,
  });

  if (result.kind === 'poll_not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
    return;
  }
  if (result.kind === 'unauthorized') {
    jsonError(
      res,
      req,
      401,
      'UNAUTHORIZED',
      'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
    );
    return;
  }
  if (result.kind === 'vote_not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'Quarantined vote not found.');
    return;
  }
  if (result.kind === 'vote_revert_not_allowed') {
    jsonError(
      res,
      req,
      400,
      'VOTE_REVERT_NOT_ALLOWED',
      'Only approved or rejected votes can be reverted to pending.',
    );
    return;
  }
  if (result.kind === 'vote_not_quarantined') {
    jsonError(res, req, 400, 'VOTE_NOT_QUARANTINED', 'Vote is not pending quarantine review.');
    return;
  }
  res.status(200).json(
    presentDecideQuarantinedVote({
      voteId: result.voteId,
      quarantineStatus: result.quarantineStatus,
      isQuarantined: result.isQuarantined,
    }),
  );
};

export default decideQuarantinedVote;
