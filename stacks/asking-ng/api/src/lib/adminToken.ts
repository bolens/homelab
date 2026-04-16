import { createHash, timingSafeEqual } from 'node:crypto';

/** Constant-time comparison for shared secrets (same-length SHA-256 digests). */
export function timingSafeAdminTokenEqual(provided: string | undefined, expected: string): boolean {
  if (provided === undefined || provided === '') return false;
  const a = createHash('sha256').update(provided, 'utf8').digest();
  const b = createHash('sha256').update(expected, 'utf8').digest();
  try {
    return timingSafeEqual(a, b);
  } catch {
    return false;
  }
}
