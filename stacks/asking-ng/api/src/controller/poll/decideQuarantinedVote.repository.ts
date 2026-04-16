import Poll from '../../model/Poll';
import Vote from '../../model/Vote';
import AuditLog from '../../models/auditlog.sequelize';

export async function findPollById(pollId: string) {
  return Poll.findByPk(pollId);
}

export async function findVoteById(voteId: string) {
  return Vote.findByPk(voteId);
}

export async function updateQuarantineDecision(args: {
  pollId: string;
  voteId: string;
  isQuarantined: boolean;
  quarantineStatus: 'pending' | 'approved' | 'rejected';
  quarantineDecidedAt: Date | null;
  quarantineDecidedBy: number | null;
  quarantineNote: string | null;
}) {
  return Vote.update(
    {
      isQuarantined: args.isQuarantined,
      quarantineStatus: args.quarantineStatus,
      quarantineDecidedAt: args.quarantineDecidedAt,
      quarantineDecidedBy: args.quarantineDecidedBy,
      quarantineNote: args.quarantineNote,
    },
    { where: { id: args.voteId, pollId: args.pollId } },
  );
}

export async function createModerationAuditLog(args: {
  action: string;
  actor: string;
  target: string;
  details: Record<string, unknown>;
}) {
  return AuditLog.create({
    action: args.action,
    actor: args.actor,
    target: args.target,
    details: args.details,
  });
}
