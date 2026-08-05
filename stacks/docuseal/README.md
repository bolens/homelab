# DocuSeal – self-hosted PDF e-signatures

[DocuSeal](https://www.docuseal.co/) is an open-source platform for building PDF forms, collecting signatures, and sending signing links. This stack runs the official **DocuSeal** image with **PostgreSQL** behind Caddy (no published ports on the host).

**Website:** https://www.docuseal.co/  
**Docs:** https://www.docuseal.com/docs  
**Docker image:** https://hub.docker.com/r/docuseal/docuseal  

## Portainer

1. **Network** – Create the shared external network once on the same Docker endpoint (if you do not already have it):

   ```bash
   docker network create ingress-sensitive
   ```

2. **Stack** – **Stacks** → **Add stack** → **Web editor**. Paste the contents of `docker-compose.yml` from this directory.

3. **Environment variables** – Expand **Environment variables** and add every **required** variable (same names as `stack.env.example`). Minimum set:

   | Name | Purpose |
   | ---- | ------- |
   | `POSTGRES_USER` | DB role (default in example: `docuseal`) |
   | `POSTGRES_DB` | DB name (default: `docuseal`) |
   | `POSTGRES_PASSWORD` | Strong DB password |
   | `DATABASE_URL` | `postgresql://USER:PASSWORD@postgres:5432/DB` — password must match `POSTGRES_PASSWORD` |
   | `SECRET_KEY_BASE` | `openssl rand -hex 64` |
   | `HOST` | Public hostname only (no `https://`), same as your Caddy site |
   | `FORCE_SSL` | Optional; omit to default to `HOST` (recommended behind Caddy) |

4. **Deploy** – Deploy the stack. DocuSeal listens on **3000** inside the stack; Caddy must reverse-proxy to container **`docuseal`** on network **`ingress-sensitive`**.

5. **Caddy** – On the host where Caddy runs, add or import the snippet from `caddy_snippet.conf.example` (replace placeholder hostnames), reload Caddy.

6. **Optional SMTP** – DocuSeal mail settings are not in the compose file by default. To enable outbound mail from Portainer, switch to **Web editor**, and under `docuseal` → `environment`, add the `SMTP_*` keys from the comments in `stack.env.example` (see upstream [environment variables](https://www.docuseal.com/docs/configuring-docuseal-via-environment-variables)). For this homelab’s relay, see [stacks/postfix](../postfix/README.md); attach DocuSeal to the dedicated mail network when enabling it.

**Note:** `env_file: ../../shared.env` in compose is optional (`required: false`). It only applies when this stack lives in a git checkout where that path exists; Portainer-only deploys can ignore it or set `TZ` via Portainer if you want.

## Quick start (CLI, from this repo)

1. `./prepare-stack.sh` — creates `stack.env`, copies `stack.env` → `.env` for compose interpolation, copies the Caddy example, and ensures `ingress-sensitive` plus `mail-clients`.
2. Edit `stack.env` (passwords, `HOST`, `SECRET_KEY_BASE`, `DATABASE_URL`).
3. Edit `caddy_snippet.conf` and reload Caddy.
4. `docker compose up -d`

## Configuration

| Item        | Details |
| ----------- | ------- |
| **Access**  | Caddy → `docuseal:3000` on `ingress-sensitive`. |
| **Network** | App on `default` + `ingress-sensitive` + `mail-clients`; Postgres on `default` only. |
| **Headers** | Caddy snippet sets `X-Forwarded-For`, `X-Forwarded-Proto`, and `X-Forwarded-Host` ([reverse proxy](https://www.docuseal.com/docs/configuring-docuseal-behind-an-existing-reverse-proxy-nginx)). |
| **Storage** | Named volumes `docuseal_data` and `docuseal_pg_data`. |

## E-signatures vs Nextcloud

If you use **Nextcloud**, you can install the **LibreSign** app from the Nextcloud app store instead of running DocuSeal. DocuSeal here is a **standalone** signing stack with no Nextcloud dependency.

## Monitoring

HTTP health: `GET /up` on port 3000. Point Uptime Kuma / Blackbox at your public or internal URL.
