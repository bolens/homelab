# docker-gc

Garbage collector for Docker containers and images. Runs a one-shot cleanup against the Docker daemon on the host using the Docker socket.

- Removes containers that exited more than an hour ago.
- Removes images that are not used by any remaining container, while keeping tags that are still referenced.
- Optionally prunes unused networks and build cache (when `REMOVE_NETWORKS` / `REMOVE_BUILD_CACHE` are enabled).

This stack builds from the [Spotify docker-gc](https://github.com/spotify/docker-gc) source (the `eeacms/docker-gc` image uses a legacy manifest format unsupported by containerd v2.1+). It has **no web UI** and does **not** sit behind Caddy or Cloudflare Tunnel.

**Docs:** https://github.com/spotify/docker-gc
**GitHub:** https://github.com/spotify/docker-gc

## Building the image

To build and push the image to your registry (e.g. Harbor):

```bash
cd stacks/docker-gc
docker build -t harbor.yourdomain.com/homelab/docker-gc:latest .
docker push harbor.yourdomain.com/homelab/docker-gc:latest
```

The stack defaults to the repository's GHCR image. Set `DOCKER_GC_IMAGE` in `stack.env` to use Harbor or another tag, then run `./prepare-stack.sh` so `.env` is updated for Compose.

## Quick start

1. Ensure `stack.env` exists (copy from example if needed):

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

   `prepare-stack.sh` also creates `.env` from `DOCKER_GC_IMAGE` in `stack.env` so compose can resolve the image. If you skip it, run with `docker compose --env-file stack.env up` instead.

   Review the settings in `stack.env`.
   - By default `DRY_RUN=true` so you can see what would be deleted without actually removing containers or images.
2. From this directory, run a one-off cleanup:

   ```bash
   docker compose up docker-gc
   ```

   or:

   ```bash
   docker compose run --rm docker-gc
   ```

3. Check logs to see what would be or was removed:

   ```bash
   docker compose logs -f docker-gc
   ```

4. Once you are comfortable with the output, set `DRY_RUN=false` in `stack.env` (or adjust the fine-grained `DRY_RUN_CONTAINERS` / `DRY_RUN_IMAGES` flags), then re-run the job.

For scheduled runs, create a cron job or systemd timer on the host that periodically calls one of the commands above from this stack directory. The container is designed to run once and exit (like Watchtower's one-off mode); **Docker will show it as Exited after each run, that is expected.** Schedule it (e.g. weekly) so it runs periodically.

### Scheduling options

**Cron (host):** Run weekly (e.g. Sunday 03:00) from the stack directory. Replace the path with your actual stack path.

```bash
# Edit crontab: crontab -e
0 3 * * 0 cd /path/to/docker/stacks/docker-gc && docker compose run --rm docker-gc >> /var/log/docker-gc.log 2>&1
```

**Systemd timer:** Create a oneshot service and timer (e.g. `~/.config/systemd/user/docker-gc.service` and `docker-gc.timer`) that run `docker compose run --rm docker-gc` from the stack directory on a schedule (e.g. weekly). Use `WorkingDirectory=` and ensure the user can run Docker.

**Portainer:** The stack has no built-in schedule. Use host cron or a systemd timer as above to invoke the one-off job; or in Portainer **Stack** → your docker-gc stack → **Editor**, then trigger **Redeploy** / run the service manually when you want a cleanup.

## Configuration

| Item      | Details                                                                                   |
|-----------|-------------------------------------------------------------------------------------------|
| **Socket** | `/var/run/docker.sock` (required; allows docker-gc to talk to the host Docker daemon).   |
| **Config** | `stack.env` (copied from `stack.env.example`) for DRY RUN and exclude settings.         |
| **State**  | Named volume `docker_gc_state` mounted at `/var/lib/docker-gc` inside the container.    |

### Key environment variables

Set these in `stack.env`:

- `DRY_RUN` – Set to `true` (default) to only log what would be deleted. Set to `false` to actually remove containers and images.
- `DRY_RUN_CONTAINERS` – Optional override: when `true`, containers are only logged, not deleted.
- `DRY_RUN_IMAGES` – Optional override: when `true`, images are only logged, not deleted.
- `DRY_RUN_VOLUMES` – Optional override for volume prune (when `REMOVE_VOLUMES=true`).
- `DRY_RUN_NETWORKS` – Optional override for network prune (when `REMOVE_NETWORKS=true`).
- `DRY_RUN_BUILD_CACHE` – Optional override for build cache prune (when `REMOVE_BUILD_CACHE=true`).
- `EXCLUDE_IMAGES` – Space-separated list of image names or IDs to protect from GC (e.g. `alpine busybox`).
- `EXCLUDE_CONTAINERS` – Space-separated list of container names to protect from GC (e.g. `portainer watchtower`).
- `EXCLUDE_VOLUMES` – Space-separated list of volume names/IDs to protect when `REMOVE_VOLUMES=true`.
- `GRACE_PERIOD` – Human-readable grace period before removal (e.g. `24h`, `1d`, `48h`). Alternative: `GRACE_PERIOD_SECONDS`. Per-resource overrides: `GRACE_PERIOD_CONTAINERS`, `GRACE_PERIOD_IMAGES`, `GRACE_PERIOD_VOLUMES`, `GRACE_PERIOD_NETWORKS`, `GRACE_PERIOD_BUILD_CACHE`.
- `MINIMUM_IMAGES_TO_SAVE` – Minimum image tags to keep per repository (default: 0).
- `REMOVE_ASSOCIATED_VOLUME` – Remove volumes when removing containers (default: true).
- `REMOVE_VOLUMES` – Remove dangling volumes (default: false). Use `VOLUME_DELETE_ONLY_DRIVER=local` to limit scope.
- `FORCE_CONTAINER_REMOVAL`, `FORCE_IMAGE_REMOVAL` – Use `-f` on docker rm/rmi (default: false).
- `EXCLUDE_DEAD` – Exclude dead containers from removal (default: false).
- `REMOVE_NETWORKS` – Remove unused networks older than grace period (default: false). Use `EXCLUDE_NETWORKS` to protect shared networks (for example the three `ingress-*` networks, `telemetry`, and `ai-backend`).
- `DRY_RUN_NETWORKS` – Dry-run for networks only (defaults to `DRY_RUN`).
- `REMOVE_BUILD_CACHE` – Remove build cache older than grace period (default: false).
- `DRY_RUN_BUILD_CACHE` – Dry-run for build cache only (defaults to `DRY_RUN`).
- `LOG_TO_SYSLOG` – Log to syslog instead of stdout (default: false).
- `TZ`, `LANG`, `LC_ALL`, `LC_CTYPE` – Optional timezone and locale for logs (see `documents/ENV-VARS.md`).

## Start

Run docker-gc once:

```bash
docker compose up docker-gc
```

or:

```bash
docker compose run --rm docker-gc
```

For scheduled cleanups, add a cron entry on the host similar to:

```bash
0 3 * * * cd /home/youruser/docker/stacks/docker-gc && docker compose run --rm docker-gc >> /var/log/docker-gc.log 2>&1
```

Adjust the path and schedule for your environment. Do not commit real cron paths or logs to git.

## Deploy in Portainer

1. **Add stack** → **Web editor** or **Git repository**.
2. **Before first deploy:** Ensure `stack.env` exists. On the host, in the stack directory, run `./prepare-stack.sh` or `cp stack.env.example stack.env`. If using **Git**: set the compose path to `stacks/docker-gc/docker-compose.yml`.
3. **Environment variables** (optional): add `DRY_RUN`, `EXCLUDE_CONTAINERS`, `EXCLUDE_IMAGES` to override defaults. Example: `DRY_RUN=false` to actually remove resources (after testing with `true`).
4. **Deploy.** The container will run once and exit (restart: no). For periodic cleanup, create a cron job or systemd timer on the host that runs `docker compose run --rm docker-gc` from this stack's directory.

## Optional builder-only capacity guard

The `builder-cache` profile runs a separate shell entrypoint. It never runs the
Spotify container/image collector, network cleanup or volume cleanup. Existing
`docker-gc` behavior stays independently configured. No ingress, ports, new host
mounts or daemon restart are needed. The image includes the Docker Buildx CLI
plugin; the installed CLI must expose `--max-used-space`, `--min-free-space` and
`--reserved-space`. Missing options or backend support cause failure, with no
fallback to a broader prune.

Start with the independent default dry-run:

```sh
docker compose --profile builder-cache run --rm builder-cache
```

Review the selected builder and these keys in `stack.env`. Preparation preserves
an existing `stack.env`, so add missing keys deliberately; do not replace it.

| Key | Default | Meaning |
| --- | --- | --- |
| `BUILDER_CACHE_DRY_RUN` | `true` | Preview command only; `false` explicitly enables this builder-only cleanup. The generic `DRY_RUN` does not enable it. |
| `BUILDER_CACHE_BUILDER` | `default` | Already running selected builder; this helper neither creates one nor requests `--bootstrap`. |
| `BUILDER_CACHE_MAX_GIB` | `20` | Target maximum cache GiB. |
| `BUILDER_CACHE_MIN_FREE_GIB` | `40` | Target free GiB on the BuildKit worker's filesystem. |
| `BUILDER_CACHE_RESERVED_GIB` | `4` | Minimum retained cache GiB, strictly below the maximum. |
| `BUILDER_CACHE_MIN_AGE_HOURS` | `168` | Only cache unused for at least this many hours may be reclaimed. |

Space settings accept whole GiB from 1 through 4096 and ages from 24 through
8760 hours. Cleanup uses only private
(unshared) cache plus the age filter; it can reclaim unused mutable cache.
BuildKit protects active leases. It does not remove images or volumes; omit
`--all` so internal/frontend caches are not broadly included. Keep current,
rollback and published candidate images available and verify them independently
after maintenance. Avoid running generic image GC or protected runtime proofs
concurrently with this job.

Capacity targets are best effort, not a filesystem quota: recent, shared or
active cache can prevent either target. The free-space option is evaluated by
BuildKit at its actual storage backend; container `/` free space is not used as
a substitute for daemon storage. Independently check actual daemon filesystem
headroom afterward. Backend errors propagate. If the target remains unmet,
hold new heavy builds or revise policy after review rather than broadening
cleanup automatically.

For periodic protection, an operator can schedule the exact `run --rm
builder-cache` command above with existing cron/systemd scheduling after
reviewing and enabling this mode. The selected builder must already be available
to the container’s Docker client; nondefault builders may need their own reviewed
client configuration. This profile adds no such configuration mounts. Run jobs
sequentially. This manual prune
policy overrides retention targets for that invocation and does not edit the
daemon's persistent GC policy. It neither requires a daemon restart nor caps
one build's temporary peak. A pre-build free-space admission check is a separate
option when all local build launchers can be coordinated.

Mylar's `DDL_CACHE_MAX_GIB`/`DDL_CACHE_MIN_FREE_GIB` guard controls retained
application downloads and expansion allocations. This builder-only guard does
not touch those files or create import ACKs.
