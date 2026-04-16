import type { CreatePollBody } from '@asking-ng/contracts/poll';
import type { AppRequest } from '../../types/http';
import randomId from '../../helpers/randomId';
import { checkActivePollQuotaForUser } from '../../lib/billingPollQuota';
import { resolveWorkspaceIdForCreatorUserId } from '../../lib/workspaceBootstrap';
import { generateEmbedReadToken, hashEmbedReadToken } from '../../lib/embedReadToken';
import { recordPollPhaseTransition } from '../../lib/pollPhaseHistory';
import { generateWebhookSecret } from '../../lib/pollWebhooks';
import { isPublicWebhookUrl } from '../../lib/webhookUrlSafe';
import { createPollRow, findPollById, findPollByVanitySlug } from './createPoll.repository';

export type CreatePollResult =
  | { kind: 'invalid_webhook_url'; url: string }
  | { kind: 'webhook_url_blocked'; url: string }
  | { kind: 'invalid_next_poll_requires_signed_in' }
  | { kind: 'invalid_next_poll_requires_next_poll_id' }
  | { kind: 'invalid_next_poll_missing_target' }
  | { kind: 'invalid_next_poll_wrong_owner' }
  | { kind: 'invalid_vanity_slug_in_use' }
  | { kind: 'usage_limit_active_polls'; max: number; current: number; plan: string }
  | {
      kind: 'ok';
      data: {
        id: string;
        api_key: string;
        webhook_secrets?: Array<{ url: string; secret: string }>;
        embed_read_token?: string;
      };
    };

export async function createPollService(req: AppRequest, body: CreatePollBody): Promise<CreatePollResult> {
  const {
    title,
    options,
    expiration,
    limit_ip,
    webhook_targets,
    phase,
    show_notes,
    generate_embed_read_token,
    open_at,
    lock_at,
    reveal_at,
    boosted_voting_enabled,
    max_boost_weight,
    show_unweighted_values,
    run_of_show_key,
    run_of_show_order,
    next_poll_id,
    auto_advance_on_close,
    vanity_slug,
    vote_friction_tier,
    soft_throttle_max_votes_per_min,
    pow_difficulty,
    results_delay_seconds,
    allow_write_in,
    write_in_max_length,
    write_in_blocklist,
    write_in_profanity_filter,
    shared_editor_user_ids,
    selection_mode,
    vote_eligibility,
  } = body;
  const bodyRecord = body as Record<string, unknown>;
  const mediaAttachmentRaw = bodyRecord.media_attachment;
  const mediaBlurByDefaultRaw = bodyRecord.media_blur_by_default;
  const themePresetRaw = typeof bodyRecord.theme_preset === 'string' ? bodyRecord.theme_preset : 'default';

  const incomingTargets = webhook_targets ?? [];
  const generatedWebhookSecrets: Array<{ url: string; secret: string }> = [];
  const webhookTargets: Array<{ url: string; secret: string }> = [];
  for (const t of incomingTargets) {
    let u: URL;
    try {
      u = new URL(t.url.trim());
    } catch {
      return { kind: 'invalid_webhook_url', url: t.url };
    }
    if (!isPublicWebhookUrl(u)) {
      return { kind: 'webhook_url_blocked', url: t.url };
    }
    const secret = t.secret?.trim() ? t.secret.trim() : generateWebhookSecret();
    if (!t.secret?.trim()) generatedWebhookSecrets.push({ url: u.toString(), secret });
    webhookTargets.push({ url: u.toString(), secret });
  }

  const creatorUserId = req.user?.id ?? null;
  const sharedEditorUserIds =
    creatorUserId != null
      ? Array.from(
          new Set(
            (shared_editor_user_ids ?? [])
              .map((id: number) => Number(id))
              .filter((id: number) => Number.isInteger(id) && id > 0 && id !== creatorUserId),
          ),
        )
      : [];

  if (next_poll_id !== undefined && next_poll_id.trim() !== '' && creatorUserId == null) {
    return { kind: 'invalid_next_poll_requires_signed_in' };
  }
  if (auto_advance_on_close === true && (!next_poll_id || next_poll_id.trim() === '')) {
    return { kind: 'invalid_next_poll_requires_next_poll_id' };
  }
  if (creatorUserId != null && next_poll_id && next_poll_id.trim() !== '') {
    const nextPoll = await findPollById(next_poll_id.trim());
    if (!nextPoll) return { kind: 'invalid_next_poll_missing_target' };
    if (Number(nextPoll.get('creatorUserId')) !== Number(creatorUserId)) {
      return { kind: 'invalid_next_poll_wrong_owner' };
    }
  }
  const vanitySlug = vanity_slug?.trim() || null;
  if (vanitySlug) {
    const existing = await findPollByVanitySlug(vanitySlug);
    if (existing) return { kind: 'invalid_vanity_slug_in_use' };
  }

  const quota = await checkActivePollQuotaForUser({
    creatorUserId,
    sessionUserRole: req.user?.role ?? null,
  });
  if (!quota.ok) {
    return { kind: 'usage_limit_active_polls', max: quota.max, current: quota.current, plan: quota.plan };
  }

  let embedReadToken: string | undefined;
  let embedReadTokenHash: string | null = null;
  if (generate_embed_read_token) {
    embedReadToken = generateEmbedReadToken();
    embedReadTokenHash = hashEmbedReadToken(embedReadToken);
  }

  const workspaceId = await resolveWorkspaceIdForCreatorUserId(creatorUserId);

  const poll = await createPollRow({
    id: randomId(16),
    api_key: randomId(16),
    title,
    options,
    expiration,
    limit_ip,
    creatorUserId,
    workspaceId,
    webhookTargets,
    phase,
    showNotes: show_notes?.trim() ? show_notes.trim() : null,
    embedReadTokenHash,
    openAt: open_at ?? null,
    lockAt: lock_at ?? null,
    revealAt: reveal_at ?? null,
    boostedVotingEnabled: boosted_voting_enabled ?? false,
    maxBoostWeight: max_boost_weight ?? 3,
    showUnweightedValues: show_unweighted_values ?? false,
    runOfShowKey: run_of_show_key ?? null,
    runOfShowOrder: run_of_show_order ?? null,
    vanitySlug,
    nextPollId: next_poll_id?.trim() ? next_poll_id.trim() : null,
    autoAdvanceOnClose: auto_advance_on_close ?? false,
    voteFrictionTier: vote_friction_tier ?? 'open',
    softThrottleMaxVotesPerMin: soft_throttle_max_votes_per_min ?? 30,
    powDifficulty: pow_difficulty ?? 4,
    resultsDelaySeconds: results_delay_seconds ?? 0,
    allowWriteIn: allow_write_in ?? false,
    writeInMaxLength: write_in_max_length ?? 80,
    writeInBlocklist: write_in_blocklist ?? [],
    writeInProfanityFilter: write_in_profanity_filter ?? true,
    sharedEditorUserIds,
    mediaAttachment: mediaAttachmentRaw ?? null,
    mediaBlurByDefault: typeof mediaBlurByDefaultRaw === 'boolean' ? mediaBlurByDefaultRaw : true,
    mediaModeration: { status: 'active' },
    themePreset: themePresetRaw,
    selectionMode: selection_mode ?? 'single',
    voteEligibility: vote_eligibility ?? 'anonymous',
  });

  const id = poll.get('id') as string;
  const api_key = poll.get('api_key') as string;
  const initialPhase = (poll.get('phase') as string) || 'open';
  await recordPollPhaseTransition({
    pollId: id,
    fromPhase: null,
    toPhase: initialPhase,
    actorType: creatorUserId != null ? 'owner_jwt' : 'api_key',
    actorUserId: creatorUserId,
    source: 'poll_create',
  });

  const data: {
    id: string;
    api_key: string;
    webhook_secrets?: Array<{ url: string; secret: string }>;
    embed_read_token?: string;
  } = { id, api_key };
  if (generatedWebhookSecrets.length > 0) {
    data.webhook_secrets = generatedWebhookSecrets;
  }
  if (embedReadToken) {
    data.embed_read_token = embedReadToken;
  }

  return { kind: 'ok', data };
}
