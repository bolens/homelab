# Cal.com

Self-hosted open-source scheduling platform. Lets users share booking links, configure availability, and manage appointments without relying on Calendly or similar SaaS tools. Backed by PostgreSQL and Redis.

**Website:** https://cal.com  
**Docs:** https://cal.com/docs/self-hosting/docker  
**GitHub:** https://github.com/calcom/cal.com  
**Docker Hub:** https://hub.docker.com/r/calcom/cal.com  

## Quick start

1. **Env:** Copy `stack.env.example` → `stack.env`. Set a strong `POSTGRES_PASSWORD`, update `DATABASE_URL` / `DATABASE_DIRECT_URL` with the same password, and generate `CAL_SIGNATURE_TOKEN` and VAPID keys (commands in the file).
2. **Create external volumes** (first deploy only):
   ```bash
   docker volume create calcom_calcom_pg_data
   docker volume create calcom_calcom_redis_data
   ```
3. **Deploy:** `docker compose up -d` (or via Portainer).
4. **Access:** Via Caddy at **https://calcom.example.com**. Create your admin account on first visit.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (reverse proxy to `calcom:3000`) |
| **Network** | `monitor` – Caddy and monitoring can reach the app |
| **Database** | PostgreSQL 16 (`calcom-db`) – data in `calcom_calcom_pg_data` volume |
| **Cache** | Redis 7 (`calcom-redis`) – data in `calcom_calcom_redis_data` volume |
| **Image** | `calcom/cal.com:latest` – updated by Watchtower |

## Key env vars

| Variable | Purpose |
|----------|---------|
| `POSTGRES_PASSWORD` | DB password – generate: `openssl rand -hex 32` |
| `DATABASE_URL` | Full Postgres connection URL (must match password above) |
| `DATABASE_DIRECT_URL` | Direct connection URL (same as `DATABASE_URL` for self-hosted) |
| `CAL_SIGNATURE_TOKEN` | Signs internal deployment keys – generate: `openssl rand -hex 32` |
| `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | Web push public key – generate: `npx web-push generate-vapid-keys` |
| `VAPID_PRIVATE_KEY` | Web push private key (from same command) |

## Dependencies

- **PostgreSQL 16** – bundled as `calcom-db`
- **Redis 7** – bundled as `calcom-redis`
- **Caddy** – reverse proxy (external `monitor` network)

## Health / monitoring

Healthcheck polls `http://127.0.0.1:3000` every 30 s with a 60 s start period (Cal.com takes ~30–60 s to finish Prisma migrations on first boot). Uptime Kuma: check `https://calcom.example.com`, expect HTTP 200 or redirect.
