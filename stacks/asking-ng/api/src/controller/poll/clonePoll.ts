import type { AppRequestHandler } from '../../types/http';
import db from '../../connections';
import randomId from '../../helpers/randomId';
import { checkClonePremiumEntitlements, normalizeClonePremiumFields } from '../../lib/pollCloneEntitlements';
import { buildPlanLimitDetails } from '../../lib/planLimit';
import { checkActivePollQuotaForUser } from '../../lib/billingPollQuota';
import { resolveWorkspaceIdForCreatorUserId } from '../../lib/workspaceBootstrap';
import { jsonError } from '../../lib/jsonError';
import { notifyPollLive } from '../../lib/pollLive';
import { recordPollPhaseTransition } from '../../lib/pollPhaseHistory';
import {
  BILLING_LICENSE_EXPIRED_CODE,
  BILLING_LICENSE_EXPIRED_MESSAGE,
} from '../../lib/selfhostProLicense';
import Poll from '../../model/Poll';
import { singleString } from '../../utils/http';

function apiKeyFrom(req: Parameters<AppRequestHandler>[0]): string | undefined {
  const v = req.headers.api_key;
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v[0];
  return undefined;
}

const clonePoll: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params.id);
  const apiKey = apiKeyFrom(req);
  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  const source = await Poll.findByPk(pollId);
  if (!source) {
    jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
    return;
  }

  const targetApiKey = source.get('api_key') as string | undefined;
  const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
  const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
  const ownerId = source.get('creatorUserId') as number | null | undefined;
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

  const now = Date.now();
  const existingExpiration = Number(source.get('expiration')) || now + 7 * 24 * 3600 * 1000;
  const safeExpiration =
    existingExpiration <= now + 60_000 ? now + 7 * 24 * 3600 * 1000 : existingExpiration;
  const sourceTitle = String(source.get('title') ?? 'Untitled poll');
  const copiedTitle = sourceTitle.includes('(copy)') ? sourceTitle : `${sourceTitle} (copy)`;

  const newCreatorId =
    ownerId != null && Number.isInteger(Number(ownerId)) && Number(ownerId) > 0 ? Number(ownerId) : null;
  const quota = await checkActivePollQuotaForUser({
    creatorUserId: newCreatorId,
    sessionUserRole: jwtOk ? req.user?.role ?? null : null,
  });
  if (!quota.ok) {
    jsonError(res, req, 403, 'USAGE_LIMIT_ACTIVE_POLLS', 'Active poll limit reached for this billing plan.', {
      max: quota.max,
      current: quota.current,
      plan: quota.plan,
    });
    return;
  }

  const workspaceId = await resolveWorkspaceIdForCreatorUserId(newCreatorId);
  const premiumFields = normalizeClonePremiumFields(source);
  const premiumBlock = await checkClonePremiumEntitlements({ pollId, ownerId, source });
  if (premiumBlock?.kind === 'billing_license_expired') {
    jsonError(
      res,
      req,
      403,
      BILLING_LICENSE_EXPIRED_CODE,
      BILLING_LICENSE_EXPIRED_MESSAGE,
      premiumBlock.details,
    );
    return;
  }
  if (premiumBlock?.kind === 'plan_limit_automation') {
    jsonError(
      res,
      req,
      403,
      'PLAN_LIMIT_AUTOMATION',
      'Webhook automation is not available on this billing plan.',
      buildPlanLimitDetails({
        plan: premiumBlock.plan,
        requiredPlan: premiumBlock.requiredPlan,
        feature: 'Webhook automation',
      }),
    );
    return;
  }
  if (premiumBlock?.kind === 'plan_limit_retention') {
    jsonError(
      res,
      req,
      403,
      'PLAN_LIMIT_RETENTION',
      'Custom retention is not available on this billing plan.',
      buildPlanLimitDetails({
        plan: premiumBlock.plan,
        requiredPlan: premiumBlock.requiredPlan,
        feature: 'Custom retention',
      }),
    );
    return;
  }

  await db.sync();
  const clone = await Poll.create({
    id: randomId(16),
    api_key: randomId(16),
    title: copiedTitle,
    options: (source.get('options') as string[]) ?? [],
    expiration: safeExpiration,
    limit_ip: !!source.get('limit_ip'),
    creatorUserId: ownerId ?? null,
    workspaceId,
    webhookTargets: premiumFields.webhookTargets,
    phase: 'draft',
    votingPaused: false,
    pauseMessage: null,
    showNotes: source.get('showNotes') ?? null,
    embedReadTokenHash: source.get('embedReadTokenHash') ?? null,
    openAt: source.get('openAt') ?? null,
    lockAt: source.get('lockAt') ?? null,
    revealAt: source.get('revealAt') ?? null,
    boostedVotingEnabled: !!source.get('boostedVotingEnabled'),
    maxBoostWeight: Number(source.get('maxBoostWeight') ?? 3),
    showUnweightedValues: !!source.get('showUnweightedValues'),
    runOfShowKey: source.get('runOfShowKey') ?? null,
    runOfShowOrder: source.get('runOfShowOrder') ?? null,
    nextPollId: null,
    autoAdvanceOnClose: false,
    voteFrictionTier: String(source.get('voteFrictionTier') ?? 'open'),
    softThrottleMaxVotesPerMin: Number(source.get('softThrottleMaxVotesPerMin') ?? 30),
    powDifficulty: Number(source.get('powDifficulty') ?? 4),
    allowWriteIn: !!source.get('allowWriteIn'),
    writeInMaxLength: Number(source.get('writeInMaxLength') ?? 80),
    writeInBlocklist: (
      (source.get('writeInBlocklist') as string[] | null | undefined) ?? []
    ).filter((s) => typeof s === 'string' && s.trim() !== ''),
    writeInProfanityFilter: source.get('writeInProfanityFilter') !== false,
    resultsDelaySeconds: Number(source.get('resultsDelaySeconds') ?? 0),
    retentionTtlDays: premiumFields.retentionTtlDays,
    retentionLegalHold: premiumFields.retentionLegalHold,
  });

  const clonedId = clone.get('id') as string;
  await recordPollPhaseTransition({
    pollId: clonedId,
    fromPhase: null,
    toPhase: 'draft',
    actorType: jwtOk ? 'owner_jwt' : 'api_key',
    actorUserId: req.user?.id ?? null,
    source: 'poll_clone',
  });
  notifyPollLive(clonedId, { type: 'update' });

  res.status(200).json({
    status: 'success',
    message: 'Poll cloned as draft.',
    data: {
      id: clonedId,
      api_key: clone.get('api_key') as string,
      source_poll_id: pollId,
    },
  });
};

export default clonePoll;
