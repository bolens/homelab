export const COLOR_VISION_STORAGE_KEY = 'asking-ng-color-vision';

export const DYSLEXIA_MODE_STORAGE_KEY = 'asking-ng-dyslexia-mode';

export const READING_COMFORT_EVENT = 'askingng-reading-comfort';

/** Simulation / assist filters (approximate). */
export const COLOR_VISION_IDS = [
  'none',
  'protanopia',
  'deuteranopia',
  'tritanopia',
  'monochrome',
] as const;

export type ColorVisionId = (typeof COLOR_VISION_IDS)[number];

/**
 * Reading comfort: system fonts with spacing tweaks, Google Fonts, or locally installed Nerd Fonts.
 */
export const DYSLEXIA_MODE_IDS = [
  'off',
  'readable',
  'lexend',
  'hyperlegible',
  'inter',
  'geist',
  'ibm-plex',
  'dm-sans',
  'plus-jakarta',
  'source-sans-3',
  'nf-jetbrains',
  'nf-fira',
  'nf-hack',
  'nf-meslo',
  'nf-cascadia',
  'nf-ubuntu',
  'nf-iosevka',
] as const;

export type DyslexiaModeId = (typeof DYSLEXIA_MODE_IDS)[number];

const DEFAULT_CVD: ColorVisionId = 'none';
const DEFAULT_DYSLEXIA: DyslexiaModeId = 'off';

/** Remote stylesheet per mode (cleared when switching away). */
const REMOTE_GOOGLE_FONTS: readonly { mode: DyslexiaModeId; linkId: string; href: string }[] = [
  {
    mode: 'lexend',
    linkId: 'asking-ng-font-lexend',
    href: 'https://fonts.googleapis.com/css2?family=Lexend:wght@400;600&display=swap',
  },
  {
    mode: 'hyperlegible',
    linkId: 'asking-ng-font-atkinson',
    href: 'https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400;1,700&display=swap',
  },
  {
    mode: 'inter',
    linkId: 'asking-ng-font-inter',
    href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap',
  },
  {
    mode: 'geist',
    linkId: 'asking-ng-font-geist',
    href: 'https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&display=swap',
  },
  {
    mode: 'ibm-plex',
    linkId: 'asking-ng-font-ibm-plex',
    href: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap',
  },
  {
    mode: 'dm-sans',
    linkId: 'asking-ng-font-dm-sans',
    href: 'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap',
  },
  {
    mode: 'plus-jakarta',
    linkId: 'asking-ng-font-plus-jakarta',
    href: 'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600&display=swap',
  },
  {
    mode: 'source-sans-3',
    linkId: 'asking-ng-font-source-sans-3',
    href: 'https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600&display=swap',
  },
];

function isColorVisionId(value: string): value is ColorVisionId {
  return (COLOR_VISION_IDS as readonly string[]).includes(value);
}

function isDyslexiaModeId(value: string): value is DyslexiaModeId {
  return (DYSLEXIA_MODE_IDS as readonly string[]).includes(value);
}

export function readStoredColorVision(): ColorVisionId {
  if (typeof localStorage === 'undefined') return DEFAULT_CVD;
  try {
    const raw = localStorage.getItem(COLOR_VISION_STORAGE_KEY);
    if (!raw || !isColorVisionId(raw)) return DEFAULT_CVD;
    return raw;
  } catch {
    return DEFAULT_CVD;
  }
}

export function readStoredDyslexiaMode(): DyslexiaModeId {
  if (typeof localStorage === 'undefined') return DEFAULT_DYSLEXIA;
  try {
    const raw = localStorage.getItem(DYSLEXIA_MODE_STORAGE_KEY);
    if (!raw || !isDyslexiaModeId(raw)) return DEFAULT_DYSLEXIA;
    return raw;
  } catch {
    return DEFAULT_DYSLEXIA;
  }
}

function dispatchComfort(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(READING_COMFORT_EVENT));
}

/** Vite `base` + public asset path for `filter: url(...)`. */
function colorVisionFilterUrl(filterId: string): string {
  const base = (import.meta.env.BASE_URL as string | undefined) ?? '/';
  const trimmed = base.endsWith('/') ? base.slice(0, -1) : base;
  const path = `${trimmed || ''}/color-vision-filters.svg`.replace(/([^:]\/)\/+/g, '$1');
  return `url('${path}#${filterId}')`;
}

function applyColorVision(id: ColorVisionId): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (id === 'none') {
    root.removeAttribute('data-color-vision');
    root.style.removeProperty('--asking-cv-filter');
  } else {
    root.setAttribute('data-color-vision', id);
    if (id === 'monochrome') {
      root.style.removeProperty('--asking-cv-filter');
    } else {
      root.style.setProperty('--asking-cv-filter', colorVisionFilterUrl(`cv-${id}`));
    }
  }
  dispatchComfort();
}

function removeLink(id: string): void {
  document.getElementById(id)?.remove();
}

function ensureStylesheetLink(id: string, href: string): void {
  if (document.getElementById(id)) return;
  const link = document.createElement('link');
  link.id = id;
  link.rel = 'stylesheet';
  link.href = href;
  document.head.appendChild(link);
}

function prefersReducedData(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-data: reduce)').matches;
}

function applyDyslexiaMode(mode: DyslexiaModeId): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;

  for (const { linkId } of REMOTE_GOOGLE_FONTS) {
    removeLink(linkId);
  }
  root.removeAttribute('data-dyslexia-font-load');

  if (mode === 'off') {
    root.removeAttribute('data-dyslexia');
    dispatchComfort();
    return;
  }

  root.setAttribute('data-dyslexia', mode);

  const skipRemoteFonts = prefersReducedData();
  const remote = REMOTE_GOOGLE_FONTS.find((e) => e.mode === mode);
  if (remote) {
    if (skipRemoteFonts) {
      root.setAttribute('data-dyslexia-font-load', 'skip');
    } else {
      ensureStylesheetLink(remote.linkId, remote.href);
    }
  }

  dispatchComfort();
}

export function setColorVision(id: ColorVisionId): void {
  try {
    localStorage.setItem(COLOR_VISION_STORAGE_KEY, id);
  } catch {
    /* private mode / quota */
  }
  applyColorVision(id);
}

export function setDyslexiaMode(mode: DyslexiaModeId): void {
  try {
    localStorage.setItem(DYSLEXIA_MODE_STORAGE_KEY, mode);
  } catch {
    /* private mode / quota */
  }
  applyDyslexiaMode(mode);
}

function applyFromStorage(): void {
  applyColorVision(readStoredColorVision());
  applyDyslexiaMode(readStoredDyslexiaMode());
}

/** Restore CVD + dyslexia prefs; sync across tabs. */
export function subscribeReadingComfort(): () => void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return () => {};

  applyFromStorage();

  const onStorage = (e: StorageEvent) => {
    if (e.key !== COLOR_VISION_STORAGE_KEY && e.key !== DYSLEXIA_MODE_STORAGE_KEY) return;
    applyFromStorage();
  };
  window.addEventListener('storage', onStorage);

  const mqReducedData =
    typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-data: reduce)')
      : null;
  const onReducedData = () => {
    applyDyslexiaMode(readStoredDyslexiaMode());
  };
  mqReducedData?.addEventListener('change', onReducedData);

  return () => {
    window.removeEventListener('storage', onStorage);
    mqReducedData?.removeEventListener('change', onReducedData);
  };
}
