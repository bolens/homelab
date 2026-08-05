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

1. **Shlink container** is running and on **ingress-public** so Caddy can reach `shlink:8080`.
2. **Shlink’s public URL** (e.g. `PUBLIC_URL` or `BASE_URL` in the Shlink stack env) is exactly your public base URL (e.g. `https://short.yourdomain.com`, no trailing slash). The API and the UI must use this base URL.
3. **Web client server URL:** When adding the server in the Shlink web UI, use that same URL (e.g. `https://short.yourdomain.com`). Not an internal hostname like `http://shlink:8080`.
4. **Caddy:** The block for your Shlink hostname must `reverse_proxy shlink:8080` and send `header_up X-Forwarded-Proto https` if the app checks for HTTPS.

If the stack is not in this repo, ensure its env has the public base URL set and attach its HTTP service to the appropriate Caddy zone (`ingress-public`, `ingress-admin`, or `ingress-sensitive`).

**Web client “Edit server” form:** Set **Name** (e.g. Shlink), **URL** to your public base URL (e.g. `https://short.yourdomain.com`), and **API key** from your Shlink server (generate via the server CLI if needed). Leave **Forward credentials to this server on every request** unchecked unless you use Shlink v4.5.0+ and need cookies/TLS client certs or auth headers sent with every request; enabling it can make requests fail on Shlink older than v4.5.0.

## Promtail healthcheck

Promtail’s compose healthcheck must use the same port as `server.http_listen_port` in your Promtail config (default **9080** in `promtail-config.yml.example`). If it was set to 3100, the healthcheck failed and the container could restart or exit; the stack is updated to use 9080.

## authentik-worker: unhealthy after Redis restart

If `authentik-worker` goes **unhealthy**, the most common cause is that `authentik-redis` restarted while the worker was up. The worker's Celery consumer hits `NOAUTH Authentication required.` or DNS resolution failures during the reconnect storm, stalls its heartbeat, and never recovers on its own.

**Diagnosis:**

```bash
docker logs authentik-worker --tail 30 2>&1 | grep -E "NOAUTH|Cannot connect|name resolution"
docker inspect authentik-worker --format '{{json .State.Health}}' | python3 -m json.tool
```

**Fix:** Restart the worker — it reconnects cleanly on startup:

```bash
docker restart authentik-worker
```

The `authentik-server` continues serving authenticated requests while the worker is down; only background tasks (outpost sync, policy refresh, scheduled cleanup) are affected.

## unless-stopped containers that won't self-recover

Containers with `restart: unless-stopped` do **not** restart after a manual stop or after a Docker daemon crash that kills them with SIGKILL (exit 137). After a host reboot, OOM event, or `docker stop`, they stay in the Exited state until manually started.

Check for these with:

```bash
docker ps -a --filter status=exited --format '{{.Names}}' | \
  xargs -I{} sh -c 'POLICY=$(docker inspect {} --format "{{.HostConfig.RestartPolicy.Name}}" 2>/dev/null); [ "$POLICY" = "unless-stopped" ] && echo "{}"'
```

Restart individually:

```bash
docker start <container-name>
```

Or restart the whole stack:

```bash
cd stacks/<stack-name> && docker compose up -d
```

Known containers that have needed manual restart after host events:

| Container | Stack | Notes |
|-----------|-------|-------|
| `alloy-log-canary` | grafana-alloy | Canary log emitter; if down, `AlloySampledStreamMissing` / `AlloyCanaryStreamMissing` alerts fire. `docker start alloy-log-canary` to recover. |
| `nextcloud-cron` | nextcloud | Background job runner; if down, Nextcloud file scans, activity, and cleanup tasks don't run. `docker start nextcloud-cron`. |
| `matomo-cron` | matomo | Scheduled analytics archival. `docker start matomo-cron`. |
| `jellystat` | jellystat | Jellyfin statistics UI; db stays up but UI needs `docker start jellystat`. |

## Checking what's exited

```bash
docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep -E "Exited|Restarting"
```

Then restart the relevant stack from `stacks/<name>` with `docker compose up -d`.

## Docker Compose: external ingress networks

Stacks that attach to Caddy declare one external trust-zone network: `ingress-public`, `ingress-admin`, or `ingress-sensitive`. Compose fails with “network … declared as external, but could not be found” when the selected network has not been created.

**Fix (once per host):**

```bash
docker network create ingress-public
docker network create ingress-admin
docker network create ingress-sensitive
```

Many stacks’ `./prepare-stack.sh` call a shared helper that creates this network when Docker is available (see `prepare_stack_ensure_docker_network` in `scripts/prepare-stack-lib.sh`). Homelab context: [SHARED-RESOURCES.md](SHARED-RESOURCES.md).

**Compose `${VAR}` in YAML:** interpolation uses the shell and a project **`.env`** file next to the compose file — **not** per-service `env_file`. Prefer **`env_file: stack.env`** plus YAML that does **not** need compose-time substitution (e.g. Postgres healthchecks using `$$VAR` inside `CMD-SHELL`, or app code building a DB URL from `POSTGRES_*`). For values that must stay in `stack.env` but are only used at **image build** time, use **`docker compose --env-file stack.env build`** or **`docker compose build --build-arg …`**.

## Docker Compose: Buildx plugin warning

If `docker compose build` logs **Docker Compose requires buildx plugin to be installed**, Compose is using the **classic** image builder. Installs usually still succeed.

**Optional:** Install the **Buildx** CLI plugin so Compose uses BuildKit by default (warning goes away). Package names vary (e.g. `docker-buildx-plugin` on Debian/Ubuntu from Docker’s apt repo, `docker-buildx` on Arch). Official guide: [Install Docker Buildx](https://docs.docker.com/build/buildx/install/).
