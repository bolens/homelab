import { createHmac, randomBytes } from 'node:crypto';
import Poll from '../model/Poll';
import { enqueueAsyncJob } from './asyncJobs';
import { appEnv } from './env';
import { logger } from './logger';
import { isPublicWebhookUrl } from './webhookUrlSafe';

type PollWebhookEvent = 'vote' | 'poll_updated' | 'poll_deleted';

export function generateWebhookSecret(): string {
  return randomBytes(24).toString('hex');
}

function signPayload(secret: string, timestampSec: number, body: string): string {
  const payload = `${timestampSec}.${body}`;
  return createHmac('sha256', secret).update(payload).digest('hex');
}

async function postWebhook(
  url: string,
  secret: string,
  event: PollWebhookEvent,
  pollId: string,
  data: Record<string, unknown>,
): Promise<void> {
  const at = new Date().toISOString();
  const bodyObj = { event, poll_id: pollId, at, data };
  const body = JSON.stringify(bodyObj);
  const t = Math.floor(Date.now() / 1000);
  const sig = signPayload(secret, t, body);
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 12_000);
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Asking-Webhook-Timestamp': String(t),
        'X-Asking-Webhook-Signature': `v1=${sig}`,
        'User-Agent': 'asking-ng-webhook/1',
      },
      body,
      signal: ac.signal,
    });
    if (!r.ok) {
      logger.warn(
        { event: 'poll.webhook.delivery_non_2xx', pollId, webhookEvent: event, status: r.status },
        'poll webhook delivery non-2xx',
      );
    }
  } catch (err: unknown) {
    logger.warn(
      { event: 'poll.webhook.delivery_failed', err, pollId, webhookEvent: event },
      'poll webhook delivery failed',
    );
  } finally {
    clearTimeout(timer);
  }
}

/** Fire-and-forget: loads webhook config for the poll and POSTs a signed JSON body. */
export function queuePollWebhook(
  pollId: string,
  event: PollWebhookEvent,
  data: Record<string, unknown>,
): void {
  if (appEnv.incidentMode) {
    logger.info({ event: 'poll.webhook.skipped_incident_mode', pollId, webhookEvent: event }, 'poll webhook skipped');
    return;
  }
  void (async () => {
    const poll = await Poll.findByPk(pollId, {
      attributes: ['webhookTargets'],
    });
    if (!poll) return;
    const targetsRaw =
      (poll.get('webhookTargets') as Array<{ url?: string; secret?: string }> | null | undefined) ??
      [];
    if (targetsRaw.length === 0) return;
    for (const target of targetsRaw) {
      const urlStr = typeof target.url === 'string' ? target.url.trim() : '';
      const sec = typeof target.secret === 'string' ? target.secret.trim() : '';
      if (!urlStr || !sec) continue;
      let url: URL;
      try {
        url = new URL(urlStr);
      } catch {
        logger.warn({ event: 'poll.webhook.invalid_url_stored', pollId }, 'poll webhook: invalid URL stored');
        continue;
      }
      if (!isPublicWebhookUrl(url)) {
        logger.warn(
          { event: 'poll.webhook.non_public_url_blocked', pollId, host: url.hostname },
          'poll webhook: blocked non-public URL',
        );
        continue;
      }
      enqueueAsyncJob(`poll_webhook:${event}:${pollId}`, async () => {
        await postWebhook(urlStr, sec, event, pollId, data);
      });
    }
  })();
}
