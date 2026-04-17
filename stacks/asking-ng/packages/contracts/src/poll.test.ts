import { describe, expect, it } from 'vitest';
import {
  allowedPollPhaseTargets,
  createPollBodySchema,
  decideQuarantinedVoteBodySchema,
  editWriteInVoteBodySchema,
  formatAllowedPhasesList,
  isPollPhaseTransitionAllowed,
  listPollsMineQuerySchema,
  listQuarantinedVotesQuerySchema,
  moderateVoteBatchBodySchema,
  normalizePollPhase,
  pollFormatExtensionSchema,
  updatePollBodySchema,
  votePollBodySchema,
} from './poll';

describe('createPollBodySchema', () => {
  it('accepts valid payload with never-style expiration', () => {
    const r = createPollBodySchema.safeParse({
      title: ' Q ',
      options: [' a ', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
    });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.title).toBe('Q');
      expect(r.data.options).toEqual(['a', 'b']);
    }
  });

  it('rejects duplicate options', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['x', 'x'],
      expiration: 999999999999999,
      limit_ip: false,
    });
    expect(r.success).toBe(false);
  });

  it('rejects out-of-range expiration', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: -1,
      limit_ip: true,
    });
    expect(r.success).toBe(false);
  });

  it('rejects invalid schedule ordering', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      open_at: 2000,
      lock_at: 1000,
    });
    expect(r.success).toBe(false);
  });

  it('rejects max_boost_weight when boosted mode is disabled', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      max_boost_weight: 3,
    });
    expect(r.success).toBe(false);
  });

  it('accepts run-of-show and auto-advance fields', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      run_of_show_key: 'stream-night-1',
      run_of_show_order: 2,
      next_poll_id: 'poll_next_1',
      auto_advance_on_close: true,
    });
    expect(r.success).toBe(true);
  });

  it('requires friction settings for selected friction tiers', () => {
    expect(
      createPollBodySchema.safeParse({
        title: 't',
        options: ['a', 'b'],
        expiration: 999999999999999,
        limit_ip: true,
        vote_friction_tier: 'soft_throttle',
      }).success,
    ).toBe(false);
    expect(
      createPollBodySchema.safeParse({
        title: 't',
        options: ['a', 'b'],
        expiration: 999999999999999,
        limit_ip: true,
        vote_friction_tier: 'proof_of_work',
      }).success,
    ).toBe(false);
  });

  it('accepts write-in hygiene settings', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      allow_write_in: true,
      write_in_max_length: 96,
      write_in_blocklist: ['spamword'],
      write_in_profanity_filter: true,
    });
    expect(r.success).toBe(true);
  });

  it('rejects selection_mode=multi with boosted voting or write-ins', () => {
    expect(
      createPollBodySchema.safeParse({
        title: 't',
        options: ['a', 'b'],
        expiration: 999999999999999,
        limit_ip: true,
        selection_mode: 'multi',
        boosted_voting_enabled: true,
      }).success,
    ).toBe(false);
    expect(
      createPollBodySchema.safeParse({
        title: 't',
        options: ['a', 'b'],
        expiration: 999999999999999,
        limit_ip: true,
        selection_mode: 'multi',
        allow_write_in: true,
      }).success,
    ).toBe(false);
  });

  it('defaults vote_eligibility to anonymous and accepts account', () => {
    const d = createPollBodySchema.parse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
    });
    expect(d.vote_eligibility).toBe('anonymous');
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      vote_eligibility: 'account',
      account_vote_consent_ack: true,
    });
    expect(r.success).toBe(true);
  });

  it('requires account_vote_consent_ack=true when vote_eligibility=account', () => {
    const missing = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      vote_eligibility: 'account',
    });
    expect(missing.success).toBe(false);
    const ok = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      vote_eligibility: 'account',
      account_vote_consent_ack: true,
    });
    expect(ok.success).toBe(true);
  });

  it('requires account_vote_consent_ack=true when vote_eligibility=platform_linked', () => {
    const missing = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      vote_eligibility: 'platform_linked',
    });
    expect(missing.success).toBe(false);
    const ok = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      vote_eligibility: 'platform_linked',
      account_vote_consent_ack: true,
      platform_identity_provider: 'twitch',
      platform_identity_consent_version: 'v1',
    });
    expect(ok.success).toBe(true);
  });

  it('requires platform identity metadata when vote_eligibility=platform_linked', () => {
    const missing = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      vote_eligibility: 'platform_linked',
      account_vote_consent_ack: true,
    });
    expect(missing.success).toBe(false);
    const ok = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      vote_eligibility: 'platform_linked',
      account_vote_consent_ack: true,
      platform_identity_provider: 'twitch',
      platform_identity_consent_version: 'v1',
    });
    expect(ok.success).toBe(true);
  });

  it('accepts retention_ttl_days', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      retention_ttl_days: 30,
    });
    expect(r.success).toBe(true);
  });

  it('accepts retention_legal_hold', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      retention_legal_hold: true,
    });
    expect(r.success).toBe(true);
  });

  it('accepts webhook target hint_locale override', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      webhook_targets: [
        { url: 'https://hooks.example.test/poll', secret: 'abcdefghijklmnop', hint_locale: 'es' },
      ],
    });
    expect(r.success).toBe(true);
  });

  it('accepts webhook target include_results_snapshot', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      webhook_targets: [
        {
          url: 'https://hooks.example.test/poll',
          secret: 'abcdefghijklmnop',
          include_results_snapshot: true,
        },
      ],
    });
    expect(r.success).toBe(true);
  });

  it('accepts webhook target include_owner_snapshot', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      webhook_targets: [
        {
          url: 'https://hooks.example.test/poll',
          secret: 'abcdefghijklmnop',
          include_owner_snapshot: true,
        },
      ],
    });
    expect(r.success).toBe(true);
  });

  it('accepts webhook target include_owner_events', () => {
    const r = createPollBodySchema.safeParse({
      title: 't',
      options: ['a', 'b'],
      expiration: 999999999999999,
      limit_ip: true,
      webhook_targets: [
        {
          url: 'https://hooks.example.test/poll',
          secret: 'abcdefghijklmnop',
          include_owner_events: true,
        },
      ],
    });
    expect(r.success).toBe(true);
  });
});

describe('updatePollBodySchema', () => {
  it('coerces string expiration', () => {
    const r = updatePollBodySchema.safeParse({ expiration: '12345678901234' });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.expiration).toBe(12345678901234);
  });

  it('accepts phase-only patch', () => {
    const r = updatePollBodySchema.safeParse({ phase: 'locked' });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.phase).toBe('locked');
  });

  it('rejects empty patch', () => {
    expect(updatePollBodySchema.safeParse({}).success).toBe(false);
  });

  it('accepts embed token rotation only', () => {
    const r = updatePollBodySchema.safeParse({ generate_embed_read_token: true });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.generate_embed_read_token).toBe(true);
  });

  it('accepts panic alone or with pause_message', () => {
    expect(updatePollBodySchema.safeParse({ panic: true }).success).toBe(true);
    const r = updatePollBodySchema.safeParse({ panic: true, pause_message: 'Stream issue' });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.panic).toBe(true);
      expect(r.data.pause_message).toBe('Stream issue');
    }
  });

  it('rejects panic combined with phase', () => {
    expect(updatePollBodySchema.safeParse({ panic: true, phase: 'open' }).success).toBe(false);
  });

  it('accepts vote_eligibility-only patch', () => {
    const r = updatePollBodySchema.safeParse({
      vote_eligibility: 'account',
      account_vote_consent_ack: true,
    });
    expect(r.success).toBe(true);
  });

  it('requires account_vote_consent_ack=true when patching vote_eligibility=account', () => {
    const missing = updatePollBodySchema.safeParse({ vote_eligibility: 'account' });
    expect(missing.success).toBe(false);
    const ok = updatePollBodySchema.safeParse({
      vote_eligibility: 'account',
      account_vote_consent_ack: true,
    });
    expect(ok.success).toBe(true);
  });

  it('requires account_vote_consent_ack=true when patching vote_eligibility=platform_linked', () => {
    const missing = updatePollBodySchema.safeParse({ vote_eligibility: 'platform_linked' });
    expect(missing.success).toBe(false);
    const ok = updatePollBodySchema.safeParse({
      vote_eligibility: 'platform_linked',
      account_vote_consent_ack: true,
      platform_identity_provider: 'twitch',
      platform_identity_consent_version: 'v1',
    });
    expect(ok.success).toBe(true);
  });

  it('requires identity metadata when patching vote_eligibility=platform_linked', () => {
    const missing = updatePollBodySchema.safeParse({
      vote_eligibility: 'platform_linked',
      account_vote_consent_ack: true,
    });
    expect(missing.success).toBe(false);
    const ok = updatePollBodySchema.safeParse({
      vote_eligibility: 'platform_linked',
      account_vote_consent_ack: true,
      platform_identity_provider: 'twitch',
      platform_identity_consent_version: 'v1',
    });
    expect(ok.success).toBe(true);
  });

  it('rejects panic combined with account_vote_consent_ack', () => {
    expect(
      updatePollBodySchema.safeParse({ panic: true, account_vote_consent_ack: true }).success,
    ).toBe(false);
  });

  it('rejects panic combined with vote_eligibility', () => {
    expect(
      updatePollBodySchema.safeParse({ panic: true, vote_eligibility: 'account' }).success,
    ).toBe(false);
  });

  it('accepts retention_ttl_days-only patch', () => {
    const r = updatePollBodySchema.safeParse({ retention_ttl_days: 60 });
    expect(r.success).toBe(true);
  });

  it('rejects panic combined with retention_ttl_days', () => {
    expect(updatePollBodySchema.safeParse({ panic: true, retention_ttl_days: 30 }).success).toBe(
      false,
    );
  });

  it('accepts retention_legal_hold-only patch', () => {
    const r = updatePollBodySchema.safeParse({ retention_legal_hold: true });
    expect(r.success).toBe(true);
  });

  it('rejects panic combined with retention_legal_hold', () => {
    expect(
      updatePollBodySchema.safeParse({ panic: true, retention_legal_hold: true }).success,
    ).toBe(false);
  });

  it('accepts schedule updates and clears', () => {
    expect(updatePollBodySchema.safeParse({ open_at: 1000, lock_at: 2000 }).success).toBe(true);
    expect(updatePollBodySchema.safeParse({ reveal_at: null }).success).toBe(true);
  });

  it('accepts boosted voting toggle and max weight update', () => {
    const r = updatePollBodySchema.safeParse({
      boosted_voting_enabled: true,
      max_boost_weight: 4,
      show_unweighted_values: true,
    });
    expect(r.success).toBe(true);
  });

  it('accepts run-of-show updates and clear fields', () => {
    expect(
      updatePollBodySchema.safeParse({
        run_of_show_key: 'show_a',
        run_of_show_order: 5,
        next_poll_id: 'poll_b',
        auto_advance_on_close: true,
      }).success,
    ).toBe(true);
    expect(updatePollBodySchema.safeParse({ run_of_show_key: null }).success).toBe(true);
    expect(updatePollBodySchema.safeParse({ next_poll_id: null }).success).toBe(true);
  });

  it('rejects auto_advance_on_close without next_poll_id', () => {
    expect(
      updatePollBodySchema.safeParse({
        auto_advance_on_close: true,
      }).success,
    ).toBe(false);
  });

  it('requires soft throttle config for soft_throttle tier', () => {
    expect(
      updatePollBodySchema.safeParse({
        vote_friction_tier: 'soft_throttle',
      }).success,
    ).toBe(false);
    expect(
      updatePollBodySchema.safeParse({
        vote_friction_tier: 'soft_throttle',
        soft_throttle_max_votes_per_min: 25,
      }).success,
    ).toBe(true);
  });

  it('accepts write-in hygiene patch fields', () => {
    const r = updatePollBodySchema.safeParse({
      allow_write_in: true,
      write_in_max_length: 100,
      write_in_blocklist: ['foo', 'bar'],
      write_in_profanity_filter: false,
    });
    expect(r.success).toBe(true);
  });

  it('rejects invalid webhook target hint_locale override', () => {
    const r = updatePollBodySchema.safeParse({
      webhook_targets: [{ url: 'https://hooks.example.test/poll', hint_locale: 'de' }],
    });
    expect(r.success).toBe(false);
  });

  it('accepts include_owner_events in webhook target patch', () => {
    const r = updatePollBodySchema.safeParse({
      webhook_targets: [{ url: 'https://hooks.example.test/poll', include_owner_events: true }],
    });
    expect(r.success).toBe(true);
  });
});

describe('poll phase transitions', () => {
  it('normalizes unknown phase to open', () => {
    expect(normalizePollPhase(null)).toBe('open');
    expect(normalizePollPhase('nope')).toBe('open');
    expect(normalizePollPhase('draft')).toBe('draft');
  });

  it('allows same-phase no-op', () => {
    expect(isPollPhaseTransitionAllowed('open', 'open')).toBe(true);
  });

  it('allows draft → open and blocks open → draft', () => {
    expect(isPollPhaseTransitionAllowed('draft', 'open')).toBe(true);
    expect(isPollPhaseTransitionAllowed('open', 'draft')).toBe(false);
  });

  it('allows open → locked and locked → open', () => {
    expect(isPollPhaseTransitionAllowed('open', 'locked')).toBe(true);
    expect(isPollPhaseTransitionAllowed('locked', 'open')).toBe(true);
  });

  it('blocks revealed → open unless panic to locked', () => {
    expect(isPollPhaseTransitionAllowed('revealed', 'open')).toBe(false);
    expect(isPollPhaseTransitionAllowed('revealed', 'locked')).toBe(false);
    expect(isPollPhaseTransitionAllowed('revealed', 'locked', { panic: true })).toBe(true);
  });

  it('allowedPollPhaseTargets for revealed is empty', () => {
    expect([...allowedPollPhaseTargets('revealed')]).toEqual([]);
    expect(formatAllowedPhasesList('revealed')).toContain('final');
  });
});

describe('votePollBodySchema', () => {
  it('trims option', () => {
    const r = votePollBodySchema.safeParse({ option: ' yes ' });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.option).toBe('yes');
  });

  it('accepts option_index instead of option', () => {
    const r = votePollBodySchema.safeParse({ option_index: 0 });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.option_index).toBe(0);
  });

  it('accepts optional boost_weight', () => {
    const r = votePollBodySchema.safeParse({ option: 'a', boost_weight: 2 });
    expect(r.success).toBe(true);
  });

  it('accepts optional proof-of-work nonce', () => {
    const r = votePollBodySchema.safeParse({ option: 'a', pow_nonce: 'abc123' });
    expect(r.success).toBe(true);
  });

  it('accepts optional chat channel and idempotency key', () => {
    const r = votePollBodySchema.safeParse({
      option_index: 0,
      chat_channel_id: 'twitch:mychannel',
      idempotency_key: 'msg-1234',
    });
    expect(r.success).toBe(true);
  });

  it('rejects mixing single-choice fields with option_indices', () => {
    expect(votePollBodySchema.safeParse({ option: 'a', option_index: 0 }).success).toBe(false);
    expect(votePollBodySchema.safeParse({ option: 'a', option_indices: [0] }).success).toBe(false);
    expect(votePollBodySchema.safeParse({ option_index: 0, option_indices: [0] }).success).toBe(
      false,
    );
  });

  it('accepts option_indices for multi ballots', () => {
    const r = votePollBodySchema.safeParse({ option_indices: [0, 2, 1] });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.option_indices).toEqual([0, 2, 1]);
  });

  it('rejects duplicate option_indices', () => {
    expect(votePollBodySchema.safeParse({ option_indices: [0, 0] }).success).toBe(false);
  });
});

describe('listPollsMineQuerySchema', () => {
  it('accepts run-of-show filters and sort', () => {
    const r = listPollsMineQuerySchema.safeParse({
      limit: 20,
      offset: 0,
      run_of_show_key: 'stream_2026',
      sort: 'run_of_show',
    });
    expect(r.success).toBe(true);
  });
});

describe('quarantine moderation schemas', () => {
  it('accepts quarantine list query defaults', () => {
    const r = listQuarantinedVotesQuerySchema.safeParse({});
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.status).toBe('pending');
      expect(r.data.limit).toBe(100);
    }
  });

  it('accepts moderation decision payload', () => {
    const r = decideQuarantinedVoteBodySchema.safeParse({
      action: 'approve',
      note: 'false positive',
    });
    expect(r.success).toBe(true);
  });

  it('accepts moderation decision revert payload', () => {
    const r = decideQuarantinedVoteBodySchema.safeParse({
      action: 'revert',
      note: 'needs another look',
    });
    expect(r.success).toBe(true);
  });

  it('accepts batch moderation payload', () => {
    const r = moderateVoteBatchBodySchema.safeParse({
      action: 'remove',
      selector: 'source_ip_hash',
      selector_value: 'abc123',
      reason_code: 'spam_wave',
      note: 'burst of duplicate votes',
    });
    expect(r.success).toBe(true);
  });

  it('accepts write-in edit payload', () => {
    const r = editWriteInVoteBodySchema.safeParse({
      option: 'Updated write in',
      note: 'cleanup',
    });
    expect(r.success).toBe(true);
  });
});

describe('pollFormatExtensionSchema (roadmap placeholder)', () => {
  it.each([
    'ranked_choice',
    'rating_scale',
    'quiz',
    'free_text_moderated',
  ] as const)('accepts %s', (value) => {
    const r = pollFormatExtensionSchema.safeParse(value);
    expect(r.success).toBe(true);
    if (r.success) expect(r.data).toBe(value);
  });

  it('rejects unknown labels', () => {
    expect(pollFormatExtensionSchema.safeParse('single').success).toBe(false);
  });
});
