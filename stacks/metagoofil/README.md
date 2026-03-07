# Metagoofil

OSINT tool for extracting metadata from publicly available documents (PDF, DOC, XLS, PPT, etc.) discovered via Google. Downloads files for a given domain and can reveal usernames, software versions, paths, and other metadata. No upstream Docker image; built from source.

**Website:** https://github.com/opsdisk/metagoofil  
**Docs:** https://www.kali.org/tools/metagoofil/  
**GitHub:** https://github.com/opsdisk/metagoofil  
**Releases:** https://github.com/opsdisk/metagoofil/releases  

## Quick start

1. **Prepare** (creates data dir, copies `stack.env`):

   ```bash
   ./prepare-stack.sh
   # or: mkdir -p ~/.config/metagoofil/data && cp stack.env.example stack.env
   ```

2. **Build the image** (required – no upstream image):

   ```bash
   docker compose build
   ```

3. **(Optional) Set timezone / proxy** in `stack.env`.

4. **Run a metadata collection** (SANITIZED examples):

   ```bash
   docker compose run --rm metagoofil -d example.com -t pdf
   docker compose run --rm metagoofil -d example.com -t pdf,doc,xls
   ```

Output is stored under `~/.config/metagoofil/data` (or `METAGOOFIL_DATA_PATH`).

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm metagoofil ...`. |
| **Image** | Built from Dockerfile (opsdisk/metagoofil). Optional `METAGOOFIL_IMAGE` for Harbor. |
| **Storage** | `~/.config/metagoofil/data` (or `METAGOOFIL_DATA_PATH`) bind‑mounted to `/data`. |

## Portainer

**From Git:** Stacks → Add stack → **Repository** → Compose path `stacks/metagoofil/docker-compose.yml`. Portainer will build from the Dockerfile. Set `METAGOOFIL_DATA_PATH` to an absolute path (e.g. `/home/youruser/.config/metagoofil/data`).

**Pre-built image:** Build on the host, push to Harbor (see below), then set `METAGOOFIL_IMAGE` in the stack Environment.

## Push to Harbor (optional)

Build and push to bypass Cloudflare limits when pulling from another host:

```bash
docker compose build
docker tag metagoofil:latest localhost:8880/homelab/metagoofil:latest
docker push localhost:8880/homelab/metagoofil:latest
```

Set `METAGOOFIL_IMAGE=localhost:8880/homelab/metagoofil:latest` in `stack.env`, run `./prepare-stack.sh`. Cloudflare free tier limits uploads to ~100 MB; push direct or use Cloudflare Pro.

## Notes

- Metagoofil issues many automated queries to search engines; respect rate limits and terms of service.
- Use only for **authorized** testing and research against domains you have permission to assess.

## Notes

- Metagoofil issues many automated queries to search engines; respect rate limits and terms of service.
- Use only for **authorized** testing and research against domains you have permission to assess.

