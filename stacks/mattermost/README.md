# Mattermost

Self-hosted team chat and collaboration with PostgreSQL backend, proxied by Caddy.

**Website:** https://mattermost.com/  
**Docs:** https://docs.mattermost.com/deployment-guide/server/deploy-containers.html  
**GitHub:** https://github.com/mattermost/mattermost

## Quick start

1. Run `./prepare-stack.sh`.
2. Set `POSTGRES_PASSWORD` and `MM_SERVICESETTINGS_SITEURL` in `stack.env`.
3. Update `caddy_snippet.conf` hostname.
4. Deploy with `docker compose up -d`.

No host ports are exposed; Caddy proxies to `mattermost:8065`.

## Portainer

Use this compose in Portainer Stacks, define env from `stack.env`, and ensure the external `ingress-public` network exists.
