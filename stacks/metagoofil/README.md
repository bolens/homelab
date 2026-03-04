# Metagoofil

OSINT tool for extracting metadata from publicly available documents (PDF, DOC, XLS, PPT, etc.) discovered via Google. Downloads files for a given domain and can reveal usernames, software versions, paths, and other metadata.

**GitHub:** https://github.com/opsdisk/metagoofil  
**Docs:** https://www.kali.org/tools/metagoofil/

## Quick start

1. **Create a data directory** for downloaded documents:

   ```bash
   mkdir -p data
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

4. **Run a metadata collection** (SANITIZED examples):

   ```bash
   # Download PDFs from example.com and extract metadata
   docker compose run --rm metagoofil -d example.com -t pdf

   # Download multiple types
   docker compose run --rm metagoofil -d example.com -t pdf,doc,xls
   ```

Downloaded files and any generated outputs are stored under `data/` in this stack.

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm metagoofil ...`. |
| **Image** | Built locally from `opsdisk/metagoofil`. |
| **Storage** | Local `data/` directory bind‑mounted into `/data` for downloads and results. |

## Notes

- Metagoofil issues many automated queries to search engines; respect rate limits and terms of service.
- Use only for **authorized** testing and research against domains you have permission to assess.

