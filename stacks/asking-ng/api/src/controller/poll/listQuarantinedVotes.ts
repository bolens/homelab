import type { ListQuarantinedVotesQuery } from '@asking-ng/contracts/poll';
import { Op } from 'sequelize';
import { jsonError } from '../../lib/jsonError';
import Poll from '../../model/Poll';
import Vote from '../../model/Vote';
import type { AppRequestHandler } from '../../types/http';
import { singleString } from '../../utils/http';

function apiKeyFrom(req: Parameters<AppRequestHandler>[0]): string | undefined {
  const v = req.headers.api_key;
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v[0];
  return undefined;
}

const listQuarantinedVotes: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params.id);
  const { status, limit, offset } = req.validatedQuery as ListQuarantinedVotesQuery;
  const apiKey = apiKeyFrom(req);

  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  const poll = await Poll.findByPk(pollId);
  if (!poll) {
    jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
    return;
  }

  const targetApiKey = poll.get('api_key') as string | undefined;
  const apiKeyTrim = typeof apiKey === 'string' ? apiKey.trim() : '';
  const apiKeyOk = apiKeyTrim !== '' && apiKeyTrim === targetApiKey;
  const ownerId = poll.get('creatorUserId') as number | null | undefined;
  const jwtOk = req.user != null && ownerId != null && Number(ownerId) === Number(req.user.id);
  if (!apiKeyOk && !jwtOk) {
    jsonError(
      res,
      req,
      401,
      'UNAUTHORIZED',
      'Valid api_key header or signed-in poll owner (Authorization: Bearer) is required.',
    );
    return;
  }

  const statusFilter = status === 'all' ? { [Op.in]: ['pending', 'approved', 'rejected'] } : status;
  const rows = await Vote.findAll({
    where: {
      pollId,
      [Op.or]: [{ isQuarantined: true }, { quarantineStatus: { [Op.ne]: null } }],
      quarantineStatus: statusFilter,
    },
    attributes: [
      'id',
      'option',
      'weight',
      'sourceIpHash',
      'userId',
      'createdAt',
      'isQuarantined',
      'quarantineReason',
      'quarantineStatus',
      'quarantineDecidedAt',
      'quarantineDecidedBy',
      'quarantineNote',
      'trustRiskScore',
    ],
    order: [['createdAt', 'DESC']],
    limit,
    offset,
  });

  res.status(200).json({
    status: 'success',
    data: rows.map((row) => ({
      id: row.get('id'),
      option: row.get('option'),
      weight: Number(row.get('weight') ?? 1) || 1,
      source_ip_hash: row.get('sourceIpHash') ?? null,
      user_id: row.get('userId') ?? null,
      created_at: row.get('createdAt'),
      is_quarantined: !!row.get('isQuarantined'),
      quarantine_reason: row.get('quarantineReason') ?? null,
      quarantine_status: row.get('quarantineStatus') ?? null,
      quarantine_decided_at: row.get('quarantineDecidedAt') ?? null,
      quarantine_decided_by: row.get('quarantineDecidedBy') ?? null,
      quarantine_note: row.get('quarantineNote') ?? null,
      trust_risk_score:
        row.get('trustRiskScore') == null ? null : Number(row.get('trustRiskScore')) || null,
    })),
  });
};

export default listQuarantinedVotes;
