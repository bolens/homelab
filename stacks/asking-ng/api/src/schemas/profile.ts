import { z } from 'zod';

const llmGatewayTokenSchema = z.preprocess(
  (v) => (typeof v === 'string' ? v.trim() : v),
  z.union([z.string().min(1).max(4096), z.null()]),
);

export const profileUpdateBodySchema = z
  .object({
    homelab-user: z.string().min(1).max(128).optional(),
    password: z.string().min(8).max(512).optional(),
    llmGatewayToken: llmGatewayTokenSchema.optional(),
  })
  .refine(
    (d) => d.homelab-user !== undefined || d.password !== undefined || d.llmGatewayToken !== undefined,
    {
      message: 'Provide at least one of homelab-user, password, or llmGatewayToken',
      path: ['homelab-user'],
    },
  );

export type ProfileUpdateBody = z.infer<typeof profileUpdateBodySchema>;
