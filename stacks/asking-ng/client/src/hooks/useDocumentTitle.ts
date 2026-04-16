import { useEffect } from 'react';

const baseTitle = () => String(import.meta.env.VITE_APP_NAME || 'asking-ng');

/**
 * Sets `document.title` to `fragment · ${VITE_APP_NAME}` when `fragment` is non-empty,
 * otherwise just the app name. Restores the previous title on unmount or when `fragment` clears.
 */
export function useDocumentTitle(fragment: string | undefined | null): void {
  useEffect(() => {
    const base = baseTitle();
    const prev = document.title;
    const t = fragment?.trim();
    document.title = t ? `${t} · ${base}` : base;
    return () => {
      document.title = prev;
    };
  }, [fragment]);
}
