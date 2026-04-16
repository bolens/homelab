import { z } from 'zod';

export const authLoginBodySchema = z.object({
  homelab-user: z.string().min(1).max(128),
  password: z.string().min(1).max(512),
});

export const authRegisterBodySchema = z.object({
  homelab-user: z.string().min(1).max(128),
  password: z.string().min(8).max(512),
  /** Must be true: user has read and agrees to Terms and Privacy policy (enforced server-side). */
  acceptTermsAndPrivacy: z.boolean().refine((v) => v === true, {
    message: 'You must accept the Terms of use and Privacy policy to register.',
  }),
});

export type AuthLoginBody = z.infer<typeof authLoginBodySchema>;
export type AuthRegisterBody = z.infer<typeof authRegisterBodySchema>;
