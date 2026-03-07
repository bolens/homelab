# Plaso (log2timeline)

Digital forensics timeline tool. [Plaso](https://plaso.readthedocs.io/) (log2timeline) extracts timestamps from disk images, directories, and evidence files into a single timeline; `psort` writes that to CSV, JSON, or other formats. Use for incident response, artifact analysis, and timeline reconstruction.

**Website:** https://plaso.readthedocs.io/  
**Docs:** https://plaso.readthedocs.io/en/latest/sources/user/  
**GitHub:** https://github.com/log2timeline/plaso  
**Docker image:** https://hub.docker.com/r/log2timeline/plaso  

## Quick start

1. **Prepare** (creates `data/`, copies `stack.env`):

   ```bash
   ./prepare-stack.sh
   # or: mkdir -p data && cp stack.env.example stack.env
   ```

2. **Place evidence** under `data/` (or mount it there). Examples: disk image `data/evidence.dd`, or a directory tree `data/capture/`.

3. **Run log2timeline** to build a storage file:

   ```bash
   docker compose run --rm plaso log2timeline --storage-file /data/case.plaso /data/evidence.dd
   ```

   Or from a directory:

   ```bash
   docker compose run --rm plaso log2timeline --storage-file /data/case.plaso /data/capture
   ```

4. **Run psort** to generate a timeline (e.g. CSV):

   ```bash
   docker compose run --rm plaso psort -w /data/timeline.csv /data/case.plaso
   ```

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm plaso ...`. |
| **Image** | `log2timeline/plaso:latest` (official Docker Hub image). |
| **Storage** | Local `data/` bind-mounted to `/data` for evidence and output. Output files may be root-owned; to access as your user run `chown -R $(id -u):$(id -g) ./data` after a run. |

## Common commands

| Command | Description |
|--------|-------------|
| `log2timeline --storage-file /data/out.plaso /data/evidence` | Extract timestamps from evidence into a Plaso storage file. |
| `psort -w /data/timeline.csv /data/out.plaso` | Write timeline to CSV. |
| `psort -o dynamic -w /data/timeline.txt /data/out.plaso` | Write timeline in dynamic format. |
| `pinfo /data/out.plaso` | Show storage file info. |

Interactive shell (e.g. to run multiple steps):

```bash
docker compose run --rm plaso /bin/bash
# inside container:
log2timeline --storage-file /data/case.plaso /data/evidence
psort -w /data/timeline.csv /data/case.plaso
exit
```

Full options: [log2timeline](https://plaso.readthedocs.io/en/latest/sources/user/Using-log2timeline.html), [psort](https://plaso.readthedocs.io/en/latest/sources/user/Using-psort.html).

## Push to Harbor (optional)

The image is ~140 MB. **Cloudflare free tier limits uploads to ~100 MB**, so pushes via a Cloudflare-proxied hostname (e.g. `harbor.yourdomain.com`) will fail with "payload too large". Options:

1. **Push direct** – Use `localhost:8880` or `harbor.home` to bypass Cloudflare (add to Docker `insecure-registries` if using HTTP).
2. **Cloudflare Pro** – Higher upload limits if you push via the proxied hostname.

```bash
docker pull log2timeline/plaso:latest
docker tag log2timeline/plaso:latest localhost:8880/homelab/plaso:latest
docker push localhost:8880/homelab/plaso:latest
```

## Notes

- Use only on **authorized** evidence (your own systems or with explicit permission).
- Evidence can be large; ensure enough disk space and memory. For very large images, consider increasing Docker memory limits.
- On SELinux hosts you may need `:z` on the volume (e.g. `./data:/data:z`); see [Plaso Docker docs](https://plaso.readthedocs.io/en/latest/sources/user/Installing-with-docker.html).
