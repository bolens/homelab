# Outline – team knowledge base / wiki

[Outline](https://www.getoutline.com/) is a modern, collaborative knowledge base and wiki. This stack runs Outline with Postgres, Redis, and S3-compatible storage (e.g. the `minio` stack) behind Caddy, and is designed to integrate with an external IdP such as Keycloak or authentik.

**Website:** https://www.getoutline.com/  
**Docs:** https://www.getoutline.com/developers  
**Docker image:** https://hub.docker.com/r/outlinewiki/outline  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Set at least:
     - `POSTGRES_PASSWORD` – DB password,
     - `URL` – public URL behind Caddy (e.g. `https://outline.yourdomain.com`),
     - `SECRET_KEY` and `UTILS_SECRET`,
     - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` and bucket settings (if using MinIO or another S3 backend).
2. **Configure S3 (MinIO example)**
   - In `stack.env`, set:

     ```bash
     AWS_ACCESS_KEY_ID=MINIO_ACCESS_KEY
     AWS_SECRET_ACCESS_KEY=MINIO_SECRET_KEY
     AWS_REGION=us-east-1
     AWS_S3_UPLOAD_BUCKET_URL=http://minio:9000/outline
     AWS_S3_UPLOAD_BUCKET_NAME=outline
     ```

   - Create the `outline` bucket in MinIO.
3. **Deploy**

   ```bash
   docker compose up -d
   ```

4. **Access**
   - Outline listens on port `3000` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://outline.yourdomain.com` → `outline:3000`

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `outline:3000`)                             |
| **Network** | `monitor` (for Caddy and other infra) + default internal network for DB/Redis |
| **Images**  | `outlinewiki/outline:latest`, `postgres:16-alpine`, `redis:alpine`      |
| **Storage** | `outline_pg_data` (Postgres), `outline_data` (local app data/cache)     |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `outline.yourdomain.com` → `outline:3000` |

## SSO / IdP integration

Outline is typically used with an external IdP (Google, OIDC, SAML, etc.). With this repo you can:

- Use **Keycloak** or **authentik** as the IdP.
- Configure an OIDC application in your IdP for Outline, pointing redirect URIs at `URL` (e.g. `https://outline.yourdomain.com/auth/oidc.callback`), and set the corresponding client ID/secret in additional env vars (see the Outline docs for the full list).

## Notes

- This stack assumes an S3-compatible backend for file uploads; for MinIO, keep traffic internal and terminate TLS at Caddy.
- For advanced configuration (OIDC, SMTP, more granular S3 settings), see the official Outline self-hosting docs.

