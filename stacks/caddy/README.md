# Caddy

Reverse proxy with automatic HTTPS. Runs on your Docker host; proxies to services on this host via `host.docker.internal`.

**Local DNS (e.g. AdGuard Home):** Add A records so hostnames resolve to your host’s IP, e.g. `portainer.home`, `kuma.home`. Then open `https://portainer.home`, `https://kuma.home`, etc.

**Public (your domain via Cloudflare):** See **CLOUDFLARE.md** for DNS, port forwarding, and SSL. Copy `Caddyfile.example` to `Caddyfile`, set your domain and email, then deploy for Let’s Encrypt.

**Caddyfile:** Copy `Caddyfile.example` to `Caddyfile` (the latter is gitignored so you can keep your real domain/email local). Edit `Caddyfile` to add or change sites, then redeploy.

**Deploying in Portainer:** Use **Stacks → Add stack → Build method: Git repository**. Set your repo URL and set **Compose path** to the path that contains both `docker-compose.yml` and `Caddyfile` (e.g. `stacks/caddy` or `docker/stacks/caddy`). Portainer clones the repo and runs compose from that path, so `./Caddyfile` is available. If you use "Web editor" only (no Git), the bind mount will fail; use Git deploy so the file is present.

**Networks:** Caddy is attached to the shared network `monitor` so Uptime Kuma can reach it at `http://caddy:80`.

**Start (CLI):** From this directory, `docker compose up -d`.
