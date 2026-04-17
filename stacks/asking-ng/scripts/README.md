# Scripts (operator helpers)

## `verify-poll-webhook-example.mjs`

Reference verifier for signed poll webhooks.

It demonstrates three required checks before accepting a callback:

1. **Timestamp skew window** via `X-Asking-Webhook-Timestamp`.
2. **HMAC signature** via `X-Asking-Webhook-Signature` (`v1=<hex>` over `${timestamp}.${rawBody}`).
3. **Replay key extraction** via `event_id` / `X-Asking-Webhook-Event-Id`.

### Usage

Pipe the raw JSON body from your webhook receiver into the script and pass headers through env vars:

```bash
cat body.json | \
ASKING_WEBHOOK_SECRET="your_webhook_secret" \
ASKING_WEBHOOK_TS="1735689600" \
ASKING_WEBHOOK_SIG="v1=abcdef..." \
ASKING_WEBHOOK_EVENT_ID="d34db33f..." \
node scripts/verify-poll-webhook-example.mjs
```

If verification passes, it prints `{ ok: true, event_id, replay_check }`.

### Production note

The script intentionally does **not** persist replay keys. In production, store `event_id`
in Redis/DB with a TTL and reject duplicates before processing business logic.
