// Modified 2026-10-22. GPL-3.0. Personal actions never use catalog capabilities.
export interface IndependentCapability {
  name: string;
  available: boolean;
  capabilities: string[];
  adapters?: {sync?: {available: boolean; capabilities: string[]}};
}
const names: Record<number, string> = {1: 'AniList', 2: 'MyAnimeList', 5: 'Hardcover', 6: 'MangaBaka'};
const actions: Record<number, string> = {0: 'progress', 1: 'wantToRead', 2: 'safeWantToReadRemoval', 3: 'ratings', 4: 'reviews', 5: 'readingStatus'};
export function personalSyncActions(providers: IndependentCapability[]): Record<number, string[]> {
  const result: Record<number, string[]> = {};
  for (const [id, name] of Object.entries(names)) {
    const found = providers.filter(p => p.name === name);
    const sync = found.length === 1 ? found[0].adapters?.sync : undefined;
    if (found[0]?.available === true && sync?.available === true && Array.isArray(sync.capabilities) &&
        sync.capabilities.every(c => typeof c === 'string')) result[Number(id)] = sync.capabilities;
  }
  return result;
}
export function supportsSyncAction(available: Record<number, string[]>, provider: number, event: number): boolean {
  const action = actions[event];
  const supplied = available[provider] ?? [];
  return !!action && (supplied.includes(action) || action === 'progress' && supplied.includes('progressWithExistingEdition'));
}
