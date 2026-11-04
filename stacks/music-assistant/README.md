# Music Assistant

Combine music sources and stream to supported network speakers. Host networking enables player discovery.

**Website:** https://www.music-assistant.io/
**Docs:** https://www.music-assistant.io/installation/
**GitHub:** https://github.com/music-assistant/server

## Prepare and deploy

1. Run `./prepare-stack.sh`. It preserves existing files, ensures external networks, synchronizes `stack.env` to `.env`, and never starts containers.
2. Edit the private `stack.env`. Create the first local account through the private route before enabling public ingress.
3. Review `caddy_snippet.conf`, replace placeholder hostnames, and import it into Caddy only after authentication is ready.
4. Validate and deploy explicitly:

   ```bash
   docker compose --env-file stack.env config --quiet
   docker compose --env-file stack.env up -d
   docker compose ps
   ```

## Access and persistence

Host networking, UI 8095 and stream server 8097. Caddy uses host.docker.internal:8095.

- `music_assistant_data` at `/data`.

Images are pinned by version and digest in Compose. Configure timezone through `stack.env`. The generated catalog metadata is in `stack.yaml`.

## Network and media requirements

Upstream requires host networking for mDNS/uPnP discovery and streaming to AirPlay, Chromecast, DLNA, and Sonos players. This shares the host network namespace and binds UI port 8095 and streaming port 8097, plus player-dependent ports. Check port conflicts and LAN firewall policy before deployment. No privileged mode, Docker socket, or in-container SMB mounting is enabled.

Caddy must have a `host.docker.internal:host-gateway` extra-host entry and reach port 8095. Use local access until authentication is configured. Complete the first-run admin flow, add music providers and player providers, and test playback on an actual player. Home Assistant integration requires an existing Home Assistant instance.

For local music, explicitly select the optional media override. Set MUSIC_PATH to the existing music directory, verify its filesystem/mount identity and permissions, then use `docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.media.yml up -d`. The mount is read-only and `create_host_path: false`; no missing media directory is created. Configure the Filesystem provider for `/media`.

## Verification, upgrades, and recovery

Check container health, open the application through its intended route, and complete an authenticated application operation. A passing health probe does not prove onboarding, external provider access, notification delivery, or device playback.

Before upgrades, record the exact image and configuration and back up all declared persistent volumes and private environment files with writers quiesced or application-consistent methods. Restore copies in isolation and verify database integrity, file hashes, and representative records. Preserve credentials and encryption keys with their matching data. Do not assume an older image can read an upgraded database. If verification fails, stop the changed service and restore verified state with the original compatible image. Never use `docker compose down -v` during routine maintenance.

On hosts with an input firewall, verify Caddy can reach the host gateway on TCP 8095. Authorize only Caddy's actual source address to that gateway, for example `ufw allow proto tcp from CADDY_IP to HOST_GATEWAY_IP port 8095`, after backing up and checking the firewall configuration. Recheck this narrow rule when Caddy's address changes. Player streaming on 8097 and provider-specific discovery ports need separate LAN rules matched to the selected players. Do not open the UI or streaming ports to the WAN.
