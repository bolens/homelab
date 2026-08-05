# NZBGet

High-performance Usenet downloader. NZBGet handles NZB downloads from Usenet providers and integrates with automation tools like Sonarr, Radarr, Lidarr, and Prowlarr.

**Website:** https://nzbget.com/  
**Docs:** https://nzbget.com/documentation  
**GitHub:** https://github.com/nzbgetcom/nzbget  
**Docker image:** https://hub.docker.com/r/linuxserver/nzbget  
**Releases:** https://github.com/nzbgetcom/nzbget/releases  

## Quick start

1. **Shared networks and host paths**
   - Create the shared **usenet** network (once per host, if not already present):
     ```bash
     docker network create usenet
     mkdir -p /mnt/unraid/media/downloads/usenet
     ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own downloaded files.
     - Confirm `NZBGET_DOWNLOADS_PATH` (default `/mnt/unraid/media/downloads/usenet`).
     - Optionally `NZBGET_USER` / `NZBGET_PASS` (web UI credentials).
3. **Deploy**
   - From this directory:
     ```bash
     docker compose --env-file stack.env up -d
     ```
   - Or add the stack in Portainer, paste the compose, and set the same variables in the stack **Environment**.
4. **First run**
   - Access NZBGet via Caddy (for example `https://nzbget.home` or `https://nzbget.yourdomain.com`) and configure:
     - Your Usenet server(s).
     - Download directory (should be `/downloads` inside the container).
     - Under **Settings → Categories → music**, set **Extensions** to
       `UnpackMusicTar`. Keep the category's built-in **Unpack** option enabled
       for RAR and 7-Zip releases.

The bundled `UnpackMusicTar` post-processing extension extracts ZIP and
tar-family music releases that NZBGet's built-in unpacker reports as “Nothing
to unpack.” Extracted folder trees are flattened into the release directory,
except for numbered `CD`, `Disc`, and `Disk` folders used by multi-disc releases.
This flattening pass also handles release folders created earlier by NZBGet's
built-in unpacker and removes directories left empty afterward.
After successful extraction, `.accurip`, `.cue`, `.jpg`, `.log`, `.m3u`,
`.m3u8`, `.md5`, `.nfo`, `.nzb`, `.pls`, `.png`, `.sfv`, `.srr`, `.toc`, and
`.txt` sidecar files are removed, along with `.url` shortcuts, while audio and
music-video files are retained. Cleanup also runs when NZBGet's built-in
unpacker has already removed the archive before this extension starts.
It validates paths and file types before extraction, refuses to overwrite
existing files, and removes each archive only after a successful extraction.
Other categories are ignored.

The stack also runs an idempotent LinuxServer initialization hook before
NZBGet starts. It restores the configured `PUID`/`PGID` on NZBGet's writable
config subdirectories, preventing Docker's nested read-only script mount from
leaving their parent directory owned by root after a container rebuild.

The built-in unpacker reads additional RAR and 7-Zip passwords from the
read-only `/etc/nzbget/unpack-passwords.txt` file. Keep
`config/unpack-passwords.txt` limited to non-sensitive release passwords; do
not commit private credentials.

This stack uses a **named config volume** (`nzbget_config`) and a **Usenet downloads bind mount** (`NZBGET_DOWNLOADS_PATH` → `/downloads`, shared with Sonarr/Radarr/Lidarr/Readarr).

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `nzbget:6789`)          |
| **Networks** | `monitor` (for Caddy/monitoring) and `usenet` (shared usenet network) |
| **Image**  | `lscr.io/linuxserver/nzbget:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, `NZBGET_DOWNLOADS_PATH`, optional `UMASK`, `NZBGET_USER`, `NZBGET_PASS` |
| **Storage**| `nzbget_config` → `/config`, `${NZBGET_DOWNLOADS_PATH}` → `/downloads` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
nzbget.home, nzbget.local {
  tls internal
  reverse_proxy nzbget:6789
}
```

For public access via Cloudflare Tunnel, add a corresponding `nzbget.yourdomain.com` block in your Caddyfile and Zero Trust Access app if you want SSO in front of the NZBGet UI.

## Integration with *arr and Prowlarr

- **Download client:** In Sonarr/Radarr/Lidarr/Readarr, add NZBGet as a download client:
  - Host: `nzbget`
  - Port: `6789`
  - URL base: (empty, unless you change it in NZBGet)
  - Category: set per-app (e.g. `tv`, `movies`, `music`, `books`) and configure NZBGet categories accordingly.
- **Path mapping:** Use `/downloads` as the download root in NZBGet and in your *arr apps so they see the same files via the shared host bind mount (`/mnt/unraid/media/downloads/usenet` by default).
