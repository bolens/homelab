import type { VotePollBody } from '@asking-ng/contracts/poll';
import { UniqueConstraintError } from 'sequelize';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AppRequest } from '../../types/http';
import { voteOnPollService } from './voteOnPoll.service';

const {
  mockFindPollByIdOrSlug,
  mockCountRecentVotesForSourceIp,
  mockCountRecentVotesForSourceIpWindowSeconds,
  mockCountRecentVotesForChatChannel,
  mockCountRecentVotesForChatChannelWindowSeconds,
  mockCountLimitIpBallotsForPoll,
  mockFindVoteByIdempotencyKey,
  mockFindVotesByIdempotencyKey,
  mockCountVotesByPollAndUser,
  mockCountVotesByPollAndPlatformIdentity,
  mockCreateVoteRow,
  mockCreateVoteRowInTransaction,
  mockUpsertPlatformIdentityMapping,
  mockGetVoteGeoEnabled,
  mockPollEmbedReadAllowed,
  mockReadEmbedReadTokenFromRequest,
  mockPollPhaseScheduleFromRow,
  mockResolveEffectivePollPhase,
  mockNotifyPollLive,
  mockQueuePollWebhook,
  mockValidateWriteInText,
  mockTransaction,
  mockRandomId,
  mockCheckMonthlyVoteQuotaForCreator,
  appEnvMutable,
} = vi.hoisted(() => {
  const appEnvMutable = {
    voteIpHashSalt: 'test-salt',
    chatChannelVoteMaxPerMin: 120,
    trustIpBurstVoteThreshold: 0,
    trustIpBurstWindowSec: 10,
    trustChatBurstVoteThreshold: 0,
    trustChatBurstWindowSec: 10,
    billingEnforceLimits: false,
    publicSiteUrl: '',
    corsOrigins: [],
    pollWebhookHintLocale: 'en' as 'en' | 'en-gb' | 'es',
  };
  return {
    mockFindPollByIdOrSlug: vi.fn(),
    mockCountRecentVotesForSourceIp: vi.fn(),
    mockCountRecentVotesForSourceIpWindowSeconds: vi.fn(),
    mockCountRecentVotesForChatChannel: vi.fn(),
    mockCountRecentVotesForChatChannelWindowSeconds: vi.fn(),
    mockCountLimitIpBallotsForPoll: vi.fn(),
    mockFindVoteByIdempotencyKey: vi.fn(),
    mockFindVotesByIdempotencyKey: vi.fn(),
    mockCountVotesByPollAndUser: vi.fn(),
    mockCountVotesByPollAndPlatformIdentity: vi.fn(),
    mockCreateVoteRow: vi.fn(),
    mockCreateVoteRowInTransaction: vi.fn(),
    mockUpsertPlatformIdentityMapping: vi.fn(),
    mockGetVoteGeoEnabled: vi.fn(),
    mockPollEmbedReadAllowed: vi.fn(),
    mockReadEmbedReadTokenFromRequest: vi.fn(),
    mockPollPhaseScheduleFromRow: vi.fn(),
    mockResolveEffectivePollPhase: vi.fn(),
    mockNotifyPollLive: vi.fn(),
    mockQueuePollWebhook: vi.fn(),
    mockValidateWriteInText: vi.fn(),
    mockTransaction: vi.fn(),
    mockRandomId: vi.fn(),
    mockCheckMonthlyVoteQuotaForCreator: vi.fn(),
    appEnvMutable,
  };
});

vi.mock('../../lib/env', () => ({
  get appEnv() {
    return appEnvMutable;
  },
}));

vi.mock('../../lib/billingVoteQuota', () => ({
  checkMonthlyVoteQuotaForCreator: mockCheckMonthlyVoteQuotaForCreator,
}));

vi.mock('../../lib/appSettings', () => ({
  getVoteGeoEnabled: mockGetVoteGeoEnabled,
}));

vi.mock('../../lib/embedReadToken', () => ({
  pollEmbedReadAllowed: mockPollEmbedReadAllowed,
  readEmbedReadTokenFromRequest: mockReadEmbedReadTokenFromRequest,
}));

vi.mock('../../lib/pollPhaseSchedule', () => ({
  pollPhaseScheduleFromRow: mockPollPhaseScheduleFromRow,
  resolveEffectivePollPhase: mockResolveEffectivePollPhase,
}));

vi.mock('../../lib/pollLive', () => ({
  notifyPollLive: mockNotifyPollLive,
}));

vi.mock('../../lib/pollWebhooks', () => ({
  queuePollWebhook: mockQueuePollWebhook,
}));

vi.mock('../../lib/writeInHygiene', () => ({
  validateWriteInText: mockValidateWriteInText,
}));

vi.mock('../../connections', () => ({
  default: {
    transaction: mockTransaction,
  },
}));

vi.mock('../../helpers/randomId', () => ({
  default: mockRandomId,
}));

vi.mock('./voteOnPoll.repository', () => ({
  findPollByIdOrSlug: mockFindPollByIdOrSlug,
  countRecentVotesForSourceIp: mockCountRecentVotesForSourceIp,
  countRecentVotesForSourceIpWindowSeconds: mockCountRecentVotesForSourceIpWindowSeconds,
  countRecentVotesForChatChannel: mockCountRecentVotesForChatChannel,
  countRecentVotesForChatChannelWindowSeconds: mockCountRecentVotesForChatChannelWindowSeconds,
  countLimitIpBallotsForPoll: mockCountLimitIpBallotsForPoll,
  findVoteByIdempotencyKey: mockFindVoteByIdempotencyKey,
  findVotesByIdempotencyKey: mockFindVotesByIdempotencyKey,
  countVotesByPollAndUser: mockCountVotesByPollAndUser,
  countVotesByPollAndPlatformIdentity: mockCountVotesByPollAndPlatformIdentity,
  createVoteRow: mockCreateVoteRow,
  createVoteRowInTransaction: mockCreateVoteRowInTransaction,
}));

vi.mock('../../lib/pollPlatformIdentity', () => ({
  upsertPlatformIdentityMapping: mockUpsertPlatformIdentityMapping,
}));

type PollFields = Record<string, unknown>;

function pollRow(fields: Partial<PollFields> = {}) {
  const base: PollFields = {
    id: 'poll-1',
    embedReadTokenHash: null,
    creatorUserId: null,
    archived: false,
    phase: 'open',
    votingPaused: false,
    options: ['A', 'B', 'C'],
    selectionMode: 'single',
    boostedVotingEnabled: false,
    maxBoostWeight: 3,
    voteFrictionTier: 'open',
    softThrottleMaxVotesPerMin: 30,
    powDifficulty: 4,
    allowWriteIn: false,
    writeInMaxLength: 80,
    writeInBlocklist: [],
    writeInProfanityFilter: true,
    expiration: Date.now() + 86_400_000,
    limit_ip: false,
    voteEligibility: 'anonymous',
  };
  const merged = { ...base, ...fields };
  return { get: (k: string) => merged[k] };
}

function req(overrides: Partial<AppRequest> = {}): AppRequest {
  return {
    ip: '203.0.113.7',
    user: undefined,
    headers: {},
    secure: false,
    ...overrides,
  } as AppRequest;
}

describe('voteOnPollService (multi-select)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appEnvMutable.trustIpBurstVoteThreshold = 0;
    appEnvMutable.trustIpBurstWindowSec = 10;
    appEnvMutable.trustChatBurstVoteThreshold = 0;
    appEnvMutable.trustChatBurstWindowSec = 10;
    appEnvMutable.billingEnforceLimits = false;
    mockCheckMonthlyVoteQuotaForCreator.mockResolvedValue({ ok: true });
    mockPollEmbedReadAllowed.mockReturnValue(true);
    mockReadEmbedReadTokenFromRequest.mockReturnValue('');
    mockPollPhaseScheduleFromRow.mockReturnValue({});
    mockResolveEffectivePollPhase.mockReturnValue('open');
    mockGetVoteGeoEnabled.mockResolvedValue(false);
    mockCountRecentVotesForSourceIp.mockResolvedValue(0);
    mockCountRecentVotesForSourceIpWindowSeconds.mockResolvedValue(0);
    mockCountRecentVotesForChatChannel.mockResolvedValue(0);
    mockCountRecentVotesForChatChannelWindowSeconds.mockResolvedValue(0);
    mockCountLimitIpBallotsForPoll.mockResolvedValue(0);
    mockFindVoteByIdempotencyKey.mockResolvedValue(null);
    mockFindVotesByIdempotencyKey.mockResolvedValue([]);
    mockCountVotesByPollAndUser.mockResolvedValue(0);
    mockCountVotesByPollAndPlatformIdentity.mockResolvedValue(0);
    mockRandomId.mockReturnValue('vote-rand-id');
    mockTransaction.mockImplementation(async (fn: (t: unknown) => Promise<unknown>) => fn({}));
    mockValidateWriteInText.mockReturnValue({ ok: true as const });
    mockCreateVoteRowInTransaction.mockImplementation(async (payload: Record<string, unknown>) => ({
      payload,
    }));
    mockCreateVoteRow.mockResolvedValue({ kind: 'single-vote' });
  });

  it('records a multi ballot as one row per option (sorted indices)', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({ selectionMode: 'multi', boostedVotingEnabled: false, limit_ip: false }),
    );

    const body = { option_indices: [2, 0] } as VotePollBody;
    const result = await voteOnPollService(req(), 'poll-1', body);

    expect(result.kind).toBe('ok');
    if (result.kind !== 'ok') return;
    expect(result.optionIndices).toEqual([0, 2]);
    expect(mockCreateVoteRowInTransaction).toHaveBeenCalledTimes(2);
    expect(mockCreateVoteRowInTransaction.mock.calls[0][0]).toMatchObject({
      option: 'A',
      weight: 1,
      pollId: 'poll-1',
    });
    expect(mockCreateVoteRowInTransaction.mock.calls[1][0]).toMatchObject({
      option: 'C',
      weight: 1,
    });
    expect(mockNotifyPollLive).toHaveBeenCalledWith('poll-1', { type: 'update' });
    expect(mockQueuePollWebhook).toHaveBeenCalledWith(
      'poll-1',
      'vote',
      expect.objectContaining({
        selection_mode: 'multi',
        option_indices: [0, 2],
        options: ['A', 'C'],
        vote_eligibility: 'anonymous',
        poll_url: expect.stringContaining('/poll-1'),
        results_url: expect.stringContaining('/poll-1/results'),
        command_hints: expect.objectContaining({
          chat_vote_short: '!vote poll-1 <option>',
          chat_results_short: '!results poll-1',
        }),
        moderation: { quarantined: false },
      }),
    );
  });

  it('uses deterministic vote ids when limit_ip is on', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({ selectionMode: 'multi', limit_ip: true, id: 'abc123' }),
    );

    await voteOnPollService(req({ ip: '198.51.100.2' } as AppRequest), 'abc123', {
      option_indices: [1],
    } as VotePollBody);

    expect(mockCreateVoteRowInTransaction).toHaveBeenCalledWith(
      expect.objectContaining({
        id: '198.51.100.2-abc123-1',
        option: 'B',
      }),
      expect.anything(),
    );
  });

  it('returns vote_shape_mismatch when multi poll receives only option', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ selectionMode: 'multi' }));
    const r = await voteOnPollService(req(), 'poll-1', { option: 'A' } as VotePollBody);
    expect(r.kind).toBe('vote_shape_mismatch');
  });

  it('returns vote_shape_mismatch when single poll receives option_indices', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ selectionMode: 'single' }));
    const r = await voteOnPollService(req(), 'poll-1', { option_indices: [0] } as VotePollBody);
    expect(r.kind).toBe('vote_shape_mismatch');
  });

  it('returns invalid_option_indices for out-of-range indices', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ selectionMode: 'multi' }));
    const r = await voteOnPollService(req(), 'poll-1', { option_indices: [0, 99] } as VotePollBody);
    expect(r.kind).toBe('invalid_option_indices');
  });

  it('returns idempotent_replay with ballot rows for multi', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ selectionMode: 'multi' }));
    const prior = [{ id: 'v1' }, { id: 'v2' }];
    mockFindVotesByIdempotencyKey.mockResolvedValue(prior);

    const r = await voteOnPollService(req(), 'poll-1', {
      option_indices: [0, 1],
      idempotency_key: 'chat-1',
    } as VotePollBody);

    expect(r.kind).toBe('idempotent_replay');
    if (r.kind !== 'idempotent_replay') return;
    expect(r.vote).toBe(prior[0]);
    expect(r.ballotVotes).toEqual(prior);
    expect(mockTransaction).not.toHaveBeenCalled();
  });

  it('returns duplicate_vote when limit_ip ballot already exists', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ selectionMode: 'multi', limit_ip: true }));
    mockCountLimitIpBallotsForPoll.mockResolvedValue(1);

    const r = await voteOnPollService(req(), 'poll-1', { option_indices: [0] } as VotePollBody);
    expect(r.kind).toBe('duplicate_vote');
    expect(mockTransaction).not.toHaveBeenCalled();
  });

  it('rejects boost_weight on multi ballots (non-trivial weight)', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ selectionMode: 'multi' }));
    const r = await voteOnPollService(req(), 'poll-1', {
      option_indices: [0],
      boost_weight: 2,
    } as VotePollBody);
    expect(r.kind).toBe('boost_weight_disabled');
  });

  it('maps unique constraint errors to duplicate_vote', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ selectionMode: 'multi' }));
    mockCreateVoteRowInTransaction.mockRejectedValue(new UniqueConstraintError({} as never));

    const r = await voteOnPollService(req(), 'poll-1', { option_indices: [0, 1] } as VotePollBody);
    expect(r.kind).toBe('duplicate_vote');
  });
});

describe('voteOnPollService (single-choice)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appEnvMutable.trustIpBurstVoteThreshold = 0;
    appEnvMutable.trustIpBurstWindowSec = 10;
    appEnvMutable.trustChatBurstVoteThreshold = 0;
    appEnvMutable.trustChatBurstWindowSec = 10;
    appEnvMutable.billingEnforceLimits = false;
    mockCheckMonthlyVoteQuotaForCreator.mockResolvedValue({ ok: true });
    mockPollEmbedReadAllowed.mockReturnValue(true);
    mockReadEmbedReadTokenFromRequest.mockReturnValue('');
    mockPollPhaseScheduleFromRow.mockReturnValue({});
    mockResolveEffectivePollPhase.mockReturnValue('open');
    mockGetVoteGeoEnabled.mockResolvedValue(false);
    mockCountRecentVotesForSourceIp.mockResolvedValue(0);
    mockCountRecentVotesForSourceIpWindowSeconds.mockResolvedValue(0);
    mockCountRecentVotesForChatChannel.mockResolvedValue(0);
    mockCountRecentVotesForChatChannelWindowSeconds.mockResolvedValue(0);
    mockCountLimitIpBallotsForPoll.mockResolvedValue(0);
    mockFindVoteByIdempotencyKey.mockResolvedValue(null);
    mockFindVotesByIdempotencyKey.mockResolvedValue([]);
    mockCountVotesByPollAndUser.mockResolvedValue(0);
    mockCountVotesByPollAndPlatformIdentity.mockResolvedValue(0);
    mockRandomId.mockReturnValue('single-rand');
    mockValidateWriteInText.mockReturnValue({ ok: true as const });
    mockCreateVoteRow.mockResolvedValue({ row: 'ok' });
  });

  it('returns idempotent_replay for duplicate idempotency key', async () => {
    const existing = { id: 'existing-vote' };
    mockFindVoteByIdempotencyKey.mockResolvedValue(existing);
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ selectionMode: 'single' }));

    const r = await voteOnPollService(req(), 'poll-1', {
      option_index: 0,
      idempotency_key: 'dup',
    } as VotePollBody);

    expect(r.kind).toBe('idempotent_replay');
    if (r.kind !== 'idempotent_replay') return;
    expect(r.vote).toBe(existing);
    expect(mockCreateVoteRow).not.toHaveBeenCalled();
  });
});

describe('voteOnPollService (vote_eligibility=account)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appEnvMutable.trustIpBurstVoteThreshold = 0;
    appEnvMutable.trustIpBurstWindowSec = 10;
    appEnvMutable.trustChatBurstVoteThreshold = 0;
    appEnvMutable.trustChatBurstWindowSec = 10;
    appEnvMutable.billingEnforceLimits = false;
    mockCheckMonthlyVoteQuotaForCreator.mockResolvedValue({ ok: true });
    mockPollEmbedReadAllowed.mockReturnValue(true);
    mockReadEmbedReadTokenFromRequest.mockReturnValue('');
    mockPollPhaseScheduleFromRow.mockReturnValue({});
    mockResolveEffectivePollPhase.mockReturnValue('open');
    mockGetVoteGeoEnabled.mockResolvedValue(false);
    mockCountRecentVotesForSourceIp.mockResolvedValue(0);
    mockCountRecentVotesForSourceIpWindowSeconds.mockResolvedValue(0);
    mockCountRecentVotesForChatChannel.mockResolvedValue(0);
    mockCountRecentVotesForChatChannelWindowSeconds.mockResolvedValue(0);
    mockCountLimitIpBallotsForPoll.mockResolvedValue(0);
    mockCountVotesByPollAndUser.mockResolvedValue(0);
    mockCountVotesByPollAndPlatformIdentity.mockResolvedValue(0);
    mockFindVoteByIdempotencyKey.mockResolvedValue(null);
    mockFindVotesByIdempotencyKey.mockResolvedValue([]);
    mockRandomId.mockReturnValue('acc-rand');
    mockValidateWriteInText.mockReturnValue({ ok: true as const });
    mockCreateVoteRow.mockResolvedValue({ row: 'ok' });
  });

  it('returns vote_requires_sign_in without JWT', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ voteEligibility: 'account' }));
    const r = await voteOnPollService(req(), 'poll-1', { option_index: 0 } as VotePollBody);
    expect(r.kind).toBe('vote_requires_sign_in');
    expect(mockCountVotesByPollAndUser).not.toHaveBeenCalled();
  });

  it('returns duplicate_vote when the user already has votes on this poll', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ voteEligibility: 'account' }));
    mockCountVotesByPollAndUser.mockResolvedValue(1);
    const r = await voteOnPollService(
      req({ user: { id: 42, homelab-user: 'u42', role: 'user' } }),
      'poll-1',
      { option_index: 0 } as VotePollBody,
    );
    expect(r.kind).toBe('duplicate_vote');
    expect(mockCountLimitIpBallotsForPoll).not.toHaveBeenCalled();
  });

  it('skips limit_ip duplicate check for account polls', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({ voteEligibility: 'account', limit_ip: true }),
    );
    mockCountLimitIpBallotsForPoll.mockResolvedValue(1);
    const r = await voteOnPollService(
      req({ user: { id: 7, homelab-user: 'u7', role: 'user' } }),
      'poll-1',
      { option_index: 0 } as VotePollBody,
    );
    expect(r.kind).toBe('ok');
    expect(mockCountLimitIpBallotsForPoll).not.toHaveBeenCalled();
  });
});

describe('voteOnPollService (vote_eligibility=platform_linked)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appEnvMutable.trustIpBurstVoteThreshold = 0;
    appEnvMutable.trustIpBurstWindowSec = 10;
    appEnvMutable.trustChatBurstVoteThreshold = 0;
    appEnvMutable.trustChatBurstWindowSec = 10;
    appEnvMutable.billingEnforceLimits = false;
    mockCheckMonthlyVoteQuotaForCreator.mockResolvedValue({ ok: true });
    mockPollEmbedReadAllowed.mockReturnValue(true);
    mockReadEmbedReadTokenFromRequest.mockReturnValue('');
    mockPollPhaseScheduleFromRow.mockReturnValue({});
    mockResolveEffectivePollPhase.mockReturnValue('open');
    mockGetVoteGeoEnabled.mockResolvedValue(false);
    mockCountRecentVotesForSourceIp.mockResolvedValue(0);
    mockCountRecentVotesForSourceIpWindowSeconds.mockResolvedValue(0);
    mockCountRecentVotesForChatChannel.mockResolvedValue(0);
    mockCountRecentVotesForChatChannelWindowSeconds.mockResolvedValue(0);
    mockCountLimitIpBallotsForPoll.mockResolvedValue(0);
    mockCountVotesByPollAndUser.mockResolvedValue(0);
    mockCountVotesByPollAndPlatformIdentity.mockResolvedValue(0);
    mockFindVoteByIdempotencyKey.mockResolvedValue(null);
    mockFindVotesByIdempotencyKey.mockResolvedValue([]);
    mockRandomId.mockReturnValue('platform-rand');
    mockValidateWriteInText.mockReturnValue({ ok: true as const });
    mockCreateVoteRow.mockResolvedValue({ row: 'ok' });
  });

  it('requires provider configuration on platform-linked poll', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(pollRow({ voteEligibility: 'platform_linked' }));
    const r = await voteOnPollService(req({ user: { id: 42 } as never }), 'poll-1', {
      option_index: 0,
    } as VotePollBody);
    expect(r.kind).toBe('platform_identity_not_configured');
  });

  it('requires platform subject header on platform-linked poll', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({ voteEligibility: 'platform_linked', platformIdentityProvider: 'twitch' }),
    );
    const r = await voteOnPollService(
      req({ user: { id: 42 } as never, headers: {} as never }),
      'poll-1',
      { option_index: 0 } as VotePollBody,
    );
    expect(r.kind).toBe('platform_identity_required');
  });

  it('rejects provider mismatch for platform-linked poll', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({ voteEligibility: 'platform_linked', platformIdentityProvider: 'twitch' }),
    );
    const r = await voteOnPollService(
      req({
        user: { id: 42 } as never,
        headers: { 'x-platform-subject': 'user123', 'x-platform-provider': 'youtube' } as never,
      }),
      'poll-1',
      { option_index: 0 } as VotePollBody,
    );
    expect(r.kind).toBe('platform_identity_provider_mismatch');
    if (r.kind !== 'platform_identity_provider_mismatch') return;
    expect(r.expectedProvider).toBe('twitch');
    expect(r.receivedProvider).toBe('youtube');
  });

  it('deduplicates by provider+subject identity hash', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({ voteEligibility: 'platform_linked', platformIdentityProvider: 'twitch' }),
    );
    mockCountVotesByPollAndPlatformIdentity.mockResolvedValue(1);
    const r = await voteOnPollService(
      req({
        user: { id: 42, homelab-user: 'u42', role: 'user' } as never,
        headers: { 'x-platform-subject': 'user123', 'x-platform-provider': 'twitch' } as never,
      }),
      'poll-1',
      { option_index: 0 } as VotePollBody,
    );
    expect(r.kind).toBe('duplicate_vote');
  });

  it('accepts vote when provider and subject headers match configured provider', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({ voteEligibility: 'platform_linked', platformIdentityProvider: 'twitch' }),
    );
    const r = await voteOnPollService(
      req({
        user: { id: 42, homelab-user: 'u42', role: 'user' } as never,
        headers: { 'x-platform-subject': 'user123', 'x-platform-provider': 'twitch' } as never,
      }),
      'poll-1',
      { option_index: 0 } as VotePollBody,
    );
    expect(r.kind).toBe('ok');
    expect(mockUpsertPlatformIdentityMapping).toHaveBeenCalledTimes(1);
    expect(mockQueuePollWebhook).toHaveBeenCalledWith(
      'poll-1',
      'vote',
      expect.objectContaining({
        vote_eligibility: 'platform_linked',
        voter_user_id: 42,
        poll_url: expect.stringContaining('/poll-1'),
        results_url: expect.stringContaining('/poll-1/results'),
        command_hints: expect.objectContaining({
          chat_vote_short: '!vote poll-1 <option>',
          chat_results_short: '!results poll-1',
        }),
        platform_identity_provider: 'twitch',
        platform_identity_subject_hash: expect.any(String),
        moderation: { quarantined: false },
      }),
    );
  });
});

describe('voteOnPollService (trust ip burst)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appEnvMutable.trustIpBurstVoteThreshold = 4;
    appEnvMutable.trustIpBurstWindowSec = 10;
    appEnvMutable.trustChatBurstVoteThreshold = 0;
    appEnvMutable.trustChatBurstWindowSec = 10;
    appEnvMutable.billingEnforceLimits = false;
    mockCheckMonthlyVoteQuotaForCreator.mockResolvedValue({ ok: true });
    mockPollEmbedReadAllowed.mockReturnValue(true);
    mockReadEmbedReadTokenFromRequest.mockReturnValue('');
    mockPollPhaseScheduleFromRow.mockReturnValue({});
    mockResolveEffectivePollPhase.mockReturnValue('open');
    mockGetVoteGeoEnabled.mockResolvedValue(false);
    mockCountRecentVotesForSourceIp.mockResolvedValue(0);
    mockCountRecentVotesForSourceIpWindowSeconds.mockResolvedValue(4);
    mockCountRecentVotesForChatChannel.mockResolvedValue(0);
    mockCountRecentVotesForChatChannelWindowSeconds.mockResolvedValue(0);
    mockCountLimitIpBallotsForPoll.mockResolvedValue(0);
    mockFindVoteByIdempotencyKey.mockResolvedValue(null);
    mockFindVotesByIdempotencyKey.mockResolvedValue([]);
    mockCountVotesByPollAndUser.mockResolvedValue(0);
    mockCountVotesByPollAndPlatformIdentity.mockResolvedValue(0);
    mockRandomId.mockReturnValue('burst-rand');
    mockValidateWriteInText.mockReturnValue({ ok: true as const });
    mockCreateVoteRow.mockResolvedValue({ row: 'ok' });
  });

  it('quarantines with ip_burst and trust score when burst threshold is exceeded', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({ selectionMode: 'single', voteFrictionTier: 'open' }),
    );

    const r = await voteOnPollService(req(), 'poll-1', { option_index: 0 } as VotePollBody);

    expect(r.kind).toBe('ok');
    if (r.kind !== 'ok') return;
    expect(r.moderation?.quarantined).toBe(true);
    expect(r.moderation?.reason).toBe('ip_burst');
    expect(r.moderation?.trust_risk_score).toBeGreaterThanOrEqual(28);
    expect(mockCreateVoteRow).toHaveBeenCalledWith(
      expect.objectContaining({
        isQuarantined: true,
        quarantineReason: 'ip_burst',
        trustRiskScore: expect.any(Number),
      }),
    );
  });

  it('uses soft_plus_burst when soft throttle and burst both trigger', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({
        selectionMode: 'single',
        voteFrictionTier: 'soft_throttle',
        softThrottleMaxVotesPerMin: 2,
      }),
    );
    mockCountRecentVotesForSourceIp.mockResolvedValue(2);
    mockCountRecentVotesForSourceIpWindowSeconds.mockResolvedValue(4);

    const r = await voteOnPollService(req(), 'poll-1', { option_index: 0 } as VotePollBody);

    expect(r.kind).toBe('ok');
    if (r.kind !== 'ok') return;
    expect(r.moderation?.reason).toBe('soft_plus_burst');
  });
});

describe('voteOnPollService (trust chat burst)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appEnvMutable.trustIpBurstVoteThreshold = 0;
    appEnvMutable.trustIpBurstWindowSec = 10;
    appEnvMutable.trustChatBurstVoteThreshold = 3;
    appEnvMutable.trustChatBurstWindowSec = 10;
    appEnvMutable.billingEnforceLimits = false;
    mockCheckMonthlyVoteQuotaForCreator.mockResolvedValue({ ok: true });
    mockPollEmbedReadAllowed.mockReturnValue(true);
    mockReadEmbedReadTokenFromRequest.mockReturnValue('');
    mockPollPhaseScheduleFromRow.mockReturnValue({});
    mockResolveEffectivePollPhase.mockReturnValue('open');
    mockGetVoteGeoEnabled.mockResolvedValue(false);
    mockCountRecentVotesForSourceIp.mockResolvedValue(0);
    mockCountRecentVotesForSourceIpWindowSeconds.mockResolvedValue(0);
    mockCountRecentVotesForChatChannel.mockResolvedValue(0);
    mockCountRecentVotesForChatChannelWindowSeconds.mockResolvedValue(3);
    mockCountLimitIpBallotsForPoll.mockResolvedValue(0);
    mockFindVoteByIdempotencyKey.mockResolvedValue(null);
    mockFindVotesByIdempotencyKey.mockResolvedValue([]);
    mockCountVotesByPollAndUser.mockResolvedValue(0);
    mockCountVotesByPollAndPlatformIdentity.mockResolvedValue(0);
    mockRandomId.mockReturnValue('chat-burst-rand');
    mockValidateWriteInText.mockReturnValue({ ok: true as const });
    mockCreateVoteRow.mockResolvedValue({ row: 'ok' });
  });

  it('quarantines with chat_burst when chat channel burst threshold is exceeded', async () => {
    mockFindPollByIdOrSlug.mockResolvedValue(
      pollRow({ selectionMode: 'single', voteFrictionTier: 'open' }),
    );

    const r = await voteOnPollService(req(), 'poll-1', {
      option_index: 0,
      chat_channel_id: 'twitch-chan-1',
    } as VotePollBody);

    expect(r.kind).toBe('ok');
    if (r.kind !== 'ok') return;
    expect(r.moderation?.reason).toBe('chat_burst');
    expect(mockCreateVoteRow).toHaveBeenCalledWith(
      expect.objectContaining({
        isQuarantined: true,
        quarantineReason: 'chat_burst',
      }),
    );
  });
});
