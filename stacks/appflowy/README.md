# AppFlowy

AppFlowy self-hosting stack scaffold for Caddy/Portainer deployment.

**Website:** https://appflowy.io/  
**Docs:** https://docs.appflowy.io/docs/guides/appflowy/  
**GitHub:** https://github.com/AppFlowy-IO/AppFlowy-Cloud

## Quick start

1. Run `./prepare-stack.sh`.
2. Update `caddy_snippet.conf` to your hostname.
3. Configure required env values in `stack.env`.
4. Deploy with `docker compose up -d`.

This scaffold is ready for Portainer flow. If you need the full upstream multi-service AppFlowy Cloud deployment, use the official AppFlowy-Cloud compose as a follow-up.

## Portainer

Use Stacks -> Add stack with this compose, set environment values from `stack.env`, and ensure network `monitor` exists.
