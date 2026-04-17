import type { ListPollsMineQuery } from '@asking-ng/contracts/poll';
import { getRequestContext } from '../../lib/requestContext';
import type { AppRequest } from '../../types/http';
import {
  getPollAndVoteColumns,
  listPollRows,
  listPollVoteMetrics,
} from './listPollsMine.repository';

type PollListItem = Record<string, unknown>;

export async function buildPollsMineView(
  req: AppRequest,
  query: ListPollsMineQuery,
): Promise<{ polls: PollListItem[]; total: number; limit: number; offset: number }> {
  const { limit, offset, run_of_show_key, sort } = query;
  const uid = getRequestContext(req).userId;
  if (uid == null) {
    return { polls: [], total: 0, limit, offset };
  }
  const { pollColumns, voteColumns } = await getPollAndVoteColumns();

  const pollAttributes = [
    'id',
    'title',
    'options',
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
    'platformIdentityProvider',
    'platformIdentityConsentVersion',
    'platformIdentityConsentCapturedAt',
    'retentionTtlDays',
    'retentionLegalHold',
    'impressionCount',
    'impressionAttribution',
    'viewEventsByHour',
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
  ].filter((column) => pollColumns.has(column));

  const { rows, count } = await listPollRows({
    uid,
    ...(run_of_show_key ? { runOfShowKey: run_of_show_key } : {}),
    sort,
    limit,
    offset,
    pollAttributes,
  });

  const pollIds = rows.map((p) => String(p.get('id')));
  const {
    voteMetricsRows,
    peakHourRows,
    peakDowRows,
    optionFunnelRows,
    voteHourBinRows,
    voteDowBinRows,
  } = await listPollVoteMetrics(pollIds, voteColumns);

  const byPollId = new Map(voteMetricsRows.map((row) => [row.poll_id, row]));
  const peakHourByPollId = new Map(peakHourRows.map((row) => [row.poll_id, row]));
  const peakDowByPollId = new Map(peakDowRows.map((row) => [row.poll_id, row]));
  const optionFunnelByPollId = new Map<
    string,
    Array<{ option_label: string; votes_total: number; votes_last_24h: number }>
  >();
  for (const row of optionFunnelRows) {
    const pollId = String(row.poll_id);
    const list = optionFunnelByPollId.get(pollId) ?? [];
    list.push({
      option_label: String(row.option_label ?? ''),
      votes_total: Number(row.votes_total ?? 0) || 0,
      votes_last_24h: Number(row.votes_last_24h ?? 0) || 0,
    });
    optionFunnelByPollId.set(pollId, list);
  }

  const hourlyVotesByPollId = new Map<string, number[]>();
  for (const row of voteHourBinRows) {
    const pollId = String(row.poll_id);
    let bins = hourlyVotesByPollId.get(pollId);
    if (!bins) {
      bins = Array.from({ length: 24 }, () => 0);
      hourlyVotesByPollId.set(pollId, bins);
    }
    const h = Number(row.hour_utc);
    if (Number.isInteger(h) && h >= 0 && h <= 23) {
      bins[h] = Number(row.vote_count) || 0;
    }
  }
  const weekdayVotesByPollId = new Map<string, number[]>();
  for (const row of voteDowBinRows) {
    const pollId = String(row.poll_id);
    let bins = weekdayVotesByPollId.get(pollId);
    if (!bins) {
      bins = Array.from({ length: 7 }, () => 0);
      weekdayVotesByPollId.set(pollId, bins);
    }
    const d = Number(row.dow_utc);
    if (Number.isInteger(d) && d >= 0 && d <= 6) {
      bins[d] = Number(row.vote_count) || 0;
    }
  }

  const nowMs = Date.now();
  const polls = rows.map((p) => {
    const hash = (p.get('embedReadTokenHash') as string | null | undefined)?.trim();
    const createdAtRaw = p.get('createdAt') as Date;
    const createdAtMs =
      createdAtRaw instanceof Date ? createdAtRaw.getTime() : Date.parse(String(createdAtRaw));
    const row = byPollId.get(String(p.get('id')));
    const totalVotes = Number(row?.total_votes ?? 0) || 0;
    const votesLast5m = Number(row?.votes_last_5m ?? 0) || 0;
    const votesLast24h = Number(row?.votes_last_24h ?? 0) || 0;
    const impressionCount = Number(p.get('impressionCount')) || 0;
    const viewsByHourRaw =
      (p.get('viewEventsByHour') as Record<string, unknown> | null | undefined) ?? {};
    const minHourKey = Number(
      new Date(nowMs - 24 * 3600 * 1000).toISOString().slice(0, 13).replace(/[-T:]/g, ''),
    );
    const viewsLast24h = Object.entries(viewsByHourRaw)
      .filter(([k]) => /^\d{10}$/.test(k) && Number(k) >= minHourKey)
      .reduce((sum, [, v]) => sum + Math.max(0, Number(v) || 0), 0);
    const attributionRaw =
      (p.get('impressionAttribution') as Record<string, unknown> | null | undefined) ?? {};
    const topCampaigns = Object.entries(attributionRaw)
      .map(([k, v]) => ({ key: k, impressions: Number(v) || 0 }))
      .filter((row) => row.impressions > 0)
      .sort((a, b) => b.impressions - a.impressions)
      .slice(0, 3)
      .map((row) => {
        const [source = '(none)', medium = '(none)', campaign = '(none)'] = row.key.split('|');
        return { source, medium, campaign, impressions: row.impressions };
      });
    const completionRatePct =
      impressionCount > 0 ? Math.min(100, (totalVotes / impressionCount) * 100) : null;
    const ageMinutes =
      Number.isFinite(createdAtMs) && nowMs > createdAtMs
        ? Math.max((nowMs - createdAtMs) / 60000, 1 / 60)
        : null;
    const engagementVelocityVotesPerMin = ageMinutes != null ? totalVotes / ageMinutes : null;
    const firstVoteAtMs =
      row?.first_vote_at instanceof Date
        ? row.first_vote_at.getTime()
        : typeof row?.first_vote_at === 'string'
          ? Date.parse(row.first_vote_at)
          : NaN;
    const timeToFirstVoteMs =
      Number.isFinite(firstVoteAtMs) && Number.isFinite(createdAtMs) && firstVoteAtMs >= createdAtMs
        ? firstVoteAtMs - createdAtMs
        : null;
    const peakHourRow = peakHourByPollId.get(String(p.get('id')));
    const peakHourUtc =
      peakHourRow != null && peakHourRow.peak_hour_utc !== undefined
        ? Number(peakHourRow.peak_hour_utc)
        : null;
    const peakHourVotes = peakHourRow != null ? Number(peakHourRow.peak_hour_votes ?? 0) || 0 : 0;
    const peakDowRow = peakDowByPollId.get(String(p.get('id')));
    const peakDowUtc =
      peakDowRow != null && peakDowRow.peak_dow_utc !== undefined
        ? Number(peakDowRow.peak_dow_utc)
        : null;
    const peakDowVotes = peakDowRow != null ? Number(peakDowRow.peak_dow_votes ?? 0) || 0 : 0;
    const pid = String(p.get('id'));
    const expiration = Number(p.get('expiration')) || 0;
    const retentionTtlDays =
      p.get('retentionTtlDays') == null
        ? null
        : Math.max(1, Number(p.get('retentionTtlDays')) || 0);
    const retentionLegalHold = p.get('retentionLegalHold') === true;
    const autoDeleteAtMs =
      !retentionLegalHold &&
      retentionTtlDays != null &&
      Number.isFinite(expiration) &&
      expiration > 0
        ? expiration + retentionTtlDays * 24 * 60 * 60 * 1000
        : null;
    const hourlyVotesByHourUtc =
      hourlyVotesByPollId.get(pid) ?? Array.from({ length: 24 }, () => 0);
    const weekdayVotesByDowUtc =
      weekdayVotesByPollId.get(pid) ?? Array.from({ length: 7 }, () => 0);
    const configuredOptions = ((p.get('options') as string[] | null | undefined) ?? [])
      .filter((opt) => typeof opt === 'string' && opt.trim() !== '')
      .map((opt) => opt.trim());
    const funnelRows = optionFunnelByPollId.get(String(p.get('id'))) ?? [];
    const funnelByOption = new Map(funnelRows.map((row) => [row.option_label, row]));
    const perOptionFunnel = configuredOptions
      .map((label) => {
        const row = funnelByOption.get(label);
        const votesTotal = row?.votes_total ?? 0;
        const votesLast24hForOption = row?.votes_last_24h ?? 0;
        return {
          option: label,
          votes_total: votesTotal,
          votes_last_24h: votesLast24hForOption,
          conversion_total_pct:
            impressionCount > 0 ? Math.min(100, (votesTotal / impressionCount) * 100) : null,
          conversion_last_24h_pct:
            viewsLast24h > 0 ? Math.min(100, (votesLast24hForOption / viewsLast24h) * 100) : null,
        };
      })
      .sort((a, b) => b.votes_total - a.votes_total);

    return {
      id: p.get('id') as string,
      title: p.get('title') as string,
      archived: !!p.get('archived'),
      createdAt: p.get('createdAt') as Date,
      hasWebhook:
        (
          (p.get('webhookTargets') as
            | Array<{ url?: string; secret?: string }>
            | null
            | undefined) ?? []
        ).filter((t) => typeof t?.url === 'string' && t.url.trim() !== '').length > 0,
      webhook_targets: (
        (p.get('webhookTargets') as
          | Array<{
              url?: string;
              secret?: string;
              hint_locale?: string;
              include_results_snapshot?: boolean;
              include_owner_snapshot?: boolean;
              include_owner_events?: boolean;
            }>
          | null
          | undefined) ?? []
      )
        .map((t) => ({
          url: typeof t?.url === 'string' ? t.url.trim() : '',
          secret:
            typeof t?.secret === 'string' && t.secret.trim() !== '' ? t.secret.trim() : undefined,
          hint_locale:
            typeof t?.hint_locale === 'string' && t.hint_locale.trim() !== ''
              ? t.hint_locale.trim()
              : undefined,
          include_results_snapshot: t?.include_results_snapshot === true ? true : undefined,
          include_owner_snapshot: t?.include_owner_snapshot === true ? true : undefined,
          include_owner_events: t?.include_owner_events === true ? true : undefined,
        }))
        .filter((t) => t.url !== ''),
      phase: (p.get('phase') as string) || 'open',
      voting_paused: !!p.get('votingPaused'),
      pause_message: (p.get('pauseMessage') as string | null | undefined) ?? null,
      show_notes: (p.get('showNotes') as string | null | undefined) ?? null,
      shared_editor_user_ids: Array.isArray(p.get('sharedEditorUserIds'))
        ? ((p.get('sharedEditorUserIds') as unknown[]) ?? [])
            .map((id) => Number(id))
            .filter((id) => Number.isInteger(id) && id > 0)
        : [],
      theme_preset: String(p.get('themePreset') ?? 'default'),
      selection_mode: String(p.get('selectionMode') ?? 'single') === 'multi' ? 'multi' : 'single',
      vote_eligibility: (() => {
        const raw = String(p.get('voteEligibility') ?? 'anonymous');
        return raw === 'account' || raw === 'platform_linked' ? raw : 'anonymous';
      })(),
      platform_identity_provider:
        (p.get('platformIdentityProvider') as string | null | undefined) ?? null,
      platform_identity_consent_version:
        (p.get('platformIdentityConsentVersion') as string | null | undefined) ?? null,
      platform_identity_consent_captured_at_ms:
        (p.get('platformIdentityConsentCapturedAt') as number | null | undefined) ?? null,
      retention_ttl_days: retentionTtlDays,
      retention_legal_hold: retentionLegalHold,
      auto_delete_at_ms: autoDeleteAtMs,
      has_embed_read_token: Boolean(hash),
      open_at: (p.get('openAt') as number | null | undefined) ?? null,
      lock_at: (p.get('lockAt') as number | null | undefined) ?? null,
      reveal_at: (p.get('revealAt') as number | null | undefined) ?? null,
      boosted_voting_enabled: !!p.get('boostedVotingEnabled'),
      max_boost_weight: Number(p.get('maxBoostWeight') ?? 3),
      show_unweighted_values: !!p.get('showUnweightedValues'),
      run_of_show_key: (p.get('runOfShowKey') as string | null | undefined) ?? null,
      run_of_show_order: (p.get('runOfShowOrder') as number | null | undefined) ?? null,
      vanity_slug: (p.get('vanitySlug') as string | null | undefined) ?? null,
      next_poll_id: (p.get('nextPollId') as string | null | undefined) ?? null,
      auto_advance_on_close: !!p.get('autoAdvanceOnClose'),
      vote_friction_tier: String(p.get('voteFrictionTier') ?? 'open'),
      soft_throttle_max_votes_per_min: Number(p.get('softThrottleMaxVotesPerMin') ?? 30),
      pow_difficulty: Number(p.get('powDifficulty') ?? 4),
      allow_write_in: !!p.get('allowWriteIn'),
      write_in_max_length: Number(p.get('writeInMaxLength') ?? 80),
      write_in_blocklist: ((p.get('writeInBlocklist') as string[] | null | undefined) ?? []).filter(
        (s) => typeof s === 'string' && s.trim() !== '',
      ),
      write_in_profanity_filter: p.get('writeInProfanityFilter') !== false,
      results_delay_seconds: Number(p.get('resultsDelaySeconds') ?? 0),
      impression_count: impressionCount,
      views_last_24h: viewsLast24h,
      top_campaigns: topCampaigns,
      total_votes: totalVotes,
      votes_last_5m: votesLast5m,
      votes_last_24h: votesLast24h,
      completion_rate_pct: completionRatePct,
      conversion_rate_last_24h_pct:
        viewsLast24h > 0 ? Math.min(100, (votesLast24h / viewsLast24h) * 100) : null,
      per_option_funnel: perOptionFunnel,
      engagement_velocity_votes_per_min: engagementVelocityVotesPerMin,
      time_to_first_vote_ms: timeToFirstVoteMs,
      peak_hour_utc: Number.isInteger(peakHourUtc) ? peakHourUtc : null,
      peak_hour_votes: peakHourVotes,
      peak_dow_utc: Number.isInteger(peakDowUtc) ? peakDowUtc : null,
      peak_dow_votes: peakDowVotes,
      hourly_votes_by_hour_utc: hourlyVotesByHourUtc,
      weekday_votes_by_dow_utc: weekdayVotesByDowUtc,
    };
  });

  return { polls, total: count, limit, offset };
}
