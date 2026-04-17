/** Build-time strings for legal pages (`VITE_*` baked at client image build). */

export function legalLastUpdated(): string | null {
  const v = import.meta.env.VITE_LEGAL_LAST_UPDATED;
  return typeof v === 'string' && v.trim() !== '' ? v.trim() : null;
}

export function securityContactEmail(): string | null {
  const s = import.meta.env.VITE_LEGAL_SECURITY_EMAIL;
  if (typeof s === 'string' && s.trim() !== '') return s.trim();
  const c = import.meta.env.VITE_LEGAL_CONTACT_EMAIL;
  return typeof c === 'string' && c.trim() !== '' ? c.trim() : null;
}

export type AnalyticsProviderId = 'umami' | 'plausible' | 'matomo';

export function configuredAnalyticsProviders(): AnalyticsProviderId[] {
  const out: AnalyticsProviderId[] = [];
  const umamiUrl = import.meta.env.VITE_UMAMI_SCRIPT_URL?.trim();
  const umamiId = import.meta.env.VITE_UMAMI_WEBSITE_ID?.trim();
  if (umamiUrl && umamiId) out.push('umami');
  if (
    import.meta.env.VITE_PLAUSIBLE_SCRIPT_URL?.trim() &&
    import.meta.env.VITE_PLAUSIBLE_DOMAIN?.trim()
  ) {
    out.push('plausible');
  }
  if (import.meta.env.VITE_MATOMO_BASE_URL?.trim() && import.meta.env.VITE_MATOMO_SITE_ID?.trim()) {
    out.push('matomo');
  }
  return out;
}
