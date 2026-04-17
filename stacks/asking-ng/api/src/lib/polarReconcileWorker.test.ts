import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  reconcile: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
}));

vi.mock('./env', () => ({
  appEnv: {
    polarAccessToken: 'token',
    polarReconcileIntervalSec: 1,
    polarReconcileLimit: 33,
  },
}));

vi.mock('./logger', () => ({
  logger: {
    info: mocks.info,
    warn: mocks.warn,
    error: mocks.error,
  },
}));

vi.mock('./polarSubscriptionReconcile', () => ({
  reconcilePolarSubscriptionsFromApi: mocks.reconcile,
}));

import { startPolarReconcileWorker, stopPolarReconcileWorker } from './polarReconcileWorker';

describe('polarReconcileWorker', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mocks.reconcile.mockReset();
    mocks.info.mockReset();
    mocks.warn.mockReset();
    mocks.error.mockReset();
    stopPolarReconcileWorker();
  });

  afterEach(() => {
    stopPolarReconcileWorker();
    vi.useRealTimers();
  });

  it('starts interval and triggers reconcile with configured limit', async () => {
    mocks.reconcile.mockResolvedValue(undefined);
    startPolarReconcileWorker();
    await vi.advanceTimersByTimeAsync(1000);
    expect(mocks.reconcile).toHaveBeenCalledWith(
      expect.objectContaining({
        limit: 33,
        dryRun: false,
      }),
    );
  });
});
