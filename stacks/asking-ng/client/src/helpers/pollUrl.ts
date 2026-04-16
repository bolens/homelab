/** Path to a poll by id, respecting `import.meta.env.BASE_URL`. */
export function pollPathForId(id: string): string {
  const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
  return base ? `${base}/${id}` : `/${id}`;
}

/** Full share URL for the current origin. */
export function shareUrlForPoll(id: string): string {
  return `${window.location.origin}${pollPathForId(id)}`;
}

/** Path to a poll results-only overlay route by id. */
export function pollResultsPathForId(id: string): string {
  return `${pollPathForId(id)}/results`;
}

/** Full share URL for the results-only overlay route. */
export function shareUrlForPollResults(id: string): string {
  return `${window.location.origin}${pollResultsPathForId(id)}`;
}
