import type { ModerateVoteBatchBody } from '@asking-ng/contracts/poll';
import { notifyPollLive } from '../../lib/pollLive';
import { queuePollWebhook } from '../../lib/pollWebhooks';
import {
  applyModerationBatch,
  createModerationBatchAuditLog,
  findPollById,
} from './moderateVoteBatch.repository';

export type ModerateVoteBatchResult =
  | { kind: 'poll_not_found' }
  | { kind: 'unauthorized' }
  | {
      kind: 'ok';
      action: 'remove' | 'restore';
      selector: 'source_ip_hash' | 'user_id';
      selectorValue: string;
      reasonCode: string;
      affectedCount: number;
    };

export async function moderateVoteBatchService(args: {
  pollId: string;
  body: ModerateVoteBatchBody;
  apiKey: string | undefined;
  actorUserId: number | null;
  actorUsername: string | null;
}): Promise<ModerateVoteBatchResult> {
  const poll = await findPollById(args.pollId);
  if (!poll) return { kind: 'poll_not_found' };

  const targetApiKey = poll.get('api_key') as string | undefined;
  const apiKeyTrim = typeof args.apiKey === 'string' ? args.apiKey.trim() : '';
  const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
  const ownerId = poll.get('creatorUserId') as number | null | undefined;
  const jwtOk = args.actorUserId != null && ownerId != null && Number(ownerId) === Number(args.actorUserId);
  if (!apiKeyOk && !jwtOk) return { kind: 'unauthorized' };

  const note = args.body.note?.trim() || null;
  const [affectedCount] = await applyModerationBatch({
    pollId: args.pollId,
    selector: args.body.selector,
    selectorValue: args.body.selector_value,
    action: args.body.action,
    reasonCode: args.body.reason_code,
    note,
    actorUserId: args.actorUserId,
  });

  await createModerationBatchAuditLog({
    action: args.body.action === 'remove' ? 'moderation.batch.remove' : 'moderation.batch.restore',
    actor: args.actorUsername ?? 'api_key',
    target: `poll:${args.pollId}`,
    details: {
      poll_id: args.pollId,
      selector: args.body.selector,
      selector_value: args.body.selector_value,
      reason_code: args.body.reason_code,
      action: args.body.action,
      affected_count: affectedCount,
      note,
    },
  });

  notifyPollLive(args.pollId, { type: 'update' });
  queuePollWebhook(args.pollId, 'poll_updated', {
    moderation_batch_action: args.body.action,
    moderation_batch_selector: args.body.selector,
    moderation_batch_selector_value: args.body.selector_value,
    moderation_batch_reason_code: args.body.reason_code,
    affected_count: affectedCount,
  });

  return {
    kind: 'ok',
    action: args.body.action,
    selector: args.body.selector,
    selectorValue: args.body.selector_value,
    reasonCode: args.body.reason_code,
    affectedCount,
  };
}
