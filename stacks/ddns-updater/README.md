# DDNS Updater

Lightweight DDNS client that keeps **A** and **AAAA** records updated across [many DNS providers](https://github.com/qdm12/ddns-updater/blob/master/README.md). Includes a small **web UI** on port 8000, optional [Shoutrrr](https://github.com/nicholas-fedor/shoutrrr) notifications, and a built-in Docker healthcheck (DNS verification of your records).

**GitHub:** https://github.com/qdm12/ddns-updater  
**Docs:** https://github.com/qdm12/ddns-updater/blob/master/README.md  
**Image:** `ghcr.io/qdm12/ddns-updater`  

## Quick start

1. From this directory run `./prepare-stack.sh` (creates `stack.env` from `stack.env.example`, `caddy_snippet.conf` from the example, `data/config.json` from `config.json.example` when missing).
2. Edit `data/config.json` and add at least one provider block per [upstream configuration](https://github.com/qdm12/ddns-updater/blob/master/README.md#configuration) (or set a one-line `CONFIG` JSON in `stack.env` to override the file).
3. Ensure the data directory is writable by the container user (**UID 1000**):  
   `chown -R 1000:1000 ./data`
4. (Optional) Set `TZ` and locale via repo-root `shared.env`; see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
5. Reload Caddy after placing the snippet so `ddns-updater` is reachable at your hostname.
6. Start: `docker compose up -d` from this directory.

**Portainer:** Add stack → paste `docker-compose.yml` → set env file contents from `stack.env.example` into the stack env UI → create bind mount or upload `data/config.json` to a volume you mount at `/updater/data`.

## Networking and Caddy

- No published host ports. The service joins the external **`monitor`** network as `ddns-updater` on **8000**.
- Copy `caddy_snippet.conf.example` → `caddy_snippet.conf`, replace `example.com` with your domain, and ensure the main Caddy stack imports `stacks/*/caddy_snippet.conf`.
- The web UI has **no built-in login**. If the hostname is on the public internet, protect it with **Cloudflare Access** or similar; see [ACCESS-SSO.md](../../documents/ACCESS-SSO.md).

## Configuration

| Item | Details |
|------|---------|
| **data/config.json** | Provider records under `settings` (required for updates). Empty `settings` starts the UI only. |
| **updates.json** | Created automatically in `./data` to track last published IPs. |
| **stack.env** | Optional: `CONFIG` (full JSON), `PERIOD`, `SHOUTRRR_ADDRESSES`, `LOG_LEVEL`, `RESOLVER_ADDRESS`, etc. See upstream [environment variables](https://github.com/qdm12/ddns-updater/blob/master/README.md#environment-variables). |

Outbound: the container needs **HTTPS (443)** and **DNS (UDP 53)** to providers and public-IP services, as in the upstream README.

## Health and monitoring

- The image defines a **HEALTHCHECK** that runs `ddns-updater healthcheck` (validates records via DNS).
- For Uptime Kuma / Blackbox, use an HTTP GET to the app URL or internally `http://ddns-updater:8000/`; see the [Prometheus stack](../prometheus/README.md) and [troubleshooting guide](../../documents/TROUBLESHOOTING.md).
