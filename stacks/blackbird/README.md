# Blackbird

OSINT tool to search for accounts by username or email across many sites (Sherlock-like, with extended coverage and report export). Supports PDF/CSV reports and optional AI-based profiling.

**Website:** https://github.com/p1ngul1n0/blackbird  
**Docs:** https://github.com/p1ngul1n0/blackbird#readme  
**GitHub:** https://github.com/p1ngul1n0/blackbird  
**Releases:** https://github.com/p1ngul1n0/blackbird/releases  

## Building the image

To build and push the image to your registry (e.g. Harbor):

```bash
cd stacks/blackbird
docker build -t harbor.yourdomain.com/homelab/blackbird:latest .
docker push harbor.yourdomain.com/homelab/blackbird:latest
```

Set `BLACKBIRD_IMAGE` in `stack.env` to match the tag you use. Run `./prepare-stack.sh` after changing the image so `.env` is updated for compose.

## Quick start

1. **Create a results directory** (for exported reports):

   ```bash
   mkdir -p results
   ```

2. **Copy env template** and prepare stack:

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

3. **(Optional) Set timezone / proxy** in `stack.env`:

   ```bash
   TZ=America/Denver
   # HTTP_PROXY=http://caddy:3128
   # HTTPS_PROXY=http://caddy:3128
   ```

   To route traffic through Caddy: enable the optional forward proxy block in `stacks/caddy/Caddyfile.example` (requires Caddy built with the `forwardproxy` plugin), expose port 3128 in the Caddy stack, then set the proxy vars above. Blackbird attaches to the `monitor` network so it can reach Caddy.

4. **Run username/email searches** (SANITIZED examples):

   ```bash
   # Simple username search (prints to console)
   docker compose run --rm blackbird --username johndoe

   # Email search with PDF export
   docker compose run --rm blackbird --email johndoe@example.com --pdf /results/johndoe.pdf

   # Username search with CSV export
   docker compose run --rm blackbird --username johndoe --csv /results/johndoe.csv
   ```

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm blackbird ...`. |
| **Image** | Built from Dockerfile; push to Harbor and set `BLACKBIRD_IMAGE` in `stack.env`. |
| **Storage** | Local `results/` directory bind‑mounted into `/results` for exported reports. |
| **Network** | Attached to `monitor` so it can reach Caddy when using the forward proxy. |

## Routing through Caddy

To route Blackbird traffic through Caddy’s HTTP forward proxy:

1. **Build Caddy with the forwardproxy plugin** (the default `serfriz/caddy-cloudflare` image does not include it):

   ```bash
   xcaddy build --with github.com/caddyserver/forwardproxy
   ```

   Use a custom Dockerfile or pre-built image that includes this plugin.

2. **Add the forward proxy block** to your Caddyfile (see `stacks/caddy/Caddyfile.example`):

   ```
   :3128 {
       forward_proxy
   }
   ```

3. **Expose port 3128** in the Caddy stack’s `docker-compose.yml` (add `3128:3128` to `ports`).

4. **Set proxy env vars** in Blackbird’s `stack.env`:

   ```
   HTTP_PROXY=http://caddy:3128
   HTTPS_PROXY=http://caddy:3128
   ```

Blackbird is already on the `monitor` network, so it can reach Caddy at `caddy:3128`.

## Notes

- Blackbird may rely on third‑party sites and APIs which can change behavior over time; check upstream docs for current flags and output formats.
- Use only for **authorized** OSINT investigations and respect each site’s terms of service.

