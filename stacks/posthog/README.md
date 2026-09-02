# PostHog (hobby self-host)

[PostHog](https://posthog.com/) is product analytics, session replay, feature flags, and experimentation. The **hobby** deployment is PostHog's supported Docker Compose layout (Postgres, ClickHouse, Kafka, Temporal, MinIO, SeaweedFS, workers, and an **internal Caddy** `proxy` service that routes traffic to `web`, capture, livestream, etc.).

This stack **vendors the upstream compose files** next to this README and adds a small **homelab override**: the `proxy` service joins the shared **`ingress-public`** network, drops host port bindings, and runs **HTTP-only** so your homelab **Caddy** can terminate TLS and forward to `proxy:80`.

**Docs:** https://posthog.com/docs/self-host
**Repo:** https://github.com/PostHog/posthog

## Requirements

- **RAM:** PostHog documents **8 GB minimum** (16 GB recommended) for hobby.
- **Disk:** tens of GB for ClickHouse/Kafka/Postgres growth.
- **Docker Compose v2.33+** (per upstream installer).
- External Docker network **`ingress-public`** (same as other stacks in this repo).
- **Host tools for prepare:** `git`, `openssl`, `curl` (optional `brotli` for GeoIP download).

## Quick start

1. **Clone upstream** (large repo; default clone is **shallow** for speed):

   ```bash
   ./clone-repo.sh
   ```

   For a **full** git history (uncommon): `POSTHOG_FULL_CLONE=1 ./clone-repo.sh`

2. **Prepare**, copies compose files from `posthog/`, writes `compose/`, GeoIP, `stack.env` from the example if missing, **auto-generates** `POSTHOG_SECRET` / `ENCRYPTION_SALT_KEYS` when they are still the `REPLACE_*` placeholders, copies `stack.env` → `.env`, copies the Caddy snippet template, ensures `ingress-public`:

   ```bash
   ./prepare-stack.sh
   ```

   One-liner (clone + prepare): `./prepare-stack.sh --clone` or `PREPARE_STACK_CLONE=1 ./prepare-stack.sh`

3. **Domain**, Edit `stack.env` so `DOMAIN` is your real public hostname (no `https://`), then run `./prepare-stack.sh` again (or `cp stack.env .env`) so `.env` stays in sync.

4. **GeoIP**, If prepare skipped the download, install `curl` and `brotli` and re-run `./prepare-stack.sh`, or place `share/GeoLite2-City.mmdb` manually (see [upstream deploy](https://github.com/PostHog/posthog/blob/master/bin/deploy-hobby)).

5. **Validate compose** (optional, catches missing env before pull):

   ```bash
   docker compose -f docker-compose.yml config >/dev/null && echo OK
   ```

6. **Caddy**, Edit `caddy_snippet.conf` from the example (placeholder `posthog.example.com`), reload Caddy.

7. **Start**, First boot can take **10+ minutes** (migrations, ClickHouse, Kafka):

   ```bash
   docker compose up -d --pull always
   ```

8. **Smoke check**, From the host:

   ```bash
   curl -sS -o /dev/null -w '%{http_code}\n' "https://YOUR_DOMAIN/_health"
   ```

   Expect `200` once migrations settle.

## Deploy checklist

| Step | Action |
| ---- | ------ |
| 1 | `./clone-repo.sh` (or `./prepare-stack.sh --clone`) |
| 2 | `./prepare-stack.sh` |
| 3 | Set real **`DOMAIN`** in `stack.env`, re-sync `.env` |
| 4 | Confirm **`share/GeoLite2-City.mmdb`** exists |
| 5 | **`docker compose … config`** sanity check |
| 6 | Caddy snippet → **`proxy:80`**, reload Caddy |
| 7 | **`docker compose up -d --pull always`**, wait, **`/_health`** |

## Portainer

1. Run **clone + prepare** on a host with Git (not inside Portainer's "Web editor" alone).
2. From this directory, export a **single merged** compose file for pasting or review:

   ```bash
   docker compose -f docker-compose.yml config >posthog.merged.compose.yml
   ```

   Portainer's editor has size limits; prefer **"Upload"** / **stack path on host** pointing at this prepared directory so Portainer runs `docker compose` from disk.
3. **Environment:** mirror every variable from your `.env` into Portainer's stack **Environment** UI (same names as `stack.env.example`). PostHog's hobby file interpolates **`$DOMAIN`**, **`$POSTHOG_SECRET`**, etc., from the project environment.
4. Ensure the **`ingress-public`** network exists on the same Docker endpoint before deploy.

## Upgrades

Refresh the `posthog/` clone (`./clone-repo.sh`), re-run `./prepare-stack.sh` to refresh copied `docker-compose.*.yml`, then `docker compose up -d --pull always`. See upstream [self-host docs](https://posthog.com/docs/self-host) and [upgrade-hobby](https://github.com/PostHog/posthog/blob/master/bin/upgrade-hobby).

## Monitoring

- Health path: `/_health` on the public UI URL (through Caddy → `proxy`).
- Internal: `http://proxy/_health` from another container on `ingress-public` (same path).

## Notes

- Default Postgres credentials in the hobby stack are the **upstream** `posthog`/`posthog` values; rotate in production per PostHog guidance.
- The internal **`proxy`** container is the correct upstream for **all** browser and SDK paths (`/batch`, `/e`, `/livestream`, …); do not point Caddy only at `web:8000`.
