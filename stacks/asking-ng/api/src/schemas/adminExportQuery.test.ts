import { describe, expect, it } from 'vitest';
import { adminExportQuerySchema } from './adminExportQuery';

describe('adminExportQuerySchema', () => {
  it('defaults missing format to json', () => {
    expect(adminExportQuerySchema.safeParse({}).success).toBe(true);
    expect(adminExportQuerySchema.parse({}).format).toBe('json');
  });

  it('accepts csv case-insensitively', () => {
    expect(adminExportQuerySchema.parse({ format: 'CSV' }).format).toBe('csv');
  });

  it('rejects unknown format', () => {
    const r = adminExportQuerySchema.safeParse({ format: 'xml' });
    expect(r.success).toBe(false);
  });
});
