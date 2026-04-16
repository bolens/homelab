/**
 * Format a UTC clock-hour bucket (0–23) for display, including a short timezone name (typically UTC).
 */
export function formatUtcHourAtTopOfHour(
  localeTag: string,
  hour: number | null | undefined,
  fallback: string,
): string {
  if (hour == null || !Number.isFinite(hour)) return fallback;
  const clamped = Math.max(0, Math.min(23, Math.floor(hour)));
  const d = new Date(Date.UTC(1970, 0, 1, clamped, 0, 0));
  try {
    return new Intl.DateTimeFormat(localeTag, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'UTC',
      timeZoneName: 'short',
    }).format(d);
  } catch {
    return `${String(clamped).padStart(2, '0')}:00 UTC`;
  }
}
