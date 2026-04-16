/**
 * Format server `peak_dow_utc` (0–6, Sunday–Saturday, UTC) for display with `Intl`.
 * Uses a fixed UTC Sunday anchor so each index maps to the correct weekday.
 */
export function formatUtcWeekdayShort(
  localeTag: string,
  dow: number | null | undefined,
  fallback: string,
): string {
  if (dow == null || !Number.isFinite(dow)) return fallback;
  const idx = Math.max(0, Math.min(6, Math.floor(dow)));
  const d = new Date(Date.UTC(1970, 0, 4 + idx, 0, 0, 0));
  try {
    return new Intl.DateTimeFormat(localeTag, { weekday: 'short', timeZone: 'UTC' }).format(d);
  } catch {
    const labels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    return labels[idx] ?? fallback;
  }
}
