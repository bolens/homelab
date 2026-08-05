# AIL framework

**AIL** (Analysis Information Leak framework) analyses potential information leaks from unstructured data: pastes (Pastebin-style), streams, and crawled content. It detects credentials, credit cards, API keys, PGP data, and more; supports trackers (YARA, regex, terms), correlation, MISP/TheHive export, and optional Tor hidden-service crawling.

**Website:** https://www.ail-project.org  
**Docs:** https://github.com/ail-project/ail-framework/tree/master/doc  
**GitHub:** https://github.com/ail-project/ail-framework  
**Releases:** https://github.com/ail-project/ail-framework/releases  

## Quick start

1. **Environment** – Copy `stack.env.example` to `stack.env` if you want to set `TZ` (optional), then run `docker compose --env-file stack.env up -d` or set the same vars in the Portainer stack Environment.
2. **Deploy:** `docker compose --env-file stack.env up -d` (or add the stack in Portainer).
3. **Access:** Open via Caddy (e.g. https://ail.home or https://ail.example.com). **Default login:** email `admin@admin.test`. (Some images may write the generated password to a file in the container; if that doesn’t work, run **Reset password** below.) Change the password after first login.
4. **Reset admin password (recommended):**  
   `docker exec ail-framework bin/LAUNCH.sh -rp`  
   (If the container name or path differs, adjust accordingly.)  
   Then read the new password: `docker exec ail-framework cat /opt/AIL/DEFAULT_PASSWORD`  
   This resets **`admin@admin.test`** (creates it if missing, or sets a new password if it already exists). It also writes a **new API key** for that user. If you had renamed the admin email, log in as **`admin@admin.test`** with the new password, then clean up duplicate users in the UI if needed.

### Login lockout (“Please wait …s”) and recovery

- **Stock image:** after **5** failed attempts per IP or per username, AIL blocks further tries for **300 seconds** (Redis_Cache, port **6379**).
- **This stack:** uses the upstream lockout behavior; no application source files are bind-mounted.
- **Clear lockout without waiting:** from this directory, `./clear-login-lockout.sh` (or `bash clear-login-lockout.sh`).
- **Username is your email** (case-sensitive in this image). After changing the admin email, use the **new** address to sign in—not `admin@admin.test`—unless you ran **`-rp`**, which resets **`admin@admin.test`** again.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `ail:7000`). The AIL UI serves HTTPS with a self-signed cert; Caddy is configured with `tls_insecure_skip_verify` for the backend. |
| **Networks** | `security-research` for trusted research peers; `ingress-admin` for Caddy. |
| **Image** | Default: CPU-only `ail-framework:6.7`. Override with `AIL_IMAGE`, or use `docker-compose.gpu.yml` for `ail-framework:6.7-gpu`. |
| **Storage** | Named volumes for PASTES, CRAWLED_SCREENSHOT, DATA_KVROCKS, indexdir, HASHS, logs. |
| **Login behavior** | Uses upstream AIL 6.7 behavior; the old 5.x `root.py` override is no longer mounted. |
| **GPU** | Disabled by default. Add `-f docker-compose.gpu.yml` to use the CUDA image and expose the host NVIDIA GPU. |
| **Flask bind** | The runtime layer changes AIL's loopback-only default to `0.0.0.0:7000` so Caddy can reach the container over `ingress-admin`. |

## Resources

AIL is resource-intensive and typically needs **>6GB RAM**. The default CPU image omits
the several-GB CUDA/NVIDIA/Triton runtime. The optional GPU image retains it for
accelerated OCR.

## Using AIL 6.x (official build)

Official releases (e.g. **v6.7**) are not published as images; this stack builds from the [official repo](https://github.com/ail-project/ail-framework). The official image and this compose file use **/opt/AIL** for data paths.

**This repo** vendors a pinned checkout under `ail-framework-docker/ail-framework` (tag **v6.7**) with small build fixes for Ubuntu 22.04 / current pip (Dockerfile paths, `install_virtualenv.sh`, pystemon installer). Prefer building from there so you do not have to re-apply patches after a fresh clone.

1. **Build both variants.** Native compilation is shared by BuildKit; build the
   CPU image first so the primary image does not wait for CUDA downloads:
   ```bash
   cd stacks/ail-framework
   docker build -f Dockerfile.build \
     --build-arg AIL_TORCH_VARIANT=cpu \
     -t ail-framework:6.7-cpu-build .
   docker build -f Dockerfile.runtime \
     --build-arg BASE_IMAGE=ail-framework:6.7-cpu-build \
     -t ail-framework:6.7 .
   docker build -f Dockerfile.build \
     --build-arg AIL_TORCH_VARIANT=gpu \
     -t ail-framework:6.7-gpu-build .
   docker build -f Dockerfile.runtime \
     --build-arg BASE_IMAGE=ail-framework:6.7-gpu-build \
     -t ail-framework:6.7-gpu .
   ```

2. **Optional GPU deployment:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
   ```
   This uses `ail-framework:6.7-gpu`; set `AIL_GPU_IMAGE` to override it.

3. **Default CPU deployment:** `docker compose --env-file stack.env up -d`.

### Pushing the AIL 6.x image to Harbor

AIL 6.x images are **large** (often **many GB** compressed). A public Harbor hostname fronted by Cloudflare is often limited to ~**100 MB** upload per request, so **push and pull via `harbor.local`** (direct to Harbor on your LAN) for this image.

1. **Check image size** (optional):
   ```bash
   docker image inspect ail-framework:6.7 --format '{{.Size}}' | awk '{print $1/1024/1024/1024 " GB"}'
   ```

2. **Log in** to the registry you will use:
   ```bash
   docker login harbor.local
   ```

3. **Tag and push** (replace `PROJECT` with your Harbor project, e.g. `homelab`):
   ```bash
   docker tag ail-framework:6.7 harbor.local/PROJECT/ail-framework:6.7
   docker push harbor.local/PROJECT/ail-framework:6.7
   ```

4. **Use on other hosts:** Set `AIL_IMAGE=harbor.local/PROJECT/ail-framework:6.7` in `stack.env`, keep `docker-compose.override.yml` (same `/opt/AIL` paths). Ensure Docker trusts Harbor’s TLS cert where needed (see e.g. [social-hunt README](../social-hunt/README.md) → “harbor.local: certificate signed by unknown authority” if applicable).

## Caddy reverse proxy

The stack uses `security-research` for research-tool communication and `ingress-admin` so Caddy can reach `ail:7000`. The AIL Flask app uses HTTPS with a self-signed certificate; the Caddyfile uses:

- `reverse_proxy https://ail:7000` with `transport http { tls_insecure_skip_verify }`.
- **`header_up Host {host}`** and **`X-Forwarded-Host`** so Flask sees your public hostname (not `ail:7000`). Without this, login and `?next=` redirects can loop or send the browser to the wrong host.
- **`header_up X-Forwarded-Proto {scheme}`** so the client scheme (https/http) matches the site block.

### Login problems (after restarts or unrelated to Docker changes)

- **Not caused by** the compose `tmpfs` for `/run/screen` or screen restarts: user accounts live in Kvrocks/Redis volumes.
- **Redirect loop or “can’t log in” via Caddy:** ensure your live Caddyfile includes the **`Host` / `X-Forwarded-*`** lines from `caddy_snippet.conf.example`, then reload Caddy. Clear site cookies for your AIL hostname and try again.
- **Wrong or unknown password / lost access after API key change:** `docker exec ail-framework bin/LAUNCH.sh -rp`, then `docker exec ail-framework cat /opt/AIL/DEFAULT_PASSWORD`. Sign in as **`admin@admin.test`**; create a new API key under settings after you are in.
- **Brute-force timer:** run `./clear-login-lockout.sh` from this stack directory (or wait for TTL).
- Flask also picks a **new random `SECRET_KEY` and session cookie name on each process start**, so expect to sign in again after container restarts; that is upstream AIL behavior, not the stack tmpfs change.

**Lacus (when using the 6.x+Lacus+Tor image):** The Lacus crawler UI listens on HTTP port 7100. Optional Caddy blocks are in `caddy_snippet.conf.example` (e.g. `lacus.ail.home` → `ail:7100`). Uncomment and adjust hostnames if you use that image.

## Start

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose, deploy.
