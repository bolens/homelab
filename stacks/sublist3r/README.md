# Sublist3r

Subdomain enumeration tool that discovers subdomains for a given domain using multiple search engines and techniques. Often used as a first step in recon workflows.

**GitHub:** https://github.com/aboul3la/Sublist3r

## Quick start

1. **Create a results directory** (optional, for saved outputs):

   ```bash
   mkdir -p results
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

4. **Run subdomain enumeration** (SANITIZED examples):

   ```bash
   # Basic enumeration for example.com (prints to console)
   docker compose run --rm sublist3r -d example.com

   # Save results to a file inside ./results
   docker compose run --rm sublist3r -d example.com -o /results/example.com.txt
   ```

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm sublist3r ...`. |
| **Image** | Built locally from `aboul3la/Sublist3r`. |
| **Storage** | Local `results/` directory bind‑mounted into `/results` for saved output files. |

## Notes

- Sublist3r relies on search engines and other data sources which may rate‑limit or block abusive traffic; use responsibly and within authorization.
- It integrates well with other recon tooling (e.g. ReconFTW, HTTP probing, port scans) as part of a broader recon pipeline.

