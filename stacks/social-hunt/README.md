# Social-Hunt

OSINT framework for username discovery across 500+ platforms, breach lookups (Have I Been Pwned, BreachVIP, Snusbase, LeakCheck), face matching, reverse image search, and optional AI demasking. Includes a web dashboard and CLI.

**Website:** https://socialhunt.org  
**GitHub:** https://github.com/AfterPacket/Social-Hunt

## Quick start

1. Copy `stack.env.example` to `stack.env`.
2. Set `ADMIN_TOKEN` (e.g. `openssl rand -hex 32`) — used to log into the dashboard.
3. Set `SOCIAL_HUNT_PUBLIC_URL` to the URL you use behind Caddy (e.g. `https://social-hunt.home` or `https://social-hunt.yourdomain.com`). Required for reverse-image links.
4. Deploy: `docker compose --env-file stack.env up -d`.
5. Open the app via Caddy (e.g. https://social-hunt.home). Log in with your admin token.

**Portainer:** Deploy the stack and set `ADMIN_TOKEN` and `SOCIAL_HUNT_PUBLIC_URL` in the stack **Environment**.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `social-hunt:8000`) |
| **Network** | `monitor` (Caddy reaches the app) |
| **Image** | `afterpacket/social-hunt:latest` |
| **Storage** | Named volumes: `social-hunt-data` (settings, history, jobs), `social-hunt-plugins`, `social-hunt-temp-uploads` |

## API keys (optional)

Add keys in the dashboard under **Settings → Add API** (no restart needed):

- **HIBP** (`hibp_api_key`) — [haveibeenpwned.com/API/Key](https://haveibeenpwned.com/API/Key)
- **Snusbase** (`snusbase_api_key`) — paid membership at snusbase.com
- **LeakCheck** (`leakcheck_api_key`) — leakcheck.io (Pro plan for API)
- **Replicate** (`replicate_api_token`) — for AI demasking

Mark keys as **Secret** so they are not sent to the browser after saving.

## Caddy reverse proxy

Example Caddy vhost:

```
social-hunt.home, social-hunt.local {
  tls internal
  reverse_proxy social-hunt:8000
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `social-hunt:8000`.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose, set `ADMIN_TOKEN` and `SOCIAL_HUNT_PUBLIC_URL` in **Environment**.
