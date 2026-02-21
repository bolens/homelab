# Infisical

Self-hosted secrets manager for API keys, environment variables, and config. Sync secrets to apps, CI/CD, and CLI. Open-source alternative to Doppler, Vault (simpler), and env vaults.

**Website:** https://infisical.com  
**GitHub:** https://github.com/Infisical/infisical

## Quick start

1. Copy env: `cp .env.example .env`
2. Generate and set all required keys/secrets (see **Generating keys and secrets** below).
3. Set `SITE_URL` to the URL you use behind Caddy (e.g. `https://infisical.home` or `https://secrets.yourdomain.com`).
4. Deploy: `docker compose up -d`
5. Open the app via Caddy; create the first admin account.

**Portainer:** The stack is Portainer-friendly (no `env_file`; uses `environment:` with variable substitution). Deploy the stack and set all required environment variables (`ENCRYPTION_KEY`, `AUTH_SECRET`, `POSTGRES_PASSWORD`, `SITE_URL`, etc.) in the stack's **Environment** section. See **Required env** below for the list.

## Generating keys and secrets

Run these and paste the output into `.env` (never use the sample values in production):

```bash
# ENCRYPTION_KEY – 32-character hex (16 bytes)
openssl rand -hex 16

# AUTH_SECRET – base64, used for JWT signing
openssl rand -base64 32

# POSTGRES_PASSWORD – strong password for the Postgres DB
openssl rand -base64 24
```

Set in `.env` (or Portainer stack Environment):

- **ENCRYPTION_KEY** = output of `openssl rand -hex 16`
- **AUTH_SECRET** = output of `openssl rand -base64 32`
- **POSTGRES_PASSWORD** = output of `openssl rand -base64 24`
- **POSTGRES_USER** = `infisical` (default, optional)
- **POSTGRES_DB** = `infisical` (default, optional)
- **SITE_URL** = your public URL (e.g. `https://infisical.home`)

Note: `DB_CONNECTION_URI` is automatically constructed from `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` in the docker-compose.yml.

Optional one-liner to append to `.env` (review before saving):

```bash
echo "ENCRYPTION_KEY=$(openssl rand -hex 16)" >> .env
echo "AUTH_SECRET=$(openssl rand -base64 32)" >> .env
echo "POSTGRES_PASSWORD=$(openssl rand -base64 24)" >> .env
```

Then edit `.env` to remove any old placeholder lines and set `SITE_URL`.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (reverse-proxy to `infisical:8080`) |
| **Network** | `monitor` (backend); `infisical` internal for db/redis |
| **Image** | `infisical/infisical:latest` (pin a tag for production) |
| **Env** | Uses `environment:` with `${VAR}` substitution (Portainer-compatible; no `env_file`) |
| **Health** | No dedicated endpoint; use HTTP check to app URL if needed |

## Required env

- **ENCRYPTION_KEY** – 32-character hex; used for encrypting secrets at rest. Generate: `openssl rand -hex 16`.
- **AUTH_SECRET** – Base64 secret for JWT signing. Generate: `openssl rand -base64 32`.
- **POSTGRES_PASSWORD** – DB password; used in `DB_CONNECTION_URI`. Generate: `openssl rand -base64 24`.
- **SITE_URL** – Full base URL (e.g. `https://infisical.home`). Must match how users reach the app or OAuth/emails will break.

See **Generating keys and secrets** above for copy-paste commands.

## Optional

- **SMTP_*** – For email invites and alerts.
- **CLIENT_ID_*_LOGIN / CLIENT_SECRET_*_LOGIN** – Google/GitHub/GitLab OAuth (see Infisical docs).
- Full `.env` reference: [Infisical .env.example](https://github.com/Infisical/infisical/blob/main/.env.example).

## Start

From this directory: `docker compose up -d`.
