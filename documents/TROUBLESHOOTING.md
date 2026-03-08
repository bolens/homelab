# Stack troubleshooting

## Healthchecks

Healthchecks must use the **port and path** the app actually listens on. Known fixes applied in this repo:

| Stack    | Issue | Fix |
|----------|--------|-----|
| **Promtail** | Checked port 3100 but config uses `http_listen_port: 9080` | Healthcheck updated to `http://127.0.0.1:9080/ready` |
| **YOURLS**   | Checked port 80 but official image listens on 8080 | Healthcheck updated to `http://127.0.0.1:8080/` |

If a container is **unhealthy** or keeps restarting, check its healthcheck: ensure the port matches the app (and any config like `promtail-config.yml` or `vhost.conf`). Run `docker inspect <container> --format '{{json .State.Health}}'` to see health status and last output.

## Exited containers and restarts

If a stack’s container is **Exited** (especially exit code **137** = OOM or `docker stop`, or **2** = config/startup failure), bring the stack back with:

From the docker repo root:

```bash
cd stacks/<stack-name>
docker compose up -d
```

Stacks that are typically long‑running and proxied by Caddy (restart these if you see them exited):

| Stack        | Notes |
|-------------|--------|
| linkwarden  | Needs postgres + meilisearch up; use same compose so dependencies start first. |
| infisical   | Needs db + redis; EAI_AGAIN on redis is often transient at boot — restart the stack. |
| convertx    | Exit 137 often = OOM or stop; `docker compose up -d` to bring back. |
| linkstack   | Same as above. |
| torbot      | Depends on tor; `docker compose up -d` restarts both. |
| kasm        | Exit 137 or failure to start: if the host has **no NVIDIA GPU** or no nvidia-container-toolkit, use the CPU-only override so Kasm doesn’t require GPU: `cp stacks/kasm/docker-compose.override.yml.example stacks/kasm/docker-compose.override.yml` then `docker compose up -d`. Otherwise ensure enough memory (stack limits to 64G). |
| cadvisor    | Exit 137: stack now sets a 512M memory limit to reduce OOM. On **cgroup v2** hosts you may see cgroup warnings in logs; cadvisor often still works. Restart with `docker compose up -d` in `stacks/cadvisor`. |
| promtail    | Exit 2 can be Loki unavailable at startup; healthcheck now uses port 9080 (matches config). Restart after Loki is up. |

One-off / job-style stacks (ghunt, blackbird, acquire, docker-gc, reconftw, sublist3r, etc.) often **exit 0** by design after the task; no need to “fix” unless you want to run them again.

## YOURLS: ERR_TOO_MANY_REDIRECTS

When YOURLS is behind Caddy (or Caddy + Cloudflare Tunnel), PHP must see the request as HTTPS. YOURLS uses `yourls_is_ssl()` which checks `$_SERVER['HTTPS']` and `$_SERVER['HTTP_X_FORWARDED_PROTO']`.

**Fix:** Ensure your vhost (e.g. `~/.config/yourls/vhost.conf`) forces HTTPS for PHP. The repo’s `vhost.conf.example` uses:

- `SetEnv HTTPS on` (so PHP sees HTTPS)
- Optional: `<IfModule mod_headers.c>` + `RequestHeader set X-Forwarded-Proto "https"` (so `HTTP_X_FORWARDED_PROTO` is set)
- Optional: RewriteRule `[E=HTTPS:on]` when `X-Forwarded-Proto` is https

Re-copy from `stacks/yourls/vhost.conf.example` (and `proxy-https-fix.php.example` to your config dir) if your vhost is older, then restart the yourls container.

The repo’s vhost rewrites `/` to `/admin/index.php` so the dashboard is served at the root; set **`YOURLS_SITE`** to the bare domain (e.g. `https://urls.yourdomain.com`) so short links are at root. If you use an older vhost without that rewrite, re-copy `vhost.conf.example`.

## Shlink: "Could not connect to this Shlink server"

The web client (browser) calls the Shlink API at the **public URL** you configured (e.g. `https://short.yourdomain.com/rest/v3/health`). If that fails, the UI shows this error.

**Check:**

1. **Shlink container** is running and on the **monitor** network so Caddy can reach `shlink:8080`.
2. **Shlink’s public URL** (e.g. `PUBLIC_URL` or `BASE_URL` in the Shlink stack env) is exactly your public base URL (e.g. `https://short.yourdomain.com`, no trailing slash). The API and the UI must use this base URL.
3. **Web client server URL:** When adding the server in the Shlink web UI, use that same URL (e.g. `https://short.yourdomain.com`). Not an internal hostname like `http://shlink:8080`.
4. **Caddy:** The block for your Shlink hostname must `reverse_proxy shlink:8080` and send `header_up X-Forwarded-Proto https` if the app checks for HTTPS.

If the stack is not in this repo, ensure its env has the public base URL set and the container is on the same Docker network as Caddy (`monitor`).

**Web client “Edit server” form:** Set **Name** (e.g. Shlink), **URL** to your public base URL (e.g. `https://short.yourdomain.com`), and **API key** from your Shlink server (generate via the server CLI if needed). Leave **Forward credentials to this server on every request** unchecked unless you use Shlink v4.5.0+ and need cookies/TLS client certs or auth headers sent with every request; enabling it can make requests fail on Shlink older than v4.5.0.

## Promtail healthcheck

Promtail’s compose healthcheck must use the same port as `server.http_listen_port` in your Promtail config (default **9080** in `promtail-config.yml.example`). If it was set to 3100, the healthcheck failed and the container could restart or exit; the stack is updated to use 9080.

## Checking what’s exited

```bash
docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep -E "Exited|Restarting"
```

Then restart the relevant stack from `stacks/<name>` with `docker compose up -d`.
