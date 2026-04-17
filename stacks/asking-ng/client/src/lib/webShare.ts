type ShareUrlResult =
  | { kind: 'shared' }
  | { kind: 'aborted' }
  | { kind: 'unavailable' }
  | { kind: 'error'; message: string };

function canShareUrl(url: string): boolean {
  if (typeof navigator === 'undefined' || typeof navigator.share !== 'function') {
    return false;
  }
  if (typeof navigator.canShare === 'function') {
    try {
      return navigator.canShare({ url });
    } catch {
      return false;
    }
  }
  return true;
}

/** True when the Web Share API may be able to share a URL (still may throw at runtime). */
export function isWebShareLikelyAvailable(url: string): boolean {
  return canShareUrl(url);
}

/**
 * Opens the system share sheet when supported (mobile and some desktops).
 * Caller should fall back to clipboard on `unavailable` or `error`.
 */
export async function shareUrlNative(opts: {
  url: string;
  title?: string | undefined;
  text?: string | undefined;
}): Promise<ShareUrlResult> {
  if (!canShareUrl(opts.url)) {
    return { kind: 'unavailable' };
  }
  try {
    await navigator.share({
      url: opts.url,
      ...(opts.title ? { title: opts.title } : {}),
      ...(opts.text ? { text: opts.text } : {}),
    });
    return { kind: 'shared' };
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      return { kind: 'aborted' };
    }
    const message = e instanceof Error ? e.message : String(e);
    return { kind: 'error', message };
  }
}
