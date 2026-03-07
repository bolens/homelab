# Privotron

CLI tool to automate opting out of data brokers. Uses Playwright to fill opt-out forms so you don't have to do it by hand. Tracks which brokers you've already opted out from via profiles. No upstream Docker image; built from source.

**Website:** https://github.com/kevinl95/Privotron  
**Docs:** https://github.com/kevinl95/Privotron#readme  
**GitHub:** https://github.com/kevinl95/Privotron  
**Releases:** https://github.com/kevinl95/Privotron/releases  

## Quick start

1. **Prepare** (copy template):

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

2. **Build the image** (required – no upstream image exists):

   ```bash
   docker compose build
   ```

3. **Run with a profile** (recommended – save your details once, then reuse):

   ```bash
   # Save a profile (run once with your details)
   docker compose run --rm privotron \
     --first "Jane" --last "Doe" --email "jane@example.com" --zip "12345" \
     --save-profile "jane"

   # Run opt-outs using that profile (skips already-processed brokers)
   docker compose run --rm privotron --profile "jane"
   ```

4. **Run with inline args** (no profile):

   ```bash
   docker compose run --rm privotron \
     --first "Jane" --last "Doe" --email "jane@example.com" --zip "12345"
   ```

5. **Optional: parallel runs** (faster, multiple brokers at once):

   ```bash
   docker compose run --rm privotron --profile "jane" --parallel 3
   ```

Profiles are stored in the `privotron-profiles` volume and persist between runs.

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no ports. Run via `docker compose run --rm privotron [args]`. |
| **Image** | Built from this stack's Dockerfile (clones [kevinl95/Privotron](https://github.com/kevinl95/Privotron)). No upstream image. |
| **Storage** | Named volume `privotron-profiles` for saved profiles. Optional bind mount `./brokers` for custom `.skipbrokers`. |
| **Headless** | Browser runs headless in the container (patched at build time). For interactive/headed use, run Privotron locally with Poetry. |

## Skipping brokers

To skip specific brokers, add a `brokers` directory and a `.skipbrokers` file, then mount it in the compose:

1. `mkdir -p brokers && touch brokers/.skipbrokers`
2. In `.skipbrokers`, add one broker slug per line (from each broker's YAML `slug` field). Lines starting with `#` are comments.
3. In `docker-compose.yml`, uncomment the brokers volume:
   `- ./brokers:/app/brokers:ro`
4. Re-run; those brokers will be skipped.

## Push to Harbor (optional)

The image is ~1.5–2 GB (Python + Chromium). **Cloudflare free tier limits uploads to ~100 MB**, so pushes via a Cloudflare-proxied hostname (e.g. `harbor.yourdomain.com`) will fail with "payload too large". Options:

1. **Push direct** – Use `localhost:8880` or `harbor.home` to bypass Cloudflare.
2. **Cloudflare Pro** – Higher upload limits if you push via the proxied hostname.

```bash
docker compose build
docker tag privotron:latest localhost:8880/homelab/privotron:latest
docker push localhost:8880/homelab/privotron:latest
```

Ensure `localhost:8880` (and `127.0.0.1:8880` if needed) is in Docker's `insecure-registries` (`/etc/docker/daemon.json`). Then set `PRIVOTRON_IMAGE=localhost:8880/homelab/privotron:latest` in `stack.env` and run `./prepare-stack.sh`. For remote pulls, use your Harbor hostname (e.g. `harbor.yourdomain.com`) instead.

## Build from a specific branch/tag

Set `PRIVOTRON_VERSION` in `stack.env` (e.g. `PRIVOTRON_VERSION=v1.0` or `PRIVOTRON_VERSION=main`). Ensure it is not empty. Then rebuild:

```bash
docker compose --env-file stack.env build --no-cache
```

## Local build and Portainer

**Local build (CLI):**

```bash
./prepare-stack.sh
docker compose build
docker compose run --rm privotron --profile jane
```

**Portainer – from Git:** Stacks → Add stack → **Repository** → set your repo URL and Compose path (e.g. `stacks/privotron/docker-compose.yml`). Portainer clones and builds from the Dockerfile. Add env vars in **Environment** (e.g. `PRIVOTRON_IMAGE` if using Harbor, `PRIVOTRON_VERSION` to pin build).

**Portainer – pre-built image:** Build on the host, push to Harbor (see [Push to Harbor](#push-to-harbor-optional)), then add the stack with `PRIVOTRON_IMAGE` set to your Harbor tag. Portainer will pull instead of building.

## Security note

Profiles can contain sensitive data (name, email, phone, SSN if you use it). They are stored in the Docker volume `privotron-profiles` on the host. Keep the host secure and consider who has access to that volume.

## Start

From this directory:

- **Run with profile:** `docker compose run --rm privotron --profile jane`
- **Run with args:** `docker compose run --rm privotron --first "Jane" --last "Doe" --email "j@ex.com" --zip "12345"`
