import { useSyncExternalStore } from 'react';

const QUERY = '(max-width: 600px)';

/**
 * True when the viewport matches the same breakpoint as mobile bulk-action UI.
 * Uses `matchMedia` + `useSyncExternalStore` for correct SSR and subscription semantics.
 */
export function useMaxWidth600(): boolean {
  return useSyncExternalStore(
    (onStoreChange) => {
      if (typeof window === 'undefined') return () => {};
      const mq = window.matchMedia(QUERY);
      mq.addEventListener('change', onStoreChange);
      return () => mq.removeEventListener('change', onStoreChange);
    },
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}
