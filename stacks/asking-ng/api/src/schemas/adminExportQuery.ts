import { z } from 'zod';

/** Query for `GET /admin/export/*` — invalid `format` yields Zod **400**. */
export const adminExportQuerySchema = z.object({
  format: z
    .string()
    .optional()
    .transform((s) => (s === undefined || s.trim() === '' ? 'json' : s.trim().toLowerCase()))
    .pipe(z.enum(['json', 'csv'])),
});

export type AdminExportQuery = z.infer<typeof adminExportQuerySchema>;
