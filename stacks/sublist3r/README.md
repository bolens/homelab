# Sublist3r

Subdomain enumeration tool that discovers subdomains for a given domain using multiple search engines and techniques. Often used as a first step in recon workflows.

**Website:** https://github.com/aboul3la/Sublist3r  
**Docs:** https://github.com/aboul3la/Sublist3r#readme  
**GitHub:** https://github.com/aboul3la/Sublist3r  
**Docker image:** https://hub.docker.com/r/opendevsecops/sublist3r  

## Quick start

1. **Prepare** (copy template):

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

2. **(Optional) Set timezone / proxy** in `stack.env`:

   ```bash
   TZ=America/Denver
   # HTTP_PROXY=http://caddy:3128
   # HTTPS_PROXY=http://caddy:3128
   ```

3. **Run subdomain enumeration** (SANITIZED examples):

   ```bash
   # Basic enumeration for example.com (prints to console)
   docker compose run --rm sublist3r -d example.com

   # Save results to file (writes to ~/.config/sublist3r/results by default)
   docker compose run --rm sublist3r -d example.com -o /results/example.com.txt
   ```

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm sublist3r ...`. |
| **Image** | `opendevsecops/sublist3r:latest` (Docker Hub). |
| **Storage** | `~/.config/sublist3r/results` (or `SUBLIST3R_RESULTS_PATH`) bind‑mounted to `/results`. |

## Portainer

Stacks → Add stack → **Repository** → set your repo URL and Compose path (e.g. `stacks/sublist3r/docker-compose.yml`). In **Environment**, set `SUBLIST3R_RESULTS_PATH` to an absolute path (e.g. `/home/youruser/.config/sublist3r/results`) since Portainer may not have `HOME` set. Run `./prepare-stack.sh` on the host first to create the results directory.

## Notes

- Sublist3r relies on search engines and other data sources which may rate‑limit or block abusive traffic; use responsibly and within authorization.
- It integrates well with other recon tooling (e.g. ReconFTW, HTTP probing, port scans) as part of a broader recon pipeline.

