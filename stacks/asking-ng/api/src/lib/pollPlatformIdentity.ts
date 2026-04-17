import { QueryTypes } from 'sequelize';
import db from '../connections';

export async function recordPlatformIdentityConsentEvent(args: {
  pollId: string;
  provider: string;
  consentVersion: string;
  capturedAtMs: number;
  actorUserId: number | null;
  source: 'poll_create' | 'poll_update';
}): Promise<void> {
  await db.query(
    `INSERT INTO poll_platform_identity_consent_history
      (poll_id, platform_identity_provider, platform_identity_consent_version,
       platform_identity_consent_captured_at, actor_user_id, source)
     VALUES
      (:pollId, :provider, :consentVersion, :capturedAtMs, :actorUserId, :source)`,
    {
      replacements: {
        pollId: args.pollId,
        provider: args.provider,
        consentVersion: args.consentVersion,
        capturedAtMs: args.capturedAtMs,
        actorUserId: args.actorUserId,
        source: args.source,
      },
      type: QueryTypes.INSERT,
    },
  );
}

export async function upsertPlatformIdentityMapping(args: {
  pollId: string;
  provider: string;
  subjectHash: string;
  userId: number | null;
  voteId: string;
}): Promise<void> {
  await db.query(
    `INSERT INTO poll_platform_identity_mappings
      (poll_id, platform_identity_provider, platform_identity_subject_hash, user_id, vote_count, last_vote_id, first_seen_at, last_seen_at)
     VALUES
      (:pollId, :provider, :subjectHash, :userId, 1, :voteId, NOW(), NOW())
     ON CONFLICT (poll_id, platform_identity_provider, platform_identity_subject_hash)
     DO UPDATE SET
      user_id = COALESCE(EXCLUDED.user_id, poll_platform_identity_mappings.user_id),
      vote_count = poll_platform_identity_mappings.vote_count + 1,
      last_vote_id = EXCLUDED.last_vote_id,
      last_seen_at = NOW()`,
    {
      replacements: {
        pollId: args.pollId,
        provider: args.provider,
        subjectHash: args.subjectHash,
        userId: args.userId,
        voteId: args.voteId,
      },
      type: QueryTypes.INSERT,
    },
  );
}
