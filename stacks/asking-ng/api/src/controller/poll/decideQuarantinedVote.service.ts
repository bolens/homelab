import type { DecideQuarantinedVoteBody } from '@asking-ng/contracts/poll';
import { notifyPollLive } from '../../lib/pollLive';
import { queuePollWebhook } from '../../lib/pollWebhooks';
import {
  createModerationAuditLog,
  findPollById,
  findVoteById,
  updateQuarantineDecision,
} from './decideQuarantinedVote.repository';

export type DecideQuarantinedVoteResult =
  | { kind: 'poll_not_found' }
  | { kind: 'unauthorized' }
  | { kind: 'vote_not_found' }
  | { kind: 'vote_revert_not_allowed' }
  | { kind: 'vote_not_quarantined' }
  | {
      kind: 'ok';
      voteId: string;
      quarantineStatus: 'pending' | 'approved' | 'rejected';
      isQuarantined: boolean;
    };

export async function decideQuarantinedVoteService(args: {
  pollId: string;
  voteId: string;
  body: DecideQuarantinedVoteBody;
  apiKey: string | undefined;
  actorUserId: number | null;
  actorUsername: string | null;
}): Promise<DecideQuarantinedVoteResult> {
  const poll = await findPollById(args.pollId);
  if (!poll) return { kind: 'poll_not_found' };

  const targetApiKey = poll.get('api_key') as string | undefined;
  const apiKeyTrim = typeof args.apiKey === 'string' ? args.apiKey.trim() : '';
  const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
  const ownerId = poll.get('creatorUserId') as number | null | undefined;
  const jwtOk = args.actorUserId != null && ownerId != null && Number(ownerId) === Number(args.actorUserId);
  if (!apiKeyOk && !jwtOk) return { kind: 'unauthorized' };

  const vote = await findVoteById(args.voteId);
  if (!vote || String(vote.get('pollId')) !== args.pollId) return { kind: 'vote_not_found' };

  const { action, note } = args.body;
  const isQuarantined = !!vote.get('isQuarantined');
  const status = String(vote.get('quarantineStatus') ?? '');
  const option = String(vote.get('option') ?? '');
  const pollOptions = ((poll.get('options') as string[] | null | undefined) ?? []).filter(Boolean);

  if (action === 'revert' && status !== 'approved' && status !== 'rejected') {
    return { kind: 'vote_revert_not_allowed' };
  }
  if (action !== 'revert' && !isQuarantined && status !== 'pending') {
    return { kind: 'vote_not_quarantined' };
  }

  const approve = action === 'approve';
  const revert = action === 'revert';
  const quarantineStatus = (revert ? 'pending' : approve ? 'approved' : 'rejected') as
    | 'pending'
    | 'approved'
    | 'rejected';
  const nextIsQuarantined = revert ? true : !approve;
  const trimmedNote = note?.trim() || null;

  await updateQuarantineDecision({
    pollId: args.pollId,
    voteId: args.voteId,
    isQuarantined: nextIsQuarantined,
    quarantineStatus,
    quarantineDecidedAt: revert ? null : new Date(),
    quarantineDecidedBy: revert ? null : args.actorUserId,
    quarantineNote: trimmedNote,
  });

  await createModerationAuditLog({
    action: approve
      ? 'moderation.quarantine.approve'
      : revert
        ? 'moderation.quarantine.revert'
        : 'moderation.quarantine.reject',
    actor: args.actorUsername ?? 'api_key',
    target: `poll:${args.pollId}:vote:${args.voteId}`,
    details: {
      poll_id: args.pollId,
      vote_id: args.voteId,
      option,
      is_write_in: !pollOptions.includes(option),
      action,
      note: trimmedNote,
    },
  });

  if (approve || revert) notifyPollLive(args.pollId, { type: 'update' });
  queuePollWebhook(args.pollId, 'poll_updated', {
    moderation_vote_id: args.voteId,
    moderation_action: action,
  });

  return {
    kind: 'ok',
    voteId: args.voteId,
    quarantineStatus,
    isQuarantined: nextIsQuarantined,
  };
}
