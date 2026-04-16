import { z } from 'zod';

const adminRoleValues = ['user', 'mod', 'admin', 'superadmin'] as const;
export const adminRoleSchema = z.enum(adminRoleValues);

export const createUserBodySchema = z.object({
  homelab-user: z.string().trim().min(1).max(128),
  password: z.string().min(8).max(512),
  role: adminRoleSchema.optional(),
});

export type CreateUserBody = z.infer<typeof createUserBodySchema>;

export const adminChangePasswordBodySchema = z.object({
  currentPassword: z.string().min(1).max(512),
  newPassword: z.string().min(8).max(512),
});

export type AdminChangePasswordBody = z.infer<typeof adminChangePasswordBodySchema>;

export const setPasswordBodySchema = z.object({
  password: z.string().min(8).max(512),
});

export type SetPasswordBody = z.infer<typeof setPasswordBodySchema>;

export const rolePatchBodySchema = z.object({
  role: adminRoleSchema,
});

export type RolePatchBody = z.infer<typeof rolePatchBodySchema>;

const pollOptionString = z.string().trim().min(1).max(500);

export const adminPollWriteBodySchema = z
  .object({
    question: z.string().trim().min(1).max(500),
    options: z.array(pollOptionString).min(2).max(32),
  })
  .refine((d) => new Set(d.options).size === d.options.length, {
    message: 'Duplicate options are not allowed',
    path: ['options'],
  });

export type AdminPollWriteBody = z.infer<typeof adminPollWriteBodySchema>;

/** Positive integer user id (path, query, or form coercions). */
export const positiveUserIdSchema = z.coerce.number().int().positive();

/** Admin UI login token (trimmed, bounded). */
export const adminLoginTokenSchema = z.string().trim().min(1).max(8192);

export const adminChangeRoleFormSchema = z.object({
  id: positiveUserIdSchema,
  role: adminRoleSchema,
});

export type AdminChangeRoleForm = z.infer<typeof adminChangeRoleFormSchema>;

export const adminResetPasswordFormSchema = z.object({
  id: positiveUserIdSchema,
  password: z.string().min(8).max(512),
});

export type AdminResetPasswordForm = z.infer<typeof adminResetPasswordFormSchema>;

export const adminSimulationBodySchema = z.object({
  users: z.coerce.number().int().min(0).max(50),
  polls: z.coerce.number().int().min(1).max(25),
  votesPerPoll: z.coerce.number().int().min(0).max(1000),
});

export type AdminSimulationBody = z.infer<typeof adminSimulationBodySchema>;
