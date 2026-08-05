# CryptPad

End-to-end encrypted collaborative office tools (docs, sheets, kanban, forms, drive) behind Caddy.

**Website:** https://cryptpad.org/  
**Docs:** https://docs.cryptpad.org/  
**GitHub:** https://github.com/cryptpad/cryptpad  
**Docker image:** https://hub.docker.com/r/cryptpad/cryptpad

## Quick start

1. Run `./prepare-stack.sh`.
2. Set hostname values in `stack.env` and `caddy_snippet.conf`.
3. Deploy with `docker compose up -d`.

No host ports are exposed; Caddy proxies to `cryptpad:3000`.

## Portainer

Create stack from `docker-compose.yml`, set environment from `stack.env`, and verify the external `ingress-public` network is present.
