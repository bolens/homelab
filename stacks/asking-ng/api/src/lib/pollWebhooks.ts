import { createHmac, randomBytes } from 'node:crypto';
import Poll from '../model/Poll';
import { enqueueAsyncJob } from './asyncJobs';
import { takePollWebhookDeliveryForPoll } from './billingPollWebhookDelivery';
import { appEnv } from './env';
import { logger } from './logger';
import { recordPollWebhookDeliveryTelemetry } from './pollWebhookDeliveryTelemetry';
import {
  buildAllPollWebhookHintPacks,
  pollWebhookHintPackForLocale,
  resolvePollWebhookHintLocale,
  SUPPORTED_POLL_WEBHOOK_HINT_LOCALES,
} from './pollWebhookHintPacks';
import { fetchPollWebhookOwnerEvents } from './pollWebhookOwnerEvents';
import { fetchPollWebhookOwnerSnapshot } from './pollWebhookOwnerSnapshot';
import { fetchPollWebhookPublicResultsSnapshot } from './pollWebhookResultsSnapshot';
import { isPublicWebhookUrl } from './webhookUrlSafe';

type PollWebhookEvent = 'vote' | 'poll_updated' | 'poll_deleted';

function utcMsFromPollField(raw: unknown): number | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  if (typeof raw === 'bigint') {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  if (typeof raw === 'string' && raw.trim() !== '') {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** Snapshot from DB at enqueue time; overlays/bots can read without refetching the poll API. */
function buildStreamerContextFromPollRow(poll: {
  get(key: string): unknown;
}): Record<string, unknown> {
  const titleRaw = poll.get('title');
  const pollTitle =
    typeof titleRaw === 'string'
      ? titleRaw
      : titleRaw === null || titleRaw === undefined
        ? ''
        : String(titleRaw);

  const phaseRaw = poll.get('phase');
  const phase = typeof phaseRaw === 'string' && phaseRaw.trim() !== '' ? phaseRaw.trim() : 'open';

  const votingPaused = Boolean(poll.get('votingPaused'));
  const archived = Boolean(poll.get('archived'));

  const selectionModeRaw = poll.get('selectionMode');
  const selection_mode =
    typeof selectionModeRaw === 'string' && selectionModeRaw.trim() !== ''
      ? selectionModeRaw.trim()
      : 'single';

  return {
    poll_title: pollTitle,
    phase,
    voting_paused: votingPaused,
    archived,
    selection_mode,
    schedule_utc_ms: {
      open_at: utcMsFromPollField(poll.get('openAt')),
      lock_at: utcMsFromPollField(poll.get('lockAt')),
      reveal_at: utcMsFromPollField(poll.get('revealAt')),
      expires_at: utcMsFromPollField(poll.get('expiration')),
    },
  };
}

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
  const pollPathDefault = `/${encodeURIComponent(pollId)}`;
  const resultsPathDefault = `${pollPathDefault}/results`;
  const existingCommandHintsRaw = data['command_hints'];
  const existingCommandHints =
    existingCommandHintsRaw && typeof existingCommandHintsRaw === 'object'
      ? (existingCommandHintsRaw as Record<string, unknown>)
      : {};
  const existingCommandAliasesRaw = existingCommandHints['command_aliases'];
  const existingCommandAliases =
    existingCommandAliasesRaw && typeof existingCommandAliasesRaw === 'object'
      ? (existingCommandAliasesRaw as Record<string, unknown>)
      : {};
  const existingCapabilityFlagsRaw = existingCommandHints['capability_flags'];
  const existingCapabilityFlags =
    existingCapabilityFlagsRaw && typeof existingCapabilityFlagsRaw === 'object'
      ? (existingCapabilityFlagsRaw as Record<string, unknown>)
      : {};
  const hintLocaleResolved = resolvePollWebhookHintLocale(
    existingCommandHints['hint_locale'],
    appEnv.pollWebhookHintLocale,
  );
  const activePack = pollWebhookHintPackForLocale(pollId, hintLocaleResolved);
  // When changing the default literal below, append docs/POLL-WEBHOOK-CONTRACT-VERSIONS.md if receivers need a breaking / visibility entry.
  const contractVersionResolved =
    typeof existingCommandHints['contract_version'] === 'string' &&
    existingCommandHints['contract_version'].trim() !== ''
      ? existingCommandHints['contract_version'].trim()
      : '2026-04-webhook-command-hints-v1';
  const {
    command_aliases: _ignoredCommandAliases,
    capability_flags: _ignoredCapabilityFlags,
    hint_packs: _ignoredHintPacks,
    hint_locale: _ignoredHintLocale,
    contract_version: _ignoredContractVersion,
    ...existingCommandHintsWithoutNested
  } = existingCommandHints;
  const normalizedData: Record<string, unknown> = {
    ...data,
    poll_path:
      typeof data['poll_path'] === 'string' && data['poll_path'].trim() !== ''
        ? data['poll_path']
        : pollPathDefault,
    results_path:
      typeof data['results_path'] === 'string' && data['results_path'].trim() !== ''
        ? data['results_path']
        : resultsPathDefault,
    command_hints: {
      chat_vote_short: activePack.chat_vote_short,
      chat_results_short: activePack.chat_results_short,
      ...existingCommandHintsWithoutNested,
      command_aliases: {
        ...activePack.command_aliases,
        ...existingCommandAliases,
      },
      capability_flags: {
        supports_vote_command: true,
        supports_results_command: true,
        supports_command_aliases: true,
        supports_hint_locale: true,
        supports_hint_locale_override: true,
        supports_hint_packs: true,
        supports_supported_hint_locales: true,
        supports_contract_version: true,
        ...existingCapabilityFlags,
        supports_streamer_context: true,
        supports_webhook_results_snapshot: true,
        supports_webhook_owner_snapshot: true,
        supports_owner_events: true,
      },
      contract_version: contractVersionResolved,
      hint_locale: hintLocaleResolved,
      supported_hint_locales: [...SUPPORTED_POLL_WEBHOOK_HINT_LOCALES],
      hint_packs: buildAllPollWebhookHintPacks(pollId),
    },
  };
  const at = new Date().toISOString();
  const eventId = randomBytes(16).toString('hex');
  const bodyObj = { event_id: eventId, event, poll_id: pollId, at, data: normalizedData };
  const body = JSON.stringify(bodyObj);
  const t = Math.floor(Date.now() / 1000);
  const sig = signPayload(secret, t, body);
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 12_000);
  try {
    recordPollWebhookDeliveryTelemetry('attempted');
    const r = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Asking-Webhook-Timestamp': String(t),
        'X-Asking-Webhook-Signature': `v1=${sig}`,
        'X-Asking-Webhook-Event-Id': eventId,
        'User-Agent': 'asking-ng-webhook/1',
      },
      body,
      signal: ac.signal,
    });
    if (!r.ok) {
      recordPollWebhookDeliveryTelemetry('delivered_non_2xx');
      logger.warn(
        { event: 'poll.webhook.delivery_non_2xx', pollId, webhookEvent: event, status: r.status },
        'poll webhook delivery non-2xx',
      );
    } else {
      recordPollWebhookDeliveryTelemetry('delivered_ok');
    }
  } catch (err: unknown) {
    recordPollWebhookDeliveryTelemetry('delivery_failed');
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
    logger.info(
      { event: 'poll.webhook.skipped_incident_mode', pollId, webhookEvent: event },
      'poll webhook skipped',
    );
    return;
  }
  void (async () => {
    const poll = await Poll.findByPk(pollId, {
      attributes: [
        'webhookTargets',
        'creatorUserId',
        'title',
        'phase',
        'votingPaused',
        'archived',
        'selectionMode',
        'openAt',
        'lockAt',
        'revealAt',
        'expiration',
        'options',
        'resultsDelaySeconds',
        'boostedVotingEnabled',
        'showUnweightedValues',
      ],
    });
    if (!poll) return;
    const streamerContext = buildStreamerContextFromPollRow(poll);
    const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
    const targetsRaw =
      (poll.get('webhookTargets') as
        | Array<{
            url?: string;
            secret?: string;
            hint_locale?: unknown;
            include_results_snapshot?: unknown;
            include_owner_snapshot?: unknown;
            include_owner_events?: unknown;
          }>
        | null
        | undefined) ?? [];
    if (targetsRaw.length === 0) return;

    const anyWantsResultsSnapshot = targetsRaw.some((t) => t?.include_results_snapshot === true);
    let resultsSnapshot: Record<string, unknown> | null = null;
    if (anyWantsResultsSnapshot) {
      try {
        resultsSnapshot = await fetchPollWebhookPublicResultsSnapshot({ pollId, poll });
      } catch (err: unknown) {
        logger.warn(
          { event: 'poll.webhook.results_snapshot_failed', err, pollId },
          'poll webhook: results snapshot query failed',
        );
        resultsSnapshot = null;
      }
    }

    const anyWantsOwnerSnapshot = targetsRaw.some((t) => t?.include_owner_snapshot === true);
    let ownerSnapshot: Record<string, unknown> | null = null;
    if (anyWantsOwnerSnapshot) {
      try {
        ownerSnapshot = await fetchPollWebhookOwnerSnapshot({ pollId, poll });
      } catch (err: unknown) {
        logger.warn(
          { event: 'poll.webhook.owner_snapshot_failed', err, pollId },
          'poll webhook: owner snapshot query failed',
        );
        ownerSnapshot = null;
      }
    }

    const anyWantsOwnerEvents = targetsRaw.some((t) => t?.include_owner_events === true);
    let ownerEvents: Record<string, unknown> | null = null;
    if (anyWantsOwnerEvents) {
      try {
        ownerEvents = await fetchPollWebhookOwnerEvents({ pollId });
      } catch (err: unknown) {
        logger.warn(
          { event: 'poll.webhook.owner_events_failed', err, pollId },
          'poll webhook: owner events query failed',
        );
        ownerEvents = null;
      }
    }

    for (const target of targetsRaw) {
      const urlStr = typeof target.url === 'string' ? target.url.trim() : '';
      const sec = typeof target.secret === 'string' ? target.secret.trim() : '';
      if (!urlStr || !sec) continue;
      let url: URL;
      try {
        url = new URL(urlStr);
      } catch {
        logger.warn(
          { event: 'poll.webhook.invalid_url_stored', pollId },
          'poll webhook: invalid URL stored',
        );
        continue;
      }
      if (!isPublicWebhookUrl(url)) {
        logger.warn(
          { event: 'poll.webhook.non_public_url_blocked', pollId, host: url.hostname },
          'poll webhook: blocked non-public URL',
        );
        continue;
      }
      if (!(await takePollWebhookDeliveryForPoll({ pollId, creatorUserId }))) {
        continue;
      }
      const targetHintLocale =
        typeof target['hint_locale'] === 'string'
          ? target['hint_locale'].trim().toLowerCase()
          : undefined;
      const includeResultsSnapshot =
        target.include_results_snapshot === true && resultsSnapshot != null;
      const includeOwnerSnapshot = target.include_owner_snapshot === true && ownerSnapshot != null;
      const includeOwnerEvents = target.include_owner_events === true && ownerEvents != null;
      enqueueAsyncJob(`poll_webhook:${event}:${pollId}`, async () => {
        await postWebhook(urlStr, sec, event, pollId, {
          ...data,
          streamer_context: streamerContext,
          ...(includeResultsSnapshot ? { results_snapshot: resultsSnapshot } : {}),
          ...(includeOwnerSnapshot ? { owner_snapshot: ownerSnapshot } : {}),
          ...(includeOwnerEvents ? { owner_events: ownerEvents } : {}),
          command_hints: {
            ...(data['command_hints'] && typeof data['command_hints'] === 'object'
              ? (data['command_hints'] as Record<string, unknown>)
              : {}),
            ...(targetHintLocale ? { hint_locale: targetHintLocale } : {}),
          },
        });
      });
    }
  })();
}
