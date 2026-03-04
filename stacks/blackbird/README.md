# Blackbird

OSINT tool to search for accounts by username or email across many sites (Sherlock-like, with extended coverage and report export). Supports PDF/CSV reports and optional AI-based profiling.

**GitHub:** https://github.com/p1ngul1n0/blackbird

## Quick start

1. **Create a results directory** (for exported reports):

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
| **Image** | Built locally from `p1ngul1n0/blackbird`. |
| **Storage** | Local `results/` directory bind‑mounted into `/results` for exported reports. |

## Notes

- Blackbird may rely on third‑party sites and APIs which can change behavior over time; check upstream docs for current flags and output formats.
- Use only for **authorized** OSINT investigations and respect each site’s terms of service.

