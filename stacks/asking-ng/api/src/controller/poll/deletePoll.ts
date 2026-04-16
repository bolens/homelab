import type { AppRequestHandler } from '../../types/http';
import { jsonError } from '../../lib/jsonError';
import { notifyPollLive } from '../../lib/pollLive';
import { queuePollWebhook } from '../../lib/pollWebhooks';
import Poll from '../../model/Poll';
import { singleString } from '../../utils/http';

function apiKeyFrom(req: Parameters<AppRequestHandler>[0]): string | undefined {
  const v = req.headers.api_key;
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v[0];
  return undefined;
}

const deletePoll: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params.id);
  const apiKey = apiKeyFrom(req);

  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  const poll = await Poll.findByPk(pollId);
  if (!poll) {
    jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
    return;
  }

  const targetApiKey = poll.get('api_key') as string | undefined;
  const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
  const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
  const ownerId = poll.get('creatorUserId') as number | null | undefined;
  const jwtOk = req.user != null && ownerId != null && Number(ownerId) === Number(req.user.id);

  if (!apiKeyOk && !jwtOk) {
    jsonError(
      res,
      req,
      401,
      'UNAUTHORIZED',
      'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
    );
    return;
  }

  notifyPollLive(pollId, { type: 'deleted' });
  queuePollWebhook(pollId, 'poll_deleted', {});
  await Poll.destroy({ where: { id: pollId } });
  res.status(200).json({
    status: 'success',
    message: 'Poll successfully destroyed.',
  });
};

export default deletePoll;
