# ReconFTW

Automated recon framework that orchestrates many tools (subdomain enumeration, port scanning, screenshots, Nuclei, directory fuzzing, OSINT, etc.) into a single workflow. Designed for offensive recon and bug bounty style asset discovery.

**Website:** https://github.com/six2dez/reconftw  
**Docs:** https://github.com/six2dez/reconftw#readme  
**GitHub:** https://github.com/six2dez/reconftw  
**Docker image:** https://hub.docker.com/r/six2dez/reconftw  
**Releases:** https://github.com/six2dez/reconftw/releases  

## Quick start

1. **Download the default config** from upstream (recommended):

   ```bash
   curl -o reconftw.cfg https://raw.githubusercontent.com/six2dez/reconftw/main/reconftw.cfg
   mkdir -p Recon
   ```

2. **Copy env template** (optional):

   ```bash
   cp stack.env.example stack.env
   ```

3. **(Optional) Set timezone / proxy** in `stack.env`:

   ```bash
   TZ=America/Denver
   # HTTP_PROXY=http://proxy.internal:3128
   # HTTPS_PROXY=http://proxy.internal:3128
   ```

4. **Run a recon scan** (SANITIZED examples):

   ```bash
   # Basic recon against a single domain
   docker compose run --rm reconftw -d example.com -r

   # Passive-only recon (see upstream docs for modes and flags)
   docker compose run --rm reconftw -d example.com -m passive
   ```

All output is written under the `Recon/` directory in this stack.

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm reconftw ...`. |
| **Image** | `six2dez/reconftw:main` from Docker Hub. |
| **Config** | `reconftw.cfg` (bind-mounted). Edit it to tune scan modes, wordlists, API keys, etc. |
| **Storage** | Local `Recon/` directory for all recon data, reports, and screenshots (bind-mounted into the container). |

## Notes

- ReconFTW is **heavy and noisy** by design: it launches many tools and network requests; use it only against targets where you have authorization.
- API keys for third‑party services (Shodan, Censys, etc.) are usually configured in `reconftw.cfg`, not via environment variables.

