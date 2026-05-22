# Soulseek (slskd)

Self-hosted Soulseek client stack using [slskd](https://github.com/slskd/slskd): web UI, API, and background Soulseek connectivity in one container.

**Website / repo:** https://github.com/slskd/slskd  
**Docs:** https://github.com/slskd/slskd/blob/master/docs/config.md  
**Docker image:** https://hub.docker.com/r/slskd/slskd  

## Quick start

1. Run `./prepare-stack.sh` from this directory (creates `stack.env` and `caddy_snippet.conf` from examples, and ensures the `monitor` network exists).
2. Edit `stack.env`:
   - Set `SLSKD_SLSK_USERNAME` and `SLSKD_SLSK_PASSWORD`.
   - Set `SLSKD_USERNAME` and `SLSKD_PASSWORD` for the slskd web UI/API login.
   - Optionally change `SLSKD_SLSK_LISTEN_PORT` (default `50300`).
   - Set `SLSKD_DOWNLOADS_PATH` to your preferred host path for completed downloads.
   - Set `SLSKD_SHARED_MUSIC_PATH` (default `/mnt/media/music/`) and keep `SLSKD_SHARED_DIR=/music` to publish your library as a share.
3. If you expose Soulseek to remote peers, forward the same TCP/UDP listen port (`50300` by default) from your router/firewall to this Docker host.
4. Replace the placeholder hostname in `caddy_snippet.conf` and reload Caddy.
5. Deploy:

   ```bash
   docker compose up -d
   ```

6. Open the UI via Caddy, for example `https://soulseek.example.com` (replace with your real, local config hostname).

## Configuration

| Item | Details |
| ---- | ------- |
| **Access** | Web UI/API via Caddy to `soulseek:5030` |
| **Network** | `monitor` (external) |
| **Image** | `slskd/slskd:latest` |
| **Peer port** | `SLSKD_SLSK_LISTEN_PORT` published as TCP+UDP (default `50300`) |
| **Storage** | `soulseek_app` → `/app`, `${SLSKD_DOWNLOADS_PATH}` → `/downloads`, `${SLSKD_SHARED_MUSIC_PATH}` → `/music`, `soulseek_incomplete` → `/incomplete` |
| **Env** | `SLSKD_SLSK_USERNAME`, `SLSKD_SLSK_PASSWORD`, `SLSKD_USERNAME`, `SLSKD_PASSWORD`, `SLSKD_SLSK_LISTEN_PORT`, `SLSKD_DOWNLOADS_PATH`, `SLSKD_SHARED_MUSIC_PATH`, `SLSKD_SHARED_DIR`, `SLSKD_FORCE_SHARE_SCAN`, optional `PUID`/`PGID` |

## Caddy reverse proxy

Use `caddy_snippet.conf.example` (placeholder hostnames only) and copy to `caddy_snippet.conf` via `./prepare-stack.sh`.

Default internal route:

```text
soulseek.home, soulseek.local {
  tls internal
  reverse_proxy soulseek:5030
}
```

## Portainer

Create a stack from this directory, ensure `stack.env` exists (run `./prepare-stack.sh` first), then deploy. Keep Caddy as the HTTP entrypoint; do not publish `5030` on the host.
