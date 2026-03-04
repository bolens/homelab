# Emby

Media server for movies, TV shows, and music. Emby serves your library to web, mobile, and TV apps and supports hardware-accelerated transcoding.

**Website:** https://emby.media/  
**Docker image:** https://hub.docker.com/r/linuxserver/emby  

## Quick start

1. **Media volumes** (if not already created):
   ```bash
   docker volume create media_tv
   docker volume create media_movies
   docker volume create media_music
   ```
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID` to match your host user/group.
3. **Deploy**
   - From this directory:
     ```bash
     docker compose up -d
     ```
4. **First run**
   - Access Emby via Caddy (see vhost example below).
   - Add libraries pointing to:
     - `/data/tv` for TV shows.
     - `/data/movies` for movies.
     - `/data/music` for music.

## NVIDIA GPU transcoding

This stack requests access to your NVIDIA GPU using Docker’s device reservations (similar to the `ollama` stack):

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

To use it:

1. Install the NVIDIA driver and NVIDIA Container Toolkit on the host.
2. Verify `nvidia-smi` works on the host.
3. Verify Docker can see the GPU, e.g.:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
   ```
4. In the Emby web UI, go to **Playback → Transcoding** and enable hardware-accelerated transcoding (select the NVIDIA option).

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host ports; reverse-proxy to `emby:8096`)           |
| **Network**| `monitor` plus default                                                  |
| **Image**  | `lscr.io/linuxserver/emby:latest`                                      |
| **Env**    | `TZ`, `PUID`, `PGID`                                                   |
| **Storage**| `emby_config` → `/config`, `media_*` → `/data/...`                     |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
emby.home, emby.local {
  tls internal
  reverse_proxy emby:8096
}
```

For public access via Cloudflare Tunnel, add e.g. `emby.yourdomain.com` in the public HTTPS section of your Caddyfile and protect it with Cloudflare Access if desired.

