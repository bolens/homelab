import { beforeEach, describe, expect, it, vi } from 'vitest';

const {
  mockFindByPk,
  mockTakePollWebhookDeliveryForPoll,
  mockEnqueueAsyncJob,
  mockIsPublicWebhookUrl,
  mockFetchResultsSnapshot,
  mockFetchOwnerSnapshot,
  mockFetchOwnerEvents,
  appEnvMutable,
} = vi.hoisted(() => {
  const appEnvMutable: { incidentMode: boolean; pollWebhookHintLocale: 'en' | 'en-gb' | 'es' } = {
    incidentMode: false,
    pollWebhookHintLocale: 'en',
  };
  return {
    mockFindByPk: vi.fn(),
    mockTakePollWebhookDeliveryForPoll: vi.fn(),
    mockEnqueueAsyncJob: vi.fn(),
    mockIsPublicWebhookUrl: vi.fn(),
    mockFetchResultsSnapshot: vi.fn(),
    mockFetchOwnerSnapshot: vi.fn(),
    mockFetchOwnerEvents: vi.fn(),
    appEnvMutable,
  };
});

vi.mock('../model/Poll', () => ({
  default: {
    findByPk: mockFindByPk,
  },
}));

vi.mock('./billingPollWebhookDelivery', () => ({
  takePollWebhookDeliveryForPoll: mockTakePollWebhookDeliveryForPoll,
}));

vi.mock('./asyncJobs', () => ({
  enqueueAsyncJob: mockEnqueueAsyncJob,
}));

vi.mock('./webhookUrlSafe', () => ({
  isPublicWebhookUrl: mockIsPublicWebhookUrl,
}));

vi.mock('./env', () => ({
  get appEnv() {
    return appEnvMutable;
  },
}));

vi.mock('./pollWebhookResultsSnapshot', () => ({
  fetchPollWebhookPublicResultsSnapshot: mockFetchResultsSnapshot,
}));

vi.mock('./pollWebhookOwnerSnapshot', () => ({
  fetchPollWebhookOwnerSnapshot: mockFetchOwnerSnapshot,
}));

vi.mock('./pollWebhookOwnerEvents', () => ({
  fetchPollWebhookOwnerEvents: mockFetchOwnerEvents,
}));

import { buildAllPollWebhookHintPacks } from './pollWebhookHintPacks';
import {
  readPollWebhookDeliveryTelemetry,
  resetPollWebhookDeliveryTelemetryForTests,
} from './pollWebhookDeliveryTelemetry';
import { queuePollWebhook } from './pollWebhooks';

function pollRow(
  webhookTargets: Array<{
    url: string;
    secret: string;
    hint_locale?: string;
    include_results_snapshot?: boolean;
    include_owner_snapshot?: boolean;
    include_owner_events?: boolean;
  }>,
  pollFields: Record<string, unknown> = {},
) {
  const defaults: Record<string, unknown> = {
    title: 'Test poll',
    phase: 'open',
    votingPaused: false,
    archived: false,
    selectionMode: 'single',
    openAt: null,
    lockAt: null,
    revealAt: null,
    expiration: null,
    ...pollFields,
  };
  return {
    get(key: string) {
      if (key === 'webhookTargets') return webhookTargets;
      if (key === 'creatorUserId') return 42;
      if (Object.prototype.hasOwnProperty.call(defaults, key)) return defaults[key];
      return null;
    },
  };
}

async function flushAsync(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe('queuePollWebhook envelope defaults', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetPollWebhookDeliveryTelemetryForTests();
    mockFetchResultsSnapshot.mockReset();
    mockFetchOwnerSnapshot.mockReset();
    mockFetchOwnerEvents.mockReset();
    appEnvMutable.incidentMode = false;
    mockTakePollWebhookDeliveryForPoll.mockResolvedValue(true);
    mockIsPublicWebhookUrl.mockReturnValue(true);
    mockFindByPk.mockResolvedValue(
      pollRow([{ url: 'https://hooks.example.test/poll', secret: 'top-secret' }]),
    );
    mockEnqueueAsyncJob.mockImplementation(async (_name: string, job: () => Promise<void>) => {
      await job();
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
      }),
    );
  });

  it.each([
    ['vote', { option: 'A' }],
    ['poll_updated', { title: 'new title' }],
    ['poll_deleted', { reason: 'owner_deleted' }],
  ] as const)('adds default helper fields for %s payloads', async (event, seedData) => {
    queuePollWebhook('poll-1', event, seedData);
    await flushAsync();

    expect(fetch).toHaveBeenCalledTimes(1);
    const reqInit = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(reqInit.body));

    expect(body).toMatchObject({
      event,
      poll_id: 'poll-1',
      data: expect.objectContaining({
        ...seedData,
        streamer_context: {
          poll_title: 'Test poll',
          phase: 'open',
          voting_paused: false,
          archived: false,
          selection_mode: 'single',
          schedule_utc_ms: {
            open_at: null,
            lock_at: null,
            reveal_at: null,
            expires_at: null,
          },
        },
        poll_path: '/poll-1',
        results_path: '/poll-1/results',
        command_hints: {
          chat_vote_short: '!vote poll-1 <option>',
          chat_results_short: '!results poll-1',
          command_aliases: {
            vote: ['/vote poll-1 <option>', '!v poll-1 <option>'],
            results: ['/results poll-1', '!r poll-1'],
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
            supports_streamer_context: true,
            supports_webhook_results_snapshot: true,
            supports_webhook_owner_snapshot: true,
            supports_owner_events: true,
          },
          contract_version: '2026-04-webhook-command-hints-v1',
          hint_locale: 'en',
          supported_hint_locales: ['en', 'en-gb', 'es'],
          hint_packs: buildAllPollWebhookHintPacks('poll-1'),
        },
      }),
    });
    expect(mockFetchResultsSnapshot).not.toHaveBeenCalled();
    expect(mockFetchOwnerSnapshot).not.toHaveBeenCalled();
    expect(body.event_id).toEqual(expect.any(String));
    expect(body.at).toEqual(expect.any(String));
    expect(reqInit.headers).toMatchObject({
      'X-Asking-Webhook-Event-Id': body.event_id,
    });
  });

  it('preserves explicit helper overrides and backfills missing hint fields', async () => {
    queuePollWebhook('poll-1', 'poll_updated', {
      title: 'renamed',
      poll_path: '/custom/poll',
      results_path: '/custom/results',
      command_hints: {
        chat_vote_short: '!vote-custom',
      },
    });
    await flushAsync();

    expect(fetch).toHaveBeenCalledTimes(1);
    const reqInit = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(reqInit.body));

    expect(body.data).toMatchObject({
      title: 'renamed',
      poll_path: '/custom/poll',
      results_path: '/custom/results',
      streamer_context: expect.objectContaining({ poll_title: 'Test poll' }),
      command_hints: {
        chat_vote_short: '!vote-custom',
        chat_results_short: '!results poll-1',
        command_aliases: {
          vote: ['/vote poll-1 <option>', '!v poll-1 <option>'],
          results: ['/results poll-1', '!r poll-1'],
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
          supports_streamer_context: true,
          supports_webhook_results_snapshot: true,
          supports_webhook_owner_snapshot: true,
          supports_owner_events: true,
        },
        contract_version: '2026-04-webhook-command-hints-v1',
        hint_locale: 'en',
        supported_hint_locales: ['en', 'en-gb', 'es'],
        hint_packs: buildAllPollWebhookHintPacks('poll-1'),
      },
    });
  });

  it('reflects poll row fields in streamer_context schedule and title', async () => {
    mockFindByPk.mockResolvedValue(
      pollRow([{ url: 'https://hooks.example.test/poll', secret: 'top-secret' }], {
        title: 'On-air poll',
        phase: 'closed',
        votingPaused: true,
        archived: false,
        selectionMode: 'multi',
        openAt: 1_700_000_000_000,
        lockAt: 1_700_000_100_000,
        revealAt: null,
        expiration: 1_700_000_200_000,
      }),
    );
    queuePollWebhook('poll-1', 'vote', { option: 'A' });
    await flushAsync();

    const reqInit = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(reqInit.body));
    expect(body.data.streamer_context).toEqual({
      poll_title: 'On-air poll',
      phase: 'closed',
      voting_paused: true,
      archived: false,
      selection_mode: 'multi',
      schedule_utc_ms: {
        open_at: 1_700_000_000_000,
        lock_at: 1_700_000_100_000,
        reveal_at: null,
        expires_at: 1_700_000_200_000,
      },
    });
  });

  it('allows partial command_aliases override while backfilling missing commands', async () => {
    queuePollWebhook('poll-1', 'poll_updated', {
      command_hints: {
        command_aliases: {
          vote: ['/vote-now poll-1 <option>'],
        },
      },
    });
    await flushAsync();

    expect(fetch).toHaveBeenCalledTimes(1);
    const reqInit = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(reqInit.body));

    expect(body.data.command_hints).toMatchObject({
      command_aliases: {
        vote: ['/vote-now poll-1 <option>'],
        results: ['/results poll-1', '!r poll-1'],
      },
    });
  });

  it('uses POLL_WEBHOOK_HINT_LOCALE for default chat hints when payload omits overrides', async () => {
    appEnvMutable.pollWebhookHintLocale = 'es';
    queuePollWebhook('poll-1', 'poll_deleted', { reason: 'owner_deleted' });
    await flushAsync();

    expect(fetch).toHaveBeenCalledTimes(1);
    const reqInit = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(reqInit.body));

    expect(body.data.command_hints).toMatchObject({
      hint_locale: 'es',
      chat_vote_short: '!votar poll-1 <opción>',
      chat_results_short: '!resultados poll-1',
      supported_hint_locales: ['en', 'en-gb', 'es'],
      hint_packs: buildAllPollWebhookHintPacks('poll-1'),
    });
    appEnvMutable.pollWebhookHintLocale = 'en';
  });

  it('allows partial capability_flags override while backfilling missing flags', async () => {
    queuePollWebhook('poll-1', 'poll_updated', {
      command_hints: {
        capability_flags: {
          supports_hint_locale: false,
        },
      },
    });
    await flushAsync();

    expect(fetch).toHaveBeenCalledTimes(1);
    const reqInit = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(reqInit.body));

    expect(body.data.command_hints).toMatchObject({
      capability_flags: {
        supports_vote_command: true,
        supports_results_command: true,
        supports_command_aliases: true,
        supports_hint_locale: false,
        supports_hint_locale_override: true,
        supports_hint_packs: true,
        supports_supported_hint_locales: true,
        supports_contract_version: true,
        supports_streamer_context: true,
        supports_webhook_results_snapshot: true,
        supports_webhook_owner_snapshot: true,
        supports_owner_events: true,
      },
    });
  });

  it('allows contract_version override for staged receiver compatibility testing', async () => {
    queuePollWebhook('poll-1', 'poll_updated', {
      command_hints: {
        contract_version: 'test-receiver-v2',
      },
    });
    await flushAsync();

    expect(fetch).toHaveBeenCalledTimes(1);
    const reqInit = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(reqInit.body));

    expect(body.data.command_hints).toMatchObject({
      contract_version: 'test-receiver-v2',
      capability_flags: {
        supports_contract_version: true,
        supports_webhook_results_snapshot: true,
        supports_webhook_owner_snapshot: true,
        supports_owner_events: true,
      },
    });
  });

  it('fetches results snapshot once when any target opts in, and attaches only to those deliveries', async () => {
    const snap = { metrics: { total_votes: 2, total_weighted_votes: 2 }, options: [] };
    mockFetchResultsSnapshot.mockResolvedValue(snap);
    mockFindByPk.mockResolvedValue(
      pollRow([
        { url: 'https://hooks.example.test/a', secret: 'top-secret' },
        { url: 'https://hooks.example.test/b', secret: 'top-secret', include_results_snapshot: true },
      ]),
    );
    queuePollWebhook('poll-1', 'poll_updated', { reason: 'x' });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));

    expect(mockFetchResultsSnapshot).toHaveBeenCalledTimes(1);
    const bodyA = JSON.parse(String((fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body));
    const bodyB = JSON.parse(String((fetch as ReturnType<typeof vi.fn>).mock.calls[1][1].body));
    expect(bodyA.data.results_snapshot).toBeUndefined();
    expect(bodyB.data.results_snapshot).toEqual(snap);
  });

  it('fetches owner snapshot once when any target opts in, and attaches only to those deliveries', async () => {
    const owner = {
      moderation_counters: {
        quarantined_votes_pending: 1,
        trust_ip_burst: { enabled: true, window_sec: 10, vote_threshold: 4 },
        trust_chat_burst: { enabled: false },
      },
      delayed_votes_pending: 0,
    };
    mockFetchOwnerSnapshot.mockResolvedValue(owner);
    mockFindByPk.mockResolvedValue(
      pollRow([
        { url: 'https://hooks.example.test/a', secret: 'top-secret' },
        { url: 'https://hooks.example.test/b', secret: 'top-secret', include_owner_snapshot: true },
      ]),
    );
    queuePollWebhook('poll-1', 'vote', { option: 'A' });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));

    expect(mockFetchOwnerSnapshot).toHaveBeenCalledTimes(1);
    expect(mockFetchResultsSnapshot).not.toHaveBeenCalled();
    const bodyA = JSON.parse(String((fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body));
    const bodyB = JSON.parse(String((fetch as ReturnType<typeof vi.fn>).mock.calls[1][1].body));
    expect(bodyA.data.owner_snapshot).toBeUndefined();
    expect(bodyB.data.owner_snapshot).toEqual(owner);
  });

  it('records live webhook delivery outcomes for admin status telemetry', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 503,
        })
        .mockRejectedValueOnce(new Error('network down')),
    );
    mockFindByPk.mockResolvedValue(
      pollRow([
        { url: 'https://hooks.example.test/ok', secret: 'top-secret-1' },
        { url: 'https://hooks.example.test/non-2xx', secret: 'top-secret-2' },
        { url: 'https://hooks.example.test/fail', secret: 'top-secret-3' },
      ]),
    );

    queuePollWebhook('poll-1', 'vote', { option: 'A' });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));

    expect(readPollWebhookDeliveryTelemetry(15)).toMatchObject({
      attempted: 3,
      delivered_ok: 1,
      delivered_non_2xx: 1,
      delivery_failed: 1,
    });
  });

  it('fetches owner events once when any target opts in, and attaches only to those deliveries', async () => {
    const ownerEvents = {
      safeguard_tags: ['trust_stack:ip_burst'],
      quarantine_recent: [{ vote_id: 'v1', reason: 'ip_burst', risk_score: 90, created_at_ms: 1, state: 'pending' }],
      moderation_actions_recent: [],
      truncated: { quarantine_recent: false, moderation_actions_recent: false },
      window_ms: 3_600_000,
    };
    mockFetchOwnerEvents.mockResolvedValue(ownerEvents);
    mockFindByPk.mockResolvedValue(
      pollRow([
        { url: 'https://hooks.example.test/a', secret: 'top-secret' },
        { url: 'https://hooks.example.test/b', secret: 'top-secret', include_owner_events: true },
      ]),
    );
    queuePollWebhook('poll-1', 'poll_updated', { reason: 'x' });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));

    expect(mockFetchOwnerEvents).toHaveBeenCalledTimes(1);
    const bodyA = JSON.parse(String((fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body));
    const bodyB = JSON.parse(String((fetch as ReturnType<typeof vi.fn>).mock.calls[1][1].body));
    expect(bodyA.data.owner_events).toBeUndefined();
    expect(bodyB.data.owner_events).toEqual(ownerEvents);
  });

  it('uses per-target hint_locale override from webhook target config', async () => {
    mockFindByPk.mockResolvedValue(
      pollRow([{ url: 'https://hooks.example.test/poll', secret: 'top-secret', hint_locale: 'es' }]),
    );
    queuePollWebhook('poll-1', 'poll_updated', { title: 'renamed' });
    await flushAsync();

    expect(fetch).toHaveBeenCalledTimes(1);
    const reqInit = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(reqInit.body));

    expect(body.data.command_hints).toMatchObject({
      hint_locale: 'es',
      chat_vote_short: '!votar poll-1 <opción>',
      chat_results_short: '!resultados poll-1',
    });
  });
});
