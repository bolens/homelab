import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { appEnv } from '../lib/env';

const JWT_SECRET = appEnv.jwtSecret || 'changeme';

type JwtUserPayload = { id: number; homelab-user: string; role: string };

export function hashPassword(password: string): string {
  return bcrypt.hashSync(password, 10);
}

export function comparePassword(password: string, hash: string): boolean {
  return bcrypt.compareSync(password, hash);
}

const JWT_SIGN_OPTS = { expiresIn: '7d' as const, algorithm: 'HS256' as const };

export function generateToken(user: JwtUserPayload): string {
  return jwt.sign(
    { id: user.id, homelab-user: user.homelab-user, role: user.role },
    JWT_SECRET,
    JWT_SIGN_OPTS,
  );
}

export function verifyToken(token: string): JwtUserPayload | null {
  try {
    const payload = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] });
    if (typeof payload === 'string' || payload === null || typeof payload !== 'object') {
      return null;
    }
    const p = payload as Record<string, unknown>;
    if (
      typeof p['id'] !== 'number' ||
      typeof p['homelab-user'] !== 'string' ||
      typeof p['role'] !== 'string'
    ) {
      return null;
    }
    return { id: p['id'], homelab-user: p['homelab-user'], role: p['role'] };
  } catch {
    return null;
  }
}
