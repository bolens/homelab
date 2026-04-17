import type { EditWriteInVoteBody } from '@asking-ng/contracts/poll';
import { jsonError } from '../../lib/jsonError';
import { notifyPollLive } from '../../lib/pollLive';
import { queuePollWebhook } from '../../lib/pollWebhooks';
import { validateWriteInText } from '../../lib/writeInHygiene';
import Poll from '../../model/Poll';
import Vote from '../../model/Vote';
import AuditLog from '../../models/auditlog.sequelize';
import type { AppRequestHandler } from '../../types/http';
import { singleString } from '../../utils/http';

function apiKeyFrom(req: Parameters<AppRequestHandler>[0]): string | undefined {
  const v = req.headers.api_key;
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v[0];
  return undefined;
}

const editWriteInVote: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params.id);
  const voteId = singleString(req.params.voteId);
  const { option, note } = req.body as EditWriteInVoteBody;
  const apiKey = apiKeyFrom(req);
  if (!pollId || !voteId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id and vote id are required.');
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

  const vote = await Vote.findByPk(voteId);
  if (!vote || String(vote.get('pollId')) !== pollId) {
    jsonError(res, req, 404, 'NOT_FOUND', 'Vote not found.');
    return;
  }

  const nextOption = option.trim();
  const validOptions = ((poll.get('options') as string[] | null | undefined) ?? []).filter(Boolean);
  const isPresetOption = validOptions.includes(nextOption);
  if (!isPresetOption) {
    const writeInCheck = validateWriteInText(nextOption, {
      allowWriteIn: !!poll.get('allowWriteIn'),
      writeInMaxLength: Number(poll.get('writeInMaxLength') ?? 80),
      writeInBlocklist: (
        (poll.get('writeInBlocklist') as string[] | null | undefined) ?? []
      ).filter((s) => typeof s === 'string' && s.trim() !== ''),
      writeInProfanityFilter: poll.get('writeInProfanityFilter') !== false,
    });
    if (!writeInCheck.ok) {
      jsonError(res, req, 400, writeInCheck.code, writeInCheck.message);
      return;
    }
  }

  const prevOption = String(vote.get('option') ?? '');
  await Vote.update({ option: nextOption }, { where: { id: voteId, pollId } });

  await AuditLog.create({
    action: 'moderation.write_in.edit',
    actor: req.user?.homelab-user ?? 'api_key',
    target: `poll:${pollId}:vote:${voteId}`,
    details: {
      poll_id: pollId,
      vote_id: voteId,
      previous_option: prevOption,
      new_option: nextOption,
      note: note?.trim() || null,
    },
  });

  notifyPollLive(pollId, { type: 'update' });
  queuePollWebhook(pollId, 'poll_updated', {
    moderation_vote_id: voteId,
    moderation_action: 'write_in_edit',
  });

  res.status(200).json({
    status: 'success',
    data: {
      vote_id: voteId,
      option: nextOption,
    },
  });
};

export default editWriteInVote;
