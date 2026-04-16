import { Op } from 'sequelize';
import Poll from '../../model/Poll';
import Vote from '../../model/Vote';
import AuditLog from '../../models/auditlog.sequelize';

export async function findPollById(pollId: string) {
  return Poll.findByPk(pollId);
}

export async function applyModerationBatch(args: {
  pollId: string;
  selector: 'source_ip_hash' | 'user_id';
  selectorValue: string;
  action: 'remove' | 'restore';
  reasonCode: string;
  note: string | null;
  actorUserId: number | null;
}) {
  const where: { pollId: string; sourceIpHash?: string; userId?: number; [k: symbol]: unknown } = {
    pollId: args.pollId,
  };
  if (args.selector === 'source_ip_hash') where.sourceIpHash = args.selectorValue;
  if (args.selector === 'user_id') where.userId = Number.parseInt(args.selectorValue, 10) || -1;

  if (args.action === 'remove') {
    where[Op.or] = [{ isQuarantined: false }, { quarantineStatus: 'approved' }, { quarantineStatus: null }];
  } else {
    where[Op.or] = [{ isQuarantined: true }, { quarantineStatus: { [Op.in]: ['pending', 'rejected'] } }];
  }

  const updates =
    args.action === 'remove'
      ? {
          isQuarantined: true,
          quarantineReason: `batch_${args.reasonCode}`,
          quarantineStatus: 'rejected',
          quarantineDecidedAt: new Date(),
          quarantineDecidedBy: args.actorUserId,
          quarantineNote: args.note,
        }
      : {
          isQuarantined: false,
          quarantineStatus: 'approved',
          quarantineDecidedAt: new Date(),
          quarantineDecidedBy: args.actorUserId,
          quarantineNote: args.note,
        };

  return Vote.update(updates, { where });
}

export async function createModerationBatchAuditLog(args: {
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
