import type { VotePollBody } from '@asking-ng/contracts/poll';
import type { AppRequestHandler } from '../../types/http';
import { jsonError } from '../../lib/jsonError';
import { loggerForRequest } from '../../lib/logger';
import { singleString } from '../../utils/http';
import { presentVoteIdempotentReplay, presentVoteSuccess } from './voteOnPoll.presenter';
import { voteOnPollService } from './voteOnPoll.service';

const voteOnPoll: AppRequestHandler = async (req, res) => {
  const pollId = singleString(req.params.id);
  const body = req.body as VotePollBody;

  if (!pollId) {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Poll id is required.');
    return;
  }

  try {
    const result = await voteOnPollService(req, pollId, body);

    if (result.kind === 'not_found') {
      jsonError(res, req, 404, 'NOT_FOUND', 'Poll not found.');
      return;
    }
    if (result.kind === 'forbidden_embed_token') {
      jsonError(
        res,
        req,
        403,
        'POLL_EMBED_TOKEN_REQUIRED',
        'Valid embed_token query parameter or X-Poll-Embed-Token header is required for this poll.',
      );
      return;
    }
    if (result.kind === 'poll_archived') {
      jsonError(res, req, 400, 'POLL_ARCHIVED', 'Poll is archived.');
      return;
    }
    if (result.kind === 'poll_not_accepting_votes') {
      jsonError(
        res,
        req,
        400,
        'POLL_NOT_ACCEPTING_VOTES',
        'This poll is not accepting votes right now.',
      );
      return;
    }
    if (result.kind === 'poll_voting_paused') {
      jsonError(res, req, 400, 'POLL_VOTING_PAUSED', 'Voting is temporarily paused for this poll.');
      return;
    }
    if (result.kind === 'vote_requires_sign_in') {
      jsonError(
        res,
        req,
        401,
        'VOTE_REQUIRES_SIGN_IN',
        'This poll only accepts votes from signed-in users. Send Authorization: Bearer with a valid user JWT.',
      );
      return;
    }
    if (result.kind === 'platform_identity_not_configured') {
      jsonError(
        res,
        req,
        400,
        'PLATFORM_IDENTITY_NOT_CONFIGURED',
        'This poll requires platform-linked identity, but provider configuration is missing.',
      );
      return;
    }
    if (result.kind === 'platform_identity_required') {
      jsonError(
        res,
        req,
        400,
        'PLATFORM_IDENTITY_REQUIRED',
        'This poll requires x-platform-subject (and optional x-platform-provider) headers.',
      );
      return;
    }
    if (result.kind === 'platform_identity_provider_mismatch') {
      jsonError(
        res,
        req,
        400,
        'PLATFORM_IDENTITY_PROVIDER_MISMATCH',
        `Platform identity provider mismatch. Expected ${result.expectedProvider}, got ${result.receivedProvider}.`,
      );
      return;
    }
    if (result.kind === 'boost_weight_disabled') {
      jsonError(
        res,
        req,
        400,
        'BOOST_WEIGHT_DISABLED',
        'boost_weight is only allowed when boosted voting is enabled for this poll.',
      );
      return;
    }
    if (result.kind === 'invalid_boost_weight') {
      jsonError(
        res,
        req,
        400,
        'INVALID_BOOST_WEIGHT',
        `boost_weight must be between 1 and ${result.maxBoostWeight}.`,
      );
      return;
    }
    if (result.kind === 'poll_soft_throttled') {
      jsonError(
        res,
        req,
        429,
        'POLL_SOFT_THROTTLED',
        `Too many recent votes from your source. Limit is ${result.softThrottleMaxVotesPerMin}/min for this poll.`,
      );
      return;
    }
    if (result.kind === 'pow_required') {
      jsonError(
        res,
        req,
        400,
        'POW_REQUIRED',
        `pow_nonce is required and must satisfy SHA-256(${result.pollId}:nonce) starting with ${'0'.repeat(result.powDifficulty)}.`,
      );
      return;
    }
    if (result.kind === 'invalid_option_index') {
      jsonError(res, req, 400, 'INVALID_OPTION_INDEX', 'option_index is out of range for this poll.');
      return;
    }
    if (result.kind === 'invalid_option_indices') {
      jsonError(
        res,
        req,
        400,
        'INVALID_OPTION_INDICES',
        'One or more option_indices are out of range for this poll.',
      );
      return;
    }
    if (result.kind === 'vote_shape_mismatch') {
      jsonError(res, req, 400, 'VOTE_SHAPE_MISMATCH', result.detail);
      return;
    }
    if (result.kind === 'invalid_write_in') {
      jsonError(res, req, 400, result.code, result.message);
      return;
    }
    if (result.kind === 'poll_expired') {
      jsonError(res, req, 400, 'POLL_EXPIRED', 'Poll has expired.');
      return;
    }
    if (result.kind === 'channel_rate_limited') {
      jsonError(
        res,
        req,
        429,
        'CHANNEL_RATE_LIMITED',
        `Too many chat votes for this channel. Limit is ${result.perChannelMax}/min.`,
      );
      return;
    }
    if (result.kind === 'idempotent_replay') {
      res.status(200).json(presentVoteIdempotentReplay(result.vote, result.ballotVotes));
      return;
    }
    if (result.kind === 'duplicate_vote') {
      jsonError(res, req, 409, 'DUPLICATE_VOTE', 'You already voted on this poll.');
      return;
    }
    if (result.kind === 'usage_limit_votes_month') {
      jsonError(res, req, 403, 'USAGE_LIMIT_VOTES', 'Monthly vote limit reached for this poll owner billing plan.', {
        max: result.max,
        current: result.current,
        plan: result.plan,
        incoming: result.incoming,
      });
      return;
    }

    res.status(200).json(
      presentVoteSuccess({
        vote: result.vote,
        ballot_votes: result.ballotVotes,
        option_indices: result.optionIndices,
        moderation: result.moderation,
      }),
    );
  } catch (err: unknown) {
    loggerForRequest(req).error({ event: 'poll.vote.unhandled_error', err, pollId }, 'voteOnPoll');
    throw err instanceof Error ? err : new Error(String(err), { cause: err });
  }
};

export default voteOnPoll;
