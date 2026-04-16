/** Append UTM query params for attribution on shared poll links. */
export function withUtm(
  url: string,
  params: { source: string; medium: string; campaign: string },
): string {
  try {
    const next = new URL(url);
    next.searchParams.set('utm_source', params.source);
    next.searchParams.set('utm_medium', params.medium);
    next.searchParams.set('utm_campaign', params.campaign);
    return next.toString();
  } catch {
    const q = new URLSearchParams({
      utm_source: params.source,
      utm_medium: params.medium,
      utm_campaign: params.campaign,
    });
    return `${url}${url.includes('?') ? '&' : '?'}${q.toString()}`;
  }
}
