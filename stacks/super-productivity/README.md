# Super Productivity

Self-hosted productivity app (tasks, timeboxing, focus, and planning UI) served as a web app behind Caddy.

**Website:** https://super-productivity.com/  
**Docs:** https://github.com/super-productivity/super-productivity/wiki/2.13-Run-with-Docker  
**GitHub:** https://github.com/super-productivity/super-productivity  
**Docker image:** https://hub.docker.com/r/super-productivity/super-productivity

## Quick start

1. Run `./prepare-stack.sh` from this directory (creates `stack.env` and `caddy_snippet.conf` if missing).
2. Edit `caddy_snippet.conf` and replace the placeholder hostname.
3. Deploy with `docker compose up -d`.

No host ports are exposed; route via Caddy to `super-productivity:80`.

## Portainer

In Portainer, create a new stack with this `docker-compose.yml`, ensure `stack.env` values are set, and confirm the external `monitor` network exists.
