import { appEnv } from './env';
import { logger } from './logger';
import { reconcilePolarSubscriptionsFromApi } from './polarSubscriptionReconcile';

let timer: NodeJS.Timeout | null = null;
let inFlight = false;

async function runScheduledReconcile(): Promise<void> {
  if (inFlight) {
    logger.warn(
      { event: 'polar.reconcile.cron_skip_inflight' },
      'scheduled polar reconcile skipped: previous run still in progress',
    );
    return;
  }
  inFlight = true;
  try {
    await reconcilePolarSubscriptionsFromApi({
      log: logger,
      limit: appEnv.polarReconcileLimit,
      dryRun: false,
    });
  } catch (err: unknown) {
    logger.error({ event: 'polar.reconcile.cron_failed', err }, 'scheduled polar reconcile failed');
  } finally {
    inFlight = false;
  }
}

export function startPolarReconcileWorker(): void {
  if (timer) return;
  if (!appEnv.polarAccessToken) return;
  if (appEnv.polarReconcileIntervalSec <= 0) return;

  const intervalMs = appEnv.polarReconcileIntervalSec * 1000;
  timer = setInterval(() => {
    void runScheduledReconcile();
  }, intervalMs);
  logger.info(
    {
      event: 'polar.reconcile.cron_started',
      interval_sec: appEnv.polarReconcileIntervalSec,
      limit: appEnv.polarReconcileLimit,
    },
    'scheduled polar reconcile worker started',
  );
}

export function stopPolarReconcileWorker(): void {
  if (!timer) return;
  clearInterval(timer);
  timer = null;
  logger.info({ event: 'polar.reconcile.cron_stopped' }, 'scheduled polar reconcile worker stopped');
}
