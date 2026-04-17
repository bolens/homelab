import { cleanEnv, num, str } from 'envalid';
import { coercePollWebhookHintLocale } from './pollWebhookHintPacks';

function parseBoolish(value: string, fallback: boolean): boolean {
  const normalized = value.trim().toLowerCase();
  if (normalized === 'true' || normalized === '1' || normalized === 'yes') return true;
  if (normalized === 'false' || normalized === '0' || normalized === 'no') return false;
  return fallback;
}

function parseOptionalPositive(value: number): number | undefined {
  return Number.isFinite(value) && value > 0 ? value : undefined;
}

const env = cleanEnv(process.env, {
  NODE_ENV: str({ default: 'development' }),
  LOG_LEVEL: str({ default: '' }),
  CORS_ORIGIN: str({ default: '' }),
  EXPOSE_SERVICE_INFO_DETAILS: str({ default: '' }),
  SERVICE_NAME: str({ default: 'asking-ng-api' }),
  GIT_COMMIT: str({ default: '' }),
  SOURCE_COMMIT: str({ default: '' }),
  JWT_SECRET: str({ default: '' }),
  DATABASE_URI: str({ default: '' }),
  POSTGRES_USER: str({ default: '' }),
  POSTGRES_PASSWORD: str({ default: '' }),
  POSTGRES_DB: str({ default: '' }),
  POSTGRES_HOST: str({ default: 'asking-db' }),
  POSTGRES_PORT: str({ default: '5432' }),
  ADMIN_TOKEN: str({ default: '' }),
  READ_MODEL_ENABLED: str({ default: '' }),
  READ_MODEL_RECONCILE_ALERT_MISMATCH_COUNT: num({ default: 0 }),
  READ_MODEL_RECONCILE_ALERT_DIFF_THRESHOLD: num({ default: 0 }),
  ENABLE_API_DOCS: str({ default: '' }),
  ASYNC_JOB_RUNNER_ENABLED: str({ default: '' }),
  ASYNC_JOB_RUNNER_CONCURRENCY: num({ default: 2 }),
  ASYNC_JOB_QUEUE_MAX: num({ default: 5000 }),
  POLL_RETENTION_SWEEP_INTERVAL_SEC: num({ default: 300 }),
  POLL_RETENTION_SWEEP_BATCH_SIZE: num({ default: 200 }),
  POLL_RETENTION_TTL_DAYS_DEFAULT: num({ default: 0 }),
  AUDIT_LOG_RETENTION_DAYS: num({ default: 0 }),
  MODERATION_REJECTED_VOTE_RETENTION_DAYS: num({ default: 0 }),
  PLATFORM_WEBHOOK_ID_HASH_SALT: str({ default: '' }),
  ENABLE_PLATFORM_WEBHOOKS: str({ default: '' }),
  PLATFORM_WEBHOOK_SHARED_SECRET: str({ default: '' }),
  ENABLE_POLAR_WEBHOOKS: str({ default: '' }),
  POLAR_WEBHOOK_SECRET: str({ default: '' }),
  POLAR_CUSTOMER_PORTAL_URL: str({ default: '' }),
  POLAR_CHECKOUT_CLOUD_TEAM_URL: str({ default: '' }),
  POLAR_CHECKOUT_CLOUD_PRO_URL: str({ default: '' }),
  POLAR_PRODUCT_ID_CLOUD_TEAM: str({ default: '' }),
  POLAR_PRODUCT_ID_CLOUD_PRO: str({ default: '' }),
  /** Organization Access Token for server-side Polar API (subscription reconcile). */
  POLAR_ACCESS_TOKEN: str({ default: '' }),
  /** `production` (default) or `sandbox` — must match where subscriptions live. */
  POLAR_SERVER: str({ default: '' }),
  /** Background Polar reconcile interval in seconds; 0 disables scheduled reconcile worker. */
  POLAR_RECONCILE_INTERVAL_SEC: num({ default: 0 }),
  /** Max workspaces scanned per scheduled reconcile run (safety cap still applies in reconcile function). */
  POLAR_RECONCILE_LIMIT: num({ default: 50 }),
  BILLING_ENFORCE_LIMITS: str({ default: '' }),
  /** Self-host Pro license expiration (UTC ms since epoch). 0/empty disables self-host license evaluation. */
  SELFHOST_PRO_LICENSE_VALID_UNTIL_MS: num({ default: 0 }),
  /** Last successful local/remote license verification timestamp (UTC ms). */
  SELFHOST_PRO_LICENSE_LAST_VERIFIED_MS: num({ default: 0 }),
  /** Offline grace window in hours after expiry while verification is unavailable (default ~72h). */
  SELFHOST_PRO_LICENSE_OFFLINE_GRACE_HOURS: num({ default: 72 }),
  PUBLIC_SITE_URL: str({ default: '' }),
  WS_ALLOWED_ORIGINS: str({ default: '' }),
  WS_ALLOW_MISSING_ORIGIN: str({ default: '' }),
  WS_UPGRADE_MAX_PER_IP: num({ default: 45 }),
  WS_UPGRADE_WINDOW_MS: num({ default: 60_000 }),
  WS_MAX_SUBSCRIBERS_PER_POLL: num({ default: 250 }),
  /** Hard ceiling for server→client poll-live messages per poll per second (billing tier may lower further). */
  WS_FANOUT_MAX_PER_POLL_PER_SEC: num({ default: 10_000 }),
  LLM_PROVIDER: str({ default: '' }),
  OLLAMA_BASE_URL: str({ default: 'http://127.0.0.1:11434' }),
  OLLAMA_API_KEY: str({ default: '' }),
  LMSTUDIO_BASE_URL: str({ default: 'http://127.0.0.1:1234' }),
  LMSTUDIO_API_KEY: str({ default: '' }),
  LLM_ALLOWED_UPSTREAM_HOSTS: str({ default: '' }),
  LLM_ALLOWED_MODELS: str({ default: '' }),
  LLM_EXPOSE_PUBLIC_DETAILS: str({ default: '' }),
  LLM_GATEWAY_TOKEN: str({ default: '' }),
  LLM_RATE_LIMIT_WINDOW_MS: num({ default: 60_000 }),
  LLM_RATE_LIMIT_MAX_PER_WINDOW: num({ default: 60 }),
  LLM_UPSTREAM_TIMEOUT_MS: num({ default: 20_000 }),
  INCIDENT_MODE: str({ default: '' }),
  VOTE_IP_HASH_SALT: str({ default: '' }),
  CHAT_CHANNEL_VOTE_MAX_PER_MIN: num({ default: 120 }),
  /** Rolling window (seconds) for optional IP burst auto-quarantine (0 threshold disables). */
  TRUST_IP_BURST_WINDOW_SEC: num({ default: 10 }),
  /** Min votes from same hashed IP in that window before the next vote is quarantined; 0 = off. */
  TRUST_IP_BURST_VOTE_THRESHOLD: num({ default: 0 }),
  /** Rolling window (seconds) for optional chat-channel burst auto-quarantine; 0 threshold disables. */
  TRUST_CHAT_BURST_WINDOW_SEC: num({ default: 10 }),
  /** Min votes with same chat_channel_id in that window before the next vote is quarantined; 0 = off. */
  TRUST_CHAT_BURST_VOTE_THRESHOLD: num({ default: 0 }),
  PANIC_PAUSE_MESSAGE: str({ default: '' }),
  SESSION_CACHE_TTL_MS: num({ default: 2_000 }),
  SEQUELIZE_SYNC_ALTER: str({ default: '' }),
  PORT: num({ default: 3001 }),
  HTTP_RATE_LIMIT_MAX: num({ default: 300 }),
  HTTP_RATE_LIMIT_WINDOW_MS: num({ default: 60_000 }),
  PRESSURE_MAX_EVENT_LOOP_DELAY_MS: num({ default: 1_000 }),
  PRESSURE_MAX_HEAP_USED_BYTES: num({ default: 0 }),
  PRESSURE_MAX_RSS_BYTES: num({ default: 0 }),
  ENABLE_PROMETHEUS_METRICS: str({ default: '' }),
  NOTIFY_WEBHOOK_URL: str({ default: '' }),
  NOTIFY_WEBHOOK_TOKEN: str({ default: '' }),
  AUDIT_LOG_SINK_URL: str({ default: '' }),
  AUDIT_LOG_SINK_TOKEN: str({ default: '' }),
  SENTRY_COMPAT_WEBHOOK_URL: str({ default: '' }),
  SENTRY_COMPAT_WEBHOOK_TOKEN: str({ default: '' }),
  INTEGRATION_WEBHOOK_TIMEOUT_MS: num({ default: 5000 }),
  INTEGRATION_CIRCUIT_BREAKER_THRESHOLD: num({ default: 5 }),
  INTEGRATION_CIRCUIT_BREAKER_COOLDOWN_MS: num({ default: 60_000 }),
  AUTH_PROXY_ENABLED: str({ default: '' }),
  AUTH_PROXY_PROVIDER: str({ default: 'generic' }),
  AUTH_PROXY_USER_HEADER: str({ default: 'x-auth-request-user' }),
  AUTH_PROXY_EMAIL_HEADER: str({ default: 'x-auth-request-email' }),
  AUTH_PROXY_GROUPS_HEADER: str({ default: 'x-auth-request-groups' }),
  AUTH_PROXY_ROLE_HEADER: str({ default: 'x-auth-request-role' }),
  AUTH_PROXY_ALLOWED_ROLES: str({ default: 'user,admin,superadmin' }),
  AUTH_PROXY_DEFAULT_ROLE: str({ default: 'user' }),
  AUTH_PROXY_AUTO_PROVISION: str({ default: '' }),
  AUTH_PROXY_TRUSTED_IPS: str({ default: '' }),
  /** Default locale for poll integration webhook `command_hints` (`en` | `en-gb` | `es`). */
  POLL_WEBHOOK_HINT_LOCALE: str({ default: 'en' }),
  /** `eu` | `non-eu` | empty (derive from geo header when set). */
  FORCE_CONSENT_REGION: str({ default: '' }),
  /** Lowercase HTTP header name with ISO country code (e.g. Cloudflare `cf-ipcountry`). */
  CONSENT_COUNTRY_HEADER: str({ default: 'cf-ipcountry' }),
});

export const appEnv = {
  nodeEnv: env.NODE_ENV,
  logLevel: env.LOG_LEVEL.trim(),
  corsOrigins: env.CORS_ORIGIN.split(',')
    .map((entry) => entry.trim())
    .filter(Boolean),
  exposeServiceInfoDetails: parseBoolish(
    env.EXPOSE_SERVICE_INFO_DETAILS,
    env.NODE_ENV !== 'production',
  ),
  serviceName: env.SERVICE_NAME.trim() || 'asking-ng-api',
  commit: env.GIT_COMMIT.trim() || env.SOURCE_COMMIT.trim() || undefined,
  jwtSecret: env.JWT_SECRET.trim(),
  databaseUri: env.DATABASE_URI.trim() || undefined,
  postgresUser: env.POSTGRES_USER.trim(),
  postgresPassword: env.POSTGRES_PASSWORD,
  postgresDb: env.POSTGRES_DB.trim(),
  postgresHost: env.POSTGRES_HOST.trim() || 'asking-db',
  postgresPort: env.POSTGRES_PORT.trim() || '5432',
  adminToken: env.ADMIN_TOKEN.trim(),
  readModelEnabled: parseBoolish(env.READ_MODEL_ENABLED, false),
  readModelReconcileAlertMismatchCount: Math.max(
    0,
    Math.floor(env.READ_MODEL_RECONCILE_ALERT_MISMATCH_COUNT),
  ),
  readModelReconcileAlertDiffThreshold: Math.max(
    0,
    Math.floor(env.READ_MODEL_RECONCILE_ALERT_DIFF_THRESHOLD),
  ),
  enableApiDocs: parseBoolish(env.ENABLE_API_DOCS, env.NODE_ENV !== 'production'),
  asyncJobRunnerEnabled: parseBoolish(env.ASYNC_JOB_RUNNER_ENABLED, false),
  asyncJobRunnerConcurrency: Math.min(
    16,
    Math.max(1, Math.floor(env.ASYNC_JOB_RUNNER_CONCURRENCY)),
  ),
  asyncJobQueueMax: Math.min(100_000, Math.max(100, Math.floor(env.ASYNC_JOB_QUEUE_MAX))),
  pollRetentionSweepIntervalSec: Math.min(
    86_400,
    Math.max(30, Math.floor(env.POLL_RETENTION_SWEEP_INTERVAL_SEC)),
  ),
  pollRetentionSweepBatchSize: Math.min(
    5_000,
    Math.max(10, Math.floor(env.POLL_RETENTION_SWEEP_BATCH_SIZE)),
  ),
  pollRetentionTtlDaysDefault: Math.max(
    0,
    Math.min(3650, Math.floor(env.POLL_RETENTION_TTL_DAYS_DEFAULT)),
  ),
  auditLogRetentionDays: Math.max(0, Math.min(3650, Math.floor(env.AUDIT_LOG_RETENTION_DAYS))),
  moderationRejectedVoteRetentionDays: Math.max(
    0,
    Math.min(3650, Math.floor(env.MODERATION_REJECTED_VOTE_RETENTION_DAYS)),
  ),
  platformWebhookIdHashSalt: env.PLATFORM_WEBHOOK_ID_HASH_SALT.trim() || 'dev-platform-id-salt',
  enablePlatformWebhooks: parseBoolish(env.ENABLE_PLATFORM_WEBHOOKS, false),
  platformWebhookSharedSecret: env.PLATFORM_WEBHOOK_SHARED_SECRET.trim(),
  enablePolarWebhooks: parseBoolish(env.ENABLE_POLAR_WEBHOOKS, false),
  polarWebhookSecret: env.POLAR_WEBHOOK_SECRET.trim(),
  polarCustomerPortalUrl: env.POLAR_CUSTOMER_PORTAL_URL.trim(),
  polarCheckoutCloudTeamUrl: env.POLAR_CHECKOUT_CLOUD_TEAM_URL.trim(),
  polarCheckoutCloudProUrl: env.POLAR_CHECKOUT_CLOUD_PRO_URL.trim(),
  polarProductIdCloudTeam: env.POLAR_PRODUCT_ID_CLOUD_TEAM.trim(),
  polarProductIdCloudPro: env.POLAR_PRODUCT_ID_CLOUD_PRO.trim(),
  polarAccessToken: env.POLAR_ACCESS_TOKEN.trim(),
  polarServer: env.POLAR_SERVER.trim().toLowerCase() === 'sandbox' ? 'sandbox' : 'production',
  polarReconcileIntervalSec: Math.max(
    0,
    Math.min(86_400, Math.floor(env.POLAR_RECONCILE_INTERVAL_SEC)),
  ),
  polarReconcileLimit: Math.max(1, Math.min(200, Math.floor(env.POLAR_RECONCILE_LIMIT))),
  billingEnforceLimits: parseBoolish(env.BILLING_ENFORCE_LIMITS, false),
  selfhostProLicenseValidUntilMs: Math.max(0, Math.floor(env.SELFHOST_PRO_LICENSE_VALID_UNTIL_MS)),
  selfhostProLicenseLastVerifiedMs: Math.max(
    0,
    Math.floor(env.SELFHOST_PRO_LICENSE_LAST_VERIFIED_MS),
  ),
  selfhostProLicenseOfflineGraceHours: Math.max(
    0,
    Math.min(24 * 30, Math.floor(env.SELFHOST_PRO_LICENSE_OFFLINE_GRACE_HOURS)),
  ),
  publicSiteUrl: env.PUBLIC_SITE_URL.trim().replace(/\/$/, ''),
  wsAllowedOriginsRaw: env.WS_ALLOWED_ORIGINS,
  wsAllowMissingOrigin: parseBoolish(env.WS_ALLOW_MISSING_ORIGIN, false),
  wsUpgradeMaxPerIp: Math.min(2000, Math.max(5, Math.floor(env.WS_UPGRADE_MAX_PER_IP))),
  wsUpgradeWindowMs: Math.min(3_600_000, Math.max(5_000, Math.floor(env.WS_UPGRADE_WINDOW_MS))),
  wsMaxSubscribersPerPoll: Math.min(
    50_000,
    Math.max(10, Math.floor(env.WS_MAX_SUBSCRIBERS_PER_POLL)),
  ),
  wsFanoutMaxPerPollPerSec: Math.min(
    50_000,
    Math.max(1, Math.floor(env.WS_FANOUT_MAX_PER_POLL_PER_SEC)),
  ),
  llmProvider: env.LLM_PROVIDER.trim().toLowerCase(),
  ollamaBaseUrl: env.OLLAMA_BASE_URL.trim().replace(/\/$/, '') || 'http://127.0.0.1:11434',
  ollamaApiKey: env.OLLAMA_API_KEY.trim() || undefined,
  lmStudioBaseUrl: env.LMSTUDIO_BASE_URL.trim().replace(/\/$/, '') || 'http://127.0.0.1:1234',
  lmStudioApiKey: env.LMSTUDIO_API_KEY.trim() || undefined,
  llmAllowedUpstreamHostsRaw: env.LLM_ALLOWED_UPSTREAM_HOSTS.trim(),
  llmAllowedModelsRaw: env.LLM_ALLOWED_MODELS.trim(),
  llmExposePublicDetails: parseBoolish(
    env.LLM_EXPOSE_PUBLIC_DETAILS,
    env.NODE_ENV !== 'production',
  ),
  llmGatewayToken: env.LLM_GATEWAY_TOKEN.trim(),
  llmRateLimitWindowMs: Math.min(
    Math.max(1_000, Math.floor(env.LLM_RATE_LIMIT_WINDOW_MS)),
    3_600_000,
  ),
  llmRateLimitMaxPerWindow: Math.min(
    Math.max(1, Math.floor(env.LLM_RATE_LIMIT_MAX_PER_WINDOW)),
    10_000,
  ),
  llmUpstreamTimeoutMs: Math.min(Math.max(1_000, Math.floor(env.LLM_UPSTREAM_TIMEOUT_MS)), 120_000),
  incidentMode: parseBoolish(env.INCIDENT_MODE, false),
  voteIpHashSalt: env.VOTE_IP_HASH_SALT.trim() || 'dev-vote-ip-salt',
  chatChannelVoteMaxPerMin: Math.max(1, Math.floor(env.CHAT_CHANNEL_VOTE_MAX_PER_MIN)),
  trustIpBurstWindowSec: Math.min(300, Math.max(3, Math.floor(env.TRUST_IP_BURST_WINDOW_SEC))),
  trustIpBurstVoteThreshold: Math.max(
    0,
    Math.min(500, Math.floor(env.TRUST_IP_BURST_VOTE_THRESHOLD)),
  ),
  trustChatBurstWindowSec: Math.min(300, Math.max(3, Math.floor(env.TRUST_CHAT_BURST_WINDOW_SEC))),
  trustChatBurstVoteThreshold: Math.max(
    0,
    Math.min(500, Math.floor(env.TRUST_CHAT_BURST_VOTE_THRESHOLD)),
  ),
  panicPauseMessage: env.PANIC_PAUSE_MESSAGE.trim(),
  sessionCacheTtlMs: Math.min(60_000, Math.max(100, Math.floor(env.SESSION_CACHE_TTL_MS))),
  sequelizeSyncAlter: parseBoolish(env.SEQUELIZE_SYNC_ALTER, env.NODE_ENV !== 'production'),
  port: env.PORT,
  httpRateLimitMax: Math.max(1, Math.floor(env.HTTP_RATE_LIMIT_MAX)),
  httpRateLimitWindowMs: Math.max(1_000, Math.floor(env.HTTP_RATE_LIMIT_WINDOW_MS)),
  pressureMaxEventLoopDelayMs: Math.max(100, Math.floor(env.PRESSURE_MAX_EVENT_LOOP_DELAY_MS)),
  pressureMaxHeapUsedBytes: parseOptionalPositive(env.PRESSURE_MAX_HEAP_USED_BYTES),
  pressureMaxRssBytes: parseOptionalPositive(env.PRESSURE_MAX_RSS_BYTES),
  enablePrometheusMetrics: parseBoolish(env.ENABLE_PROMETHEUS_METRICS, false),
  notifyWebhookUrl: env.NOTIFY_WEBHOOK_URL.trim() || undefined,
  notifyWebhookToken: env.NOTIFY_WEBHOOK_TOKEN.trim() || undefined,
  auditLogSinkUrl: env.AUDIT_LOG_SINK_URL.trim() || undefined,
  auditLogSinkToken: env.AUDIT_LOG_SINK_TOKEN.trim() || undefined,
  sentryCompatWebhookUrl: env.SENTRY_COMPAT_WEBHOOK_URL.trim() || undefined,
  sentryCompatWebhookToken: env.SENTRY_COMPAT_WEBHOOK_TOKEN.trim() || undefined,
  integrationWebhookTimeoutMs: Math.min(
    30_000,
    Math.max(500, Math.floor(env.INTEGRATION_WEBHOOK_TIMEOUT_MS)),
  ),
  integrationCircuitBreakerThreshold: Math.min(
    100,
    Math.max(1, Math.floor(env.INTEGRATION_CIRCUIT_BREAKER_THRESHOLD)),
  ),
  integrationCircuitBreakerCooldownMs: Math.min(
    60 * 60_000,
    Math.max(5_000, Math.floor(env.INTEGRATION_CIRCUIT_BREAKER_COOLDOWN_MS)),
  ),
  authProxyEnabled: parseBoolish(env.AUTH_PROXY_ENABLED, false),
  authProxyProvider: env.AUTH_PROXY_PROVIDER.trim().toLowerCase() || 'generic',
  authProxyUserHeader: env.AUTH_PROXY_USER_HEADER.trim().toLowerCase() || 'x-auth-request-user',
  authProxyEmailHeader: env.AUTH_PROXY_EMAIL_HEADER.trim().toLowerCase() || 'x-auth-request-email',
  authProxyGroupsHeader:
    env.AUTH_PROXY_GROUPS_HEADER.trim().toLowerCase() || 'x-auth-request-groups',
  authProxyRoleHeader: env.AUTH_PROXY_ROLE_HEADER.trim().toLowerCase() || 'x-auth-request-role',
  authProxyAllowedRoles: env.AUTH_PROXY_ALLOWED_ROLES.split(',')
    .map((entry) => entry.trim().toLowerCase())
    .filter((role) => role === 'user' || role === 'admin' || role === 'superadmin'),
  authProxyDefaultRole: ['user', 'admin', 'superadmin'].includes(
    env.AUTH_PROXY_DEFAULT_ROLE.trim().toLowerCase(),
  )
    ? (env.AUTH_PROXY_DEFAULT_ROLE.trim().toLowerCase() as 'user' | 'admin' | 'superadmin')
    : 'user',
  authProxyAutoProvision: parseBoolish(env.AUTH_PROXY_AUTO_PROVISION, true),
  authProxyTrustedIps: env.AUTH_PROXY_TRUSTED_IPS.split(',')
    .map((entry) => entry.trim())
    .filter(Boolean),
  forceConsentRegion: ((): '' | 'eu' | 'non-eu' => {
    const v = env.FORCE_CONSENT_REGION.trim().toLowerCase();
    if (v === 'eu' || v === 'non-eu') return v;
    return '';
  })(),
  consentCountryHeader: env.CONSENT_COUNTRY_HEADER.trim().toLowerCase() || 'cf-ipcountry',
  pollWebhookHintLocale: coercePollWebhookHintLocale(env.POLL_WEBHOOK_HINT_LOCALE.trim() || 'en'),
} as const;
