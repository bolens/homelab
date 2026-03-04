# Privotron

CLI tool to automate opting out of data brokers. Uses Playwright to fill opt-out forms so you don’t have to do it by hand. Tracks which brokers you’ve already opted out from via profiles.

**Website:** https://github.com/kevinl95/Privotron  
**Docs:** https://github.com/kevinl95/Privotron#readme  
**GitHub:** https://github.com/kevinl95/Privotron  
**Releases:** https://github.com/kevinl95/Privotron/releases  

## Quick start

1. **Build the image** (once, or when you want to pull the latest Privotron from GitHub):

   ```bash
   docker compose build
   ```

2. **Run with a profile** (recommended – save your details once, then reuse):

   ```bash
   # Save a profile (run once with your details)
   docker compose run --rm privotron \
     --first "Jane" --last "Doe" --email "jane@example.com" --zip "12345" \
     --save-profile "jane"

   # Run opt-outs using that profile (skips already-processed brokers)
   docker compose run --rm privotron --profile "jane"
   ```

3. **Run with inline args** (no profile):

   ```bash
   docker compose run --rm privotron \
     --first "Jane" --last "Doe" --email "jane@example.com" --zip "12345"
   ```

4. **Optional: parallel runs** (faster, multiple brokers at once):

   ```bash
   docker compose run --rm privotron --profile "jane" --parallel 3
   ```

Profiles are stored in the `privotron-profiles` volume and persist between runs.

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no ports. Run via `docker compose run --rm privotron [args]`. |
| **Image** | Built from this stack’s Dockerfile (clones [kevinl95/Privotron](https://github.com/kevinl95/Privotron)). |
| **Storage** | Named volume `privotron-profiles` for saved profiles. Optional bind mount `./brokers` for custom `.skipbrokers`. |
| **Headless** | Browser runs headless in the container (patched at build time). For interactive/headed use, run Privotron locally with Poetry. |

## Skipping brokers

To skip specific brokers, add a `brokers` directory and a `.skipbrokers` file, then mount it in the compose:

1. `mkdir -p brokers && touch brokers/.skipbrokers`
2. In `.skipbrokers`, add one broker slug per line (from each broker’s YAML `slug` field). Lines starting with `#` are comments.
3. In `docker-compose.yml`, uncomment the brokers volume:
   `- ./brokers:/app/brokers:ro`
4. Re-run; those brokers will be skipped.

## Build from a specific branch/tag

Set `PRIVOTRON_VERSION` when building (e.g. a tag or branch name):

```bash
PRIVOTRON_VERSION=v1.0 docker compose build
```

Or in `.env`: `PRIVOTRON_VERSION=main`

## Security note

Profiles can contain sensitive data (name, email, phone, SSN if you use it). They are stored in the Docker volume `privotron-profiles` on the host. Keep the host secure and consider who has access to that volume.

## Start

From this directory:

- **Build:** `docker compose build`
- **Run with profile:** `docker compose run --rm privotron --profile jane`
- **Run with args:** `docker compose run --rm privotron --first "Jane" --last "Doe" --email "j@ex.com" --zip "12345"`
