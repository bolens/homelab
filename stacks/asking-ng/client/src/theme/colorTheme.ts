export const COLOR_THEME_STORAGE_KEY = 'asking-ng-color-theme';

export const COLOR_THEME_EVENT = 'askingng-colortheme';

/** Built-in + popular community palettes (Bootstrap stays light/dark for components). */
export const COLOR_THEME_IDS = [
  'system',
  'light',
  'dark',
  'dracula',
  'solarized-dark',
  'solarized-light',
  'nord',
  'gruvbox-dark',
  'gruvbox-light',
  'catppuccin-mocha',
  'tokyo-night',
] as const;

export type ColorThemeId = (typeof COLOR_THEME_IDS)[number];

const DEFAULT_THEME: ColorThemeId = 'system';

function isColorThemeId(value: string): value is ColorThemeId {
  return (COLOR_THEME_IDS as readonly string[]).includes(value);
}

export function readStoredThemeId(): ColorThemeId {
  if (typeof localStorage === 'undefined') return DEFAULT_THEME;
  try {
    const raw = localStorage.getItem(COLOR_THEME_STORAGE_KEY);
    if (!raw || !isColorThemeId(raw)) return DEFAULT_THEME;
    return raw;
  } catch {
    return DEFAULT_THEME;
  }
}

/** Bootstrap `data-bs-theme` for navbar / native form chrome. */
function bootstrapModeFor(themeId: ColorThemeId): 'light' | 'dark' {
  if (themeId === 'system') {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'light';
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  if (themeId === 'light' || themeId === 'solarized-light' || themeId === 'gruvbox-light')
    return 'light';
  if (themeId === 'dark') return 'dark';
  return 'dark';
}

/** Toolbar / PWA `theme-color` (surface); matches active palette. */
const THEME_COLOR_HEX: Record<ColorThemeId, string> = {
  system: '#ffffff',
  light: '#ffffff',
  dark: '#18181b',
  dracula: '#282a36',
  'solarized-dark': '#002b36',
  'solarized-light': '#fdf6e3',
  nord: '#2e3440',
  'gruvbox-dark': '#282828',
  'gruvbox-light': '#fbf1c7',
  'catppuccin-mocha': '#1e1e2e',
  'tokyo-night': '#1a1b26',
};

/** Resolved surface color for `<meta name="theme-color">` and web manifest. */
function themeSurfaceHex(themeId: ColorThemeId): string {
  const mode = bootstrapModeFor(themeId);
  return themeId === 'system'
    ? mode === 'dark'
      ? '#18181b'
      : '#ffffff'
    : THEME_COLOR_HEX[themeId];
}

function syncThemeColorMeta(themeId: ColorThemeId): void {
  if (typeof document === 'undefined') return;
  const hex = themeSurfaceHex(themeId);
  let el = document.getElementById('asking-theme-color') as HTMLMetaElement | null;
  if (!el) {
    el = document.createElement('meta');
    el.id = 'asking-theme-color';
    el.name = 'theme-color';
    document.head.appendChild(el);
  }
  el.content = hex;
}

let manifestSourceHref: string | null = null;
/** Original `href` attribute on `<link rel="manifest">` (e.g. `manifest.json`) for restore on failure. */
let manifestHrefAttr: string | null = null;
let manifestBlobUrl: string | null = null;
let manifestSyncGeneration = 0;

/** Re-point `<link rel="manifest">` at a JSON blob so PWA chrome colors match the active palette. */
function syncWebManifest(themeId: ColorThemeId): void {
  if (typeof document === 'undefined' || typeof URL === 'undefined' || typeof fetch !== 'function')
    return;
  const link = document.querySelector('link[rel="manifest"]') as HTMLLinkElement | null;
  if (!link) return;

  if (manifestHrefAttr == null) {
    const raw = link.getAttribute('href');
    if (!raw) return;
    manifestHrefAttr = raw;
    manifestSourceHref = new URL(raw, window.location.href).href;
  }

  const hex = themeSurfaceHex(themeId);
  const gen = ++manifestSyncGeneration;
  void (async () => {
    const restoreCanonical = () => {
      if (manifestBlobUrl) {
        URL.revokeObjectURL(manifestBlobUrl);
        manifestBlobUrl = null;
      }
      if (manifestHrefAttr) link.setAttribute('href', manifestHrefAttr);
    };

    try {
      const res = await fetch(manifestSourceHref!, { cache: 'no-store' });
      if (!res.ok) {
        if (gen === manifestSyncGeneration) restoreCanonical();
        return;
      }
      const data = (await res.json()) as Record<string, unknown>;
      if (gen !== manifestSyncGeneration) return;
      const next = {
        ...data,
        theme_color: hex,
        theme_colors: [{ color: hex }],
        background_color: hex,
      };
      const blob = new Blob([JSON.stringify(next, null, 2)], { type: 'application/manifest+json' });
      if (manifestBlobUrl) URL.revokeObjectURL(manifestBlobUrl);
      manifestBlobUrl = URL.createObjectURL(blob);
      link.href = manifestBlobUrl;
    } catch {
      if (gen === manifestSyncGeneration) restoreCanonical();
    }
  })();
}

/** Applies `data-bs-theme` and optional `data-color-theme` on `<html>`. */
function applyColorTheme(themeId: ColorThemeId): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.setAttribute('data-bs-theme', bootstrapModeFor(themeId));
  if (themeId === 'system' || themeId === 'light' || themeId === 'dark') {
    root.removeAttribute('data-color-theme');
  } else {
    root.setAttribute('data-color-theme', themeId);
  }
  syncThemeColorMeta(themeId);
  syncWebManifest(themeId);
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(COLOR_THEME_EVENT));
  }
}

export function setColorTheme(themeId: ColorThemeId): void {
  try {
    localStorage.setItem(COLOR_THEME_STORAGE_KEY, themeId);
  } catch {
    /* private mode / quota */
  }
  applyColorTheme(themeId);
}

function applyFromStorage(): void {
  applyColorTheme(readStoredThemeId());
}

/** Run once at startup: restore theme, react to OS theme when set to System, sync other tabs. */
export function subscribeColorTheme(): () => void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return () => {};

  applyFromStorage();

  const mq =
    typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-color-scheme: dark)')
      : null;

  const onOsTheme = () => {
    if (readStoredThemeId() === 'system') applyFromStorage();
  };

  mq?.addEventListener('change', onOsTheme);

  const onStorage = (e: StorageEvent) => {
    if (e.key === COLOR_THEME_STORAGE_KEY) applyFromStorage();
  };
  window.addEventListener('storage', onStorage);

  return () => {
    mq?.removeEventListener('change', onOsTheme);
    window.removeEventListener('storage', onStorage);
  };
}
