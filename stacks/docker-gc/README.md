# docker-gc

Garbage collector for Docker containers and images. Runs a one-shot cleanup against the Docker daemon on the host using the Docker socket.

- Removes containers that exited more than an hour ago.
- Removes images that are not used by any remaining container, while keeping tags that are still referenced.

This stack runs `eeacms/docker-gc` as a maintenance job; it has **no web UI** and does **not** sit behind Caddy or Cloudflare Tunnel.

**Docs:** https://github.com/spotify/docker-gc  
**GitHub:** https://github.com/spotify/docker-gc  
**Docker image:** https://hub.docker.com/r/eeacms/docker-gc  
**Releases:** https://github.com/spotify/docker-gc/releases  

## Quick start

1. Copy `stack.env.example` → `stack.env` and review the settings.
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

For scheduled runs, create a cron job or systemd timer on the host that periodically calls one of the commands above from this stack directory.

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
- `EXCLUDE_IMAGES` – Space-separated list of image names or IDs to protect from GC (e.g. `alpine busybox`).
- `EXCLUDE_CONTAINERS` – Space-separated list of container names to protect from GC (e.g. `portainer watchtower`).
- `TZ`, `LANG`, `LC_ALL`, `LC_CTYPE` – Optional timezone and locale for logs (see `documents/ENV-VARS.md`).

### Exclude files

The container mounts `/etc` from the host read-only so docker-gc can read the standard exclude files if you prefer file-based patterns:

- `/etc/docker-gc-exclude` – image name or ID patterns (one per line).
- `/etc/docker-gc-exclude-containers` – container name patterns (one per line).

This is useful if you want a single exclude list shared across multiple ways of running docker-gc.

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

