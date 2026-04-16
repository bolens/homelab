export const HIGH_CONTRAST_STORAGE_KEY = 'asking-ng-high-contrast';

export const HIGH_CONTRAST_EVENT = 'askingng-high-contrast';

function dispatch(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(HIGH_CONTRAST_EVENT));
}

function applyHighContrast(on: boolean): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (on) root.setAttribute('data-high-contrast', 'on');
  else root.removeAttribute('data-high-contrast');
  dispatch();
}

export function readStoredHighContrast(): boolean {
  if (typeof localStorage === 'undefined') return false;
  try {
    return localStorage.getItem(HIGH_CONTRAST_STORAGE_KEY) === 'on';
  } catch {
    return false;
  }
}

export function setHighContrast(on: boolean): void {
  try {
    if (on) localStorage.setItem(HIGH_CONTRAST_STORAGE_KEY, 'on');
    else localStorage.removeItem(HIGH_CONTRAST_STORAGE_KEY);
  } catch {
    /* private mode / quota */
  }
  applyHighContrast(on);
}

function applyFromStorage(): void {
  applyHighContrast(readStoredHighContrast());
}

export function subscribeHighContrast(): () => void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return () => {};

  applyFromStorage();

  const onStorage = (e: StorageEvent) => {
    if (e.key === HIGH_CONTRAST_STORAGE_KEY) applyFromStorage();
  };
  window.addEventListener('storage', onStorage);

  return () => {
    window.removeEventListener('storage', onStorage);
  };
}
