import { z } from 'zod';

const pollOptionString = z.string().trim().min(1).max(500);

/** Max ms timestamp we accept (year ~275760); still allows legacy "never" sentinel. */
const MAX_EXPIRATION_MS = 8640000000000000;

const httpsWebhookUrl = z
  .string()
  .trim()
  .max(2048)
  .refine(
    (s) => {
      try {
        const u = new URL(s);
        if (u.protocol !== 'https:' && !(u.protocol === 'http:' && u.hostname === 'localhost')) {
          return false;
        }
        return true;
      } catch {
        return false;
      }
    },
    { message: 'webhook target url must be https (or http://localhost only)', path: ['url'] },
  );

const webhookTargetSchema = z.object({
  url: httpsWebhookUrl,
  secret: z.string().trim().min(16).max(128).optional(),
});

const runOfShowKeySchema = z
  .string()
  .trim()
  .min(1)
  .max(64)
  .regex(/^[A-Za-z0-9_-]+$/, 'run_of_show_key must contain only letters, numbers, "_" or "-"');

const vanitySlugSchema = z
  .string()
  .trim()
  .min(3)
  .max(64)
  .regex(/^[a-z0-9][a-z0-9-]*$/, 'vanity_slug must use lowercase letters, numbers, and "-"');

const writeInBlocklistItemSchema = z.string().trim().min(1).max(64);
const collaboratorUserIdSchema = z.coerce.number().int().positive();
export const pollThemePresetSchema = z.enum(['default', 'sunset', 'ocean', 'neon']);
/** How voters submit choices for this poll. */
export const pollSelectionModeSchema = z.enum(['single', 'multi']);
export type PollSelectionMode = z.infer<typeof pollSelectionModeSchema>;

/** Who may cast a ballot (`PUT /poll/:id/vote`). */
export const pollVoteEligibilitySchema = z.enum(['anonymous', 'account']);
export type PollVoteEligibility = z.infer<typeof pollVoteEligibilitySchema>;

/**
 * Roadmap poll formats (ranked, ratings, quiz, moderated free-text). **Not used** by create/vote
 * APIs yet — shared vocabulary for docs, clients, and future wire fields. See
 * `docs/CREATOR-STREAMER-ROADMAP.md`.
 */
export const pollFormatExtensionSchema = z.enum([
  'ranked_choice',
  'rating_scale',
  'quiz',
  'free_text_moderated',
]);
export type PollFormatExtension = z.infer<typeof pollFormatExtensionSchema>;
const mediaAttachmentSchema = z.object({
  kind: z.enum(['image', 'video']),
  url: z.string().trim().url().max(2048),
  preview_url: z.string().trim().url().max(2048).optional(),
  alt: z.string().trim().max(280).optional(),
});

export const pollPhaseSchema = z.enum(['draft', 'open', 'locked', 'revealed']);
export type PollPhase = z.infer<typeof pollPhaseSchema>;
export const voteFrictionTierSchema = z.enum(['open', 'soft_throttle', 'proof_of_work']);
export type VoteFrictionTier = z.infer<typeof voteFrictionTierSchema>;

/**
 * Allowed one-way moves for creator **`PUT /poll/:id`** (enforced server-side; UI may mirror).
 * - **draft** → launch, lock early, or skip to revealed.
 * - **open** → no return to **draft**; can lock or reveal.
 * - **locked** → reopen (**open**) or finalize (**revealed**).
 * - **revealed** → terminal (**panic** may still force **locked**).
 */
const PHASE_TRANSITION_EDGES: Record<PollPhase, readonly PollPhase[]> = {
  draft: ['open', 'locked', 'revealed'],
  open: ['locked', 'revealed'],
  locked: ['open', 'revealed'],
  revealed: [],
};

export function normalizePollPhase(raw: unknown): PollPhase {
  const r = pollPhaseSchema.safeParse(raw);
  return r.success ? r.data : 'open';
}

export function allowedPollPhaseTargets(from: PollPhase): readonly PollPhase[] {
  return PHASE_TRANSITION_EDGES[from] ?? [];
}

export function isPollPhaseTransitionAllowed(
  from: PollPhase,
  to: PollPhase,
  opts?: { panic?: boolean },
): boolean {
  if (from === to) return true;
  if (opts?.panic && to === 'locked') return true;
  return (allowedPollPhaseTargets(from) as readonly string[]).includes(to);
}

export function formatAllowedPhasesList(from: PollPhase): string {
  const a = allowedPollPhaseTargets(from);
  if (a.length === 0) return '(none — phase is final unless using panic)';
  return a.join(', ');
}

export const createPollBodySchema = z
  .object({
    title: z.string().trim().min(1).max(500),
    options: z.array(pollOptionString).min(2).max(32),
    expiration: z.coerce.number().finite(),
    limit_ip: z.coerce.boolean(),
    webhook_targets: z.array(webhookTargetSchema).max(10).optional(),
    /** Initial lifecycle phase (`draft` = no votes until moved to `open`). */
    phase: pollPhaseSchema.optional().default('open'),
    /** Private run-of-show notes; only returned to the signed-in poll owner on `GET /poll/:id`. */
    show_notes: z.string().max(10_000).optional(),
    /** When true, response includes a one-time `embed_read_token` (store hash only in DB). */
    generate_embed_read_token: z.boolean().optional(),
    /** Optional schedule window (UTC ms epoch) for auto open/lock/reveal. */
    open_at: z.coerce.number().int().positive().max(MAX_EXPIRATION_MS).optional(),
    lock_at: z.coerce.number().int().positive().max(MAX_EXPIRATION_MS).optional(),
    reveal_at: z.coerce.number().int().positive().max(MAX_EXPIRATION_MS).optional(),
    /** Optional weighted voting mode (boost values >1). */
    boosted_voting_enabled: z.boolean().optional(),
    /** Max accepted per-vote boost when weighted voting is enabled (inclusive). */
    max_boost_weight: z.coerce.number().int().min(1).max(10).optional(),
    /** When true, include raw (unweighted) counts beside weighted values in responses/exports. */
    show_unweighted_values: z.boolean().optional(),
    /** Optional run-of-show queue key (same key = same sequence). */
    run_of_show_key: runOfShowKeySchema.optional(),
    /** Optional ordering number within a run-of-show key (ascending). */
    run_of_show_order: z.coerce.number().int().min(0).max(1_000_000).optional(),
    /** Optional linked next poll id for queue/bracket advancement. */
    next_poll_id: z.string().trim().min(1).max(255).optional(),
    /** If true, closing this poll can auto-open `next_poll_id`. */
    auto_advance_on_close: z.boolean().optional(),
    /** Optional human-friendly alias for short links (`/s/:slug`). */
    vanity_slug: vanitySlugSchema.optional(),
    /** Per-poll anti-raid voting friction mode. */
    vote_friction_tier: voteFrictionTierSchema.optional(),
    /** Max accepted votes/minute per source IP hash in soft-throttle mode. */
    soft_throttle_max_votes_per_min: z.coerce.number().int().min(1).max(240).optional(),
    /** Required leading zero hex chars for proof-of-work mode. */
    pow_difficulty: z.coerce.number().int().min(1).max(6).optional(),
    /** Delay live public result totals by N seconds to reduce tactical vote manipulation. */
    results_delay_seconds: z.coerce.number().int().min(0).max(600).optional(),
    /** Enable free-text vote options that are not pre-listed poll choices. */
    allow_write_in: z.boolean().optional(),
    /** Max write-in character length when write-ins are enabled. */
    write_in_max_length: z.coerce.number().int().min(1).max(280).optional(),
    /** Additional blocked write-in terms (case-insensitive). */
    write_in_blocklist: z.array(writeInBlocklistItemSchema).max(200).optional(),
    /** Built-in profanity filter for write-ins. */
    write_in_profanity_filter: z.boolean().optional(),
    /** Optional collaborator user ids allowed to edit this draft. */
    shared_editor_user_ids: z.array(collaboratorUserIdSchema).max(20).optional(),
    /** Optional media attachment metadata (stored as external URL only). */
    media_attachment: mediaAttachmentSchema.optional(),
    /** Blur media by default for safer on-stream rendering. */
    media_blur_by_default: z.boolean().optional(),
    /** Optional per-poll visual preset for creator branding. */
    theme_preset: pollThemePresetSchema.optional(),
    /** `multi` allows one ballot with several fixed options (no write-ins, no boosted weights in v1). */
    selection_mode: pollSelectionModeSchema.optional().default('single'),
    /**
     * `anonymous` (default): anyone may vote. `account`: voter must send a valid user JWT
     * (`Authorization: Bearer`); one ballot per authenticated user.
     */
    vote_eligibility: pollVoteEligibilitySchema.optional().default('anonymous'),
  })
  .refine((d) => new Set(d.options).size === d.options.length, {
    message: 'Duplicate options are not allowed',
    path: ['options'],
  })
  .refine((d) => d.expiration > 0 && d.expiration <= MAX_EXPIRATION_MS, {
    message: 'Invalid expiration',
    path: ['expiration'],
  })
  .refine((d) => d.open_at === undefined || d.lock_at === undefined || d.lock_at >= d.open_at, {
    message: 'lock_at must be greater than or equal to open_at',
    path: ['lock_at'],
  })
  .refine((d) => d.open_at === undefined || d.reveal_at === undefined || d.reveal_at >= d.open_at, {
    message: 'reveal_at must be greater than or equal to open_at',
    path: ['reveal_at'],
  })
  .refine((d) => d.lock_at === undefined || d.reveal_at === undefined || d.reveal_at >= d.lock_at, {
    message: 'reveal_at must be greater than or equal to lock_at',
    path: ['reveal_at'],
  })
  .refine((d) => d.max_boost_weight === undefined || d.boosted_voting_enabled === true, {
    message: 'max_boost_weight requires boosted_voting_enabled',
    path: ['max_boost_weight'],
  })
  .refine((d) => d.auto_advance_on_close !== true || typeof d.next_poll_id === 'string', {
    message: 'auto_advance_on_close requires next_poll_id',
    path: ['auto_advance_on_close'],
  })
  .refine(
    (d) =>
      d.vote_friction_tier !== 'soft_throttle' || d.soft_throttle_max_votes_per_min !== undefined,
    {
      message: 'soft_throttle_max_votes_per_min is required when vote_friction_tier=soft_throttle',
      path: ['soft_throttle_max_votes_per_min'],
    },
  )
  .refine((d) => d.vote_friction_tier !== 'proof_of_work' || d.pow_difficulty !== undefined, {
    message: 'pow_difficulty is required when vote_friction_tier=proof_of_work',
    path: ['pow_difficulty'],
  })
  .refine(
    (d) =>
      d.shared_editor_user_ids === undefined ||
      new Set(d.shared_editor_user_ids).size === d.shared_editor_user_ids.length,
    {
      message: 'shared_editor_user_ids contains duplicates',
      path: ['shared_editor_user_ids'],
    },
  )
  .refine((d) => d.selection_mode !== 'multi' || d.boosted_voting_enabled !== true, {
    message: 'multi selection_mode cannot be combined with boosted_voting_enabled',
    path: ['selection_mode'],
  })
  .refine((d) => d.selection_mode !== 'multi' || d.allow_write_in !== true, {
    message: 'multi selection_mode cannot be combined with allow_write_in',
    path: ['selection_mode'],
  });

export type CreatePollBody = z.infer<typeof createPollBodySchema>;

export const updatePollBodySchema = z
  .object({
    expiration: z.coerce
      .number()
      .finite()
      .refine((n) => n > 0 && n <= MAX_EXPIRATION_MS, { message: 'Invalid expiration' })
      .optional(),
    phase: pollPhaseSchema.optional(),
    voting_paused: z.boolean().optional(),
    pause_message: z.union([z.string().trim().max(280), z.null()]).optional(),
    show_notes: z.union([z.string().max(10_000), z.null()]).optional(),
    /** When true, issues a new read-only embed token once in the response and replaces the stored hash. */
    generate_embed_read_token: z.boolean().optional(),
    open_at: z
      .union([z.coerce.number().int().positive().max(MAX_EXPIRATION_MS), z.null()])
      .optional(),
    lock_at: z
      .union([z.coerce.number().int().positive().max(MAX_EXPIRATION_MS), z.null()])
      .optional(),
    reveal_at: z
      .union([z.coerce.number().int().positive().max(MAX_EXPIRATION_MS), z.null()])
      .optional(),
    boosted_voting_enabled: z.boolean().optional(),
    max_boost_weight: z.union([z.coerce.number().int().min(1).max(10), z.null()]).optional(),
    show_unweighted_values: z.boolean().optional(),
    run_of_show_key: z.union([runOfShowKeySchema, z.null()]).optional(),
    run_of_show_order: z
      .union([z.coerce.number().int().min(0).max(1_000_000), z.null()])
      .optional(),
    next_poll_id: z.union([z.string().trim().min(1).max(255), z.null()]).optional(),
    auto_advance_on_close: z.boolean().optional(),
    vanity_slug: z.union([vanitySlugSchema, z.null()]).optional(),
    vote_friction_tier: voteFrictionTierSchema.optional(),
    soft_throttle_max_votes_per_min: z
      .union([z.coerce.number().int().min(1).max(240), z.null()])
      .optional(),
    pow_difficulty: z.union([z.coerce.number().int().min(1).max(6), z.null()]).optional(),
    results_delay_seconds: z.union([z.coerce.number().int().min(0).max(600), z.null()]).optional(),
    allow_write_in: z.boolean().optional(),
    write_in_max_length: z.union([z.coerce.number().int().min(1).max(280), z.null()]).optional(),
    write_in_blocklist: z
      .union([z.array(writeInBlocklistItemSchema).max(200), z.null()])
      .optional(),
    write_in_profanity_filter: z.boolean().optional(),
    shared_editor_user_ids: z.union([z.array(collaboratorUserIdSchema).max(20), z.null()]).optional(),
    media_attachment: z.union([mediaAttachmentSchema, z.null()]).optional(),
    media_blur_by_default: z.boolean().optional(),
    theme_preset: z.union([pollThemePresetSchema, z.null()]).optional(),
    selection_mode: z.union([pollSelectionModeSchema, z.null()]).optional(),
    vote_eligibility: z.union([pollVoteEligibilitySchema, z.null()]).optional(),
    webhook_targets: z.union([z.array(webhookTargetSchema).max(10), z.null()]).optional(),
    /**
     * One-shot kill switch: sets **phase** to `locked`, **voting_paused** true, and **pause_message**
     * (body value, else `PANIC_PAUSE_MESSAGE` env, else a default). Must not be combined with other
     * update fields except optional **pause_message**.
     */
    panic: z.literal(true).optional(),
  })
  .refine(
    (d) =>
      d.panic === true ||
      d.expiration !== undefined ||
      d.phase !== undefined ||
      d.voting_paused !== undefined ||
      d.pause_message !== undefined ||
      d.show_notes !== undefined ||
      d.generate_embed_read_token === true ||
      d.open_at !== undefined ||
      d.lock_at !== undefined ||
      d.reveal_at !== undefined ||
      d.boosted_voting_enabled !== undefined ||
      d.max_boost_weight !== undefined ||
      d.show_unweighted_values !== undefined ||
      d.run_of_show_key !== undefined ||
      d.run_of_show_order !== undefined ||
      d.next_poll_id !== undefined ||
      d.auto_advance_on_close !== undefined ||
      d.vanity_slug !== undefined ||
      d.vote_friction_tier !== undefined ||
      d.soft_throttle_max_votes_per_min !== undefined ||
      d.pow_difficulty !== undefined ||
      d.results_delay_seconds !== undefined ||
      d.allow_write_in !== undefined ||
      d.write_in_max_length !== undefined ||
      d.write_in_blocklist !== undefined ||
      d.write_in_profanity_filter !== undefined ||
      d.shared_editor_user_ids !== undefined ||
      d.media_attachment !== undefined ||
      d.media_blur_by_default !== undefined ||
      d.theme_preset !== undefined ||
      d.selection_mode !== undefined ||
      d.vote_eligibility !== undefined ||
      d.webhook_targets !== undefined,
    { message: 'At least one field is required', path: ['expiration'] },
  )
  .refine(
    (d) => {
      if (d.panic !== true) return true;
      return (
        d.expiration === undefined &&
        d.phase === undefined &&
        d.voting_paused === undefined &&
        d.show_notes === undefined &&
        d.generate_embed_read_token !== true &&
        d.open_at === undefined &&
        d.lock_at === undefined &&
        d.reveal_at === undefined &&
        d.boosted_voting_enabled === undefined &&
        d.max_boost_weight === undefined &&
        d.show_unweighted_values === undefined &&
        d.run_of_show_key === undefined &&
        d.run_of_show_order === undefined &&
        d.next_poll_id === undefined &&
        d.auto_advance_on_close === undefined &&
        d.vanity_slug === undefined &&
        d.vote_friction_tier === undefined &&
        d.soft_throttle_max_votes_per_min === undefined &&
        d.pow_difficulty === undefined &&
        d.results_delay_seconds === undefined &&
        d.allow_write_in === undefined &&
        d.write_in_max_length === undefined &&
        d.write_in_blocklist === undefined &&
        d.write_in_profanity_filter === undefined &&
        d.shared_editor_user_ids === undefined &&
        d.media_attachment === undefined &&
        d.media_blur_by_default === undefined &&
        d.theme_preset === undefined &&
        d.selection_mode === undefined &&
        d.vote_eligibility === undefined &&
        d.webhook_targets === undefined
      );
    },
    {
      message:
        'panic cannot be combined with expiration, phase, voting_paused, show_notes, generate_embed_read_token, schedule fields, boosted voting fields, run-of-show fields, vanity_slug, friction settings, results delay, write-in settings, media settings, shared_editor_user_ids, selection_mode, vote_eligibility, or webhook_targets',
      path: ['panic'],
    },
  )
  .refine(
    (d) =>
      d.max_boost_weight === undefined ||
      d.max_boost_weight === null ||
      d.boosted_voting_enabled === true,
    {
      message: 'max_boost_weight requires boosted_voting_enabled',
      path: ['max_boost_weight'],
    },
  )
  .refine(
    (d) =>
      d.auto_advance_on_close !== true ||
      (typeof d.next_poll_id === 'string' && d.next_poll_id.trim() !== ''),
    {
      message: 'auto_advance_on_close requires next_poll_id',
      path: ['auto_advance_on_close'],
    },
  )
  .refine(
    (d) =>
      d.vote_friction_tier !== 'soft_throttle' ||
      (d.soft_throttle_max_votes_per_min !== undefined &&
        d.soft_throttle_max_votes_per_min !== null),
    {
      message: 'soft_throttle_max_votes_per_min is required when vote_friction_tier=soft_throttle',
      path: ['soft_throttle_max_votes_per_min'],
    },
  )
  .refine(
    (d) =>
      d.vote_friction_tier !== 'proof_of_work' ||
      (d.pow_difficulty !== undefined && d.pow_difficulty !== null),
    {
      message: 'pow_difficulty is required when vote_friction_tier=proof_of_work',
      path: ['pow_difficulty'],
    },
  )
  .refine(
    (d) =>
      d.shared_editor_user_ids === undefined ||
      d.shared_editor_user_ids === null ||
      new Set(d.shared_editor_user_ids).size === d.shared_editor_user_ids.length,
    {
      message: 'shared_editor_user_ids contains duplicates',
      path: ['shared_editor_user_ids'],
    },
  );

export type UpdatePollBody = z.infer<typeof updatePollBodySchema>;

export const votePollBodySchema = z
  .object({
    option: pollOptionString.optional(),
    /** 0-based index into the poll's `options` array (for bots / chat commands). */
    option_index: z.coerce.number().int().min(0).max(31).optional(),
    /** For `selection_mode=multi` polls: one or more 0-based indices (fixed options only). */
    option_indices: z.array(z.coerce.number().int().min(0).max(31)).min(1).max(32).optional(),
    location: z
      .object({
        latitude: z.number().finite().gte(-90).lte(90),
        longitude: z.number().finite().gte(-180).lte(180),
        accuracyM: z.number().finite().positive().max(200_000).optional(),
      })
      .optional(),
    /** Optional weight for boosted voting polls (defaults to 1). */
    boost_weight: z.coerce.number().int().min(1).max(10).optional(),
    /** Optional nonce for proof-of-work vote friction mode. */
    pow_nonce: z.string().trim().min(1).max(256).optional(),
    /** Optional chat channel identifier for per-channel throttling. */
    chat_channel_id: z.string().trim().min(1).max(128).optional(),
    /** Optional idempotency key for chat-bot retries. */
    idempotency_key: z.string().trim().min(1).max(128).optional(),
  })
  .refine(
    (d) => {
      const hasOpt = d.option !== undefined;
      const hasIdx = d.option_index !== undefined;
      const hasMulti = d.option_indices !== undefined && d.option_indices.length > 0;
      return (
        (hasOpt && !hasIdx && !hasMulti) ||
        (!hasOpt && hasIdx && !hasMulti) ||
        (!hasOpt && !hasIdx && hasMulti)
      );
    },
    {
      message: 'Provide exactly one of option, option_index, or option_indices',
      path: ['option'],
    },
  )
  .refine(
    (d) =>
      d.option_indices === undefined ||
      new Set(d.option_indices).size === d.option_indices.length,
    { message: 'option_indices must not contain duplicates', path: ['option_indices'] },
  );

export type VotePollBody = z.infer<typeof votePollBodySchema>;

export const pollVoteHeatmapQuerySchema = z.object({
  minCount: z.coerce.number().int().min(2).max(20).optional().default(2),
});

export type PollVoteHeatmapQuery = z.infer<typeof pollVoteHeatmapQuerySchema>;

export const pollReplayQuerySchema = z.object({
  limit: z.coerce.number().int().min(1).max(10_000).optional().default(5_000),
});

export type PollReplayQuery = z.infer<typeof pollReplayQuerySchema>;

export const listPollsMineQuerySchema = z.object({
  limit: z.coerce.number().int().min(1).max(100).optional().default(30),
  offset: z.coerce.number().int().min(0).optional().default(0),
  run_of_show_key: runOfShowKeySchema.optional(),
  sort: z.enum(['created_desc', 'run_of_show']).optional().default('created_desc'),
});

export type ListPollsMineQuery = z.infer<typeof listPollsMineQuerySchema>;

export const listQuarantinedVotesQuerySchema = z.object({
  status: z.enum(['pending', 'approved', 'rejected', 'all']).optional().default('pending'),
  limit: z.coerce.number().int().min(1).max(500).optional().default(100),
  offset: z.coerce.number().int().min(0).optional().default(0),
});

export type ListQuarantinedVotesQuery = z.infer<typeof listQuarantinedVotesQuerySchema>;

export const decideQuarantinedVoteBodySchema = z.object({
  action: z.enum(['approve', 'reject', 'revert']),
  note: z.string().trim().max(500).optional(),
});

export type DecideQuarantinedVoteBody = z.infer<typeof decideQuarantinedVoteBodySchema>;

export const editWriteInVoteBodySchema = z.object({
  option: pollOptionString,
  note: z.string().trim().max(500).optional(),
});

export type EditWriteInVoteBody = z.infer<typeof editWriteInVoteBodySchema>;

export const moderateVoteBatchBodySchema = z
  .object({
    action: z.enum(['remove', 'restore']),
    selector: z.enum(['source_ip_hash', 'user_id']),
    selector_value: z.string().trim().min(1).max(128),
    reason_code: z.enum(['spam_wave', 'bot_pattern', 'compromised_account', 'manual_review']),
    note: z.string().trim().max(500).optional(),
  })
  .strict();

export type ModerateVoteBatchBody = z.infer<typeof moderateVoteBatchBodySchema>;

export const exportPollQuerySchema = z.object({
  format: z.enum(['json', 'csv']),
  /** `votes`: per-vote timestamps (JSON or CSV) for editing / analytics. */
  include: z.enum(['summary', 'votes']).optional().default('summary'),
});

export type ExportPollQuery = z.infer<typeof exportPollQuerySchema>;
