import type { IncomingHttpHeaders } from 'node:http';

/** EU member states + EEA (IS, LI, NO). Uppercase ISO 3166-1 alpha-2. */
const EU_EEA = new Set([
  'AT',
  'BE',
  'BG',
  'HR',
  'CY',
  'CZ',
  'DK',
  'EE',
  'FI',
  'FR',
  'DE',
  'GR',
  'HU',
  'IE',
  'IT',
  'LV',
  'LT',
  'LU',
  'MT',
  'NL',
  'PL',
  'PT',
  'RO',
  'SK',
  'SI',
  'ES',
  'SE',
  'IS',
  'LI',
  'NO',
  'CH',
  'GB',
  'UK',
  'GI',
]);

export type PublicConsentRegion = 'eu' | 'non-eu' | 'unknown';

export type ConsentRegionSource = 'forced' | 'header' | 'unknown';

function headerValue(headers: IncomingHttpHeaders, nameLower: string): string | undefined {
  for (const [k, v] of Object.entries(headers)) {
    if (k.toLowerCase() === nameLower) {
      if (typeof v === 'string') return v;
      if (Array.isArray(v) && typeof v[0] === 'string') return v[0];
    }
  }
  return undefined;
}

function normalizeCountry(raw: string | undefined): string | null {
  if (raw == null) return null;
  const t = raw.trim().toUpperCase();
  if (t === '' || t === 'XX' || t === 'T1') return null;
  return t;
}

export function isEuEeaCountry(iso2: string | null | undefined): boolean {
  if (!iso2) return false;
  return EU_EEA.has(iso2.trim().toUpperCase());
}

/**
 * Resolve public consent region for cookie UI (no raw country exposed to clients).
 * @param force — `eu` | `non-eu` | empty for automatic from geo header
 */
export function resolvePublicConsentRegion(
  headers: IncomingHttpHeaders,
  opts: { force: '' | 'eu' | 'non-eu'; countryHeaderLower: string },
): { region: PublicConsentRegion; source: ConsentRegionSource } {
  if (opts.force === 'eu') return { region: 'eu', source: 'forced' };
  if (opts.force === 'non-eu') return { region: 'non-eu', source: 'forced' };

  const code = normalizeCountry(headerValue(headers, opts.countryHeaderLower));
  if (!code) return { region: 'unknown', source: 'unknown' };
  if (isEuEeaCountry(code)) return { region: 'eu', source: 'header' };
  return { region: 'non-eu', source: 'header' };
}
