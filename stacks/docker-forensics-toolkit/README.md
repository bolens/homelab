# Docker Forensics Toolkit

Post-mortem analysis of Docker runtime environments from forensic copies of a Docker host’s disk. [Docker Forensics Toolkit](https://github.com/docker-forensics-toolkit/toolkit) can mount host disk images, list containers/images, show configs and logs, mount container filesystems, and extract metadata for timeline analysis (e.g. with Sleuth Kit’s `mactime`).

**GitHub:** https://github.com/docker-forensics-toolkit/toolkit  
**Usage guide:** https://github.com/docker-forensics-toolkit/toolkit/blob/master/USAGE.md  

## Quick start

1. **Create a data directory** and place your forensic disk image (e.g. raw, VMDK) there:

   ```bash
   mkdir -p data
   # Copy or link your Docker host disk image to data/ (e.g. data/host.raw)
   ```

2. **Copy env template** and prepare stack:

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

   `prepare-stack.sh` creates `stack.env` from the example and syncs `DOCKER_FORENSICS_TOOLKIT_IMAGE` to `.env` for compose. If using a pre-built Harbor image, set that variable in `stack.env`.

3. **Build and push the image** (for Harbor; skip if using a pre-built image):

   ```bash
   docker build -t harbor.yourdomain.com/homelab/docker-forensics-toolkit:latest .
   docker push harbor.yourdomain.com/homelab/docker-forensics-toolkit:latest
   ```

   Set `DOCKER_FORENSICS_TOOLKIT_IMAGE` in `stack.env` to match, then run `./prepare-stack.sh`.

4. **Mount the forensic image** (may require privileged mode; see notes below):

   ```bash
   docker compose run --rm --privileged docker-forensics-toolkit mount-image /data/host.raw
   ```

   Note the mountpoint printed (e.g. `/tmp/...-root-2`). Use it for the next commands.

5. **Inspect the Docker host** (replace `<MOUNTPOINT>` with the path from step 4):

   ```bash
   docker compose run --rm docker-forensics-toolkit status <MOUNTPOINT>
   docker compose run --rm docker-forensics-toolkit list-containers <MOUNTPOINT>
   docker compose run --rm docker-forensics-toolkit list-images <MOUNTPOINT>
   ```

## Using the CLI

The toolkit is a **CLI-only** tool. Each invocation runs a single operation and exits. Use:

```bash
docker compose run --rm [--privileged] docker-forensics-toolkit <operation> [args]
```

- **`--rm`** – Remove the container after it exits (recommended).
- **`--privileged`** – Required for `mount-image` (FUSE/loop). Omit for other operations.
- **`<operation>`** – One of the subcommands in the table below.

**Get help:**

```bash
# General help and list of operations
docker compose run --rm docker-forensics-toolkit -h

# Help for a specific operation (e.g. mount-image)
docker compose run --rm docker-forensics-toolkit mount-image help
```

**Typical workflow:**

1. Place your forensic disk image in `./data/` (e.g. `./data/host.raw`).
2. Mount it: `docker compose run --rm --privileged docker-forensics-toolkit mount-image /data/host.raw` → note the root mountpoint (e.g. `/tmp/...-root-2`).
3. Run other commands with that mountpoint: `status`, `list-containers`, `list-images`, `show-container-config`, etc.

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm docker-forensics-toolkit ...`. |
| **Image** | Build locally and push to Harbor, or use a pre-built image. Set `DOCKER_FORENSICS_TOOLKIT_IMAGE` in `stack.env`. |
| **Storage** | Local `data/` bind-mounted to `/data` for disk images. Files created in `data/` may be root-owned; to access as your user run `chown -R $(id -u):$(id -g) ./data` after use. |
| **docker-gc** | If you use the docker-gc stack, add `docker-forensics-toolkit` to `EXCLUDE_CONTAINERS` in docker-gc’s `stack.env` so the container is not pruned when it has not run recently. Images may still be cleaned. |
| **docker-gc** | If you use the docker-gc stack, add `docker-forensics-toolkit` to `EXCLUDE_CONTAINERS` in docker-gc’s `stack.env` so the container is not pruned when it has not run recently. Images may still be cleaned. |

## Common commands

| Command | Description |
|--------|-------------|
| `mount-image <image>` | Mount the forensic disk image; outputs root mountpoint. |
| `status <mountpoint>` | Docker version and overview (containers, images). |
| `list-containers <mountpoint>` | Containers found on the host. |
| `list-images <mountpoint>` | Images found on the host. |
| `show-container-config --container <name> <mountpoint>` | Container config (config.v2.json, hostconfig.json). |
| `show-container-log --container <name> <mountpoint>` | Container log output. |
| `show-image-history --image <tag> <mountpoint>` | Image build history. |
| `mount-container --container <name> <mountpoint>` | Mount container FS at a temp path (overlay2). |
| `macrobber-container-layer --container <name> <mountpoint>` | Metadata for timeline (pipe to `mactime`). |
| `macrobber-volumes --container <name> <mountpoint>` | Volume metadata for timeline. |

Full tour: [USAGE.md](https://github.com/docker-forensics-toolkit/toolkit/blob/master/USAGE.md).

## Notes

- Use only on **authorized** forensic copies (your own systems or with explicit permission).
- **mount-image** uses FUSE/loop and may require running the container with `--privileged`. If you hit permission or mount errors, use `docker compose run --rm --privileged docker-forensics-toolkit mount-image /data/host.raw` or set `privileged: true` in `docker-compose.yml` for that run.
- The toolkit expects a **full disk or partition image** of a Linux host that ran Docker (e.g. raw, VMDK). The repo uses [imagemounter](https://github.com/ralphje/imagemounter); swap partitions may produce warnings but the root FS mount still succeeds.
- Optional: set `DOF_IMAGE_MOUNTPOINT` in `stack.env` to the root mountpoint so you don’t have to pass it to every command (then use `docker compose run --rm -e DOF_IMAGE_MOUNTPOINT=/path docker-forensics-toolkit status` or similar).
