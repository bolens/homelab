# AIL framework

**AIL** (Analysis Information Leak framework) analyses potential information leaks from unstructured data: pastes (Pastebin-style), streams, and crawled content. It detects credentials, credit cards, API keys, PGP data, and more; supports trackers (YARA, regex, terms), correlation, MISP/TheHive export, and optional Tor hidden-service crawling.

**Website:** https://www.ail-project.org  
**GitHub:** https://github.com/ail-project/ail-framework  
**Docs:** https://github.com/ail-project/ail-framework/blob/master/doc/README.md

## Quick start

1. **Environment** – Copy `stack.env.example` to `stack.env` if you want to set `TZ` (optional), then run `docker compose --env-file stack.env up -d` or set the same vars in the Portainer stack Environment.
2. **Deploy:** `docker compose --env-file stack.env up -d` (or add the stack in Portainer).
3. **Access:** Open via Caddy (e.g. https://ail.home or https://ail.yourdomain.com). First login uses the default password (see **Reset password** below).
4. **Reset admin password (recommended):**  
   `docker exec ail bin/LAUNCH.sh -rp`  
   (If the image uses a different path, use the path to `LAUNCH.sh` inside the container.)

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `ail:7000`). The AIL UI serves HTTPS with a self-signed cert; Caddy is configured with `tls_insecure_skip_verify` for the backend. |
| **Network** | `monitor` (external) — Caddy can reach `ail:7000`. |
| **Image** | `cciucd/ail-framework:latest` (community image; not officially maintained by ail-project). |
| **Storage** | Named volumes for PASTES, CRAWLED_SCREENSHOT, DATA_KVROCKS, indexdir, HASHS, logs. |

## Resources

AIL is resource-intensive: the image is large (~2GB+) and the app typically needs **>6GB RAM**. Ensure the host has enough memory.

## Alternative: build from source

The official repo does not publish a Docker image. This stack uses the community image [cciucd/ail-framework](https://hub.docker.com/r/cciucd/ail-framework). For a full build (including Lacus crawler and Tor), you can use [MatthisClavijo/ail-framework-docker](https://github.com/MatthisClavijo/ail-framework-docker): clone that repo and the ail-framework repo, build the image, then point this stack’s `image` at your built image and keep the same volumes and network so Caddy still proxies to `ail:7000`.

## Caddy reverse proxy

The stack is on the `monitor` network so Caddy can reach `ail:7000`. The AIL Flask app uses HTTPS with a self-signed certificate; the Caddyfile uses:

- `reverse_proxy https://ail:7000` with `transport http { tls_insecure_skip_verify }` and `header_up X-Forwarded-Proto https`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose, deploy.
