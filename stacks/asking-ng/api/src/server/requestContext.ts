import type { FastifyPluginAsync, FastifyRequest } from 'fastify';
import { getSessionUserFromCache, setSessionUserCache } from '../lib/sessionUserCache';
import User from '../models/user.sequelize';
import { verifyToken } from '../utils/auth';

function bearerFrom(req: FastifyRequest): string | null {
  const auth = req.headers.authorization;
  if (typeof auth !== 'string') return null;
  const [scheme, token] = auth.split(' ');
  if (scheme?.toLowerCase() !== 'bearer' || !token) return null;
  return token;
}

export const requestContextPlugin: FastifyPluginAsync = async (app) => {
  app.decorateRequest('user', undefined);
  app.decorateRequest('context', undefined);

  app.addHook('onRequest', async (request) => {
    let user: { id: number; homelab-user: string; role: string; billingPlan?: string } | null = null;
    const token = bearerFrom(request);

    if (token) {
      const payload = verifyToken(token);
      if (payload) {
        const cached = getSessionUserFromCache(payload.id);
        if (cached && cached.id === payload.id) {
          user = {
            id: cached.id,
            homelab-user: cached.homelab-user,
            role: cached.role,
            billingPlan: cached.billingPlan,
          };
        } else {
          const dbUser = await User.findByPk(payload.id, {
            attributes: ['id', 'homelab-user', 'role', 'active', 'billingPlan'],
          });
          if (dbUser && !!dbUser.get('active')) {
            const billingPlan = String(dbUser.get('billingPlan') ?? 'free').trim() || 'free';
            const snapshot = {
              id: dbUser.get('id') as number,
              homelab-user: dbUser.get('homelab-user') as string,
              role: dbUser.get('role') as string,
              active: true,
              billingPlan,
            };
            setSessionUserCache(snapshot);
            user = {
              id: snapshot.id,
              homelab-user: snapshot.homelab-user,
              role: snapshot.role,
              billingPlan,
            };
          }
        }
      }
    }

    request.user = user;
    request.context = {
      requestId: request.id,
      userId: user?.id ?? null,
      homelab-user: user?.homelab-user ?? null,
      role: user?.role ?? null,
      ip: typeof request.ip === 'string' && request.ip.trim() !== '' ? request.ip : null,
    };
  });
};
