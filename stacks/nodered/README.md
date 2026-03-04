# Node-RED stack – low-code flows for your homelab

Node-RED is a **flow-based, low-code programming tool** for wiring together hardware devices, APIs, and online services. It lets you build automations as drag‑and‑drop flows that react to events, timers, webhooks, MQTT messages, and more.

**Website:** https://nodered.org/  
**Docs:** https://nodered.org/docs/  
**GitHub:** https://github.com/node-red/node-red  
**Docker image:** https://hub.docker.com/r/nodered/node-red  
**Releases:** https://github.com/node-red/node-red/releases  

This stack runs a single Node-RED instance with persistent storage on a Docker volume, attached to the shared `monitor` network so Caddy can reverse proxy it.

## Hostname and access

- Internal hostnames (via local DNS + Caddy internal TLS):
  - `nodered.home`
  - `nodered.local`
- Public hostname (via Caddy + Cloudflare DNS, optionally behind Cloudflare Tunnel + Access SSO):
  - `nodered.yourdomain.com`

There are **no host ports exposed** in this stack. All access is through Caddy:

- Local: `https://nodered.home` (or `https://nodered.local`)
- Public: `https://nodered.yourdomain.com`

See the main `docker/stacks/caddy/Caddyfile.example` for the corresponding `reverse_proxy` blocks.

## Volumes and data

Persistent data (flows, credentials, settings, installed nodes) is stored in:

- Docker volume: `nodered_data`
- Mounted to: `/data` inside the container (Node-RED default)

Back up the `nodered_data` volume as part of your regular homelab backups.

## Environment variables

By default the compose file sets timezone and locale:

- `TZ`
- `LANG`
- `LC_ALL`
- `LC_CTYPE`

Copy `stack.env.example` to `stack.env` if you prefer to override them or set additional variables (e.g. `NODE_OPTIONS`), then run `docker compose --env-file stack.env up -d`. For a full list of Node-RED runtime options, see the upstream docs.

## Deploy

From this directory:

```bash
cp .env.example .env    # optional: then edit values
docker compose up -d
```

Then visit:

- `https://nodered.home` on your LAN, or
- `https://nodered.yourdomain.com` if you’ve configured public DNS, Cloudflare Tunnel, and (optionally) Cloudflare Access SSO.

