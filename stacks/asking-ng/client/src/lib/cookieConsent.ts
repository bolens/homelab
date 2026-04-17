import { apiUrl } from '../apiBase';

export const COOKIE_CONSENT_STORAGE_KEY = 'asking-ng-cookie-consent';
export const COOKIE_CONSENT_GRANULAR_UI_KEY = 'asking-ng-cookie-consent-granular-ui';
export const COOKIE_CONSENT_CHANGED_EVENT = 'asking-ng:cookie-consent-changed';

export type CookieConsentChoice = 'accepted' | 'rejected';
export type CookieConsentState = CookieConsentChoice | 'unknown';
export type CookieConsentSource = 'banner' | 'settings' | 'browser_signal';

export type ConsentRegionHint = 'eu' | 'non-eu' | 'unknown';

export type CookieConsentChangedDetail = {
  analyticsEnabled: boolean;
};

export type GranularConsentCategories = {
  functional: boolean;
  analytics: boolean;
  /** Always false for this product; kept for EU-style disclosure. */
  marketing: boolean;
};

const V2 = 2 as const;

type StoredV2 = {
  v: typeof V2;
  analytics: boolean;
  functional: boolean;
  marketing: boolean;
};

type NavigatorWithPrivacySignals = Navigator & {
  globalPrivacyControl?: boolean;
  msDoNotTrack?: string | null;
};

function readDoNotTrackValue(): string | null {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return null;
  const nav = navigator as NavigatorWithPrivacySignals;
  const win = window as Window & { doNotTrack?: string | null };
  return (nav.doNotTrack || win.doNotTrack || nav.msDoNotTrack || null)?.toLowerCase() ?? null;
}

export function hasBrowserPrivacyOptOutSignal(): boolean {
  if (typeof navigator === 'undefined') return false;
  const nav = navigator as NavigatorWithPrivacySignals;
  if (nav.globalPrivacyControl === true) return true;
  const dnt = readDoNotTrackValue();
  return dnt === '1' || dnt === 'yes';
}

function parseStoredV2(raw: string): StoredV2 | null {
  try {
    const j = JSON.parse(raw) as unknown;
    if (!j || typeof j !== 'object' || Array.isArray(j)) return null;
    const o = j as Record<string, unknown>;
    if (o['v'] !== V2) return null;
    if (
      typeof o['analytics'] !== 'boolean' ||
      typeof o['functional'] !== 'boolean' ||
      typeof o['marketing'] !== 'boolean'
    ) {
      return null;
    }
    return {
      v: V2,
      analytics: o['analytics'],
      functional: o['functional'],
      marketing: o['marketing'],
    };
  } catch {
    return null;
  }
}

function readRaw(): string | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    return localStorage.getItem(COOKIE_CONSENT_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeRaw(value: string): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(COOKIE_CONSENT_STORAGE_KEY, value);
  } catch {
    /* private mode / quota */
  }
}

function persistV2(c: StoredV2): void {
  writeRaw(JSON.stringify(c));
}

/** Legacy `accepted` / `rejected` strings or v2 JSON. */
export function readStoredCookieConsent(): CookieConsentState {
  const raw = readRaw();
  if (raw === 'accepted' || raw === 'rejected') return raw;
  const v2 = raw ? parseStoredV2(raw) : null;
  if (v2) return v2.analytics ? 'accepted' : 'rejected';
  return 'unknown';
}

export function getParsedGranularConsent(): StoredV2 | null {
  const raw = readRaw();
  if (!raw) return null;
  return parseStoredV2(raw);
}

export function readGranularUiPreference(): boolean {
  if (typeof localStorage === 'undefined') return false;
  try {
    return localStorage.getItem(COOKIE_CONSENT_GRANULAR_UI_KEY) === '1';
  } catch {
    return false;
  }
}

export function setGranularUiPreference(enabled: boolean): void {
  if (typeof localStorage === 'undefined') return;
  try {
    if (enabled) localStorage.setItem(COOKIE_CONSENT_GRANULAR_UI_KEY, '1');
    else localStorage.removeItem(COOKIE_CONSENT_GRANULAR_UI_KEY);
  } catch {
    /* private mode */
  }
}

export function prefersGranularConsentUi(region: ConsentRegionHint): boolean {
  return region === 'eu' || readGranularUiPreference();
}

let regionCache: ConsentRegionHint | null = null;
let regionFetch: Promise<ConsentRegionHint> | null = null;

export function getCachedConsentRegion(): ConsentRegionHint | null {
  return regionCache;
}

export async function fetchConsentRegion(): Promise<ConsentRegionHint> {
  if (regionCache !== null) return regionCache;
  if (regionFetch) return regionFetch;
  regionFetch = fetch(apiUrl('telemetry/consent-region'))
    .then(async (r) => {
      if (!r.ok) return 'unknown' as const;
      const j = (await r.json()) as { region?: string };
      const reg =
        j.region === 'eu' || j.region === 'non-eu'
          ? (j.region as ConsentRegionHint)
          : ('unknown' as const);
      regionCache = reg;
      return reg;
    })
    .catch(() => {
      regionCache = 'unknown';
      return 'unknown' as const;
    })
    .finally(() => {
      regionFetch = null;
    });
  return regionFetch;
}

function dispatchConsentChanged(analyticsEnabled: boolean): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<CookieConsentChangedDetail>(COOKIE_CONSENT_CHANGED_EVENT, {
      detail: { analyticsEnabled },
    }),
  );
}

function postTelemetry(
  body:
    | {
        mode: 'simple';
        choice: CookieConsentChoice;
        source?: CookieConsentSource | undefined;
        clientTs: string;
      }
    | {
        mode: 'granular';
        necessary: true;
        functional: boolean;
        analytics: boolean;
        marketing: boolean;
        consentRegion?: ConsentRegionHint | undefined;
        source?: CookieConsentSource | undefined;
        clientTs: string;
      },
): void {
  if (typeof fetch === 'undefined') return;
  void fetch(apiUrl('telemetry/consent'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).catch(() => {
    /* best-effort */
  });
}

export function saveGranularConsent(
  cats: GranularConsentCategories,
  source: CookieConsentSource | undefined,
  consentRegion: ConsentRegionHint,
): void {
  persistV2({
    v: V2,
    analytics: cats.analytics,
    functional: cats.functional,
    marketing: cats.marketing,
  });
  postTelemetry({
    mode: 'granular',
    necessary: true,
    functional: cats.functional,
    analytics: cats.analytics,
    marketing: cats.marketing,
    consentRegion,
    source,
    clientTs: new Date().toISOString(),
  });
  dispatchConsentChanged(cats.analytics);
}

export function saveCookieConsent(choice: CookieConsentChoice, source?: CookieConsentSource): void {
  persistV2({
    v: V2,
    analytics: choice === 'accepted',
    functional: false,
    marketing: false,
  });
  postTelemetry({
    mode: 'simple',
    choice,
    source,
    clientTs: new Date().toISOString(),
  });
  dispatchConsentChanged(choice === 'accepted');
}

export function getCookieConsentState(): CookieConsentState {
  const stored = readStoredCookieConsent();
  if (stored !== 'unknown') return stored;
  if (hasBrowserPrivacyOptOutSignal()) {
    saveGranularConsent(
      { functional: false, analytics: false, marketing: false },
      'browser_signal',
      'unknown',
    );
    return 'rejected';
  }
  return 'unknown';
}

export function shouldLoadAnalytics(): boolean {
  const raw = readRaw();
  if (raw === 'accepted') return true;
  if (raw === 'rejected') return false;
  const v2 = raw ? parseStoredV2(raw) : null;
  if (v2) return v2.analytics;
  return false;
}
