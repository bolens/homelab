import type { AppRequest } from '../../types/http';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getPollView } from './getPoll.service';

const {
  mockFindByPk,
  mockIncrement,
  mockUpdate,
  mockPollEmbedViewAllowed,
  mockReadEmbedReadTokenFromRequest,
  mockPollPhaseScheduleFromRow,
  mockResolveEffectivePollPhase,
  mockGetPollVoteAnalytics,
} = vi.hoisted(() => ({
  mockFindByPk: vi.fn(),
  mockIncrement: vi.fn(),
  mockUpdate: vi.fn().mockResolvedValue([1]),
  mockPollEmbedViewAllowed: vi.fn(),
  mockReadEmbedReadTokenFromRequest: vi.fn(),
  mockPollPhaseScheduleFromRow: vi.fn(),
  mockResolveEffectivePollPhase: vi.fn(),
  mockGetPollVoteAnalytics: vi.fn(),
}));

vi.mock('../../model/Poll', () => ({
  default: {
    findByPk: mockFindByPk,
    increment: mockIncrement,
    update: mockUpdate,
  },
}));

vi.mock('../../lib/embedReadToken', () => ({
  pollEmbedViewAllowed: mockPollEmbedViewAllowed,
  readEmbedReadTokenFromRequest: mockReadEmbedReadTokenFromRequest,
}));

vi.mock('../../lib/pollPhaseSchedule', () => ({
  pollPhaseScheduleFromRow: mockPollPhaseScheduleFromRow,
  resolveEffectivePollPhase: mockResolveEffectivePollPhase,
}));

vi.mock('./getPoll.repository', () => ({
  getPollVoteAnalytics: mockGetPollVoteAnalytics,
}));

const { mockTrustIpBurstOwnerSummary, mockTrustChatBurstOwnerSummary, mockTrustStackSafeguardTags } =
  vi.hoisted(() => {
    const mockTrustIpBurstOwnerSummary = vi.fn(() => ({ enabled: false as const }));
    const mockTrustChatBurstOwnerSummary = vi.fn(() => ({ enabled: false as const }));
    const mockTrustStackSafeguardTags = vi.fn(() => {
      const tags: string[] = [];
      if (mockTrustIpBurstOwnerSummary().enabled) tags.push('trust_stack:ip_burst');
      if (mockTrustChatBurstOwnerSummary().enabled) tags.push('trust_stack:chat_burst');
      return tags;
    });
    return { mockTrustIpBurstOwnerSummary, mockTrustChatBurstOwnerSummary, mockTrustStackSafeguardTags };
  });

vi.mock('../../lib/trustStackSignals', () => ({
  trustIpBurstOwnerSummary: mockTrustIpBurstOwnerSummary,
  trustChatBurstOwnerSummary: mockTrustChatBurstOwnerSummary,
  trustStackSafeguardTags: mockTrustStackSafeguardTags,
}));

type PollFieldMap = Record<string, unknown>;

function buildPoll(fields: PollFieldMap): { get: (key: string) => unknown } {
  return {
    get: (key: string) => fields[key],
  };
}

function buildReq(userId?: number, role?: string): AppRequest {
  return {
    user: userId != null ? { id: userId, role } : undefined,
  } as AppRequest;
}

function basePollFields(overrides: PollFieldMap = {}): PollFieldMap {
  return {
    id: 'poll-1',
    title: 'Poll title',
    options: ['A', 'B'],
    createdAt: new Date('2026-01-01T00:00:00.000Z'),
    expiration: Date.now() + 100_000,
    archived: false,
    phase: 'open',
    votingPaused: false,
    pauseMessage: null,
    impressionCount: 10,
    showNotes: 'secret note',
    embedReadTokenHash: 'hash',
    creatorUserId: 42,
    boostedVotingEnabled: true,
    showUnweightedValues: true,
    maxBoostWeight: 3,
    runOfShowKey: null,
    runOfShowOrder: null,
    vanitySlug: null,
    nextPollId: null,
    autoAdvanceOnClose: false,
    voteFrictionTier: 'soft_throttle',
    softThrottleMaxVotesPerMin: 30,
    powDifficulty: 4,
    allowWriteIn: true,
    writeInMaxLength: 80,
    writeInBlocklist: ['x'],
    writeInProfanityFilter: true,
    resultsDelaySeconds: 60,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockTrustIpBurstOwnerSummary.mockReturnValue({ enabled: false });
  mockTrustChatBurstOwnerSummary.mockReturnValue({ enabled: false });
  mockReadEmbedReadTokenFromRequest.mockReturnValue('token');
  mockPollEmbedViewAllowed.mockReturnValue(true);
  mockPollPhaseScheduleFromRow.mockReturnValue(null);
  mockResolveEffectivePollPhase.mockReturnValue('open');
  mockGetPollVoteAnalytics.mockResolvedValue({
    voteData: [
      { option: 'A', vote_count: 4, weighted_vote_count: 6 },
      { option: 'B', vote_count: 2, weighted_vote_count: 2 },
    ],
    metricsRow: {
      total_votes: 6,
      total_weighted_votes: 8,
      votes_last_5m: 3,
      first_vote_at: new Date('2026-01-01T00:01:00.000Z'),
    },
    peakHourRow: { peak_hour_utc: 0, peak_hour_votes: 4 },
    peakDowRow: { peak_dow_utc: 4, peak_dow_votes: 4 },
    hourBins: [{ hour_utc: 0, vote_count: 6 }],
    dowBins: [{ dow_utc: 4, vote_count: 6 }],
    rateCountersRow: {
      votes_last_1m: 2,
      unique_ip_hashes_last_1m: 2,
      unique_accounts_last_1m: 1,
      top_ip_votes_last_1m: 2,
      quarantined_votes_pending: 5,
    },
    delayedVotesPending: 7,
  });
});

describe('getPollView', () => {
  it('returns not_found when poll does not exist', async () => {
    mockFindByPk.mockResolvedValue(null);

    const result = await getPollView(buildReq(), 'missing');

    expect(result).toEqual({ kind: 'not_found' });
  });

  it('returns forbidden_embed_token when embed token is required', async () => {
    mockFindByPk.mockResolvedValue(buildPoll(basePollFields()));
    mockPollEmbedViewAllowed.mockReturnValue(false);

    const result = await getPollView(buildReq(), 'poll-1');

    expect(result).toEqual({ kind: 'forbidden_embed_token' });
    expect(mockIncrement).not.toHaveBeenCalled();
  });

  it('returns delayed results for non-owner viewers', async () => {
    mockFindByPk.mockResolvedValue(buildPoll(basePollFields()));

    const result = await getPollView(buildReq(100), 'poll-1');

    expect(result.kind).toBe('ok');
    if (result.kind !== 'ok') return;
    expect(result.data.live_results_are_delayed).toBe(true);
    expect(result.data.delayed_votes_pending).toBe(7);
    expect(result.data.moderation_counters).toBeUndefined();
    expect(mockGetPollVoteAnalytics).toHaveBeenCalledWith(
      expect.objectContaining({
        pollId: 'poll-1',
        liveResultsAreDelayed: true,
        youOwnThisPoll: false,
      }),
    );
  });

  it('includes moderation counters for poll owner', async () => {
    mockFindByPk.mockResolvedValue(buildPoll(basePollFields()));

    const result = await getPollView(buildReq(42), 'poll-1');

    expect(result.kind).toBe('ok');
    if (result.kind !== 'ok') return;
    expect(result.data.live_results_are_delayed).toBe(false);
    expect(result.data.show_notes).toBe('secret note');
    expect(result.data.moderation_counters).toEqual({
      votes_last_1m: 2,
      unique_ip_hashes_last_1m: 2,
      unique_accounts_last_1m: 1,
      top_ip_votes_last_1m: 2,
      quarantined_votes_pending: 5,
      trust_ip_burst: { enabled: false },
      trust_chat_burst: { enabled: false },
    });
    expect(mockGetPollVoteAnalytics).toHaveBeenCalledWith(
      expect.objectContaining({
        pollId: 'poll-1',
        liveResultsAreDelayed: false,
        youOwnThisPoll: true,
      }),
    );
  });

  it('includes private show_notes for mod viewers', async () => {
    mockFindByPk.mockResolvedValue(buildPoll(basePollFields()));

    const result = await getPollView(buildReq(7, 'mod'), 'poll-1');

    expect(result.kind).toBe('ok');
    if (result.kind !== 'ok') return;
    expect(result.data.show_notes).toBe('secret note');
    expect(result.data.moderation_counters).toBeUndefined();
  });

  it('includes trust_ip_burst summary when stack enables burst quarantine', async () => {
    mockTrustIpBurstOwnerSummary.mockReturnValue({
      enabled: true,
      window_sec: 10,
      vote_threshold: 6,
    });
    mockFindByPk.mockResolvedValue(buildPoll(basePollFields()));

    const result = await getPollView(buildReq(42), 'poll-1');

    expect(result.kind).toBe('ok');
    if (result.kind !== 'ok') return;
    expect(result.data.moderation_counters).toMatchObject({
      trust_ip_burst: { enabled: true, window_sec: 10, vote_threshold: 6 },
    });
    const panel = result.data.integrity_panel as { safeguards_applied: string[] };
    expect(panel.safeguards_applied).toContain('trust_stack:ip_burst');
  });

  it('includes trust_chat_burst and safeguard tag when chat burst is enabled', async () => {
    mockTrustChatBurstOwnerSummary.mockReturnValue({
      enabled: true,
      window_sec: 12,
      vote_threshold: 5,
    });
    mockFindByPk.mockResolvedValue(buildPoll(basePollFields()));

    const result = await getPollView(buildReq(42), 'poll-1');

    expect(result.kind).toBe('ok');
    if (result.kind !== 'ok') return;
    expect(result.data.moderation_counters).toMatchObject({
      trust_chat_burst: { enabled: true, window_sec: 12, vote_threshold: 5 },
    });
    const panel = result.data.integrity_panel as { safeguards_applied: string[] };
    expect(panel.safeguards_applied).toContain('trust_stack:chat_burst');
  });
});
