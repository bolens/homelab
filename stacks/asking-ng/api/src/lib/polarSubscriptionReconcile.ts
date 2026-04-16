import type { Subscription } from '@polar-sh/sdk/models/components/subscription';
import type { FastifyBaseLogger } from 'fastify';
import { Op } from 'sequelize';
import { createPolarServerClient } from './polarApiClient';
import {
  analyzePolarSubscriptionPlan,
  persistPolarSubscriptionSnapshotOnWorkspace,
} from './polarSubscriptionApply';
import { observeIntegrationEvent } from './metrics';
import Workspace from '../models/workspace.sequelize';

export type PolarReconcileRow = {
  ownerUserId: number;
  workspaceId: number;
  subscriptionId: string;
  dbPlanBefore: string;
  polarStatus: string;
  polarProductId: string;
  /** Intended plan after applying Polar snapshot (same rules as webhooks). */
  expectedPlan: string | null;
  drift: boolean;
  /** Row was saved (false when dryRun or no changes). */
  updated: boolean;
  error?: string;
};

export type PolarReconcileSummary = {
  scanned: number;
  polarFetchErrors: number;
  driftDetected: number;
  rowsUpdated: number;
  dryRun: boolean;
  rows: PolarReconcileRow[];
};

const RECONCILE_EVENT = 'subscription.updated';

function rowError(
  partial: Omit<PolarReconcileRow, 'error'> & { error: string },
): PolarReconcileRow {
  return { ...partial, error: partial.error };
}

/**
 * For each workspace with a stored `polar_subscription_id`, fetch the subscription from Polar and
 * align `workspaces.billing_plan` + Polar ids with the same rules as webhooks (owner user row mirrored).
 */
export async function reconcilePolarSubscriptionsFromApi(options: {
  log: FastifyBaseLogger;
  limit: number;
  dryRun: boolean;
}): Promise<PolarReconcileSummary> {
  const polar = createPolarServerClient();
  if (!polar) {
    throw new Error('POLAR_ACCESS_TOKEN is not configured');
  }

  const cap = Math.min(200, Math.max(1, Math.floor(options.limit)));
  const workspaces = await Workspace.findAll({
    where: {
      [Op.and]: [
        { polarSubscriptionId: { [Op.ne]: null } },
        { polarSubscriptionId: { [Op.ne]: '' } },
      ],
    },
    order: [['id', 'ASC']],
    limit: cap,
  });

  const rows: PolarReconcileRow[] = [];
  let polarFetchErrors = 0;
  let driftDetected = 0;
  let rowsUpdated = 0;

  for (const workspace of workspaces) {
    const workspaceId = workspace.get('id') as number;
    const ownerUserId = workspace.get('ownerUserId') as number;
    const subId = String(workspace.get('polarSubscriptionId') ?? '').trim();
    const dbPlanBefore = String(workspace.get('billingPlan') ?? 'free');

    if (!subId) {
      rows.push({
        ownerUserId,
        workspaceId,
        subscriptionId: '',
        dbPlanBefore,
        polarStatus: '',
        polarProductId: '',
        expectedPlan: null,
        drift: false,
        updated: false,
        error: 'empty_polar_subscription_id',
      });
      continue;
    }

    let remote: Subscription;
    try {
      remote = await polar.subscriptions.get({ id: subId });
    } catch (e: unknown) {
      polarFetchErrors += 1;
      const msg = e instanceof Error ? e.message : String(e);
      options.log.warn(
        {
          event: 'polar.reconcile.fetch_failed',
          workspace_id: workspaceId,
          owner_user_id: ownerUserId,
          subscription_id: subId,
          err: msg,
        },
        'polar reconcile: failed to fetch subscription',
      );
      rows.push(
        rowError({
          ownerUserId,
          workspaceId,
          subscriptionId: subId,
          dbPlanBefore,
          polarStatus: '',
          polarProductId: '',
          expectedPlan: null,
          drift: false,
          updated: false,
          error: msg,
        }),
      );
      continue;
    }

    const analysis = analyzePolarSubscriptionPlan(remote, RECONCILE_EVENT);
    const expectedPlan =
      analysis.touchBillingPlan && analysis.nextPlan != null ? analysis.nextPlan : dbPlanBefore;
    const drift =
      analysis.touchBillingPlan && analysis.nextPlan != null && analysis.nextPlan !== dbPlanBefore;

    if (drift) {
      driftDetected += 1;
      options.log.warn(
        {
          event: 'polar.reconcile.plan_drift',
          workspace_id: workspaceId,
          owner_user_id: ownerUserId,
          subscription_id: subId,
          db_plan: dbPlanBefore,
          expected_plan: analysis.nextPlan,
          polar_status: remote.status,
        },
        'polar reconcile: billing_plan drift vs Polar API',
      );
    }

    let updated = false;
    if (!options.dryRun) {
      updated = await persistPolarSubscriptionSnapshotOnWorkspace(workspace, remote, RECONCILE_EVENT, options.log);
    }

    if (updated) rowsUpdated += 1;

    rows.push({
      ownerUserId,
      workspaceId,
      subscriptionId: subId,
      dbPlanBefore,
      polarStatus: remote.status,
      polarProductId: remote.productId,
      expectedPlan,
      drift,
      updated: options.dryRun ? false : updated,
    });
  }

  options.log.info(
    {
      event: 'polar.reconcile.summary',
      scanned: workspaces.length,
      polar_fetch_errors: polarFetchErrors,
      drift_detected: driftDetected,
      rows_updated: rowsUpdated,
      dry_run: options.dryRun,
    },
    'polar subscription reconcile finished',
  );

  if (driftDetected > 0) {
    observeIntegrationEvent('polar_reconcile_drift');
  }

  return {
    scanned: workspaces.length,
    polarFetchErrors,
    driftDetected,
    rowsUpdated,
    dryRun: options.dryRun,
    rows,
  };
}
