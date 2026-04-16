import type { ZodError } from 'zod';

/** First issue message, suitable for inline form errors. */
export function zodErrorSummary(err: ZodError): string {
  const [first] = err.issues;
  if (!first) return 'Validation failed';
  if (first.path.length === 0) return first.message;
  const path = first.path.map(String).join('.');
  return `${path}: ${first.message}`;
}
