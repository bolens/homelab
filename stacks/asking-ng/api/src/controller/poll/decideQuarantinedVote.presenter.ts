export function presentDecideQuarantinedVote(payload: {
  voteId: string;
  quarantineStatus: 'pending' | 'approved' | 'rejected';
  isQuarantined: boolean;
}): Record<string, unknown> {
  return {
    status: 'success',
    data: {
      vote_id: payload.voteId,
      quarantine_status: payload.quarantineStatus,
      is_quarantined: payload.isQuarantined,
    },
  };
}
