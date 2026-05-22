# Enclosed

Minimal web app for sharing **end-to-end encrypted** notes and files: the server only stores ciphertext (similar idea to PrivateBin / Bitwarden Send).

**Website:** https://enclosed.cc  
**Docs:** https://docs.enclosed.cc/self-hosting/docker  
**GitHub:** https://github.com/CorentinTh/enclosed  
**Docker image:** https://hub.docker.com/r/corentinth/enclosed  

## Quick start

1. From this directory: `./prepare-stack.sh` (creates `stack.env` and `caddy_snippet.conf` from the `.example` files if missing).
2. If the app will be reached at a public HTTPS hostname, set `PUBLIC_BASE_API_URL` and `SERVER_CORS_ORIGINS` in `stack.env` to that URL (see `stack.env.example`).
3. Add the hostname to your main Caddy stack (it imports `stacks/*/caddy_snippet.conf`).
4. Deploy: `docker compose up -d`

Access via Caddy only (no host port). Internal service: `http://enclosed:8787`.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Caddy → `enclosed:8787` on the `monitor` network |
| **Data** | Named volume `enclosed_data` → `/app/.data` (encrypted note blobs) |
| **Auth** | Optional: set `PUBLIC_IS_AUTHENTICATION_REQUIRED`, `AUTHENTICATION_JWT_SECRET`, and `AUTHENTICATION_USERS` per [upstream configuration](https://docs.enclosed.cc/self-hosting/configuration) |

## CLI

The [Enclosed CLI](https://docs.enclosed.cc/cli/installation) can target your instance:

```bash
enclosed config set instance-url https://enclosed.example.com
```

## Portainer

**Stacks → Add stack** → paste `docker-compose.yml`, set **Environment variables** from `stack.env.example`, or upload a prepared `stack.env`. Ensure the `monitor` network exists and Caddy can reach `enclosed:8787`.
