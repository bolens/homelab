import { Op } from 'sequelize';
import Vote from '../model/Vote';
import AuditLog from '../models/auditlog.sequelize';
import { trustStackSafeguardTags } from './trustStackSignals';

const OWNER_EVENTS_WINDOW_MS = 60 * 60 * 1000;
const OWNER_EVENTS_MAX_ITEMS = 10;

type VoteRow = {
  get(key: string): unknown;
};

type AuditRow = {
  get(key: string): unknown;
};

/**
 * Sensitive owner-side automation context for opted-in webhook targets only.
 * Bounded, aggregate-friendly, and intentionally excludes raw identity surfaces.
 */
export async function fetchPollWebhookOwnerEvents(args: {
  pollId: string;
}): Promise<Record<string, unknown>> {
  const { pollId } = args;
  const windowStart = new Date(Date.now() - OWNER_EVENTS_WINDOW_MS);

  const quarantinedRows = (await Vote.findAll({
    where: { pollId, isQuarantined: true },
    attributes: ['id', 'quarantineReason', 'trustRiskScore', 'createdAt', 'quarantineStatus'],
    order: [['createdAt', 'DESC']],
    limit: OWNER_EVENTS_MAX_ITEMS + 1,
  })) as VoteRow[];

  const moderationRows = (await AuditLog.findAll({
    where: {
      target: `poll:${pollId}`,
      action: { [Op.in]: ['moderation.batch.remove', 'moderation.batch.restore'] },
      createdAt: { [Op.gte]: windowStart },
    },
    attributes: ['action', 'actor', 'details', 'createdAt'],
    order: [['createdAt', 'DESC']],
    limit: OWNER_EVENTS_MAX_ITEMS + 1,
  })) as AuditRow[];

  const quarantineRecent = quarantinedRows.slice(0, OWNER_EVENTS_MAX_ITEMS).map((row) => ({
    vote_id: String(row.get('id') ?? ''),
    reason: row.get('quarantineReason') == null ? null : String(row.get('quarantineReason')),
    risk_score: row.get('trustRiskScore') == null ? null : Number(row.get('trustRiskScore')) || 0,
    created_at_ms: new Date(String(row.get('createdAt'))).getTime(),
    state: String(row.get('quarantineStatus') ?? 'pending'),
  }));

  const moderationActionsRecent = moderationRows.slice(0, OWNER_EVENTS_MAX_ITEMS).map((row) => {
    const detailsRaw = row.get('details');
    const details =
      detailsRaw && typeof detailsRaw === 'object' && !Array.isArray(detailsRaw)
        ? (detailsRaw as Record<string, unknown>)
        : {};
    const actor = row.get('actor');
    return {
      action: String(row.get('action') ?? ''),
      actor_role: actor === 'api_key' ? 'api_key' : 'owner',
      count:
        typeof details['affected_count'] === 'number'
          ? details['affected_count']
          : Number(details['affected_count'] ?? 0) || 0,
      created_at_ms: new Date(String(row.get('createdAt'))).getTime(),
    };
  });

  return {
    captured_at_ms: Date.now(),
    window_ms: OWNER_EVENTS_WINDOW_MS,
    safeguard_tags: trustStackSafeguardTags(),
    quarantine_recent: quarantineRecent,
    moderation_actions_recent: moderationActionsRecent,
    truncated: {
      quarantine_recent: quarantinedRows.length > OWNER_EVENTS_MAX_ITEMS,
      moderation_actions_recent: moderationRows.length > OWNER_EVENTS_MAX_ITEMS,
    },
  };
}
