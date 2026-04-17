/** Shared description for JSON `{ error, requestId }` error responses. */
const jsonErrorResponse = {
  description: 'Structured error: `{ error: { code, message, details? }, requestId }`',
  content: {
    'application/json': {
      schema: {
        type: 'object',
        required: ['error', 'requestId'],
        properties: {
          error: {
            type: 'object',
            required: ['code', 'message'],
            properties: {
              code: { type: 'string' },
              message: { type: 'string' },
              details: { type: 'object', additionalProperties: true },
            },
          },
          requestId: { type: 'string' },
        },
      },
    },
  },
} as const;

const pollIdParam = { name: 'id', in: 'path' as const, required: true, schema: { type: 'string' } };

/** Optional gate when poll has `embed_read_token` configured (query or header). */
const pollEmbedAccessParams = [
  {
    name: 'embed_token',
    in: 'query' as const,
    required: false,
    schema: { type: 'string' },
    description:
      'When a hash is stored, send this or `X-Poll-Embed-Token`. Poll **owner** may send **`Authorization: Bearer`** instead on GET poll / meta / heatmap / export and PUT vote — not on GET `/embed` (unfurlers have no session). For **WebSocket** `/ws/poll/:id`, owners use query **`ws_bearer`** (same JWT).',
  },
  {
    name: 'X-Poll-Embed-Token',
    in: 'header' as const,
    required: false,
    schema: { type: 'string' },
    description:
      'Same secret as `embed_token` (header form for tools that cannot use query strings).',
  },
] as const;

/** OpenAPI document for `/api-docs` (Swagger UI). */
export const openApiDocument = {
  openapi: '3.0.3',
  info: {
    title: 'asking-ng API',
    version: '1.0.0',
    description:
      'Poll API, auth, admin, readiness, optional LLM gateway (Ollama / LM Studio; returns **503** `LLM_DISABLED` when **INCIDENT_MODE** is set). WebSocket live poll updates at GET /ws/poll/:id (same host/port as HTTP; behind Caddy with /api prefix: /api/ws/poll/:id). Optional **embed read token** gates public reads/votes when configured (`embed_token` query or **X-Poll-Embed-Token** header); WS upgrades also accept **`ws_bearer`** (same user JWT as HTTP `Authorization`) when the caller owns the poll — browsers cannot set WS headers, so use the query param. Optional signed webhooks; GET /poll/:id/meta for compact bot metadata; GET /poll/:id/embed for oEmbed (PUBLIC_SITE_URL); GET /poll/:id/export (api_key or owner JWT). Optional Polar billing: GET /profile/billing (JWT) and POST /billing/webhooks/polar (feature-flagged). WS upgrades honor `WS_ALLOWED_ORIGINS` or `CORS_ORIGIN`, per-IP rate limits, per-poll cap — see stack.env.example.',
  },
  paths: {
    '/healthcheck': {
      get: {
        summary: 'Liveness',
        responses: { '200': { description: 'Process is up' } },
      },
    },
    '/ready': {
      get: {
        summary: 'Readiness (database)',
        responses: {
          '200': { description: 'DB accepts connections' },
          '503': jsonErrorResponse,
        },
      },
    },
    '/info': {
      get: {
        summary: 'Service metadata',
        responses: {
          '200': {
            description:
              'In production, only `{ "service": "…" }` unless EXPOSE_SERVICE_INFO_DETAILS=true. Otherwise: service, version, node, environment; optional commit when GIT_COMMIT or SOURCE_COMMIT is set.',
          },
        },
      },
    },
    '/status/history': {
      get: {
        summary: 'Public status history and incidents',
        parameters: [
          {
            name: 'windowHours',
            in: 'query',
            required: false,
            schema: { type: 'integer', minimum: 1, maximum: 720, default: 24 },
            description: 'How many hours of probe history to aggregate (max 720).',
          },
        ],
        responses: {
          '200': {
            description:
              '{ windowHours, generatedAt, sampleCount, uptimePct|null, incidents[] } based on readiness probe snapshots.',
          },
          '500': jsonErrorResponse,
        },
      },
    },
    '/platform/webhooks/info': {
      get: {
        summary: 'Platform webhook ingestion capability (feature-flagged)',
        responses: {
          '200': {
            description:
              '{ enabled, providers, auth, stored_fields } when platform webhooks are enabled.',
          },
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/platform/webhooks/{provider}': {
      post: {
        summary:
          'Receive platform webhooks (feature-flagged; includes twitch, youtube, kick, discord, telegram, and other common providers).',
        parameters: [
          {
            name: 'provider',
            in: 'path',
            required: true,
            schema: {
              type: 'string',
              enum: [
                'twitch',
                'youtube',
                'kick',
                'discord',
                'telegram',
                'slack',
                'x',
                'tiktok',
                'facebook',
                'instagram',
              ],
            },
          },
          {
            name: 'x-platform-webhook-token',
            in: 'header',
            required: true,
            schema: { type: 'string' },
            description: 'Shared secret token from PLATFORM_WEBHOOK_SHARED_SECRET.',
          },
        ],
        requestBody: {
          required: false,
          content: {
            'application/json': {
              schema: { type: 'object', additionalProperties: true },
            },
          },
        },
        responses: {
          '200': { description: 'Challenge response (provider verification handshake).' },
          '202': { description: 'Webhook accepted and audit-minimized metadata stored.' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '503': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/billing/webhooks/info': {
      get: {
        summary: 'Polar webhook capability (feature-flagged)',
        tags: ['Billing'],
        responses: {
          '200': {
            description:
              '{ enabled, path, verification, deliveriesStoredCount, lastStoredDelivery? } when ENABLE_POLAR_WEBHOOKS=true; Polar Standard Webhooks. Delivery stats come from polar_webhook_deliveries (idempotency log).',
          },
          '404': jsonErrorResponse,
        },
      },
    },
    '/billing/webhooks/polar': {
      post: {
        summary: 'Polar Standard Webhooks delivery (raw JSON body; ENABLE_POLAR_WEBHOOKS)',
        tags: ['Billing'],
        description:
          'Body must be the **raw** webhook JSON as sent by Polar (do not re-serialize). Verified with POLAR_WEBHOOK_SECRET via @polar-sh/sdk.',
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: { type: 'object', additionalProperties: true },
            },
          },
        },
        responses: {
          '204': { description: 'Signature valid; event accepted (no response body).' },
          '400': jsonErrorResponse,
          '403': {
            ...jsonErrorResponse,
            description:
              'Embed token required, `FEATURE_DISABLED` when vote geo collection is off, or when `BILLING_ENFORCE_LIMITS=true`: `PLAN_LIMIT_HEATMAP` for `free` plan workspaces (details include `plan`, `required_plan`, `upgrade_hint`) and `BILLING_LICENSE_EXPIRED` for expired `selfhost-pro` premium access.',
          },
          '404': jsonErrorResponse,
          '503': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/s/{slug}': {
      get: {
        summary: 'Resolve vanity slug to canonical poll URL',
        parameters: [
          {
            name: 'slug',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '302': { description: 'Redirect to the canonical public poll page.' },
          '400': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/auth/login': {
      post: {
        summary: 'Login (JWT)',
        tags: ['Auth'],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['homelab-user', 'password'],
                properties: { homelab-user: { type: 'string' }, password: { type: 'string' } },
              },
            },
          },
        },
        responses: {
          '200': { description: '{ user, token }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': {
            ...jsonErrorResponse,
            description:
              'Embed token required, or when `BILLING_ENFORCE_LIMITS=true`: `PLAN_LIMIT_FORENSIC` for `free` plan workspaces (details include `plan`, `required_plan`, `upgrade_hint`) and `BILLING_LICENSE_EXPIRED` for expired `selfhost-pro` premium access.',
          },
          '429': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/auth/register': {
      post: {
        summary: 'Register user (always created as role user)',
        tags: ['Auth'],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['homelab-user', 'password', 'acceptTermsAndPrivacy'],
                properties: {
                  homelab-user: { type: 'string' },
                  password: { type: 'string', minLength: 8 },
                  acceptTermsAndPrivacy: {
                    type: 'boolean',
                    enum: [true],
                    description: 'Must be true: user has read and agrees to Terms and Privacy policy.',
                  },
                },
              },
            },
          },
        },
        responses: {
          '201': { description: '{ user, token }' },
          '400': jsonErrorResponse,
          '403': jsonErrorResponse,
          '409': jsonErrorResponse,
          '429': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/profile': {
      get: {
        summary: 'Current user profile',
        tags: ['Auth'],
        security: [{ jwtAuth: [] }],
        responses: {
          '200': { description: '{ user: { id, homelab-user, role, llmGatewayToken, billingPlan } }' },
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      delete: {
        summary: 'Delete own account and anonymize linked personal data',
        tags: ['Auth'],
        security: [{ jwtAuth: [] }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['password'],
                properties: { password: { type: 'string' } },
              },
            },
          },
        },
        responses: {
          '200': { description: 'Account deleted' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      put: {
        summary: 'Update own profile',
        tags: ['Auth'],
        security: [{ jwtAuth: [] }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                properties: {
                  homelab-user: { type: 'string' },
                  password: { type: 'string' },
                  llmGatewayToken: { type: 'string', nullable: true, maxLength: 4096 },
                },
              },
            },
          },
        },
        responses: {
          '200': { description: '{ user: { id, homelab-user, role, llmGatewayToken, billingPlan } }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/profile/billing': {
      get: {
        summary: 'Polar checkout / portal links (server-configured URLs for hosted billing)',
        tags: ['Auth'],
        security: [{ jwtAuth: [] }],
        responses: {
          '200': {
            description:
              '{ polar, billing: { plan, pastDue?, subscriptionStatus?, selfhostProLicense? }, usage: { ... } } — Polar URLs from POLAR_*; plan from DB; `billing.pastDue` + `billing.subscriptionStatus` when the default workspace is linked to Polar (e.g. `past_due` for grace UX). For `selfhost-pro`, `billing.selfhostProLicense` exposes phase-1 license state (`active` / `grace` / `expired` / `unknown`) from env-backed timestamps. `usage.usageLedger` now includes recent customer-visible metered rows (latest first; currently `usage.data_export`, `usage.campaign_attribution_shed`, `usage.poll_webhook_delivery_shed`, `usage.ws_fanout_shed`, and `usage.api_rate_limited`), `usage.usageLedgerDaily` includes UTC-day grouped rollups for the same action taxonomy (default trailing 14 days), and `usage.usageReconcile` includes internal UTC-day parity checks between rollup-derived counts and uncapped raw `audit_logs` action counts for exports, shed telemetry actions, and API rate-limit hits. Future metered actions should be added to `usage.usageLedger` and `usage.usageReconcile` together so customer-visible history remains explainable against raw logs. When BILLING_ENFORCE_LIMITS=true, usage includes meters plus outbound WS fanout cap (`min(WS_FANOUT_MAX_PER_POLL_PER_SEC, plan tier)`), optional `webhookDeliveriesThisUtcMinute` / `maxWebhookDeliveriesPerUtcMinute`, optional `campaignAttributionIncrementsToday` / `maxCampaignAttributionPerUtcDay` (in-process UTC **day** UTM attribution increments for the billing workspace), and optional `warnings` (`80` / `95` per meter) when nearing caps.',
          },
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/profile/export': {
      get: {
        summary: 'Download portable JSON export of own account-linked data',
        tags: ['Auth'],
        security: [{ jwtAuth: [] }],
        responses: {
          '200': {
            description: 'JSON attachment (account, polls, votes)',
            content: {
              'application/json': {
                schema: { type: 'object', additionalProperties: true },
              },
            },
          },
          '401': jsonErrorResponse,
          '403': {
            ...jsonErrorResponse,
            description:
              'When `BILLING_ENFORCE_LIMITS=true`: `USAGE_LIMIT_EXPORTS` if this user workspace already reached its daily export job cap (details: max, current, plan).',
          },
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/telemetry/consent-region': {
      get: {
        summary: 'Public consent region hint for cookie UI (no raw country code; from geo header or FORCE_CONSENT_REGION)',
        tags: ['Telemetry'],
        responses: {
          '200': {
            description: '{ region: eu | non-eu | unknown, source: forced | header | unknown }',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  required: ['region', 'source'],
                  properties: {
                    region: { type: 'string', enum: ['eu', 'non-eu', 'unknown'] },
                    source: { type: 'string', enum: ['forced', 'header', 'unknown'] },
                  },
                },
              },
            },
          },
          '500': jsonErrorResponse,
        },
      },
    },
    '/telemetry/consent': {
      post: {
        summary: 'Record cookie / analytics consent (server logs only; no cookies set server-side)',
        tags: ['Telemetry'],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                oneOf: [
                  {
                    type: 'object',
                    required: ['mode', 'choice'],
                    properties: {
                      mode: { type: 'string', enum: ['simple'] },
                      choice: { type: 'string', enum: ['accepted', 'rejected'] },
                      source: { type: 'string', enum: ['banner', 'settings', 'browser_signal'] },
                      clientTs: { type: 'string', format: 'date-time' },
                    },
                  },
                  {
                    type: 'object',
                    required: ['mode', 'necessary', 'functional', 'analytics', 'marketing'],
                    properties: {
                      mode: { type: 'string', enum: ['granular'] },
                      necessary: { type: 'boolean', enum: [true] },
                      functional: { type: 'boolean' },
                      analytics: { type: 'boolean' },
                      marketing: { type: 'boolean' },
                      consentRegion: { type: 'string', enum: ['eu', 'non-eu', 'unknown'] },
                      source: { type: 'string', enum: ['banner', 'settings', 'browser_signal'] },
                      clientTs: { type: 'string', format: 'date-time' },
                    },
                  },
                ],
              },
            },
          },
        },
        responses: {
          '202': { description: '{ status: "accepted" }' },
          '400': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/users': {
      get: {
        summary: 'List users (admin or superadmin JWT only)',
        tags: ['Users'],
        security: [{ jwtAuth: [] }],
        responses: {
          '200': { description: '{ users }' },
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      post: {
        summary: 'Create user (admin or superadmin JWT only)',
        tags: ['Users'],
        security: [{ jwtAuth: [] }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['homelab-user', 'password'],
                properties: {
                  homelab-user: { type: 'string' },
                  password: { type: 'string' },
                  role: { type: 'string', enum: ['user', 'mod', 'admin', 'superadmin'] },
                },
              },
            },
          },
        },
        responses: {
          '201': { description: '{ user }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '409': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/users/reset-password': {
      post: {
        summary: 'Change own password',
        tags: ['Users'],
        security: [{ jwtAuth: [] }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['oldPassword', 'newPassword'],
                properties: {
                  oldPassword: { type: 'string' },
                  newPassword: { type: 'string' },
                },
              },
            },
          },
        },
        responses: {
          '200': { description: 'Password updated' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/users/{id}': {
      get: {
        summary: 'Get user by id (self, or admin/superadmin for any id)',
        tags: ['Users'],
        security: [{ jwtAuth: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        responses: {
          '200': { description: 'User object' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      delete: {
        summary: 'Delete user (admin or superadmin JWT only)',
        tags: ['Users'],
        security: [{ jwtAuth: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        responses: {
          '200': { description: 'Deleted' },
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/users/{id}/role': {
      patch: {
        summary: 'Set user role (admin or superadmin JWT only)',
        tags: ['Users'],
        security: [{ jwtAuth: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['role'],
                properties: {
                  role: { type: 'string', enum: ['user', 'mod', 'admin', 'superadmin'] },
                },
              },
            },
          },
        },
        responses: {
          '200': { description: '{ user }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/users/{id}/reset-password': {
      post: {
        summary: 'Admin reset user password (admin or superadmin JWT only)',
        tags: ['Users'],
        security: [{ jwtAuth: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['password'],
                properties: { password: { type: 'string' } },
              },
            },
          },
        },
        responses: {
          '200': { description: 'Password reset' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll': {
      post: {
        summary: 'Create poll',
        tags: ['Polls'],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['title', 'options', 'expiration', 'limit_ip'],
                properties: {
                  title: { type: 'string' },
                  options: { type: 'array', items: { type: 'string' }, minItems: 2 },
                  expiration: { type: 'number' },
                  limit_ip: { type: 'boolean' },
                  phase: {
                    type: 'string',
                    enum: ['draft', 'open', 'locked', 'revealed'],
                    description:
                      'Initial lifecycle; default **open** (`draft` = no votes until phase changes).',
                  },
                  open_at: {
                    type: 'number',
                    description:
                      'Optional UTC ms epoch to auto-open voting (before this, effective phase is `draft`).',
                  },
                  lock_at: {
                    type: 'number',
                    description:
                      'Optional UTC ms epoch to auto-lock voting (effective phase becomes `locked`).',
                  },
                  reveal_at: {
                    type: 'number',
                    description:
                      'Optional UTC ms epoch to auto-reveal (effective phase becomes `revealed`).',
                  },
                  boosted_voting_enabled: {
                    type: 'boolean',
                    description:
                      'Enable weighted votes (`boost_weight` > 1 allowed on vote endpoint).',
                  },
                  max_boost_weight: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 10,
                    description:
                      'Max allowed `boost_weight` when boosted voting is enabled (default 3).',
                  },
                  show_unweighted_values: {
                    type: 'boolean',
                    description:
                      'When boosted voting is enabled, also expose raw unweighted counts in responses/exports.',
                  },
                  run_of_show_key: {
                    type: 'string',
                    maxLength: 64,
                    description:
                      'Optional queue key for run-of-show grouping (same key = same sequence).',
                  },
                  run_of_show_order: {
                    type: 'integer',
                    minimum: 0,
                    description: 'Optional order index within the run-of-show key.',
                  },
                  vanity_slug: {
                    type: 'string',
                    minLength: 3,
                    maxLength: 64,
                    description:
                      'Optional short slug for redirects at `/s/{slug}` (lowercase letters, numbers, `-`).',
                  },
                  next_poll_id: {
                    type: 'string',
                    description:
                      'Optional linked poll id used by queue/bracket flows for next-step advancement.',
                  },
                  auto_advance_on_close: {
                    type: 'boolean',
                    description:
                      'When true, closing this poll (locked/revealed) can auto-open `next_poll_id`.',
                  },
                  vote_friction_tier: {
                    type: 'string',
                    enum: ['open', 'soft_throttle', 'proof_of_work'],
                    description: 'Per-poll anti-raid vote friction mode.',
                  },
                  allow_write_in: {
                    type: 'boolean',
                    description: 'Allow free-text vote values not present in `options`.',
                  },
                  write_in_max_length: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 280,
                    description: 'Max accepted write-in length when `allow_write_in=true`.',
                  },
                  write_in_blocklist: {
                    type: 'array',
                    items: { type: 'string', maxLength: 64 },
                    description: 'Case-insensitive blocked write-in terms.',
                  },
                  write_in_profanity_filter: {
                    type: 'boolean',
                    description: 'Enable built-in profanity filtering for write-ins.',
                  },
                  soft_throttle_max_votes_per_min: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 240,
                    description:
                      'Max accepted votes per minute per source hash when `vote_friction_tier=soft_throttle`.',
                  },
                  pow_difficulty: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 6,
                    description:
                      'Leading-zero hex difficulty for SHA-256(pollId:nonce) when `vote_friction_tier=proof_of_work`.',
                  },
                  show_notes: {
                    type: 'string',
                    maxLength: 10_000,
                    description:
                      'Private run-of-show notes; returned only to the signed-in owner on GET /poll/:id.',
                  },
                  shared_editor_user_ids: {
                    type: 'array',
                    maxItems: 20,
                    items: { type: 'integer', minimum: 1 },
                    description:
                      'Optional user IDs allowed to edit this poll while it remains in draft phase.',
                  },
                  theme_preset: {
                    type: 'string',
                    enum: ['default', 'sunset', 'ocean', 'neon'],
                    description: 'Optional per-poll visual preset for the public poll page.',
                  },
                  selection_mode: {
                    type: 'string',
                    enum: ['single', 'multi'],
                    description:
                      '`multi` = voters send **option_indices** (fixed options only; mutually exclusive with boosted voting and write-ins in v1). Defaults to **single**.',
                  },
                  vote_eligibility: {
                    type: 'string',
                    enum: ['anonymous', 'account', 'platform_linked'],
                    description:
                      '`anonymous` (default): public voting. `account`: voters must send `Authorization: Bearer` with a valid user JWT; one ballot per user. `platform_linked`: roadmap scaffold for provider-linked voter identity (currently same signed-in requirement as `account`).',
                  },
                  account_vote_consent_ack: {
                    type: 'boolean',
                    description:
                      'Required as `true` when `vote_eligibility` is `account` or `platform_linked` to explicitly acknowledge signed-in identity gating consent/copy.',
                  },
                  platform_identity_provider: {
                    type: 'string',
                    description:
                      'Required when `vote_eligibility=platform_linked`; provider key scaffold (for future OAuth/provider binding).',
                  },
                  platform_identity_consent_version: {
                    type: 'string',
                    description:
                      'Required when `vote_eligibility=platform_linked`; consent/policy copy version acknowledged by creator.',
                  },
                  retention_ttl_days: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 3650,
                    description:
                      'Optional per-poll retention window in days after expiration; auto-delete worker removes expired polls after this TTL.',
                  },
                  retention_legal_hold: {
                    type: 'boolean',
                    description:
                      'Optional legal-hold switch. When true, retention sweeps skip auto-delete for this poll until cleared.',
                  },
                  generate_embed_read_token: {
                    type: 'boolean',
                    description:
                      'When true, response includes one-time **embed_read_token** (store safely; only a hash is kept server-side).',
                  },
                  webhook_targets: {
                    type: 'array',
                    maxItems: 10,
                    description: 'Optional list of signed POST webhook targets.',
                    items: {
                      type: 'object',
                      required: ['url'],
                      properties: {
                        url: { type: 'string', maxLength: 2048 },
                        secret: {
                          type: 'string',
                          minLength: 16,
                          maxLength: 128,
                          description:
                            'Optional signing secret; if omitted the server generates one and returns it once in create response.',
                        },
                        hint_locale: {
                          type: 'string',
                          enum: ['en', 'en-gb', 'es'],
                          description: 'Optional per-target locale for webhook command hint strings.',
                        },
                        include_results_snapshot: {
                          type: 'boolean',
                          description:
                            'When true, this target receives `data.results_snapshot` on poll webhooks (public tallies; excludes quarantined votes).',
                        },
                        include_owner_snapshot: {
                          type: 'boolean',
                          description:
                            'When true, this target receives `data.owner_snapshot` (moderation-style counters; sensitive — trusted URLs only).',
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
        responses: {
          '200': {
            description:
              '{ status, data: { id, api_key, webhook_secrets?: [{ url, secret }], embed_read_token? } } — generated webhook secrets and embed token appear at most once.',
          },
          '400': jsonErrorResponse,
          '403': {
            description:
              'When `BILLING_ENFORCE_LIMITS=true`: `USAGE_LIMIT_ACTIVE_POLLS` if the signed-in creator already owns `max` non-archived polls for their `billing_plan` (details include max, current, plan), `PLAN_LIMIT_AUTOMATION` when non-empty `webhook_targets` are requested on a `free` workspace, `PLAN_LIMIT_RETENTION` when `retention_ttl_days` or `retention_legal_hold=true` is requested on a `free` workspace (plan-limit details include `plan`, `required_plan`, `upgrade_hint`), and `BILLING_LICENSE_EXPIRED` when `selfhost-pro` premium license is expired.',
          },
          '429': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/mine': {
      get: {
        summary: 'List polls owned by the signed-in user (JWT; creatorUserId)',
        tags: ['Polls'],
        security: [{ jwtAuth: [] }],
        parameters: [
          {
            name: 'limit',
            in: 'query',
            schema: { type: 'integer', minimum: 1, maximum: 100 },
            description: 'Default 30',
          },
          {
            name: 'offset',
            in: 'query',
            schema: { type: 'integer', minimum: 0 },
            description: 'Default 0',
          },
          {
            name: 'run_of_show_key',
            in: 'query',
            schema: { type: 'string', maxLength: 64 },
            description: 'Optional filter to one run-of-show queue.',
          },
          {
            name: 'sort',
            in: 'query',
            schema: {
              type: 'string',
              enum: ['created_desc', 'run_of_show'],
              default: 'created_desc',
            },
            description:
              '`run_of_show` sorts by run-of-show order (ascending) then createdAt; default is newest first.',
          },
        ],
        responses: {
          '200': {
            description:
              '{ polls, total, limit, offset } — each poll includes list analytics (**hourly_votes_by_hour_utc** length 24, **weekday_votes_by_dow_utc** length 7, UTC, non-quarantined votes) plus existing impression/vote/peak/UTM funnel fields.',
          },
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/{id}/embed': {
      get: {
        summary: 'oEmbed-style JSON for embeds / link previews (public)',
        tags: ['Polls'],
        parameters: [
          pollIdParam,
          ...pollEmbedAccessParams,
          {
            name: 'X-Platform-Provider',
            in: 'header',
            required: false,
            schema: { type: 'string', maxLength: 64 },
            description:
              'For `vote_eligibility=platform_linked`: provider key. Must match poll `platform_identity_provider` when provided.',
          },
          {
            name: 'X-Platform-Subject',
            in: 'header',
            required: false,
            schema: { type: 'string', maxLength: 256 },
            description:
              'For `vote_eligibility=platform_linked`: required provider-subject identifier for the voter (ASCII token shape).',
          },
        ],
        responses: {
          '200': { description: 'OEmbed JSON (type link + html snippet)' },
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/{id}/meta': {
      get: {
        summary:
          'Compact poll metadata for bots (option indices, can_vote, vote_path, vote_http_method, timestamps_timezone, phase schedule/countdowns, boosted voting flags, run-of-show links, vote friction config, retention fields, integrity_panel, pause_message, embed_gate, public_poll_url/public_results_url; no tallies, no impression bump)',
        tags: ['Polls'],
        parameters: [pollIdParam, ...pollEmbedAccessParams],
        responses: {
          '200': {
            description:
              '{ status, data: { …, **phase** (effective at `server_now_ms`), **phase_schedule** (`open_at`, `lock_at`, `reveal_at`), **boosted_voting_enabled**, **max_boost_weight**, **show_unweighted_values**, run-of-show fields (**run_of_show_key**, **run_of_show_order**, **vanity_slug**, **next_poll_id**, **auto_advance_on_close**), vote-friction fields (**vote_friction_tier**, **soft_throttle_max_votes_per_min**, **pow_difficulty**), retention fields (**`retention_ttl_days`**, **`retention_legal_hold`**, **`auto_delete_at_ms`**), **integrity_panel** safeguard summary, optional owner-only **moderation_counters** (`votes_last_1m`, `unique_ip_hashes_last_1m`, `unique_accounts_last_1m`, `top_ip_votes_last_1m`, `quarantined_votes_pending`, `quarantined_votes_pending_account_linked`, `votes_account_linked_last_24h`, `votes_anonymous_last_24h`), **vote_path** (e.g. `poll/{id}/vote` relative to API base), **vote_http_method**: `PUT`, **timestamps_timezone**: `UTC`, **phase_history**: oldest→newest phase events (`from_phase`, `to_phase`, `at`, `actor_type`, `actor_user_id`, `source`), **public_results_url** (`/{id}/results`) } } — **public_poll_url** uses `PUBLIC_SITE_URL` / `CORS_ORIGIN` or request Host (same rules as oEmbed).',
          },
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/{id}/export': {
      get: {
        summary: 'Export vote totals (api_key header or owner JWT)',
        tags: ['Polls'],
        security: [{ pollApiKey: [] }, { jwtAuth: [] }],
        parameters: [
          pollIdParam,
          {
            name: 'format',
            in: 'query',
            required: true,
            schema: { type: 'string', enum: ['json', 'csv'] },
          },
          {
            name: 'include',
            in: 'query',
            required: false,
            schema: { type: 'string', enum: ['summary', 'votes'], default: 'summary' },
            description: '**votes** = per-vote rows with timestamps where supported.',
          },
        ],
        responses: {
          '200': {
            description:
              '**CSV** — table text only. **JSON** — includes **`exported_at`** (ISO UTC), **`timestamps_timezone`**: `UTC`, **`expiration`**, **`vote_velocity_by_minute_utc`** (`{ minute_utc, vote_count }[]`), and **`phase_history`** (`from_phase`, `to_phase`, `at`, `actor_type`, `actor_user_id`, `source`) plus summary or per-vote rows (`include=votes`: **`voted_at`** ISO strings).',
          },
          '401': jsonErrorResponse,
          '403': {
            ...jsonErrorResponse,
            description:
              'When `BILLING_ENFORCE_LIMITS=true`: `USAGE_LIMIT_EXPORTS` if the poll owner workspace already reached its daily export job cap (details: max, current, plan). Embed token errors also use 403.',
          },
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/{id}/clone': {
      post: {
        summary:
          'Clone an existing poll as a new draft (owner JWT or api_key), copying options/settings with fresh id/api_key and zero votes',
        tags: ['Polls'],
        security: [{ pollApiKey: [] }, { jwtAuth: [] }],
        parameters: [pollIdParam],
        responses: {
          '200': {
            description:
              '{ status, message, data: { id, api_key, source_poll_id } } — cloned poll starts in draft phase.',
          },
          '401': jsonErrorResponse,
          '403': {
            description:
              'When BILLING_ENFORCE_LIMITS=true: USAGE_LIMIT_ACTIVE_POLLS if cloning would exceed non-archived poll cap for the creator billing plan; PLAN_LIMIT_AUTOMATION if the source poll has non-empty webhook_targets on a free workspace; PLAN_LIMIT_RETENTION if the source poll has custom retention_ttl_days or retention_legal_hold=true on a free workspace (plan-limit details include plan, required_plan, upgrade_hint); BILLING_LICENSE_EXPIRED when selfhost-pro premium license is expired on those premium paths.',
          },
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/{id}/votes/{voteId}/text': {
      put: {
        summary:
          'Owner moderation tool: edit a stored vote text (supports write-in cleanup) with audit log entry',
        tags: ['Polls'],
        security: [{ pollApiKey: [] }, { jwtAuth: [] }],
        parameters: [
          pollIdParam,
          { name: 'voteId', in: 'path', required: true, schema: { type: 'string' } },
        ],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['option'],
                properties: {
                  option: { type: 'string', minLength: 1, maxLength: 500 },
                  note: { type: 'string', maxLength: 500 },
                },
              },
            },
          },
        },
        responses: {
          '200': { description: '{ status, data: { vote_id, option } }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': {
            ...jsonErrorResponse,
            description:
              'When `BILLING_ENFORCE_LIMITS=true`: `PLAN_LIMIT_AUTOMATION` if non-empty `webhook_targets` are set on a `free` workspace, `PLAN_LIMIT_RETENTION` if `retention_ttl_days` is set to a non-null value or `retention_legal_hold=true` on a `free` workspace (details include `plan`, `required_plan`, `upgrade_hint`), or `BILLING_LICENSE_EXPIRED` when `selfhost-pro` premium license is expired.',
          },
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/{id}': {
      get: {
        summary:
          'Get poll (public). Optional **Authorization: Bearer** (user JWT) returns **show_notes** when the caller owns the poll.',
        tags: ['Polls'],
        parameters: [pollIdParam, ...pollEmbedAccessParams],
        responses: {
          '200': {
            description:
              'Poll with vote counts, **phase** (effective at `server_now_ms`), **phase_schedule** (`open_at`, `lock_at`, `reveal_at`), boosted voting fields (**boosted_voting_enabled**, **max_boost_weight**, **show_unweighted_values**), run-of-show fields (**run_of_show_key**, **run_of_show_order**, **vanity_slug**, **next_poll_id**, **auto_advance_on_close**), vote-friction fields (**vote_friction_tier**, **soft_throttle_max_votes_per_min**, **pow_difficulty**), write-in hygiene fields (**allow_write_in**, **write_in_max_length**, **write_in_blocklist**, **write_in_profanity_filter**), retention fields (**`retention_ttl_days`**, **`retention_legal_hold`**, **`auto_delete_at_ms`**), **integrity_panel** safeguard summary, optional owner-only **moderation_counters** (`votes_last_1m`, `unique_ip_hashes_last_1m`, `unique_accounts_last_1m`, `top_ip_votes_last_1m`, `quarantined_votes_pending`, `quarantined_votes_pending_account_linked`, `votes_account_linked_last_24h`, `votes_anonymous_last_24h`), **metrics** (aggregate UTC hour/weekday histograms; when **`you_own_this_poll`**, also **`option_hourly_votes_utc`**: per configured option, **`hourly_votes_by_hour_utc`** length 24, **`vote_velocity_by_minute_utc`**: same shape as export summary — up to **4000** most recent UTC minutes with ≥1 vote, chronological; **`vote_velocity_by_minute_utc_truncated`**: `true` when that cap is hit; and **`option_vote_velocity_by_minute_utc`**: per configured option, each with **`vote_velocity_by_minute_utc`** `{ minute_utc, vote_count }[]` on the same up-to-**120** most recent distinct UTC minutes that had any vote, zeros filled, chronological), **voting_paused**, **pause_message**, **impression_count**, **option_entries**; **show_notes** only when caller JWT matches poll owner. **`embed_gate`**: an embed-read hash is configured (WS/live clients may need **`ws_bearer`** when **`you_own_this_poll`**). **`you_own_this_poll`**: caller JWT is the poll creator.',
          },
          '400': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '429': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      put: {
        summary:
          'Update poll: expiration, phase, optional schedule (`open_at`/`lock_at`/`reveal_at`), boosted voting config, run-of-show links/auto-advance, voting pause, notes, rotate embed token, or **panic** kill switch (disallowed **phase** jumps → **400** **`INVALID_PHASE_TRANSITION`**; invalid schedule windows → **400** **`INVALID_PHASE_SCHEDULE`**; invalid boosted config → **400** **`INVALID_BOOSTED_VOTING_CONFIG`**; invalid next poll linkage → **400** **`INVALID_NEXT_POLL`**; **panic** may force **locked** from any phase)',
        tags: ['Polls'],
        security: [{ pollApiKey: [] }, { jwtAuth: [] }],
        parameters: [pollIdParam],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                minProperties: 1,
                properties: {
                  expiration: { type: 'number' },
                  phase: { type: 'string', enum: ['draft', 'open', 'locked', 'revealed'] },
                  open_at: { type: 'number', nullable: true },
                  lock_at: { type: 'number', nullable: true },
                  reveal_at: { type: 'number', nullable: true },
                  boosted_voting_enabled: { type: 'boolean' },
                  max_boost_weight: { type: 'integer', minimum: 1, maximum: 10, nullable: true },
                  show_unweighted_values: { type: 'boolean' },
                  run_of_show_key: { type: 'string', maxLength: 64, nullable: true },
                  run_of_show_order: { type: 'integer', minimum: 0, nullable: true },
                  vanity_slug: { type: 'string', minLength: 3, maxLength: 64, nullable: true },
                  next_poll_id: { type: 'string', nullable: true },
                  auto_advance_on_close: { type: 'boolean' },
                  vote_friction_tier: {
                    type: 'string',
                    enum: ['open', 'soft_throttle', 'proof_of_work'],
                  },
                  allow_write_in: { type: 'boolean' },
                  write_in_max_length: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 280,
                    nullable: true,
                  },
                  write_in_blocklist: {
                    type: 'array',
                    nullable: true,
                    items: { type: 'string', maxLength: 64 },
                  },
                  write_in_profanity_filter: { type: 'boolean' },
                  soft_throttle_max_votes_per_min: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 240,
                    nullable: true,
                  },
                  pow_difficulty: { type: 'integer', minimum: 1, maximum: 6, nullable: true },
                  voting_paused: { type: 'boolean' },
                  pause_message: { type: 'string', nullable: true, maxLength: 280 },
                  show_notes: { type: 'string', nullable: true, maxLength: 10_000 },
                  shared_editor_user_ids: {
                    type: 'array',
                    nullable: true,
                    maxItems: 20,
                    items: { type: 'integer', minimum: 1 },
                  },
                  theme_preset: {
                    type: 'string',
                    nullable: true,
                    enum: ['default', 'sunset', 'ocean', 'neon'],
                  },
                  selection_mode: {
                    type: 'string',
                    nullable: true,
                    enum: ['single', 'multi'],
                    description:
                      'Editable only while the poll is in **draft**; incompatible with boosted voting and write-ins.',
                  },
                  vote_eligibility: {
                    type: 'string',
                    nullable: true,
                    enum: ['anonymous', 'account', 'platform_linked'],
                    description:
                      'Editable only while the poll is in **draft**. `null` resets to **anonymous**.',
                  },
                  account_vote_consent_ack: {
                    type: 'boolean',
                    description:
                      'Required as `true` whenever patching `vote_eligibility=account` or `vote_eligibility=platform_linked`.',
                  },
                  platform_identity_provider: {
                    type: 'string',
                    nullable: true,
                    description:
                      'When `vote_eligibility=platform_linked`, provider key scaffold for provider-linked identity mode.',
                  },
                  platform_identity_consent_version: {
                    type: 'string',
                    nullable: true,
                    description:
                      'When `vote_eligibility=platform_linked`, consent/policy copy version acknowledged for identity-linked voting.',
                  },
                  retention_ttl_days: {
                    type: 'integer',
                    nullable: true,
                    minimum: 1,
                    maximum: 3650,
                    description:
                      'Optional per-poll retention window (days) after expiration; `null` clears to use global default.',
                  },
                  retention_legal_hold: {
                    type: 'boolean',
                    description:
                      'When true, pause retention auto-delete for this poll (legal hold).',
                  },
                  generate_embed_read_token: {
                    type: 'boolean',
                    description:
                      'When **true**, returns one-time **data.embed_read_token** and replaces the stored hash.',
                  },
                  panic: {
                    type: 'boolean',
                    enum: [true],
                    description:
                      'When **true**, sets **phase** `locked`, **voting_paused** `true`, and **pause_message** (from this body if provided, else `PANIC_PAUSE_MESSAGE`, else a default). Must be sent alone except optional **pause_message**; triggers WebSocket `{ type: "panic" }`.',
                  },
                },
                description:
                  'Send at least one field. **panic**: true alone (or with **pause_message** only) is a kill switch; do not combine with phase, voting_paused, expiration, show_notes, account_vote_consent_ack, platform_identity_provider, platform_identity_consent_version, retention_ttl_days, retention_legal_hold, or embed rotation.',
              },
            },
          },
        },
        responses: {
          '200': {
            description:
              '{ status, message } or, when rotating embed token, `{ status, message, data: { embed_read_token } }`',
          },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      delete: {
        summary: 'Delete poll (api_key or owner JWT)',
        tags: ['Polls'],
        security: [{ pollApiKey: [] }, { jwtAuth: [] }],
        parameters: [pollIdParam],
        responses: {
          '200': { description: 'Deleted' },
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/{id}/vote': {
      put: {
        summary:
          'Vote on poll by id or vanity slug (**option** string **or** **option_index** for single-choice polls; **option_indices** array for `selection_mode=multi`; optional **boost_weight**, **pow_nonce**, **chat_channel_id**, **idempotency_key** for bot retries)',
        tags: ['Polls'],
        parameters: [pollIdParam, ...pollEmbedAccessParams],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                oneOf: [
                  {
                    type: 'object',
                    required: ['option'],
                    properties: {
                      option: { type: 'string', minLength: 1, maxLength: 500 },
                      boost_weight: { type: 'integer', minimum: 1, maximum: 10 },
                      pow_nonce: { type: 'string', minLength: 1, maxLength: 256 },
                      chat_channel_id: {
                        type: 'string',
                        minLength: 1,
                        maxLength: 128,
                        description: 'Optional channel id for per-channel vote throttling.',
                      },
                      idempotency_key: {
                        type: 'string',
                        minLength: 1,
                        maxLength: 128,
                        description: 'Optional dedupe key for replay-safe chat command retries.',
                      },
                      location: {
                        type: 'object',
                        description:
                          'Optional browser geolocation. Server stores coarse buckets only for privacy.',
                        properties: {
                          latitude: { type: 'number', minimum: -90, maximum: 90 },
                          longitude: { type: 'number', minimum: -180, maximum: 180 },
                          accuracyM: { type: 'number', minimum: 0 },
                        },
                      },
                    },
                  },
                  {
                    type: 'object',
                    required: ['option_index'],
                    properties: {
                      option_index: { type: 'integer', minimum: 0, maximum: 31 },
                      boost_weight: { type: 'integer', minimum: 1, maximum: 10 },
                      pow_nonce: { type: 'string', minLength: 1, maxLength: 256 },
                      chat_channel_id: {
                        type: 'string',
                        minLength: 1,
                        maxLength: 128,
                        description: 'Optional channel id for per-channel vote throttling.',
                      },
                      idempotency_key: {
                        type: 'string',
                        minLength: 1,
                        maxLength: 128,
                        description: 'Optional dedupe key for replay-safe chat command retries.',
                      },
                      location: {
                        type: 'object',
                        properties: {
                          latitude: { type: 'number', minimum: -90, maximum: 90 },
                          longitude: { type: 'number', minimum: -180, maximum: 180 },
                          accuracyM: { type: 'number', minimum: 0 },
                        },
                      },
                    },
                  },
                  {
                    type: 'object',
                    required: ['option_indices'],
                    properties: {
                      option_indices: {
                        type: 'array',
                        minItems: 1,
                        maxItems: 32,
                        items: { type: 'integer', minimum: 0, maximum: 31 },
                        description:
                          'For `selection_mode=multi` polls only: unique 0-based indices into the poll `options` array.',
                      },
                      pow_nonce: { type: 'string', minLength: 1, maxLength: 256 },
                      chat_channel_id: {
                        type: 'string',
                        minLength: 1,
                        maxLength: 128,
                        description: 'Optional channel id for per-channel vote throttling.',
                      },
                      idempotency_key: {
                        type: 'string',
                        minLength: 1,
                        maxLength: 128,
                        description: 'Optional dedupe key for replay-safe chat command retries.',
                      },
                      location: {
                        type: 'object',
                        properties: {
                          latitude: { type: 'number', minimum: -90, maximum: 90 },
                          longitude: { type: 'number', minimum: -180, maximum: 180 },
                          accuracyM: { type: 'number', minimum: 0 },
                        },
                      },
                    },
                  },
                ],
              },
            },
          },
        },
        responses: {
          '200': { description: 'Vote recorded' },
          '400': {
            ...jsonErrorResponse,
            description:
              'Validation errors and vote-shape checks, plus `PLATFORM_IDENTITY_REQUIRED` when a platform-linked poll is voted without valid `X-Platform-Subject` header.',
          },
          '403': {
            ...jsonErrorResponse,
            description:
              'Embed token required, `PLATFORM_IDENTITY_PROVIDER_MISMATCH` for provider mismatch on platform-linked polls, or when `BILLING_ENFORCE_LIMITS=true`: `USAGE_LIMIT_VOTES` if the poll owner would exceed monthly non-quarantined vote rows for their billing plan (details: max, current, plan, incoming). Otherwise structured error per default schema.',
          },
          '404': jsonErrorResponse,
          '409': {
            ...jsonErrorResponse,
            description:
              'Conflict conditions such as duplicate votes and `PLATFORM_IDENTITY_NOT_CONFIGURED` when a platform-linked poll is missing provider metadata.',
          },
          '429': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/{id}/heatmap': {
      get: {
        summary: 'Get aggregated vote-location heatmap buckets',
        tags: ['Polls'],
        parameters: [
          pollIdParam,
          ...pollEmbedAccessParams,
          {
            name: 'minCount',
            in: 'query',
            schema: { type: 'integer', minimum: 2, maximum: 20, default: 2 },
            description: 'Only return buckets with at least this many votes (privacy threshold).',
          },
        ],
        responses: {
          '200': {
            description:
              '{ data: { points: [{ latitude, longitude, intensity }], minCount, geo_collection_mode: "opt_in_coarse", coordinate_precision_decimals: 1, note } }',
          },
          '400': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/poll/{id}/replay': {
      get: {
        summary: 'Get vote replay events for completed polls',
        tags: ['Polls'],
        parameters: [
          pollIdParam,
          ...pollEmbedAccessParams,
          {
            name: 'limit',
            in: 'query',
            schema: { type: 'integer', minimum: 1, maximum: 10000, default: 5000 },
            description: 'Maximum replay events to return (ordered oldest to newest).',
          },
        ],
        responses: {
          '200': {
            description:
              '{ data: { options, total_votes, completed, events: [{ option_index, offset_ms }] } } where **offset_ms** is relative to the first recorded vote.',
          },
          '400': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '409': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/impersonate/{id}': {
      post: {
        summary: 'Issue JWT for user (admin token)',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        responses: {
          '200': { description: '{ token }' },
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '429': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/status': {
      get: {
        summary: 'Dashboard counts',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': {
            description:
              'users, polls, audit summary, creatorMetrics (votes / peaks / histograms), trustMetrics (quarantine_pending_total, quarantine_pending_polls, quarantine_pending_by_reason, quarantine_approved_last_24h, quarantine_rejected_last_24h, trust_risk_avg_pending, quarantine_pending_account_linked, votes_account_linked_last_24h, votes_anonymous_last_24h), webhookDeliveryTelemetry (recent in-process poll webhook attempts / ok / non-2xx / failed / shed counters; current API process only)',
          },
          '401': jsonErrorResponse,
          '429': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/me': {
      get: {
        summary: 'Primary admin user (superadmin if present, else first admin role)',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': { description: '{ admin: { id, homelab-user, role } } from users table' },
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/signups': {
      get: {
        summary: 'Registration enabled flag',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': { description: '{ enabled }' },
          '401': jsonErrorResponse,
        },
      },
    },
    '/admin/signups/enable': {
      post: {
        summary: 'Enable signups',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': { description: '{ enabled: true }' },
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/signups/disable': {
      post: {
        summary: 'Disable signups',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': { description: '{ enabled: false }' },
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/vote-geo': {
      get: {
        summary: 'Vote geolocation enabled flag',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': { description: '{ enabled }' },
          '401': jsonErrorResponse,
        },
      },
    },
    '/admin/vote-geo/enable': {
      post: {
        summary: 'Enable vote geolocation collection + heatmap',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': { description: '{ enabled: true }' },
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/vote-geo/disable': {
      post: {
        summary: 'Disable vote geolocation collection + heatmap',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': { description: '{ enabled: false }' },
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/change-password': {
      post: {
        summary: 'Change admin password (first admin user in DB)',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['currentPassword', 'newPassword'],
                properties: {
                  currentPassword: { type: 'string' },
                  newPassword: { type: 'string' },
                },
              },
            },
          },
        },
        responses: {
          '200': { description: 'Password updated' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/export/users': {
      get: {
        summary: 'Export users CSV/JSON',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [
          {
            name: 'format',
            in: 'query',
            required: true,
            schema: { type: 'string', enum: ['csv', 'json'] },
          },
        ],
        responses: {
          '200': { description: 'File attachment' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/export/polls': {
      get: {
        summary: 'Export polls CSV/JSON',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [
          {
            name: 'format',
            in: 'query',
            required: true,
            schema: { type: 'string', enum: ['csv', 'json'] },
          },
        ],
        responses: {
          '200': { description: 'File attachment' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/export/audit-logs': {
      get: {
        summary: 'Export audit logs CSV/JSON',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [
          {
            name: 'format',
            in: 'query',
            required: true,
            schema: { type: 'string', enum: ['csv', 'json'] },
          },
        ],
        responses: {
          '200': { description: 'File attachment' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/users': {
      get: {
        summary: 'List users',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': { description: '{ users }' },
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      post: {
        summary: 'Create user',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['homelab-user', 'password'],
                properties: {
                  homelab-user: { type: 'string' },
                  password: { type: 'string' },
                  role: { type: 'string', enum: ['user', 'mod', 'admin', 'superadmin'] },
                },
              },
            },
          },
        },
        responses: {
          '201': { description: '{ user }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '409': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/users/{id}': {
      delete: {
        summary: 'Delete user',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        responses: {
          '200': { description: 'Deleted' },
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/users/{id}/reset-password': {
      post: {
        summary: 'Reset user password',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['password'],
                properties: { password: { type: 'string' } },
              },
            },
          },
        },
        responses: {
          '200': { description: 'Password reset' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/users/{id}/role': {
      patch: {
        summary: 'Change user role',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['role'],
                properties: {
                  role: { type: 'string', enum: ['user', 'mod', 'admin', 'superadmin'] },
                },
              },
            },
          },
        },
        responses: {
          '200': { description: '{ user }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/users/{id}/suspend': {
      patch: {
        summary: 'Suspend user',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        responses: {
          '200': { description: 'Suspended' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/users/{id}/activate': {
      patch: {
        summary: 'Activate user',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [{ name: 'id', in: 'path', required: true, schema: { type: 'integer' } }],
        responses: {
          '200': { description: 'Activated' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/polls': {
      get: {
        summary: 'List polls (admin shape)',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        responses: {
          '200': { description: '{ polls }' },
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      post: {
        summary: 'Create poll',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['question', 'options'],
                properties: {
                  question: { type: 'string' },
                  options: { type: 'array', items: { type: 'string' }, minItems: 2 },
                },
              },
            },
          },
        },
        responses: {
          '201': { description: '{ poll }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/polls/{id}': {
      get: {
        summary: 'Get poll',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [pollIdParam],
        responses: {
          '200': { description: '{ poll }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      patch: {
        summary: 'Update poll question/options',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [pollIdParam],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['question', 'options'],
                properties: {
                  question: { type: 'string' },
                  options: { type: 'array', items: { type: 'string' }, minItems: 2 },
                },
              },
            },
          },
        },
        responses: {
          '200': { description: '{ poll }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
      delete: {
        summary: 'Delete poll and votes',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [pollIdParam],
        responses: {
          '200': { description: 'Deleted' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/polls/{id}/archive': {
      patch: {
        summary: 'Archive poll',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [pollIdParam],
        responses: {
          '200': { description: 'Archived' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/polls/{id}/unarchive': {
      patch: {
        summary: 'Unarchive poll',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [pollIdParam],
        responses: {
          '200': { description: 'Unarchived' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/polls/{id}/reset-votes': {
      post: {
        summary: 'Clear votes for poll',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [pollIdParam],
        responses: {
          '200': { description: 'Votes reset' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/polls/{id}/pause': {
      patch: {
        summary: 'Pause poll voting',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [pollIdParam],
        requestBody: {
          required: false,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                properties: {
                  pause_message: { type: 'string', maxLength: 280 },
                },
              },
            },
          },
        },
        responses: {
          '200': { description: 'Voting paused' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/polls/{id}/unpause': {
      patch: {
        summary: 'Resume poll voting',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [pollIdParam],
        responses: {
          '200': { description: 'Voting resumed' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '404': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/audit-logs': {
      get: {
        summary: 'List audit logs (admin)',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        parameters: [
          { name: 'action', in: 'query', schema: { type: 'string' } },
          { name: 'actor', in: 'query', schema: { type: 'string' } },
          { name: 'target', in: 'query', schema: { type: 'string' } },
          { name: 'start', in: 'query', schema: { type: 'string' } },
          { name: 'end', in: 'query', schema: { type: 'string' } },
          {
            name: 'limit',
            in: 'query',
            schema: { type: 'integer', minimum: 1, maximum: 500, default: 100 },
          },
        ],
        responses: {
          '200': { description: '{ logs: [...] }' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '429': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/admin/billing/reconcile-polar': {
      post: {
        summary: 'Reconcile Polar subscriptions vs DB (admin)',
        description:
          'Fetches Polar **`subscriptions.get`** for **`workspaces`** rows with **`polar_subscription_id`** and aligns **`workspaces.billing_plan`** (mirrored on the owner **`users`** row) using the same rules as webhooks. Requires **`POLAR_ACCESS_TOKEN`** (returns **503** if unset).',
        tags: ['Admin'],
        security: [{ adminToken: [] }],
        requestBody: {
          required: false,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                properties: {
                  dryRun: { type: 'boolean', description: 'Preview drift without writing the DB' },
                  dry_run: { type: 'boolean', description: 'Alias of dryRun' },
                  limit: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 200,
                    description: 'Max workspace rows to scan (default 50, capped at 200)',
                  },
                },
              },
            },
          },
        },
        responses: {
          '200': {
            description:
              '{ ok: true, scanned, polarFetchErrors, driftDetected, rowsUpdated, dryRun, rows[] } each row: ownerUserId, workspaceId, subscriptionId, dbPlanBefore, polarStatus, polarProductId, expectedPlan, drift, updated, optional error',
          },
          '401': jsonErrorResponse,
          '403': jsonErrorResponse,
          '503': jsonErrorResponse,
          '500': jsonErrorResponse,
        },
      },
    },
    '/llm/status': {
      get: {
        summary: 'LLM gateway configuration (no secrets)',
        tags: ['LLM'],
        responses: {
          '200': {
            description:
              'provider, gatewayAuth; in production base URLs are omitted unless LLM_EXPOSE_PUBLIC_DETAILS=true',
          },
          '503': jsonErrorResponse,
        },
      },
    },
    '/llm/v1/models': {
      get: {
        summary: 'List models (OpenAI-style or mapped from Ollama)',
        tags: ['LLM'],
        responses: {
          '200': { description: 'Model list' },
          '503': jsonErrorResponse,
        },
        description: 'Returns **503** `LLM_DISABLED` when **INCIDENT_MODE** is enabled.',
      },
    },
    '/llm/v1/chat/completions': {
      post: {
        summary: 'Chat completions (OpenAI request; Ollama or LM Studio)',
        tags: ['LLM'],
        security: [{ llmGatewayBearer: [] }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['model', 'messages'],
                properties: {
                  model: { type: 'string' },
                  messages: { type: 'array' },
                  temperature: { type: 'number' },
                  max_tokens: { type: 'integer' },
                  stream: { type: 'boolean', description: 'Must be false or omitted' },
                },
              },
            },
          },
        },
        responses: {
          '200': { description: 'OpenAI-style chat completion' },
          '400': jsonErrorResponse,
          '401': jsonErrorResponse,
          '429': jsonErrorResponse,
          '503': jsonErrorResponse,
        },
      },
    },
  },
  components: {
    securitySchemes: {
      jwtAuth: {
        type: 'http',
        scheme: 'bearer',
        description: 'JWT from POST /auth/login (Authorization: Bearer <token>)',
      },
      pollApiKey: {
        type: 'apiKey',
        in: 'header',
        name: 'api_key',
        description:
          'Poll creator secret returned when the poll was created. On **PUT**/**DELETE** `/poll/:id`, either this header **or** a valid **Authorization: Bearer** user JWT matching **creatorUserId** is accepted.',
      },
      llmGatewayBearer: {
        type: 'http',
        scheme: 'bearer',
        description:
          'Optional LLM_GATEWAY_TOKEN when set on the server (same header shape as jwtAuth; different secret)',
      },
      adminToken: {
        type: 'apiKey',
        in: 'header',
        name: 'x-admin-token',
        description: 'ADMIN_TOKEN value from server env',
      },
    },
  },
  tags: [
    { name: 'Auth', description: 'Login, register, profile' },
    { name: 'Telemetry', description: 'Optional client telemetry and consent reporting' },
    { name: 'Billing', description: 'Optional Polar hosted billing webhooks (feature-flagged)' },
    { name: 'Users', description: 'JWT-protected user directory and password routes' },
    { name: 'Polls', description: 'Strawpoll-style poll CRUD and voting' },
    { name: 'Admin', description: 'Admin routes (x-admin-token)' },
    { name: 'LLM', description: 'Local inference via Ollama or LM Studio' },
  ],
} as const;
