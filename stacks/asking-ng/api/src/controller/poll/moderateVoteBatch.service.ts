import type { ModerateVoteBatchBody } from '@asking-ng/contracts/poll';
import { hasModerationAutomationForBillingPlan } from '../../lib/billingLimits';
import { appEnv } from '../../lib/env';
import { notifyPollLive } from '../../lib/pollLive';
import { queuePollWebhook } from '../../lib/pollWebhooks';
import {
  type SelfhostProLicenseExpiredDetails,
  selfhostProLicenseExpiredDetailsForPlan,
} from '../../lib/selfhostProLicense';
import { findBillingPlanAndRoleForVoteQuota } from '../self/self.repository';
import {
  applyModerationBatch,
  createModerationBatchAuditLog,
  findPollById,
} from './moderateVoteBatch.repository';

export type ModerateVoteBatchResult =
  | { kind: 'poll_not_found' }
  | { kind: 'unauthorized' }
  | { kind: 'billing_license_expired'; details: SelfhostProLicenseExpiredDetails }
  | { kind: 'plan_limit_automation'; plan: string; requiredPlan: 'cloud-team' }
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
  const jwtOk =
    args.actorUserId != null && ownerId != null && Number(ownerId) === Number(args.actorUserId);
  if (!apiKeyOk && !jwtOk) return { kind: 'unauthorized' };
  if (appEnv.billingEnforceLimits) {
    const { billingPlan, role } =
      typeof ownerId === 'number' && Number.isFinite(ownerId) && ownerId > 0
        ? await findBillingPlanAndRoleForVoteQuota({ pollId: args.pollId, creatorUserId: ownerId })
        : { billingPlan: 'free', role: null };
    const licenseExpired =
      role !== 'superadmin' ? selfhostProLicenseExpiredDetailsForPlan(billingPlan) : null;
    if (licenseExpired) {
      return { kind: 'billing_license_expired', details: licenseExpired };
    }
    if (role !== 'superadmin' && !hasModerationAutomationForBillingPlan(billingPlan)) {
      return { kind: 'plan_limit_automation', plan: billingPlan, requiredPlan: 'cloud-team' };
    }
  }

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
