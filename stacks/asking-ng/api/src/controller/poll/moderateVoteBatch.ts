import type { ModerateVoteBatchBody } from '@asking-ng/contracts/poll';
import type { AppRequestHandler } from '../../types/http';
import { jsonError } from '../../lib/jsonError';
import { buildPlanLimitDetails } from '../../lib/planLimit';
import { BILLING_LICENSE_EXPIRED_CODE, BILLING_LICENSE_EXPIRED_MESSAGE } from '../../lib/selfhostProLicense';
import { singleString } from '../../utils/http';
import { presentModerateVoteBatch } from './moderateVoteBatch.presenter';
import { moderateVoteBatchService } from './moderateVoteBatch.service';

function apiKeyFrom(req: Parameters<AppRequestHandler>[0]): string | undefined {
  const v = req.headers.api_key;
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v[0];
  return undefined;
}

const moderateVoteBatch: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params.id);
  const apiKey = apiKeyFrom(req);
  const body = req.body as ModerateVoteBatchBody;

  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  const result = await moderateVoteBatchService({
    pollId,
    body,
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
  if (result.kind === 'plan_limit_automation') {
    jsonError(
      res,
      req,
      403,
      'PLAN_LIMIT_AUTOMATION',
      'Moderation batch automation is not available on this billing plan.',
      buildPlanLimitDetails({
        plan: result.plan,
        requiredPlan: result.requiredPlan,
        feature: 'Moderation batch automation',
      }),
    );
    return;
  }
  if (result.kind === 'billing_license_expired') {
    jsonError(
      res,
      req,
      403,
      BILLING_LICENSE_EXPIRED_CODE,
      BILLING_LICENSE_EXPIRED_MESSAGE,
      result.details,
    );
    return;
  }
  res.status(200).json(
    presentModerateVoteBatch({
      action: result.action,
      selector: result.selector,
      selectorValue: result.selectorValue,
      reasonCode: result.reasonCode,
      affectedCount: result.affectedCount,
    }),
  );
};

export default moderateVoteBatch;
