import { QueryTypes } from 'sequelize';
import db from '../connections';

export type PollPhaseActorType = 'owner_jwt' | 'api_key' | 'admin_token';

type RecordPollPhaseTransitionInput = {
  pollId: string;
  fromPhase: string | null;
  toPhase: string;
  actorType: PollPhaseActorType;
  actorUserId?: number | null;
  source: string;
};

export type PollPhaseHistoryEntry = {
  from_phase: string | null;
  to_phase: string;
  at: string;
  actor_type: PollPhaseActorType;
  actor_user_id: number | null;
  source: string;
};

export async function recordPollPhaseTransition(
  input: RecordPollPhaseTransitionInput,
): Promise<void> {
  await db.query(
    `INSERT INTO poll_phase_events
      ("pollId", "fromPhase", "toPhase", "actorType", "actorUserId", source, "createdAt")
     VALUES
      (:pollId, :fromPhase, :toPhase, :actorType, :actorUserId, :source, NOW())`,
    {
      replacements: {
        pollId: input.pollId,
        fromPhase: input.fromPhase,
        toPhase: input.toPhase,
        actorType: input.actorType,
        actorUserId: input.actorUserId ?? null,
        source: input.source,
      },
      type: QueryTypes.INSERT,
    },
  );
}

export async function listPollPhaseHistory(
  pollId: string,
  opts?: { limit?: number },
): Promise<PollPhaseHistoryEntry[]> {
  const limit = Math.max(1, Math.min(200, Number(opts?.limit ?? 20)));
  const rows = await db.query<{
    fromPhase: string | null;
    toPhase: string;
    createdAt: string | Date;
    actorType: PollPhaseActorType;
    actorUserId: number | null;
    source: string;
  }>(
    `SELECT "fromPhase", "toPhase", "createdAt", "actorType", "actorUserId", source
     FROM poll_phase_events
     WHERE "pollId" = :pollId
     ORDER BY "createdAt" ASC
     LIMIT :limit`,
    { replacements: { pollId, limit }, type: QueryTypes.SELECT },
  );
  return rows.map((r) => ({
    from_phase: r.fromPhase,
    to_phase: r.toPhase,
    at: new Date(r.createdAt).toISOString(),
    actor_type: r.actorType,
    actor_user_id: r.actorUserId,
    source: r.source,
  }));
}
