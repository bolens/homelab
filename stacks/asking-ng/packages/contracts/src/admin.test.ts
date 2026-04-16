import { describe, expect, it } from 'vitest';
import {
  adminChangeRoleFormSchema,
  adminLoginTokenSchema,
  adminPollWriteBodySchema,
  adminResetPasswordFormSchema,
  createUserBodySchema,
} from './admin';

describe('adminPollWriteBodySchema', () => {
  it('rejects duplicate options', () => {
    const r = adminPollWriteBodySchema.safeParse({
      question: 'Q',
      options: ['a', 'a'],
    });
    expect(r.success).toBe(false);
  });

  it('trims fields', () => {
    const r = adminPollWriteBodySchema.safeParse({
      question: ' hi ',
      options: [' x ', 'y'],
    });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.question).toBe('hi');
      expect(r.data.options).toEqual(['x', 'y']);
    }
  });
});

describe('createUserBodySchema', () => {
  it('requires password length', () => {
    const r = createUserBodySchema.safeParse({
      homelab-user: 'u',
      password: 'short',
    });
    expect(r.success).toBe(false);
  });

  it('accepts mod role', () => {
    const r = createUserBodySchema.safeParse({
      homelab-user: 'moduser',
      password: '12345678',
      role: 'mod',
    });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.role).toBe('mod');
  });
});

describe('adminChangeRoleFormSchema', () => {
  it('coerces id from string', () => {
    const r = adminChangeRoleFormSchema.safeParse({ id: '5', role: 'admin' });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.id).toBe(5);
  });
});

describe('adminResetPasswordFormSchema', () => {
  it('validates id and password', () => {
    const r = adminResetPasswordFormSchema.safeParse({ id: '1', password: '12345678' });
    expect(r.success).toBe(true);
  });
});

describe('adminLoginTokenSchema', () => {
  it('rejects whitespace-only', () => {
    expect(adminLoginTokenSchema.safeParse('   ').success).toBe(false);
  });
});
