/** Coerce route `params` / query values (often typed as `unknown`) to a single string. */
export function singleString(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    const x = value[0];
    return typeof x === 'string' ? x : undefined;
  }
  return undefined;
}
