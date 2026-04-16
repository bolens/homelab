/**
 * Locale-aware display helpers (use with {@link useLocaleTag} from I18n).
 * UI strings remain English until catalogs exist; numbers and dates follow the browser locale.
 */

export function formatLocaleInteger(value: number, locale: string): string {
  if (!Number.isFinite(value)) return String(value);
  try {
    return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value);
  } catch {
    return String(Math.trunc(value));
  }
}

/** Formats timestamps from the API (ISO or parseable date strings, epoch ms, or Date). */
export function formatLocaleDateTime(value: unknown, locale: string): string {
  if (value == null || value === '') return '';
  const d =
    value instanceof Date
      ? value
      : new Date(typeof value === 'number' && Number.isFinite(value) ? value : String(value));
  if (Number.isNaN(d.getTime())) return typeof value === 'string' ? value : String(value);
  try {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(d);
  } catch {
    try {
      return d.toLocaleString(locale);
    } catch {
      return d.toISOString();
    }
  }
}
