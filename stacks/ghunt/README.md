# GHunt

OSINT framework for investigating Google accounts and assets: emails, Gaia IDs, Drive files, BSSIDs, and Digital Asset Links. Provides CLI modules with JSON export and requires a one-time login using the GHunt Companion browser extension.

**Website:** https://github.com/mxrch/GHunt  
**Docs:** https://github.com/mxrch/GHunt/wiki  
**GitHub:** https://github.com/mxrch/GHunt  
**Releases:** https://github.com/mxrch/GHunt/releases  

## Quick start

1. **Copy env template** (optional):

   ```bash
   cp stack.env.example stack.env
   ```

2. **(Optional) Set timezone / proxy** in `stack.env`:

   ```bash
   TZ=America/Denver
   # HTTP_PROXY=http://proxy.internal:3128
   # HTTPS_PROXY=http://proxy.internal:3128
   ```

3. **Authenticate GHunt** (one-time setup, persists in the `ghunt-config` volume):

   ```bash
   docker compose run --rm ghunt login
   ```

   Follow the prompts in the terminal and in the **GHunt Companion** browser extension (see upstream README). After login, your cookies and settings are stored in `/root/.config/ghunt` (the `ghunt-config` volume).

4. **Run OSINT modules** (SANITIZED examples):

   ```bash
   # Email investigation, JSON export
   docker compose run --rm ghunt email user@example.com --json /data/user.json

   # Gaia ID investigation
   docker compose run --rm ghunt gaia 123456789012345678901

   # Drive file investigation
   docker compose run --rm ghunt drive https://drive.google.com/file/d/EXAMPLE_ID/view
   ```

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm ghunt ...`. |
| **Image** | Built locally from the GHunt PyPI package (`ghunt` CLI). |
| **Storage** | Named volume `ghunt-config` for GHunt config/cookies; `ghunt-data` for JSON exports and other outputs. |

## Notes

- GHunt is an offensive/defensive research tool; use it only for **lawful and ethical** purposes and follow the upstream license and disclaimer.
- The container does not run persistently; each `docker compose run` invocation performs one operation and exits.

