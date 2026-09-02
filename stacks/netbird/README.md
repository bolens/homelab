# NetBird

Self-hosted [NetBird](https://netbird.io/) control plane: WireGuard-based mesh VPN with a web dashboard, embedded identity (Dex), and combined management/signal/relay in one server image ([NetBird Docs](https://docs.netbird.io/selfhosted/selfhosted-quickstart)).

**Website:** https://netbird.io  
**Docs:** https://docs.netbird.io/selfhosted/selfhosted-quickstart  
**GitHub:** https://github.com/netbirdio/netbird  
**External reverse proxy (Caddy):** https://docs.netbird.io/selfhosted/external-reverse-proxy#caddy-combined  

## Quick start

1. Run `./prepare-stack.sh` (creates `stack.env`, `dashboard.env`, `config.yaml`, `caddy_snippet.conf` when missing).
2. Edit `config.yaml`:
   - Set `authSecret` and `store.encryptionKey` (see generation commands below).
   - Replace `netbird.example.com` with your public hostname (`exposedAddress`, `auth.issuer`, `auth.dashboardRedirectURIs`).
3. Edit `dashboard.env` so `NETBIRD_MGMT_*` and `AUTH_AUTHORITY` use the **same** `https://` hostname and port clients will use (typically `https://netbird.example.com` with no path).
4. Import the stack's `caddy_snippet.conf` into your main Caddyfile (this repo's Caddy stack imports `stacks/*/caddy_snippet.conf`).
5. From this directory: `docker compose up -d`.

**Portainer:** Set `NETBIRD_CONFIG_PATH` in the stack environment to the **absolute** path of `config.yaml` on the host (compose defaults to `./config.yaml` relative to the stack dir).

## Secrets

Run on your machine; do not commit outputs:

```bash
# Relay auth secret (paste into config.yaml → server.authSecret)
openssl rand -base64 32

# SQLite store encryption key (paste into config.yaml → server.store.encryptionKey; keep any trailing =)
openssl rand -base64 32
```

## Networking

| Path | Backend |
|------|---------|
| gRPC (`Content-Type: application/grpc*`) | `netbird-server:80` (h2c) |
| `/relay*`, `/ws-proxy/*`, `/api/*`, `/oauth2/*` | `netbird-server:80` |
| Everything else | `netbird-dashboard:80` |

- **TCP:** No host ports; HTTPS is terminated at Caddy on the shared `ingress-admin` network.
- **UDP:** STUN is published on the host as `${NETBIRD_STUN_HOST_PORT:-3478}` → container `3478/udp`. This port must be reachable from the internet for NAT traversal; it cannot go through an HTTP reverse proxy.

## First login

Open `https://<your-hostname>/setup` when no users exist to create the first admin (see [quickstart troubleshooting](https://docs.netbird.io/selfhosted/selfhosted-quickstart#troubleshoot)).

## Clients

Install NetBird agents from [Installation](https://docs.netbird.io/how-to/installation); point self-hosted installs at your management URL as described in the self-hosted docs.

## Dependencies

- **Caddy** (or another proxy) must support **HTTP/2**, **gRPC**, and **WebSocket** to `netbird-server` per [External reverse proxy](https://docs.netbird.io/selfhosted/external-reverse-proxy).
- Optional external IdP (Authentik, Keycloak, etc.) can be added in the dashboard; see [Identity providers](https://docs.netbird.io/selfhosted/identity-providers).

## Backup

Persisted state lives in the `netbird_data` volume and in `config.yaml`. Back up both before upgrades. See [Backup](https://docs.netbird.io/selfhosted/selfhosted-guide#backup).
