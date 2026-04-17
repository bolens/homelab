import { QueryTypes } from 'sequelize';
import db from '../connections';
import { computePollWebhookPublicDelayWindow } from './pollWebhookDelayWindow';

type VoteTallyRow = {
  option: string;
  vote_count: string | number;
  weighted_vote_count: string | number;
};

function buildOptionVoteRow(
  label: string,
  cell: { vc: number; wv: number },
  boostedVotingEnabled: boolean,
  showUnweightedValues: boolean,
): Record<string, unknown> {
  const base: Record<string, unknown> = {
    option: label,
    vote_count: boostedVotingEnabled ? cell.wv : cell.vc,
  };
  if (boostedVotingEnabled && showUnweightedValues) {
    base.unweighted_vote_count = cell.vc;
  }
  if (boostedVotingEnabled) {
    base.weighted_vote_count = cell.wv;
  }
  return base;
}

/**
 * Public-consumer tallies (excludes quarantined votes), aligned with `GET /poll/:id` delay window
 * when results are delayed during `open` phase.
 */
export async function fetchPollWebhookPublicResultsSnapshot(args: {
  pollId: string;
  poll: { get(key: string): unknown };
}): Promise<Record<string, unknown>> {
  const { pollId, poll } = args;
  const delay = computePollWebhookPublicDelayWindow(poll);
  const {
    now,
    effectivePhase,
    liveResultsAreDelayed,
    resultsVisibleThroughMs,
    resultsVisibleThroughIso,
  } = delay;
  const liveVoteWindowSql = liveResultsAreDelayed
    ? `AND "createdAt" <= :resultsVisibleThrough`
    : ``;

  const configuredOptions = ((poll.get('options') as string[]) || []).filter(
    (s) => typeof s === 'string' && s.trim() !== '',
  );
  const boostedVotingEnabled = Boolean(poll.get('boostedVotingEnabled'));
  const showUnweightedValues = Boolean(poll.get('showUnweightedValues'));

  const rows = (await db.query(
    `SELECT option, count(option) as vote_count, COALESCE(sum(weight), count(option)) as weighted_vote_count
     FROM votes
     WHERE "pollId" = :pollId
       AND COALESCE("isQuarantined", false) = false
       ${liveVoteWindowSql}
     GROUP BY option`,
    {
      replacements: { pollId, resultsVisibleThrough: resultsVisibleThroughIso },
      type: QueryTypes.SELECT,
    },
  )) as VoteTallyRow[];

  const byOption = new Map<string, { vc: number; wv: number }>();
  for (const row of rows) {
    const opt = String(row.option ?? '');
    byOption.set(opt, {
      vc: Number(row.vote_count) || 0,
      wv: Number(row.weighted_vote_count) || 0,
    });
  }

  const seen = new Set(configuredOptions);
  const optionsOut: Record<string, unknown>[] = configuredOptions.map((label) =>
    buildOptionVoteRow(
      label,
      byOption.get(label) ?? { vc: 0, wv: 0 },
      boostedVotingEnabled,
      showUnweightedValues,
    ),
  );

  for (const row of rows) {
    const opt = String(row.option ?? '');
    if (!opt || seen.has(opt)) continue;
    seen.add(opt);
    const cell = {
      vc: Number(row.vote_count) || 0,
      wv: Number(row.weighted_vote_count) || 0,
    };
    optionsOut.push(buildOptionVoteRow(opt, cell, boostedVotingEnabled, showUnweightedValues));
  }

  let totalVotes = 0;
  let totalWeighted = 0;
  for (const row of rows) {
    totalVotes += Number(row.vote_count) || 0;
    totalWeighted += Number(row.weighted_vote_count) || 0;
  }

  return {
    captured_at_ms: now,
    effective_phase: effectivePhase,
    results_delay_applied: liveResultsAreDelayed,
    results_visible_through_ms: resultsVisibleThroughMs,
    boosted_voting_enabled: boostedVotingEnabled,
    options: optionsOut,
    metrics: {
      total_votes: totalVotes,
      total_weighted_votes: totalWeighted,
    },
  };
}
