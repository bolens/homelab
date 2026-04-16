/** Browser session JWT for `Authorization: Bearer` (e.g. superadmin actions on `/users`). */
const STORAGE_KEY = 'askingNgUserJwt';

const AUTH_CHANGE_EVENT = 'asking-ng-user-jwt-changed';

function notifyUserJwtChanged(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function subscribeUserJwtChanged(fn: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  window.addEventListener(AUTH_CHANGE_EVENT, fn);
  return () => window.removeEventListener(AUTH_CHANGE_EVENT, fn);
}

export function getStoredUserJwt(): string | null {
  try {
    const v = sessionStorage.getItem(STORAGE_KEY)?.trim();
    return v || null;
  } catch {
    return null;
  }
}

export function setStoredUserJwt(token: string): void {
  sessionStorage.setItem(STORAGE_KEY, token.trim());
  notifyUserJwtChanged();
}

export function clearStoredUserJwt(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
    notifyUserJwtChanged();
  } catch {
    /* private mode / quota */
  }
}
