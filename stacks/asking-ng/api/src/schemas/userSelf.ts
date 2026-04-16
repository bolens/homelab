import { z } from 'zod';

export const selfPasswordChangeBodySchema = z.object({
  oldPassword: z.string().min(1).max(512),
  newPassword: z.string().min(8).max(512),
});

export type SelfPasswordChangeBody = z.infer<typeof selfPasswordChangeBodySchema>;

export const selfDeleteBodySchema = z.object({
  password: z.string().min(1).max(512),
});

export type SelfDeleteBody = z.infer<typeof selfDeleteBodySchema>;
