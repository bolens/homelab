# Maigret

OSINT tool: collect a dossier on a person **by username only**, checking thousands of sites and gathering available info from profile pages. No API keys. Fork of Sherlock with profile parsing, recursive search, and report export (HTML, PDF, XMind).

**Website:** https://maigret.readthedocs.io  
**Docs:** https://maigret.readthedocs.io  
**GitHub:** https://github.com/soxoj/maigret  
**Docker image:** https://hub.docker.com/r/soxoj/maigret  
**Releases:** https://github.com/soxoj/maigret/releases  

## Quick start

1. **Deploy:** `docker compose up -d` (or add stack in Portainer).
2. **Access:** Open via Caddy (e.g. https://maigret.home or https://maigret.yourdomain.com).
3. In the web UI, enter one or more usernames, run the search, then view the graph/table and download reports (HTML, PDF, XMind).

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `maigret:5000`) |
| **Network** | `monitor` (external) — Caddy reaches `maigret:5000` |
| **Image** | `soxoj/maigret:latest` (pin a tag for production) |
| **Storage** | Named volume `maigret-reports` for generated reports |

The container runs the web interface (`maigret --web 5000`). For CLI-only runs (e.g. one-off username search), use the image directly:

```bash
docker run --rm -v maigret-reports:/app/reports soxoj/maigret:latest username --html
```

## Caddy reverse proxy

Example Caddy vhost:

```
maigret.home, maigret.local {
  tls internal
  reverse_proxy maigret:5000
}
```

Ensure the stack is on the `monitor` network.

## Disclaimer

Use only for **educational and lawful purposes**. Ensure your use complies with applicable laws (e.g. GDPR, CCPA). See the [project disclaimer](https://github.com/soxoj/maigret#disclaimer).

## Start

From this directory: `docker compose up -d`.
