/** Cross-tab channel so multiple poll tabs stay in sync. */
const POLL_SYNC_CHANNEL = 'asking-ng-poll-sync';

type PollSyncMessage = { type: 'invalidate'; pollId: string } | { type: 'voted'; pollId: string };

export function openPollSyncChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === 'undefined') return null;
  try {
    return new BroadcastChannel(POLL_SYNC_CHANNEL);
  } catch {
    return null;
  }
}

export function postPollSync(ch: BroadcastChannel | null, msg: PollSyncMessage): void {
  if (!ch) return;
  try {
    ch.postMessage(msg);
  } catch {
    // ignore
  }
}
