/**
 * Message catalogs and UI locale ids.
 * Add a new `*.ts` catalog and extend {@link UI_LOCALES} / {@link CATALOGS} to ship another language.
 */

import { de } from './de';
import { en, interpolate } from './en';
import { enGb } from './en-gb';
import { es } from './es';
import { fr } from './fr';
import { ga } from './ga';
import { it } from './it';

export { en, interpolate };

export type MessageKey = keyof typeof en;
/** All UI locales must expose the same keys; values are plain strings (not English literal types). */
type MessageCatalog = Record<MessageKey, string>;

/** Shipped UI languages (string catalogs). Keep `ulIds` in `index.html` in sync when adding a locale. */
export const UI_LOCALES = ['en-us', 'en-gb', 'fr', 'es', 'ga', 'de', 'it'] as const;
export type UILocale = (typeof UI_LOCALES)[number];

export const UI_LOCALE_STORAGE_KEY = 'asking-ng-ui-locale';

const UI_LOCALE_SET = new Set<string>(UI_LOCALES);

function normalizeStoredLocale(raw: string | null): UILocale | null {
  if (!raw) return null;
  const v = raw.toLowerCase().trim();
  if (UI_LOCALE_SET.has(v)) return v as UILocale;
  // Backward compatibility: previous builds stored generic "en".
  if (v === 'en') return 'en-us';
  if (v === 'en-gb' || v === 'en_uk' || v === 'en-uk') return 'en-gb';
  if (v === 'en-us' || v === 'en_us') return 'en-us';
  return null;
}

export function readStoredUILocale(): UILocale {
  if (typeof localStorage === 'undefined') return 'en-us';
  try {
    const normalized = normalizeStoredLocale(localStorage.getItem(UI_LOCALE_STORAGE_KEY));
    if (normalized) return normalized;
  } catch {
    /* private mode */
  }
  return 'en-us';
}

/** Resolved message object for the active UI locale. */
export const CATALOGS: Record<UILocale, MessageCatalog> = {
  'en-us': en,
  'en-gb': enGb,
  fr,
  es,
  ga,
  de,
  it,
};
