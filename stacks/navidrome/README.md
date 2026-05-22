# Navidrome

Self-hosted music streaming server: index your music library and stream it from anywhere with a modern web UI and Subsonic-compatible mobile apps (Android/iOS, desktop players, etc.). Navidrome is lightweight, fast, and handles very large libraries.

**Website:** https://www.navidrome.org/  
**Docs:** https://www.navidrome.org/docs/  
**GitHub:** https://github.com/navidrome/navidrome  
**Docker image:** https://hub.docker.com/r/deluan/navidrome  
**Releases:** https://github.com/navidrome/navidrome/releases  

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
   - Or add the stack in Portainer and set the same variables in the stack **Environment**. The `navidrome_data` named volume is created automatically. The music library uses a bind mount from `NAVIDROME_MUSIC_PATH` (default `/mnt/media/music`) — make sure that path exists on the host before deploying.
   - Access Navidrome via Caddy (for example, `https://music.home` or `https://music.yourdomain.com`).
   - Complete the initial setup in the web UI and point Navidrome at your music folder (mounted at `/music` in the container).

This stack uses a **named volume** (`navidrome_data`) for app data and a **bind mount** for music (set `NAVIDROME_MUSIC_PATH` in `stack.env`).

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `navidrome:4533`)       |
| **Network**| `monitor` (external) — Caddy can reverse-proxy to `navidrome:4533`     |
| **Image**  | `deluan/navidrome:latest`                                              |
| **Env**    | `TZ` optional; `ND_BASEURL`, `ND_LOGLEVEL`, `ND_SCANSCHEDULE`, etc.    |
| **Storage**| Named volume `navidrome_data` (`/data`); music bind-mounted from `${NAVIDROME_MUSIC_PATH:-/mnt/media/music}` to `/music` |

## Music library path

The music library defaults to `/mnt/media/music` on the host (bind-mounted read-write to `/music` in the container). Override by setting `NAVIDROME_MUSIC_PATH` in `stack.env`:

```env
NAVIDROME_MUSIC_PATH=/srv/media/music
```

Ensure the host path is readable by Navidrome (runs as UID 1000). If needed: `chown -R 1000:1000 /srv/media/music`.

## Uptime Kuma health checks

You can monitor Navidrome in Uptime Kuma in two ways:

- **Simple HTTP check:** Point a standard HTTP(s) monitor at your Navidrome URL (for example, `https://music.yourdomain.com/`). This is enough for “is it up?” checks.
- **Prometheus metrics path:** If you enable metrics with `ND_PROMETHEUS_ENABLED=true` and set a secret `ND_PROMETHEUS_METRICSPATH` (for example, `/metrics_SOME_SECRET_KEY`), you can:
  - Add a Prometheus scrape job pointing at `navidrome:4533` and that metricspath.
  - Optionally create an HTTP monitor in Kuma that hits the same path through Caddy to ensure the metrics endpoint stays reachable.

## Last.fm scrobbling

To enable Last.fm scrobbling in Navidrome:

1. In `stack.env`, set:
   - `ND_LASTFM_ENABLED=true`
   - `ND_LASTFM_APIKEY=<your last.fm api key>`
   - `ND_LASTFM_SECRET=<your last.fm shared secret>`
2. Restart Navidrome from this directory:
   ```bash
   docker compose up -d
   ```
3. In Navidrome web UI, each user must open **Personal Settings** and enable **Scrobble to Last.fm**.
4. Complete the Last.fm authorization page (`Yes, allow access`) and return to Navidrome.

If the scrobble toggle is disabled in Personal Settings, Navidrome is not reading valid `ND_LASTFM_APIKEY`/`ND_LASTFM_SECRET` values yet; check `stack.env` and restart the container.

## Caddy reverse proxy

Example Caddy vhost (SANITIZED example hostnames):

```text
music.home, music.local {
  tls internal
  reverse_proxy navidrome:4533
}
```

In your real setup, use the hostname you expose via Caddy and (optionally) Cloudflare Tunnel (for example, `music.yourdomain.com`) and keep the container on the `monitor` network so Caddy can resolve `navidrome`.

