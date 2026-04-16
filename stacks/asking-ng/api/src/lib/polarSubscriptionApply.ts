import type { Subscription } from '@polar-sh/sdk/models/components/subscription';
import type { FastifyBaseLogger } from 'fastify';
import { appEnv } from './env';
import { invalidateSessionUserCache } from './sessionUserCache';
import { ensureDefaultWorkspaceForUser } from './workspaceBootstrap';
import User from '../models/user.sequelize';
import Workspace from '../models/workspace.sequelize';

const SUBSCRIPTION_WEBHOOK_TYPES = new Set([
  'subscription.active',
  'subscription.updated',
  'subscription.canceled',
  'subscription.uncanceled',
  'subscription.revoked',
]);

export type PaidBillingPlan = 'free' | 'cloud-team' | 'cloud-pro';

/** Map Polar `product_id` to internal plan; requires env `POLAR_PRODUCT_ID_*`. */
export function resolveBillingPlanFromPolarProductId(productId: string): 'cloud-team' | 'cloud-pro' | null {
  const team = appEnv.polarProductIdCloudTeam;
  const pro = appEnv.polarProductIdCloudPro;
  if (pro && productId === pro) return 'cloud-pro';
  if (team && productId === team) return 'cloud-team';
  return null;
}

/** Whether the subscription should keep a paid `billing_plan` (not `free`). */
export function subscriptionGrantsPaidPlan(subscriptionStatus: string, eventType: string): boolean {
  if (eventType === 'subscription.revoked') return false;
  switch (subscriptionStatus) {
    case 'active':
    case 'trialing':
    case 'past_due':
      return true;
    default:
      return false;
  }
}

function isRecord(data: unknown): data is Record<string, unknown> {
  return typeof data === 'object' && data !== null && !Array.isArray(data);
}

function isSubscriptionData(data: unknown): data is Subscription {
  if (!isRecord(data)) return false;
  return (
    typeof data.id === 'string' &&
    typeof data.customerId === 'string' &&
    typeof data.productId === 'string' &&
    typeof data.status === 'string'
  );
}

export type WorkspaceInstance = NonNullable<Awaited<ReturnType<typeof Workspace.findByPk>>>;

/**
 * Resolve billing workspace from a Polar subscription payload (webhooks + reconcile).
 * Order: **`asking_ng_workspace_id`** metadata → **`asking_ng_user_id`** (default workspace) →
 * **`workspaces.polar_subscription_id`** → **`workspaces.polar_customer_id`**.
 */
export async function findWorkspaceForPolarSubscription(sub: Subscription): Promise<WorkspaceInstance | null> {
  const meta = sub.metadata && typeof sub.metadata === 'object' ? sub.metadata : {};
  const metaRec = meta as Record<string, unknown>;

  const wsMeta = metaRec['asking_ng_workspace_id'];
  if (wsMeta !== undefined && wsMeta !== null) {
    const n = Number(String(wsMeta).trim());
    if (Number.isInteger(n) && n > 0) {
      const byWsId = await Workspace.findByPk(n);
      if (byWsId) return byWsId;
    }
  }

  const userMeta = metaRec['asking_ng_user_id'];
  if (userMeta !== undefined && userMeta !== null) {
    const n = Number(String(userMeta).trim());
    if (Number.isInteger(n) && n > 0) {
      const byId = await User.findByPk(n);
      if (byId) {
        await ensureDefaultWorkspaceForUser(byId);
        const wid = byId.get('defaultWorkspaceId') as number | null | undefined;
        if (wid != null && wid > 0) {
          const ws = await Workspace.findByPk(wid);
          if (ws) return ws;
        }
      }
    }
  }

  if (sub.id) {
    const bySubscriptionId = await Workspace.findOne({ where: { polarSubscriptionId: sub.id } });
    if (bySubscriptionId) return bySubscriptionId;
  }
  if (sub.customerId) {
    const byCustomer = await Workspace.findOne({ where: { polarCustomerId: sub.customerId } });
    if (byCustomer) return byCustomer;
  }
  return null;
}

export type PolarPlanAnalysis = {
  /** When true, `billing_plan` should be set to `nextPlan`. */
  touchBillingPlan: boolean;
  nextPlan: PaidBillingPlan | null;
  /** Paid Polar status but `product_id` not in `POLAR_PRODUCT_ID_*` — do not change `billing_plan`. */
  unmappedPaidProduct: boolean;
};

/** Derive how `billing_plan` should change from a subscription snapshot (webhook or Polar API). */
export function analyzePolarSubscriptionPlan(sub: Subscription, eventType: string): PolarPlanAnalysis {
  const grants = subscriptionGrantsPaidPlan(sub.status, eventType);
  const mappedPlan = resolveBillingPlanFromPolarProductId(sub.productId);
  if (grants && mappedPlan != null) {
    return { touchBillingPlan: true, nextPlan: mappedPlan, unmappedPaidProduct: false };
  }
  if (!grants) {
    return { touchBillingPlan: true, nextPlan: 'free', unmappedPaidProduct: false };
  }
  return { touchBillingPlan: false, nextPlan: null, unmappedPaidProduct: true };
}

/** Mirror workspace billing + Polar linkage onto the owner `users` row (compat + profile reads). */
export async function syncOwnerUserBillingFromWorkspace(workspace: WorkspaceInstance): Promise<void> {
  const ownerId = workspace.get('ownerUserId') as number;
  const user = await User.findByPk(ownerId);
  if (!user) return;
  user.set('billingPlan', workspace.get('billingPlan'));
  user.set('polarCustomerId', workspace.get('polarCustomerId'));
  user.set('polarSubscriptionId', workspace.get('polarSubscriptionId'));
  const changed = user.changed();
  if (!changed || changed.length === 0) return;
  await user.save();
  invalidateSessionUserCache(ownerId);
}

/**
 * Persist Polar subscription ids and optional `billing_plan` on a workspace row (source of truth).
 * Mirrors onto the owner user row. Returns whether the workspace row was saved.
 */
export async function persistPolarSubscriptionSnapshotOnWorkspace(
  workspace: WorkspaceInstance,
  sub: Subscription,
  eventType: string,
  log: FastifyBaseLogger,
): Promise<boolean> {
  const analysis = analyzePolarSubscriptionPlan(sub, eventType);
  if (analysis.unmappedPaidProduct) {
    log.warn(
      {
        event: 'polar.subscription.unmapped_product',
        product_id: sub.productId,
        workspace_id: workspace.get('id'),
        owner_user_id: workspace.get('ownerUserId'),
      },
      'polar subscription: paid status but product_id not in POLAR_PRODUCT_ID_* env; billing_plan unchanged',
    );
  }

  workspace.set('polarCustomerId', sub.customerId);
  workspace.set('polarSubscriptionId', sub.id);
  if (analysis.touchBillingPlan && analysis.nextPlan != null) {
    workspace.set('billingPlan', analysis.nextPlan);
  }

  const changed = workspace.changed();
  const dirty = Boolean(changed && changed.length > 0);
  if (dirty) {
    await workspace.save();
  }

  await syncOwnerUserBillingFromWorkspace(workspace);

  if (dirty) {
    log.info(
      {
        event: 'polar.subscription.workspace_updated',
        workspace_id: workspace.get('id'),
        owner_user_id: workspace.get('ownerUserId'),
        billing_plan: workspace.get('billingPlan'),
        polar_event: eventType,
      },
      'polar subscription applied to workspace',
    );
  }

  return dirty;
}

/**
 * Apply Polar subscription webhook payloads to the billing workspace (+ owner user mirror).
 * Safe to call after signature verification; logs and returns on missing workspace / unmapped product.
 */
export async function applyPolarSubscriptionWebhookEvent(
  event: { type: string; data: unknown },
  log: FastifyBaseLogger,
): Promise<void> {
  const eventType = event.type;
  if (!SUBSCRIPTION_WEBHOOK_TYPES.has(eventType)) return;
  if (!isSubscriptionData(event.data)) {
    log.warn({ event: 'polar.subscription.invalid_data_shape', eventType }, 'polar subscription webhook: bad data');
    return;
  }
  const sub = event.data;
  const workspace = await findWorkspaceForPolarSubscription(sub);
  if (!workspace) {
    log.info(
      {
        event: 'polar.subscription.workspace_not_found',
        eventType,
        customer_id: sub.customerId,
        subscription_id: sub.id,
      },
      'polar subscription webhook: no matching workspace (set metadata asking_ng_user_id or asking_ng_workspace_id on checkout, or link polar ids on the default workspace)',
    );
    return;
  }

  await persistPolarSubscriptionSnapshotOnWorkspace(workspace, sub, eventType, log);
}
