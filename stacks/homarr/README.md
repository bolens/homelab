# Homarr – homelab dashboard

[Homarr](https://homarr.dev/) is a dashboard for your homelab: add links to your services, widgets (Docker, Uptime Kuma, etc.), and optional integrations. This stack runs Homarr behind Caddy. No host ports; access via Caddy.

**Website:** https://homarr.dev/  
**Docs:** https://homarr.dev/docs/  
**GitHub:** https://github.com/homarr-labs/homarr<br>
**Docker image:** https://github.com/homarr-labs/homarr/pkgs/container/homarr<br>

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Generate `SECRET_ENCRYPTION_KEY` with `openssl rand -hex 32` and save it in `stack.env`. Preserve this key with the application backup.
   - Optionally set `TZ`.
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Homarr listens on port `7575` inside the container.
   - Put it behind Caddy on the `ingress-admin` network, e.g.:
     - `https://homarr.yourdomain.com` → `homarr:7575`
   - Add your apps and widgets in the UI (drag-and-drop).

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `homarr:7575`)                                   |
| **Networks** | `ingress-admin` for Caddy, `media-automation` and `media-services` for dashboard integrations, plus private `docker-api` |
| **Images**  | Immutable Homarr image in `docker-compose.yml`                                               |
| **Storage** | `homarr_appdata`; Docker integration uses a scoped private proxy |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `homarr.yourdomain.com` → `homarr:7575` |

## Portainer

Add stack from this directory; ensure `stack.env` exists. No host ports; use Caddy to expose the service.

The Docker widget connects to `homarr-docker-socket-proxy`. Container
start/stop/restart operations remain enabled, while container creation,
deletion, exec, volume, secret, and host-management APIs remain blocked.

## Updates

Before replacing the image, record its current identity and stop only Homarr for
an application-consistent backup of `homarr_appdata` and runtime configuration,
including `SECRET_ENCRYPTION_KEY`. Verify an isolated restore with the original
image, then test the selected image on a separate restored copy. Keep the original
backup and image until login, dashboard data and integrations pass verification.
If the new image fails, restore the verified data/configuration with the prior
image rather than reusing a potentially migrated database. Review the selected
[release notes](https://github.com/homarr-labs/homarr/releases) before deployment.
