# Password Pusher

Secure password and secret sharing: create shareable links with **view limits** and **expiration**. Recipients see the secret once (or a set number of times), then the link expires. Optional passphrase for extra protection.

**Website:** https://pwpush.com  
**Docs:** https://docs.pwpush.com  
**GitHub:** https://github.com/pglombardo/PasswordPusher

## Quick start

1. **Environment**
   - Copy `.env.example` to `.env`.
   - Set `PWPUSH_MASTER_KEY` (required). Generate with the command below, or at https://us.pwpush.com/generate_key.
2. **Deploy:** `docker compose up -d` (or add the stack in Portainer and set the same vars in the stack Environment).
3. **Access:** Open via Caddy (e.g. https://pwpush.home or https://pwpush.yourdomain.com). Create a push, set “Expire after X views” and/or “Expire after X days”, share the link.

## Generating keys and secrets

**PWPUSH_MASTER_KEY** (required) – used to encrypt pushes. Generate a random key:

```bash
openssl rand -base64 32
```

Set the output as `PWPUSH_MASTER_KEY` in `.env`. Alternatively, generate a key at https://us.pwpush.com/generate_key.

The stack uses a **named volume** for the SQLite database and file uploads, so it works when deployed from Portainer.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `pwpush:5100`) |
| **Network** | `monitor` (external) — Caddy can reverse-proxy to `pwpush:5100` |
| **Image** | `pglombardo/pwpush:stable` |
| **Env** | `PWPUSH_MASTER_KEY` (required); optional `TZ`, `PWP__HOST_DOMAIN`, `PWP__HOST_PROTOCOL`, `PWP__ENABLE_LOGINS`, `PWP__PURGE_AFTER` |
| **Storage** | Named volume `pwpush-storage` (SQLite + file pushes) |

## Features

- **View limits** — Expire after 1 view, 2 views, etc.
- **Expiration** — Expire after X days or hours.
- **Optional passphrase** — Require a password to reveal the secret.
- **Text, files, URLs, QR** — Multiple push types (can disable in config).
- **Optional logins** — User accounts (requires SMTP for confirmation emails and password resets; see below).

**Confirmation emails:** If you signed up but never got a confirmation email, SMTP is not configured. Either [configure SMTP](#smtp-optional) below, or confirm your account manually: `docker exec -it pwpush bin/pwpush console`, then run `user = User.find_by(email: 'your@email.com'); user.confirm` and `exit`.

Defaults for new pushes (e.g. default days, max views) are configurable via [environment variables](https://docs.pwpush.com/docs/self-hosted-configuration/).

## SMTP (optional)

To send signup confirmation emails and password-reset emails, set these in your `.env` or Portainer stack Environment (see [docs](https://docs.pwpush.com/docs/enabling-logins/)):

- `PWP__MAIL__SMTP_ADDRESS`, `PWP__MAIL__SMTP_PORT`, `PWP__MAIL__SMTP_USER_NAME`, `PWP__MAIL__SMTP_PASSWORD`
- `PWP__MAIL__SMTP_AUTHENTICATION=plain`, `PWP__MAIL__SMTP_STARTTLS=true`
- `PWP__MAIL__MAILER_SENDER` (e.g. `"Password Pusher" <noreply@yourdomain.com>`)
- `PWP__HOST_DOMAIN` and `PWP__HOST_PROTOCOL=https` so links in emails point to your instance

Without SMTP, you can still confirm users manually via the app console (see note above).

## Caddy reverse proxy

Example Caddy vhost (e.g. in your Caddyfile):

```
pwpush.home, pwpush.yourdomain.com {
  reverse_proxy pwpush:5100
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `pwpush:5100`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose and set `PWPUSH_MASTER_KEY` (and optional vars) in **Environment**.
