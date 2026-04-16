import { randomUUID } from 'node:crypto';
import { appEnv } from './env';
import { logger } from './logger';
import { observeAsyncJobDrop, setAsyncQueueDepth } from './metrics';

type AsyncTask = {
  id: string;
  name: string;
  run: () => Promise<void>;
  enqueuedAtMs: number;
};

const queue: AsyncTask[] = [];
let activeWorkers = 0;
let stopping = false;
let idleWaiters: Array<() => void> = [];

function asyncRunnerEnabled(): boolean {
  return appEnv.asyncJobRunnerEnabled;
}

function workerConcurrency(): number {
  return appEnv.asyncJobRunnerConcurrency;
}

function resolveIdleWaitersIfDone(): void {
  if (queue.length > 0 || activeWorkers > 0) return;
  const waiters = idleWaiters;
  idleWaiters = [];
  for (const done of waiters) done();
}

function runNext(): void {
  if (stopping) return;
  const maxWorkers = workerConcurrency();
  while (activeWorkers < maxWorkers && queue.length > 0) {
    const task = queue.shift()!;
    setAsyncQueueDepth(queue.length);
    activeWorkers += 1;
    void task
      .run()
      .catch((err: unknown) => {
        logger.warn({ event: 'async_job.failed', err, taskId: task.id, taskName: task.name }, 'async job failed');
      })
      .finally(() => {
        activeWorkers -= 1;
        runNext();
        resolveIdleWaitersIfDone();
      });
  }
}

type EnqueueAsyncJobOptions = {
  critical?: boolean;
  dropCategory?: string;
};

function queueMax(): number {
  return appEnv.asyncJobQueueMax;
}

export function enqueueAsyncJob(
  name: string,
  run: () => Promise<void>,
  options: EnqueueAsyncJobOptions = {},
): string {
  const id = randomUUID();
  if (!asyncRunnerEnabled()) {
    void run().catch((err: unknown) => {
      logger.warn(
        { event: 'async_job.inline_failed', err, taskId: id, taskName: name },
        'async job failed (inline mode)',
      );
    });
    return id;
  }
  if (queue.length >= queueMax() && !options.critical) {
    observeAsyncJobDrop(options.dropCategory || 'default');
    logger.warn(
      { event: 'async_job.queue_drop', taskId: id, taskName: name, queueLength: queue.length },
      'async job dropped because queue is at capacity',
    );
    return id;
  }
  queue.push({ id, name, run, enqueuedAtMs: Date.now() });
  setAsyncQueueDepth(queue.length);
  runNext();
  return id;
}

export function enqueuePollExportJob(
  pollId: string,
  requestedBy: string | null,
  run: () => Promise<void>,
): string {
  return enqueueAsyncJob(`poll_export:${pollId}:${requestedBy ?? 'anonymous'}`, run, {
    critical: true,
    dropCategory: 'poll_export',
  });
}

export async function stopAsyncJobs(timeoutMs = 15_000): Promise<void> {
  stopping = true;
  if (queue.length === 0 && activeWorkers === 0) return;
  await Promise.race([
    new Promise<void>((resolve) => {
      idleWaiters.push(resolve);
    }),
    new Promise<void>((resolve) => setTimeout(resolve, timeoutMs)),
  ]);
  setAsyncQueueDepth(queue.length);
}

