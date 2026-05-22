# RustDesk Server OSS

Self-hosted **ID / rendezvous** (`hbbs`) and **relay** (`hbbr`) for [RustDesk](https://rustdesk.com) remote desktop. Traffic stays on infrastructure you control; clients use your public hostname or IP with the ports below.

**Docs:** https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/  
**Docker guide:** https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/  
**GitHub:** https://github.com/rustdesk/rustdesk-server  

## Stack type

- **No Caddy / no HTTP UI (OSS)** – RustDesk Server Pro adds a web console on TCP 21114; this stack is OSS only.
- **`network_mode: host`** – Matches upstream guidance so NAT, hole punching, and relay see real client IPs ([Docker – RustDesk](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/)). Linux only; if you hit issues on another platform, try removing host networking and publishing ports explicitly (see upstream docs).

## Ports (host firewall / router)

Allow these on the Docker host (and forward from the internet if clients connect from outside the LAN):

| Service | Port | Protocol | Purpose |
|--------|------|----------|---------|
| hbbs | 21115 | TCP | NAT type test |
| hbbs | 21116 | TCP **and** UDP | ID registration, heartbeat, hole punching |
| hbbs | 21118 | TCP | Web client (optional; omit if unused) |
| hbbr | 21117 | TCP | Relay |
| hbbr | 21119 | TCP | Web client relay (optional) |

If you do **not** use web clients, you can leave 21118/21119 closed.

## Quick start

1. **Environment**  
   Run `./prepare-stack.sh` or copy `stack.env.example` → `stack.env`. Optional: set `ALWAYS_USE_RELAY=Y` in `stack.env` (see [RustDesk Docker examples](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/)).

2. **Deploy**  
   From this directory:

   ```bash
   docker compose up -d
   ```

3. **Keys**  
   On first start, `hbbs` creates `id_ed25519` / `id_ed25519.pub` in the volume (under `/root` in the container). Get the public key from logs:

   ```bash
   docker logs rustdesk-hbbs 2>&1 | head -n 30
   ```

4. **Clients**  
   In RustDesk: set **ID server** to `your.example.com` (or IP) and **Relay server** to the same host (default ports 21116 / 21117 are used by the app when the hostname is set correctly). Paste the **public key** from the logs when the client asks for it. Use your real hostname in local config; committed files in this repo use placeholders only.

## Configuration

| Item | Details |
|------|---------|
| **Storage** | Named volume `rustdesk_data` → `/root` (shared by both containers). **Back up** this volume; it holds server keys and state. |
| **Separate relay host** | Run `hbbr` elsewhere and set `hbbs` command to `hbbs -r relay.example.com:21117` (edit `docker-compose.yml`). |
| **Env** | Optional `ALWAYS_USE_RELAY=Y` and other variables supported by the upstream image; see official docs. |

## Portainer

Paste this stack’s `docker-compose.yml`, add an **Environment** section or upload `stack.env` contents. **Host networking** applies to the Portainer host; ensure firewall rules match the table above.
