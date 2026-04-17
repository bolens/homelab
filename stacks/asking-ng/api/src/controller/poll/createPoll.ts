import type { CreatePollBody } from '@asking-ng/contracts/poll';
import { jsonError } from '../../lib/jsonError';
import { buildPlanLimitDetails } from '../../lib/planLimit';
import {
  BILLING_LICENSE_EXPIRED_CODE,
  BILLING_LICENSE_EXPIRED_MESSAGE,
} from '../../lib/selfhostProLicense';
import type { AppRequestHandler } from '../../types/http';
import { presentCreatePollResponse } from './createPoll.presenter';
import { createPollService } from './createPoll.service';

const createPoll: AppRequestHandler = async (req, res) => {
  const result = await createPollService(req, req.body as CreatePollBody);

  if (result.kind === 'invalid_webhook_url') {
    jsonError(res, req, 400, 'BAD_REQUEST', `Invalid webhook target URL: ${result.url}`);
    return;
  }
  if (result.kind === 'webhook_url_blocked') {
    jsonError(res, req, 400, 'WEBHOOK_URL_BLOCKED', `Blocked webhook target URL: ${result.url}`);
    return;
  }
  if (result.kind === 'invalid_next_poll_requires_signed_in') {
    jsonError(
      res,
      req,
      400,
      'INVALID_NEXT_POLL',
      'next_poll_id requires a signed-in creator-owned poll.',
    );
    return;
  }
  if (result.kind === 'invalid_next_poll_requires_next_poll_id') {
    jsonError(res, req, 400, 'INVALID_NEXT_POLL', 'auto_advance_on_close requires next_poll_id.');
    return;
  }
  if (result.kind === 'invalid_next_poll_missing_target') {
    jsonError(res, req, 400, 'INVALID_NEXT_POLL', 'next_poll_id does not exist.');
    return;
  }
  if (result.kind === 'invalid_next_poll_wrong_owner') {
    jsonError(
      res,
      req,
      400,
      'INVALID_NEXT_POLL',
      'next_poll_id must belong to the same signed-in creator.',
    );
    return;
  }
  if (result.kind === 'invalid_vanity_slug_in_use') {
    jsonError(res, req, 400, 'INVALID_VANITY_SLUG', 'vanity_slug is already in use.');
    return;
  }
  if (result.kind === 'plan_limit_automation') {
    jsonError(
      res,
      req,
      403,
      'PLAN_LIMIT_AUTOMATION',
      'Webhook automation is not available on this billing plan.',
      buildPlanLimitDetails({
        plan: result.plan,
        requiredPlan: result.requiredPlan,
        feature: 'Webhook automation',
      }),
    );
    return;
  }
  if (result.kind === 'plan_limit_retention') {
    jsonError(
      res,
      req,
      403,
      'PLAN_LIMIT_RETENTION',
      'Custom retention is not available on this billing plan.',
      buildPlanLimitDetails({
        plan: result.plan,
        requiredPlan: result.requiredPlan,
        feature: 'Custom retention policy',
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
  if (result.kind === 'usage_limit_active_polls') {
    jsonError(
      res,
      req,
      403,
      'USAGE_LIMIT_ACTIVE_POLLS',
      'Active poll limit reached for this billing plan.',
      {
        max: result.max,
        current: result.current,
        plan: result.plan,
      },
    );
    return;
  }

  res.status(200).json(presentCreatePollResponse(result.data));
};

export default createPoll;
