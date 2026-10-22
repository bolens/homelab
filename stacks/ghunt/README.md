# GHunt

OSINT framework for investigating Google accounts and assets: emails, Gaia IDs, Drive files, BSSIDs, and Digital Asset Links. Provides CLI modules with JSON export and requires a one-time login using the GHunt Companion browser extension.

**Website:** https://github.com/mxrch/GHunt  
**Docs:** https://github.com/mxrch/GHunt/wiki  
**GitHub:** https://github.com/mxrch/GHunt  
**Releases:** https://github.com/mxrch/GHunt/releases  

## Quick start

1. **Prepare env** (copy the template; optionally select the Harbor fallback):

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

   The default image comes from GHCR. To use Harbor instead, set `GHUNT_IMAGE` in `stack.env` and run `./prepare-stack.sh`.

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

## Building the image

To build and push the image to your registry (e.g. Harbor):

```bash
cd stacks/ghunt
docker build -t harbor.yourdomain.com/homelab/ghunt:latest .
docker push harbor.yourdomain.com/homelab/ghunt:latest
```

The build uses GHunt 2.3.4 and alive-progress 3.3.0 with local compatibility
versions `2.3.4+homelab.1` and `3.3.0+homelab.1`. Upstream still caps HTTPX and
jsonpickle below these versions and pins the older graphemeu. The image tests
HTTPX 0.28.1, jsonpickle 4.1.2, graphemeu 0.11.0 and Pillow 13.0.0 offline.
Pillow retains its JPEG/TIFF security fixes.

`build-compat-wheels.py` verifies the original PyPI wheel hashes, changes only
version and dependency metadata, rebuilds RECORD and emits reproducible wheels.
Application code and upstream licenses remain unchanged. These are local
compatibility declarations, not upstream support claims. The installed graph
must pass `pip check` without exceptions. The image also tests the actual GHunt
client, per-request cookie isolation, JSON export of slotted objects, Unicode
progress rendering and JPEG/TIFF image hashing, then checks CLI help. No Google
requests, cookies or user configuration are used by these checks.

To regenerate the lock, first download the two exact upstream wheels listed in
`Dockerfile` into a disposable `upstream` directory. Then run from this stack:

```sh
python3 build-compat-wheels.py upstream wheels
uv pip compile --python-version 3.14 --python-platform x86_64-manylinux_2_28 \
  --find-links wheels --override requirements.override --generate-hashes \
  --output-file requirements.txt requirements.lock
```

The output wheel hashes must match the lock. Do not commit either disposable
directory. Dependabot continues monitoring the installed dependency lock. Review
the upstream GHunt and alive-progress versions and these local recipes monthly,
because automatic updates cannot regenerate the compatibility wheels. Retire the
local recipes when upstream bounds support the tested graph. Any recipe change
requires new wheel hashes and successful image compatibility checks.

Set `GHUNT_IMAGE` in `stack.env` to match the tag you use. Run `./prepare-stack.sh` after changing the image so `.env` is updated for compose.

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm ghunt ...`. |
| **Image** | Defaults to the repository's GHCR build from the GHunt PyPI package; `GHUNT_IMAGE` selects Harbor or another registry. |
| **Storage** | Named volume `ghunt-config` for GHunt config/cookies; `ghunt-data` for JSON exports and other outputs. |

## Notes

- GHunt is an offensive/defensive research tool; use it only for **lawful and ethical** purposes and follow the upstream license and disclaimer.
- The container does not run persistently; each `docker compose run` invocation performs one operation and exits.
