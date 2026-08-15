# MeTube

Self-hosted web GUI for `yt-dlp`/`youtube-dl` with playlist support and a download queue. Lets you send video URLs from your browser and download them as video or audio to your homelab storage.

**Website:** https://github.com/alexta69/metube  
**Docs:** https://github.com/alexta69/metube#readme  
**GitHub:** https://github.com/alexta69/metube  
**Docker image:** https://github.com/alexta69/metube/pkgs/container/metube  
**Releases:** https://github.com/alexta69/metube/releases  

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Ensure `/mnt/unraid/media/downloads/metube` exists, or set `METUBE_DOWNLOADS_PATH` to an existing host directory.
   - Adjust `TZ` if needed, and optionally set `PUID`, `PGID`, and `UMASK` so downloaded files match your host user/group.
   - Optionally tune behaviour with `MAX_CONCURRENT_DOWNLOADS`, `DELETE_FILE_ON_TRASHCAN`, or `DEFAULT_OPTION_PLAYLIST_ITEM_LIMIT`, and set advanced options via `YTDL_OPTIONS` / `YTDL_OPTIONS_FILE` (see upstream README).

2. **Deploy**

   From this directory:

   ```bash
   docker compose up -d
   ```

   `prepare-stack.sh` synchronizes the private `stack.env` to the ignored
   Compose `.env` file, so `docker compose up -d` is sufficient after
   preparation. Re-run `./prepare-stack.sh` after changing `stack.env`.
   You can also bypass the synchronized `.env` file explicitly:

   ```bash
   docker compose --env-file stack.env up -d
   ```

3. **Access via Caddy**

   MeTube does **not** publish a host port. Access it only through Caddy at your chosen hostname (for example, `https://metube.yourdomain.com` in this homelab).

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse proxy to `metube:8081`)          |
| **Network**| `ingress-public` (external) for dedicated Caddy ingress                 |
| **Image**  | `ghcr.io/alexta69/metube:latest`                                        |
| **Env**    | Optional `TZ`, `PUID`, `PGID`, `UMASK`; download knobs like `MAX_CONCURRENT_DOWNLOADS`, `DELETE_FILE_ON_TRASHCAN`, playlist limits; advanced `YTDL_OPTIONS` / `YTDL_OPTIONS_FILE`; UI/logging via `DEFAULT_THEME`, `LOGLEVEL`, `ENABLE_ACCESSLOG` |
| **Storage**| `${METUBE_DOWNLOADS_PATH:-/mnt/unraid/media/downloads/metube}` bind-mounted at `/downloads` (videos, audio, state, temp files). Compose refuses to create a missing host path. |

The one-shot `metube-init` service creates the `audio`, `.metube`, and `tmp`
subdirectories as the configured `PUID`/`PGID` before MeTube starts. This is
compatible with NFS root-squash and recreates those subdirectories if they are
removed. The parent host directory must still exist so a missing remote mount
cannot silently redirect downloads onto the Docker host.

See the upstream README for the full list of supported environment variables and examples.

## Caddy reverse proxy

Example Caddy vhosts (SANITIZED example hostnames):

```caddy
metube.home, metube.local {
	tls internal
	reverse_proxy metube:8081
}
```

When running publicly, set up a hostname with TLS and point it at the same container:

```caddy
metube.yourdomain.com {
	tls {
		dns cloudflare {env.CLOUDFLARE_API_TOKEN}
	}
	reverse_proxy metube:8081
}
```

In this repo’s Caddy stack, you can add similar site blocks to `Caddyfile` so Caddy can route both local (`*.home`) and public (`*.yourdomain.com`) hostnames to MeTube.

## Optional: browser cookies

To download private or age-restricted videos that require your browser session:

1. Install a browser extension that can export cookies for the video site (see the MeTube README for links).
2. Export cookies and save them to a file named `cookies.txt` on your host.
3. Mount that directory into the container (for example, in your local `Caddyfile` or Portainer stack editor, add a volume like `./cookies:/cookies:ro`).
4. In `stack.env`, set:

   ```bash
   YTDL_OPTIONS={"cookiefile":"/cookies/cookies.txt"}
   ```

MeTube will then pass those cookies to `yt-dlp` when downloading.
