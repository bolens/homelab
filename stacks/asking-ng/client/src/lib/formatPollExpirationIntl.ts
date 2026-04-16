type PollExpiryRelativeState = 'expired' | 'never' | 'invalid' | 'relative';

type PollExpiryRelative = {
  state: PollExpiryRelativeState;
  /** When `state` is `relative`, localized string from Intl (e.g. "in 5 minutes"). */
  text: string;
};

const HOURS_NEVER = 864000;

/**
 * Localized relative expiry (Intl.RelativeTimeFormat), aligned with Poll page "never" threshold.
 */
export function formatPollExpiryRelative(
  locale: string,
  expiration: number,
  nowMs: number,
): PollExpiryRelative {
  if (!Number.isFinite(expiration) || expiration <= 0) {
    return { state: 'invalid', text: '' };
  }
  const ms = expiration - nowMs;
  if (ms < 0) {
    return { state: 'expired', text: '' };
  }
  const hoursRemaining = ms / 3600000;
  if (hoursRemaining > HOURS_NEVER) {
    return { state: 'never', text: '' };
  }

  try {
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
    const minutesTotal = ms / 60000;
    if (minutesTotal < 1) {
      const sec = Math.max(1, Math.round(ms / 1000));
      return { state: 'relative', text: rtf.format(sec, 'second') };
    }
    if (minutesTotal < 60) {
      const min = Math.round(minutesTotal);
      return { state: 'relative', text: rtf.format(min, 'minute') };
    }
    const hoursTotal = ms / 3600000;
    if (hoursTotal < 24) {
      const h = Math.round(hoursTotal);
      return { state: 'relative', text: rtf.format(h, 'hour') };
    }
    const daysTotal = ms / 86400000;
    if (daysTotal < 7) {
      const d = Math.round(daysTotal);
      return { state: 'relative', text: rtf.format(d, 'day') };
    }
    const weeksTotal = ms / (7 * 86400000);
    if (weeksTotal < 5) {
      const w = Math.round(weeksTotal);
      return { state: 'relative', text: rtf.format(w, 'week') };
    }
    const monthsTotal = ms / (30 * 86400000);
    if (monthsTotal < 12) {
      const mo = Math.round(monthsTotal);
      return { state: 'relative', text: rtf.format(mo, 'month') };
    }
    const yearsTotal = ms / (365.25 * 86400000);
    const y = Math.max(1, Math.round(yearsTotal));
    return { state: 'relative', text: rtf.format(y, 'year') };
  } catch {
    try {
      const abs = new Date(expiration);
      const relMs = expiration - nowMs;
      const fmt = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
      const minutesTotal = relMs / 60000;
      if (minutesTotal < 1) {
        const sec = Math.max(1, Math.round(relMs / 1000));
        return { state: 'relative', text: fmt.format(sec, 'second') };
      }
      if (minutesTotal < 60) {
        return { state: 'relative', text: fmt.format(Math.round(minutesTotal), 'minute') };
      }
      return {
        state: 'relative',
        text: new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
          abs,
        ),
      };
    } catch {
      const hours = Math.floor(ms / 3600000);
      const minutes = Math.floor(ms / 60000) % 60;
      const seconds = Math.floor(ms / 1000) % 60;
      return { state: 'relative', text: `${hours}h ${minutes}m ${seconds}s` };
    }
  }
}

/** Calendar-style local end time for tooltips / assistive context. */
export function formatPollExpiryAbsolute(locale: string, expiration: number): string {
  try {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(expiration));
  } catch {
    return new Date(expiration).toLocaleString(locale);
  }
}
