import type { AppRequest } from '../../types/http';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildPollsMineView } from './listPollsMine.service';

const { mockGetPollAndVoteColumns, mockListPollRows, mockListPollVoteMetrics } = vi.hoisted(() => ({
  mockGetPollAndVoteColumns: vi.fn(),
  mockListPollRows: vi.fn(),
  mockListPollVoteMetrics: vi.fn(),
}));

vi.mock('./listPollsMine.repository', () => ({
  getPollAndVoteColumns: mockGetPollAndVoteColumns,
  listPollRows: mockListPollRows,
  listPollVoteMetrics: mockListPollVoteMetrics,
}));

function buildReq(userId: number): AppRequest {
  return { user: { id: userId } } as AppRequest;
}

function buildPollRow(fields: Record<string, unknown>): { get: (key: string) => unknown } {
  return { get: (key: string) => fields[key] };
}

describe('buildPollsMineView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetPollAndVoteColumns.mockResolvedValue({
      pollColumns: new Set([
        'id',
        'title',
        'archived',
        'createdAt',
        'webhookTargets',
        'phase',
        'votingPaused',
        'pauseMessage',
        'showNotes',
        'sharedEditorUserIds',
        'themePreset',
        'selectionMode',
        'voteEligibility',
        'impressionCount',
        'embedReadTokenHash',
        'openAt',
        'lockAt',
        'revealAt',
        'boostedVotingEnabled',
        'maxBoostWeight',
        'showUnweightedValues',
        'runOfShowKey',
        'runOfShowOrder',
        'vanitySlug',
        'nextPollId',
        'autoAdvanceOnClose',
        'voteFrictionTier',
        'softThrottleMaxVotesPerMin',
        'powDifficulty',
        'allowWriteIn',
        'writeInMaxLength',
        'writeInBlocklist',
        'writeInProfanityFilter',
        'resultsDelaySeconds',
      ]),
      voteColumns: new Set(['isQuarantined']),
    });
    mockListPollRows.mockResolvedValue({
      rows: [
        buildPollRow({
          id: 'poll-1',
          title: 'Example',
          archived: false,
          createdAt: new Date('2026-01-01T00:00:00.000Z'),
          webhookTargets: [{ url: 'https://hooks.example/a', secret: 's' }],
          phase: 'open',
          votingPaused: false,
          pauseMessage: null,
          showNotes: null,
          sharedEditorUserIds: [77, 88],
          themePreset: 'default',
          selectionMode: 'single',
          voteEligibility: 'anonymous',
          impressionCount: 10,
          embedReadTokenHash: 'hash',
          openAt: null,
          lockAt: null,
          revealAt: null,
          boostedVotingEnabled: true,
          maxBoostWeight: 4,
          showUnweightedValues: true,
          runOfShowKey: 'r1',
          runOfShowOrder: 1,
          vanitySlug: 'example',
          nextPollId: null,
          autoAdvanceOnClose: false,
          voteFrictionTier: 'open',
          softThrottleMaxVotesPerMin: 30,
          powDifficulty: 4,
          allowWriteIn: true,
          writeInMaxLength: 80,
          writeInBlocklist: ['bad'],
          writeInProfanityFilter: true,
          resultsDelaySeconds: 20,
        }),
      ],
      count: 1,
    });
    mockListPollVoteMetrics.mockResolvedValue({
      voteMetricsRows: [
        {
          poll_id: 'poll-1',
          total_votes: 7,
          votes_last_5m: 2,
          votes_last_24h: 0,
          first_vote_at: new Date('2026-01-01T00:01:00.000Z'),
        },
      ],
      peakHourRows: [{ poll_id: 'poll-1', peak_hour_utc: 0, peak_hour_votes: 5 }],
      peakDowRows: [{ poll_id: 'poll-1', peak_dow_utc: 4, peak_dow_votes: 5 }],
      optionFunnelRows: [],
      voteHourBinRows: [
        { poll_id: 'poll-1', hour_utc: 0, vote_count: 3 },
        { poll_id: 'poll-1', hour_utc: 1, vote_count: 4 },
      ],
      voteDowBinRows: [{ poll_id: 'poll-1', dow_utc: 4, vote_count: 7 }],
    });
  });

  it('returns client-expected response shape for mine polls', async () => {
    const result = await buildPollsMineView(buildReq(12), {
      limit: 50,
      offset: 0,
      sort: 'created_desc',
    });

    expect(result.total).toBe(1);
    expect(result.limit).toBe(50);
    expect(result.offset).toBe(0);
    expect(result.polls).toHaveLength(1);

    const poll = result.polls[0] as Record<string, unknown>;
    expect(poll).toMatchObject({
      id: 'poll-1',
      title: 'Example',
      archived: false,
      hasWebhook: true,
      phase: 'open',
      voting_paused: false,
      show_notes: null,
      shared_editor_user_ids: [77, 88],
      has_embed_read_token: true,
      theme_preset: 'default',
      selection_mode: 'single',
      vote_eligibility: 'anonymous',
      boosted_voting_enabled: true,
      max_boost_weight: 4,
      show_unweighted_values: true,
      vote_friction_tier: 'open',
      results_delay_seconds: 20,
      impression_count: 10,
      total_votes: 7,
      votes_last_5m: 2,
      peak_hour_utc: 0,
      peak_dow_utc: 4,
      hourly_votes_by_hour_utc: [
        3, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      ],
      weekday_votes_by_dow_utc: [0, 0, 0, 0, 7, 0, 0],
    });
  });
});
