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
  mockTakeCampaignAttribution,
} = vi.hoisted(() => ({
  mockFindByPk: vi.fn(),
  mockIncrement: vi.fn(),
  mockUpdate: vi.fn().mockResolvedValue([1]),
  mockPollEmbedViewAllowed: vi.fn(),
  mockReadEmbedReadTokenFromRequest: vi.fn(),
  mockPollPhaseScheduleFromRow: vi.fn(),
  mockResolveEffectivePollPhase: vi.fn(),
  mockGetPollVoteAnalytics: vi.fn(),
  mockTakeCampaignAttribution: vi.fn().mockResolvedValue(true),
}));

vi.mock('../../lib/billingCampaignAttributionQuota', () => ({
  takeCampaignAttributionIncrementForPoll: mockTakeCampaignAttribution,
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
    const mockTrustIpBurstOwnerSummary = vi.fn((): {
      enabled: boolean;
      window_sec?: number;
      vote_threshold?: number;
    } => ({ enabled: false }));
    const mockTrustChatBurstOwnerSummary = vi.fn((): {
      enabled: boolean;
      window_sec?: number;
      vote_threshold?: number;
    } => ({ enabled: false }));
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

function buildReq(userId?: number, role?: string, query?: Record<string, unknown>): AppRequest {
  return {
    user: userId != null ? { id: userId, role } : undefined,
    query: query ?? {},
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
    retentionTtlDays: 30,
    retentionLegalHold: false,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockTakeCampaignAttribution.mockReset();
  mockTakeCampaignAttribution.mockResolvedValue(true);
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
    optionHourBins: [
      { option_label: 'A', hour_utc: 0, vote_count: 4 },
      { option_label: 'B', hour_utc: 0, vote_count: 2 },
    ],
    voteMinuteBins: [
      { minute_utc: new Date('2026-01-01T00:03:00.000Z'), vote_count: 5 },
      { minute_utc: new Date('2026-01-01T00:02:00.000Z'), vote_count: 1 },
    ],
    optionVoteMinuteBins: [
      { option_label: 'A', minute_utc: new Date('2026-01-01T00:03:00.000Z'), vote_count: 4 },
      { option_label: 'B', minute_utc: new Date('2026-01-01T00:03:00.000Z'), vote_count: 1 },
      { option_label: 'A', minute_utc: new Date('2026-01-01T00:02:00.000Z'), vote_count: 1 },
    ],
    rateCountersRow: {
      votes_last_1m: 2,
      unique_ip_hashes_last_1m: 2,
      unique_accounts_last_1m: 1,
      top_ip_votes_last_1m: 2,
      quarantined_votes_pending: 5,
      quarantined_votes_pending_account_linked: 2,
      votes_account_linked_last_24h: 9,
      votes_anonymous_last_24h: 3,
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
    const m = result.data.metrics as Record<string, unknown>;
    expect(m.vote_velocity_by_minute_utc).toBeUndefined();
    expect(m.vote_velocity_by_minute_utc_truncated).toBeUndefined();
    expect(m.option_hourly_votes_utc).toBeUndefined();
    expect(m.option_vote_velocity_by_minute_utc).toBeUndefined();
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
    expect(result.data.retention_ttl_days).toBe(30);
    expect(result.data.retention_legal_hold).toBe(false);
    expect(typeof result.data.auto_delete_at_ms).toBe('number');
    expect(result.data.show_notes).toBe('secret note');
    expect(result.data.moderation_counters).toEqual({
      votes_last_1m: 2,
      unique_ip_hashes_last_1m: 2,
      unique_accounts_last_1m: 1,
      top_ip_votes_last_1m: 2,
      quarantined_votes_pending: 5,
      quarantined_votes_pending_account_linked: 2,
      votes_account_linked_last_24h: 9,
      votes_anonymous_last_24h: 3,
      trust_ip_burst: { enabled: false },
      trust_chat_burst: { enabled: false },
    });
    const metrics = result.data.metrics as Record<string, unknown>;
    expect(metrics.option_hourly_votes_utc).toEqual([
      { option: 'A', hourly_votes_by_hour_utc: [4, ...Array(23).fill(0)] },
      { option: 'B', hourly_votes_by_hour_utc: [2, ...Array(23).fill(0)] },
    ]);
    expect(metrics.vote_velocity_by_minute_utc).toEqual([
      { minute_utc: '2026-01-01T00:02:00.000Z', vote_count: 1 },
      { minute_utc: '2026-01-01T00:03:00.000Z', vote_count: 5 },
    ]);
    expect(metrics.option_vote_velocity_by_minute_utc).toEqual([
      {
        option: 'A',
        vote_velocity_by_minute_utc: [
          { minute_utc: '2026-01-01T00:02:00.000Z', vote_count: 1 },
          { minute_utc: '2026-01-01T00:03:00.000Z', vote_count: 4 },
        ],
      },
      {
        option: 'B',
        vote_velocity_by_minute_utc: [
          { minute_utc: '2026-01-01T00:02:00.000Z', vote_count: 0 },
          { minute_utc: '2026-01-01T00:03:00.000Z', vote_count: 1 },
        ],
      },
    ]);
    expect(metrics.vote_velocity_by_minute_utc_truncated).toBeUndefined();
    expect(mockGetPollVoteAnalytics).toHaveBeenCalledWith(
      expect.objectContaining({
        pollId: 'poll-1',
        liveResultsAreDelayed: false,
        youOwnThisPoll: true,
      }),
    );
  });

  it('suppresses auto_delete_at_ms when retention legal hold is enabled', async () => {
    mockFindByPk.mockResolvedValue(
      buildPoll(
        basePollFields({
          retentionTtlDays: 30,
          retentionLegalHold: true,
        }),
      ),
    );

    const result = await getPollView(buildReq(42), 'poll-1');
    expect(result.kind).toBe('ok');
    if (result.kind !== 'ok') return;
    expect(result.data.retention_ttl_days).toBe(30);
    expect(result.data.retention_legal_hold).toBe(true);
    expect(result.data.auto_delete_at_ms).toBeNull();
  });

  it('sets vote_velocity_by_minute_utc_truncated when minute series hits cap', async () => {
    const baseMs = Date.UTC(2026, 5, 10, 0, 0, 0);
    const voteMinuteBins = Array.from({ length: 4000 }, (_, i) => ({
      minute_utc: new Date(baseMs + (3999 - i) * 60_000),
      vote_count: 1,
    }));
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
      optionHourBins: [
        { option_label: 'A', hour_utc: 0, vote_count: 4 },
        { option_label: 'B', hour_utc: 0, vote_count: 2 },
      ],
      voteMinuteBins,
      optionVoteMinuteBins: [],
      rateCountersRow: {
        votes_last_1m: 2,
        unique_ip_hashes_last_1m: 2,
        unique_accounts_last_1m: 1,
        top_ip_votes_last_1m: 2,
        quarantined_votes_pending: 0,
        quarantined_votes_pending_account_linked: 0,
        votes_account_linked_last_24h: 0,
        votes_anonymous_last_24h: 0,
      },
      delayedVotesPending: 0,
    });
    mockFindByPk.mockResolvedValue(buildPoll(basePollFields()));

    const result = await getPollView(buildReq(42), 'poll-1');

    expect(result.kind).toBe('ok');
    if (result.kind !== 'ok') return;
    const metrics = result.data.metrics as Record<string, unknown>;
    expect(metrics.vote_velocity_by_minute_utc_truncated).toBe(true);
    expect(Array.isArray(metrics.vote_velocity_by_minute_utc)).toBe(true);
    expect((metrics.vote_velocity_by_minute_utc as unknown[]).length).toBe(4000);
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

  it('skips impressionAttribution update when campaign quota rejects increment', async () => {
    mockTakeCampaignAttribution.mockResolvedValue(false);
    mockFindByPk.mockResolvedValue(
      buildPoll(
        basePollFields({
          impressionAttribution: { 'x|y|z': 3 },
          viewEventsByHour: {},
        }),
      ),
    );

    const result = await getPollView(
      buildReq(undefined, undefined, {
        utm_source: 'x',
        utm_medium: 'y',
        utm_campaign: 'z',
      }),
      'poll-1',
    );

    expect(result.kind).toBe('ok');
    expect(mockTakeCampaignAttribution).toHaveBeenCalledWith({
      pollId: 'poll-1',
      creatorUserId: 42,
    });
    expect(mockUpdate).toHaveBeenCalled();
    const patch = mockUpdate.mock.calls[0][0] as Record<string, unknown>;
    expect(patch.impressionCount).toBe(11);
    expect(patch).not.toHaveProperty('impressionAttribution');
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
