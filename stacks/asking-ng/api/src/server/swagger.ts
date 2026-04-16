import fastifySwagger from '@fastify/swagger';
import fastifySwaggerUi from '@fastify/swagger-ui';
import type { FastifyInstance } from 'fastify';
import { appEnv } from '../lib/env';
import { openApiDocument } from '../openapi/document';

function shouldMountApiDocs(): boolean {
  return appEnv.enableApiDocs;
}

export async function registerFastifySwagger(app: FastifyInstance): Promise<void> {
  if (!shouldMountApiDocs()) {
    app.get('/api-docs', async (request, reply) => {
      reply.code(403).send({
        error: {
          code: 'API_DOCS_DISABLED',
          message:
            'Swagger UI is disabled in production. Set ENABLE_API_DOCS=true for the API container, then restart.',
        },
        requestId: request.id,
      });
    });
    return;
  }

  await app.register(fastifySwagger, {
    mode: 'static',
    specification: {
      document: openApiDocument as unknown as Record<string, unknown>,
    },
  } as never);
  await app.register(fastifySwaggerUi, {
    routePrefix: '/api-docs',
    staticCSP: true,
  });
}
