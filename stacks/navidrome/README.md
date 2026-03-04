# Navidrome

Self-hosted music streaming server: index your music library and stream it from anywhere with a modern web UI and Subsonic-compatible mobile apps (Android/iOS, desktop players, etc.). Navidrome is lightweight, fast, and handles very large libraries.

**Website:** https://www.navidrome.org/  
**Docs:** https://navidrome.org/docs/  
**GitHub:** https://github.com/navidrome/navidrome

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ` to your timezone if different from `America/Denver`.
   - Optionally set `ND_BASEURL`, `ND_LOGLEVEL`, `ND_SCANSCHEDULE`, etc. in `stack.env` (see Navidrome config docs).
2. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
   - Or add the stack in Portainer and set the same variables in the stack **Environment**. The named volumes (`navidrome_data`, `navidrome_music`) are created automatically, so the stack works well from Portainer’s web editor.
3. **First run**
   - Access Navidrome via Caddy (for example, `https://music.home` or `https://music.yourdomain.com`).
   - Complete the initial setup in the web UI and point Navidrome at your music folder (mounted at `/music` in the container).

This stack uses **named volumes** so it works cleanly when deployed from Portainer's web editor.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `navidrome:4533`)       |
| **Network**| `monitor` (external) — Caddy can reverse-proxy to `navidrome:4533`     |
| **Image**  | `deluan/navidrome:latest`                                              |
| **Env**    | `TZ` optional; `ND_BASEURL`, `ND_LOGLEVEL`, `ND_SCANSCHEDULE`, etc.    |
| **Storage**| Named volumes: `navidrome_data` (`/data`), `navidrome_music` (`/music`)|

## Adding your music (bind mounts)

By default, this stack uses the `navidrome_music` named volume for `/music`. To use a specific host directory instead (for example, `/srv/media/music`), change the `volumes` section of the `navidrome` service:

```yaml
services:
  navidrome:
    volumes:
      - navidrome_data:/data
      - /srv/media/music:/music:ro
```

Then configure the music library in the Navidrome UI to use `/music` as the library path.

## Uptime Kuma health checks

You can monitor Navidrome in Uptime Kuma in two ways:

- **Simple HTTP check:** Point a standard HTTP(s) monitor at your Navidrome URL (for example, `https://music.yourdomain.com/`). This is enough for “is it up?” checks.
- **Prometheus metrics path:** If you enable metrics with `ND_PROMETHEUS_ENABLED=true` and set a secret `ND_PROMETHEUS_METRICSPATH` (for example, `/metrics_SOME_SECRET_KEY`), you can:
  - Add a Prometheus scrape job pointing at `navidrome:4533` and that metricspath.
  - Optionally create an HTTP monitor in Kuma that hits the same path through Caddy to ensure the metrics endpoint stays reachable.

## Caddy reverse proxy

Example Caddy vhost (SANITIZED example hostnames):

```text
music.home, music.local {
  tls internal
  reverse_proxy navidrome:4533
}
```

In your real setup, use the hostname you expose via Caddy and (optionally) Cloudflare Tunnel (for example, `music.yourdomain.com`) and keep the container on the `monitor` network so Caddy can resolve `navidrome`.

