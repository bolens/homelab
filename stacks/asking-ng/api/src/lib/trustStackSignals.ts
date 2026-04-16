import { appEnv } from './env';

/** Owner-visible summary of stack-level burst auto-quarantine (see `TRUST_*_BURST_*`). */
export type TrustBurstOwnerSummary =
  | { enabled: false }
  | { enabled: true; window_sec: number; vote_threshold: number };

export function trustIpBurstOwnerSummary(): TrustBurstOwnerSummary {
  if (appEnv.trustIpBurstVoteThreshold <= 0) return { enabled: false };
  return {
    enabled: true,
    window_sec: appEnv.trustIpBurstWindowSec,
    vote_threshold: appEnv.trustIpBurstVoteThreshold,
  };
}

export function trustChatBurstOwnerSummary(): TrustBurstOwnerSummary {
  if (appEnv.trustChatBurstVoteThreshold <= 0) return { enabled: false };
  return {
    enabled: true,
    window_sec: appEnv.trustChatBurstWindowSec,
    vote_threshold: appEnv.trustChatBurstVoteThreshold,
  };
}

/** Tags appended to `integrity_panel.safeguards_applied` for enabled stack trust modes. */
export function trustStackSafeguardTags(): string[] {
  const tags: string[] = [];
  if (trustIpBurstOwnerSummary().enabled) tags.push('trust_stack:ip_burst');
  if (trustChatBurstOwnerSummary().enabled) tags.push('trust_stack:chat_burst');
  return tags;
}
