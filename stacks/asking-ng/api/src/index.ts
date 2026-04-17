import type { Server } from 'node:http';
import { stopAsyncJobs } from './lib/asyncJobs';
import { appEnv } from './lib/env';
import {
  allowedLlmUpstreamHosts,
  assertLlmUpstreamUrlAllowed,
  lmStudioBaseUrl,
  ollamaBaseUrl,
  resolveLlmProvider,
} from './lib/llmProviders';
import { logger } from './lib/logger';
import { runMigrations } from './lib/migrate';
import { startPolarReconcileWorker, stopPolarReconcileWorker } from './lib/polarReconcileWorker';
import { attachPollLiveWss } from './lib/pollLive';
import { startPollRetentionWorker, stopPollRetentionWorker } from './lib/pollRetention';
import sequelize from './models';
import { buildFastifyApp } from './server/app';
import './models/auditlog.sequelize';
import './models/appsettings.sequelize';
import './models/user.sequelize';
import './models/workspace.sequelize';
import './models/polarWebhookDelivery.sequelize';
import './model/Poll';
import './model/Vote';
let app: Awaited<ReturnType<typeof buildFastifyApp>> | undefined;
let isShuttingDown = false;

function wantSyncAlter(): boolean {
  return appEnv.sequelizeSyncAlter;
}

async function shutdown(signal: string) {
  if (isShuttingDown) return;
  isShuttingDown = true;
  logger.info({ event: 'api.shutdown.start', signal }, 'api shutdown');
  if (app) {
    await app.close().catch((err: unknown) => {
      logger.error({ event: 'api.shutdown.fastify_close_failed', err }, 'fastify.close error');
    });
  }
  await stopAsyncJobs().catch((err: unknown) => {
    logger.error({ event: 'api.shutdown.async_jobs_failed', err }, 'async job shutdown error');
  });
  stopPollRetentionWorker();
  stopPolarReconcileWorker();
  await sequelize.close().catch((err: unknown) => {
    logger.error({ event: 'api.shutdown.sequelize_close_failed', err }, 'sequelize.close error');
  });
  process.exit(0);
}

process.once('SIGTERM', () => void shutdown('SIGTERM'));
process.once('SIGINT', () => void shutdown('SIGINT'));

function assertProductionJwtSecret(): void {
  if (appEnv.nodeEnv === 'production' && (!appEnv.jwtSecret || appEnv.jwtSecret === 'changeme')) {
    logger.error(
      { event: 'api.bootstrap.jwt_secret_invalid' },
      'JWT_SECRET must be set to a strong non-default value when NODE_ENV is production',
    );
    process.exit(1);
  }
}

function assertProductionAdminToken(): void {
  if (appEnv.nodeEnv === 'production' && (!appEnv.adminToken || appEnv.adminToken === 'changeme')) {
    logger.error(
      { event: 'api.bootstrap.admin_token_invalid' },
      'ADMIN_TOKEN must be set to a strong non-default value when NODE_ENV is production',
    );
    process.exit(1);
  }
}

function assertProductionLlmGatewayToken(): void {
  if (appEnv.nodeEnv !== 'production') return;
  const provider = appEnv.llmProvider;
  if (provider !== 'ollama' && provider !== 'lmstudio' && provider !== 'lm_studio') return;
  if (!appEnv.llmGatewayToken || appEnv.llmGatewayToken === 'changeme') {
    logger.error(
      { event: 'api.bootstrap.llm_gateway_token_invalid' },
      'LLM_GATEWAY_TOKEN must be set to a strong non-default value when LLM_PROVIDER is enabled in production',
    );
    process.exit(1);
  }
}

function assertProductionLlmUpstreamAllowlist(): void {
  if (appEnv.nodeEnv !== 'production') return;
  const provider = resolveLlmProvider();
  if (!provider) return;
  const allowedHosts = allowedLlmUpstreamHosts();
  if (allowedHosts.size === 0) {
    logger.error(
      { event: 'api.bootstrap.llm_allowlist_missing' },
      'LLM_ALLOWED_UPSTREAM_HOSTS must be set when LLM_PROVIDER is enabled in production',
    );
    process.exit(1);
  }
  const baseUrl = provider === 'ollama' ? ollamaBaseUrl() : lmStudioBaseUrl();
  try {
    assertLlmUpstreamUrlAllowed(baseUrl);
  } catch (err: unknown) {
    logger.error(
      { event: 'api.bootstrap.llm_allowlist_validation_failed', err },
      'LLM upstream host allowlist validation failed',
    );
    process.exit(1);
  }
}

async function bootstrap() {
  assertProductionJwtSecret();
  assertProductionAdminToken();
  assertProductionLlmGatewayToken();
  assertProductionLlmUpstreamAllowlist();
  try {
    await runMigrations();
  } catch (err: unknown) {
    logger.error({ event: 'api.bootstrap.migrations_failed', err }, 'migrations failed');
    process.exit(1);
  }
  try {
    await sequelize.sync(wantSyncAlter() ? { alter: true } : {});
  } catch (err: unknown) {
    logger.error({ event: 'api.bootstrap.sequelize_sync_failed', err }, 'sequelize sync failed');
    process.exit(1);
  }
  const port = appEnv.port;
  const listenPort = Number.isFinite(port) && port >= 1 && port <= 65535 ? port : 3001;
  app = await buildFastifyApp();
  attachPollLiveWss(app.server as Server);
  startPollRetentionWorker();
  startPolarReconcileWorker();
  await app.listen({ host: '0.0.0.0', port: listenPort });
  logger.info(
    { event: 'api.bootstrap.listen_ready', port: listenPort },
    'fastify api server listening',
  );
}

void bootstrap();
