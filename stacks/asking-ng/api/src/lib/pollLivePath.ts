/** Match `/ws/poll/:pollId` (poll id may be URL-encoded). */
export function matchPollLivePath(pathname: string): string | null {
  const m = pathname.match(/^\/ws\/poll\/([^/]+)\/?$/);
  if (!m?.[1]) return null;
  try {
    const id = decodeURIComponent(m[1]);
    return id.trim() !== '' ? id : null;
  } catch {
    return null;
  }
}
