import { useSyncExternalStore } from 'react';
import { COLOR_THEME_EVENT, COLOR_THEME_STORAGE_KEY } from '../theme/colorTheme';

function subscribe(onStoreChange: () => void) {
  if (typeof window === 'undefined' || typeof document === 'undefined') return () => {};
  const mq =
    typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-color-scheme: dark)')
      : null;
  const onMq = () => onStoreChange();
  mq?.addEventListener('change', onMq);
  window.addEventListener(COLOR_THEME_EVENT, onStoreChange);
  const onStorage = (e: StorageEvent) => {
    if (e.key === COLOR_THEME_STORAGE_KEY) onStoreChange();
  };
  window.addEventListener('storage', onStorage);
  return () => {
    mq?.removeEventListener('change', onMq);
    window.removeEventListener(COLOR_THEME_EVENT, onStoreChange);
    window.removeEventListener('storage', onStorage);
  };
}

function getSnapshot() {
  if (typeof document === 'undefined') return false;
  return document.documentElement.getAttribute('data-bs-theme') === 'dark';
}

function getServerSnapshot() {
  return false;
}

/** Matches `data-bs-theme` on `<html>` for Bootstrap navbar variant. */
export function useBootstrapNavDark(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
