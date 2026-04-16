import 'fastify';

declare module 'fastify' {
  interface FastifyRequest {
    user?: { id: number; homelab-user: string; role: string; billingPlan?: string } | null;
    context?: {
      requestId: string;
      userId: number | null;
      homelab-user: string | null;
      role: string | null;
      ip: string | null;
    };
  }
}

export {};
