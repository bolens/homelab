/**
 * Reject obvious SSRF targets for user-supplied webhook URLs (best-effort; not a full DNS rebinding defense).
 */
export function isPublicWebhookUrl(url: URL): boolean {
  const proto = url.protocol.toLowerCase();
  if (proto !== 'https:' && !(proto === 'http:' && url.hostname === 'localhost')) {
    return false;
  }
  const h = url.hostname.toLowerCase();
  if (h === 'localhost' || h === '[::1]' || h === '127.0.0.1') {
    return proto === 'http:';
  }
  if (h.endsWith('.localhost') || h.endsWith('.local')) return false;
  if (/^(0\.0\.0\.0|255\.255\.255\.255)$/.test(h)) return false;
  if (/^10\./.test(h)) return false;
  if (/^192\.168\./.test(h)) return false;
  if (/^127\./.test(h)) return false;
  if (/^169\.254\./.test(h)) return false;
  const m = /^172\.(\d+)\./.exec(h);
  if (m) {
    const n = Number.parseInt(m[1], 10);
    if (n >= 16 && n <= 31) return false;
  }
  if (proto === 'https:' && h === 'metadata.google.internal') return false;
  return true;
}
