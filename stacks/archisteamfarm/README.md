# ArchiSteamFarm (ASF)

Steam card idling and automation. ASF runs in the background, optionally exposing a web IPC (API + ASF-ui) for management. Access via Caddy at **https://asf.yourdomain.com** (or your configured hostname).

**Homepage:** https://asf.steamworks.download  
**GitHub:** https://github.com/JustArchiNET/ArchiSteamFarm  
**Docs:** https://github.com/JustArchiNET/ArchiSteamFarm/wiki  
**Docker:** https://github.com/JustArchiNET/ArchiSteamFarm/wiki/Docker  

## Quick start

1. **Config directory:** From the stack directory, create `config` and add your ASF config:
   - Copy `ASF.json.example` → `config/ASF.json`.
   - Set `IPCPassword` in `config/ASF.json` (required when IPC is reachable over the network). Generate with: `openssl rand -base64 32`.
   - Add bot configs to `config/` as needed (see [ASF wiki – Configuration](https://github.com/JustArchiNET/ArchiSteamFarm/wiki/Configuration)).
2. **Env (optional):** Copy `stack.env.example` → `stack.env` and set `TZ` (and optionally `ASF_UID`).
3. **Deploy:** `docker compose up -d`.
4. **Access:** Via Caddy only at https://asf.yourdomain.com (no host port). Log in with the IPC password you set in `ASF.json`.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (reverse proxy to `asf:1242`) |
| **Network** | `monitor` – Caddy and monitoring can reach the IPC |
| **Image** | `justarchi/archisteamfarm:released` (use `latest` for in-container auto-updates, or a fixed `A.B.C.D` tag) |
| **Config** | `./config` → `/app/config` (ASF.json, bot configs, plugins) |

### IPC (web UI)

- By default ASF listens on `127.0.0.1:1242`. To allow Caddy to reach it, `config/ASF.json` must set Kestrel to `http://0.0.0.0:1242` (see `ASF.json.example`).
- Set `IPCPassword` in `ASF.json` when exposing IPC; otherwise anyone on the network could control ASF.
- The IPC offers the ASF-ui web interface, Swagger API docs, and the low-level API.

### Tags

- **released** – Latest release (including pre-releases); recommended if you rebuild images regularly.
- **latest** – Stable + in-container auto-updates (different image layout).
- **A.B.C.D** – Frozen version, e.g. `6.2.0.0`.

## Portainer

Add stack → paste the contents of `docker-compose.yml` → set env vars from `stack.env` (or mount `stack.env`). Ensure the `config` directory exists and contains `ASF.json` (and optionally bot configs) before starting.

## Health / monitoring

ASF IPC does not expose a dedicated health endpoint. Use an HTTP check to the app URL (e.g. https://asf.yourdomain.com) or to a path that requires auth; Uptime Kuma can check the root and expect 200 or 401.

## Dependencies

None. Optional: if you use plugins or scripts that need outbound access, the container uses the host network stack via Docker; no extra stacks required.
