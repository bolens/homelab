import { enqueueAsyncJob } from './asyncJobs';
import { appEnv } from './env';
import { observeIntegrationDelivery } from './metrics';

type WebhookPayload = Record<string, unknown>;
type SinkName = 'notify' | 'audit' | 'error';
type BreakerState = { consecutiveFailures: number; openUntilMs: number };

const circuitBreakerState: Record<SinkName, BreakerState> = {
  notify: { consecutiveFailures: 0, openUntilMs: 0 },
  audit: { consecutiveFailures: 0, openUntilMs: 0 },
  error: { consecutiveFailures: 0, openUntilMs: 0 },
};

function breakerIsOpen(sink: SinkName): boolean {
  return Date.now() < circuitBreakerState[sink].openUntilMs;
}

function recordSinkSuccess(sink: SinkName): void {
  circuitBreakerState[sink].consecutiveFailures = 0;
  circuitBreakerState[sink].openUntilMs = 0;
}

function recordSinkFailure(sink: SinkName): void {
  const state = circuitBreakerState[sink];
  state.consecutiveFailures += 1;
  if (state.consecutiveFailures >= appEnv.integrationCircuitBreakerThreshold) {
    state.openUntilMs = Date.now() + appEnv.integrationCircuitBreakerCooldownMs;
    state.consecutiveFailures = 0;
  }
}

async function postJson(
  url: string,
  payload: WebhookPayload,
  sink: SinkName,
  token?: string,
  timeoutMs = 5_000,
): Promise<void> {
  if (appEnv.incidentMode) {
    observeIntegrationDelivery({ sink, outcome: 'skipped_open' });
    return;
  }
  if (breakerIsOpen(sink)) {
    observeIntegrationDelivery({ sink, outcome: 'skipped_open' });
    return;
  }
  let attempt = 0;
  let backoffMs = 150;
  while (attempt < 3) {
    attempt += 1;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          ...(token ? { authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (response.ok) {
        observeIntegrationDelivery({ sink, outcome: 'ok' });
        recordSinkSuccess(sink);
        return;
      }
      observeIntegrationDelivery({ sink, outcome: 'non_2xx' });
      if (response.status < 500 || attempt >= 3) {
        throw new Error(`integration webhook non-2xx status=${response.status}`);
      }
    } catch (err: unknown) {
      const isAbort =
        (err instanceof DOMException && err.name === 'AbortError') ||
        (typeof err === 'object' &&
          err !== null &&
          'name' in err &&
          (err as { name?: string }).name === 'AbortError');
      observeIntegrationDelivery({ sink, outcome: isAbort ? 'timeout' : 'error' });
      if (attempt >= 3) {
        recordSinkFailure(sink);
        throw err;
      }
      await new Promise((resolve) => setTimeout(resolve, backoffMs));
      backoffMs *= 2;
    } finally {
      clearTimeout(timeout);
    }
  }
}

export function notifyWebhook(event: string, payload: WebhookPayload): void {
  if (!appEnv.notifyWebhookUrl) return;
  const targetUrl = appEnv.notifyWebhookUrl;
  enqueueAsyncJob(
    `integration_notify:${event}`,
    async () => {
      await postJson(
        targetUrl,
        {
          source: 'asking-ng-api',
          event,
          at: new Date().toISOString(),
          payload,
        },
        'notify',
        appEnv.notifyWebhookToken,
        appEnv.integrationWebhookTimeoutMs,
      );
    },
    { dropCategory: 'integration_notify' },
  );
}

export function sinkAuditLog(event: WebhookPayload): void {
  if (!appEnv.auditLogSinkUrl) return;
  const targetUrl = appEnv.auditLogSinkUrl;
  enqueueAsyncJob(
    'integration_audit_sink',
    async () => {
      await postJson(
        targetUrl,
        {
          source: 'asking-ng-api',
          type: 'audit_log',
          at: new Date().toISOString(),
          event,
        },
        'audit',
        appEnv.auditLogSinkToken,
        appEnv.integrationWebhookTimeoutMs,
      );
    },
    { dropCategory: 'integration_audit' },
  );
}

export function reportErrorToSentryCompat(event: WebhookPayload): void {
  if (!appEnv.sentryCompatWebhookUrl) return;
  const targetUrl = appEnv.sentryCompatWebhookUrl;
  enqueueAsyncJob(
    'integration_error_sink',
    async () => {
      await postJson(
        targetUrl,
        {
          source: 'asking-ng-api',
          type: 'error',
          at: new Date().toISOString(),
          event,
        },
        'error',
        appEnv.sentryCompatWebhookToken,
        appEnv.integrationWebhookTimeoutMs,
      );
    },
    { dropCategory: 'integration_error' },
  );
}
