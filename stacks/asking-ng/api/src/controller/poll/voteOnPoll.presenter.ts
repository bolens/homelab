export function presentVoteSuccess(payload: {
  vote: unknown;
  ballot_votes?: unknown[];
  option_indices?: number[];
  moderation?: { quarantined: true; reason: string | null; trust_risk_score: number | null };
}): Record<string, unknown> {
  return {
    status: 'success',
    data: payload.vote,
    ...(payload.ballot_votes && payload.ballot_votes.length > 0
      ? { ballot_votes: payload.ballot_votes, option_indices: payload.option_indices ?? [] }
      : {}),
    ...(payload.moderation ? { moderation: payload.moderation } : {}),
  };
}

export function presentVoteIdempotentReplay(
  vote: unknown,
  ballotVotes?: unknown[],
): Record<string, unknown> {
  return {
    status: 'success',
    data: vote,
    ...(ballotVotes && ballotVotes.length > 0 ? { ballot_votes: ballotVotes } : {}),
    idempotent_replay: true,
  };
}
