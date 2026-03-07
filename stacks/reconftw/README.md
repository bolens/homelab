# ReconFTW

Automated recon framework that orchestrates many tools (subdomain enumeration, port scanning, screenshots, Nuclei, directory fuzzing, OSINT, etc.) into a single workflow. Designed for offensive recon and bug bounty style asset discovery.

**Website:** https://github.com/six2dez/reconftw  
**Docs:** https://github.com/six2dez/reconftw#readme  
**GitHub:** https://github.com/six2dez/reconftw  
**Docker image:** https://hub.docker.com/r/six2dez/reconftw  
**Releases:** https://github.com/six2dez/reconftw/releases  

## Quick start

1. **Prepare** (creates `~/.config/reconftw/`, downloads `reconftw.cfg`, copies `stack.env`):

   ```bash
   ./prepare-stack.sh
   # or manually: mkdir -p ~/.config/reconftw/Recon && curl -o ~/.config/reconftw/reconftw.cfg https://raw.githubusercontent.com/six2dez/reconftw/main/reconftw.cfg && cp stack.env.example stack.env
   ```

2. **(Optional) Set timezone / proxy** in `stack.env`:

   ```bash
   TZ=America/Denver
   # HTTP_PROXY=http://caddy:3128
   # HTTPS_PROXY=http://caddy:3128
   ```

3. **Run a recon scan** (SANITIZED examples):

   ```bash
   # Basic recon against a single domain
   docker compose run --rm reconftw -d example.com -r

   # Passive-only recon (see upstream docs for modes and flags)
   docker compose run --rm reconftw -d example.com -m passive
   ```

All output is written under `~/.config/reconftw/Recon` (or `RECONFTW_RECON_PATH` if set).

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm reconftw ...`. |
| **Image** | `six2dez/reconftw:main` from Docker Hub. |
| **Config** | `~/.config/reconftw/reconftw.cfg` (or `RECONFTW_CONFIG_PATH`). Edit to tune scan modes, wordlists, API keys. |
| **Storage** | `~/.config/reconftw/Recon` (or `RECONFTW_RECON_PATH`) for recon data, reports, screenshots. |

## Portainer

Stacks → Add stack → **Repository** → set your repo URL and Compose path (e.g. `stacks/reconftw/docker-compose.yml`). In **Environment**, set absolute paths (Portainer may not have `HOME` set):

- `RECONFTW_CONFIG_PATH` – e.g. `/home/youruser/.config/reconftw/reconftw.cfg`
- `RECONFTW_RECON_PATH` – e.g. `/home/youruser/.config/reconftw/Recon`

Run `./prepare-stack.sh` on the host first to create the config directory and download `reconftw.cfg`.

## Notes

- ReconFTW is **heavy and noisy** by design: it launches many tools and network requests; use it only against targets where you have authorization.
- API keys for third‑party services (Shodan, Censys, etc.) are usually configured in `reconftw.cfg`, not via environment variables.

