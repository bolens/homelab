# AIL framework

**AIL** (Analysis Information Leak framework) analyses potential information leaks from unstructured data: pastes (Pastebin-style), streams, and crawled content. It detects credentials, credit cards, API keys, PGP data, and more; supports trackers (YARA, regex, terms), correlation, MISP/TheHive export, and optional Tor hidden-service crawling.

**Website:** https://www.ail-project.org  
**Docs:** https://github.com/ail-project/ail-framework/tree/master/doc  
**GitHub:** https://github.com/ail-project/ail-framework  
**Docker image:** https://hub.docker.com/r/cciucd/ail-framework  
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
- **This stack:** `docker-compose.yml` bind-mounts `patches/var/www/blueprints/root.py` with **15** attempts and **120** seconds. Adjust `_LOGIN_MAX_ATTEMPTS` / `_LOGIN_LOCKOUT_SEC` in that file, then recreate the container so Flask reloads. Remove the volume line to return to upstream behavior.
- **Clear lockout without waiting:** from this directory, `./clear-login-lockout.sh` (or `bash clear-login-lockout.sh`).
- **Username is your email** (case-sensitive in this image). After changing the admin email, use the **new** address to sign in—not `admin@admin.test`—unless you ran **`-rp`**, which resets **`admin@admin.test`** again.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `ail:7000`). The AIL UI serves HTTPS with a self-signed cert; Caddy is configured with `tls_insecure_skip_verify` for the backend. |
| **Network** | `monitor` (external) — Caddy can reach `ail:7000`. |
| **Image** | Default: `cciucd/ail-framework:latest` (5.x, community image). Override with `AIL_IMAGE` in `stack.env` to use official 6.x or your own build (see **Using AIL 6.x** below). |
| **Storage** | Named volumes for PASTES, CRAWLED_SCREENSHOT, DATA_KVROCKS, indexdir, HASHS, logs. |
| **Login patch** | Optional bind mount: `patches/.../root.py` (see **Login lockout** above). Drop the mount when switching to an AIL image whose `root.py` no longer matches. |

## Resources

AIL is resource-intensive: the image is large (~2GB+) and the app typically needs **>6GB RAM**. Ensure the host has enough memory.

## Using AIL 6.x (official build)

The default image ([cciucd/ail-framework](https://hub.docker.com/r/cciucd/ail-framework)) is 5.x. Official releases (e.g. **v6.7**) are not published as images; you build from the [official repo](https://github.com/ail-project/ail-framework). The official image uses **/opt/AIL** for data paths (not /opt/ail-framework), so you must use the provided override.

**This repo** vendors a pinned checkout under `ail-framework-docker/ail-framework` (tag **v6.7**) with small build fixes for Ubuntu 22.04 / current pip (Dockerfile paths, `install_virtualenv.sh`, pystemon installer). Prefer building from there so you do not have to re-apply patches after a fresh clone.

1. **Build the image** (takes a long time, several GB disk/RAM and network):
   ```bash
   cd stacks/ail-framework/ail-framework-docker/ail-framework
   docker build -f other_installers/docker/Dockerfile -t ail-framework:6.7 .
   ```
   Or clone upstream at `v6.7` and copy the patched files from `ail-framework-docker/ail-framework` if you maintain a separate tree (see `ail-framework-docker/README.md`).

2. **Enable the override** so the stack uses the 6.x image and `/opt/AIL` volume paths:
   ```bash
   cd /path/to/docker/stacks/ail-framework
   cp docker-compose.override.example docker-compose.override.yml
   ```
   Optionally set `AIL_IMAGE=ail-framework:6.7` in `stack.env` (the override defaults to that local tag).

3. **Deploy:** `docker compose --env-file stack.env up -d`. Access and Caddy config are unchanged.

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

## AIL 6.x with Lacus crawler and Tor

For AIL 6.x **plus** the [Lacus](https://github.com/ail-project/lacus) crawler and a Tor SOCKS proxy in one image, use [MatthisClavijo/ail-framework-docker](https://github.com/MatthisClavijo/ail-framework-docker). That image uses **/opt/ail-framework** (same as the default 5.x image), so you use the **default** compose—**no** `docker-compose.override.yml`. Pin to the AIL release tag you want (e.g. v6.7) by checking out that tag before building.

**Tor:** Port 9050 is SOCKS, not HTTP. Caddy does not proxy it. Other containers on the `monitor` network use `socks5://ail:9050` directly. No Caddy block needed.

---

### Step-by-step: Build, push to harbor.local, deploy (Caddy handles AIL + Lacus)

All access is via Caddy; no host ports. Caddy proxies **AIL UI** (7000) and **Lacus UI** (7100). Replace `PROJECT` with your Harbor project (e.g. `homelab`) and your domain (e.g. `example.com`) where shown.

**1. Build the image (on a machine with Docker, network, and enough disk; image ~20 GB)**

```bash
git clone https://github.com/MatthisClavijo/ail-framework-docker.git
cd ail-framework-docker
git clone https://github.com/ail-project/ail-framework.git
cd ail-framework && git checkout v6.6 && cd ..

docker compose build
docker tag ubuntu:ail ail-framework:6.6-lacus-tor
```

**2. Trust Harbor’s TLS cert (only when using harbor.local)**

If `docker login harbor.local` or push will fail with “certificate signed by unknown authority”, trust the cert on the machine where you run `docker push`:

```bash
# Fetch full chain
echo | openssl s_client -connect harbor.local:443 -servername harbor.local -showcerts 2>/dev/null \
  | awk '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/ { print }' > /tmp/harbor.local-chain.crt

# Arch / CachyOS (recommended)
sudo trust anchor --store /tmp/harbor.local-chain.crt
sudo systemctl restart docker

# Or: Debian/Ubuntu – copy to ca-certificates and update
# sudo cp /tmp/harbor.local-chain.crt /usr/local/share/ca-certificates/harbor.local.crt
# sudo update-ca-certificates
# sudo systemctl restart docker
```

**3. Push the image to harbor.local** (use harbor.local for large images to avoid Cloudflare limits)

```bash
docker login harbor.local
docker tag ail-framework:6.6-lacus-tor harbor.local/PROJECT/ail-framework:6.6-lacus-tor
docker push harbor.local/PROJECT/ail-framework:6.6-lacus-tor
```

**4. Caddy: include the AIL snippet (AIL + Lacus)**

Ensure the stack’s Caddy snippet is included in your Caddyfile so Caddy handles both internal ports:

- **AIL UI** → `https://ail.home` / `https://ail.yourdomain` → `https://ail:7000` (with `tls_insecure_skip_verify`)
- **Lacus UI** → `https://lacus.home` / `https://lacus.yourdomain` → `http://ail:7100`

Copy from `stacks/ail/caddy_snippet.conf` (or the example and uncomment the Lacus block). Reload Caddy after changes:

```bash
caddy reload --config /path/to/Caddyfile
```

**5. Deploy the stack (on the host where AIL will run)**

```bash
cd /path/to/docker/stacks/ail
```

In `stack.env` set:

```bash
AIL_IMAGE=harbor.local/PROJECT/ail-framework:6.6-lacus-tor
```

Do **not** use `docker-compose.override.yml` (that’s for the official 6.x image with `/opt/AIL`; this image uses `/opt/ail-framework`).

```bash
docker compose --env-file stack.env up -d
```

**6. Access**

- **AIL:** https://ail.home (or your configured AIL hostname)
- **Lacus:** https://lacus.home (or your configured Lacus hostname)
- **Tor (other containers only):** `socks5://ail:9050` on the `monitor` network

**7. (Optional) Other hosts**

On another host that should run AIL from Harbor: ensure Docker trusts `harbor.local` (step 2 if needed), then set `AIL_IMAGE=harbor.local/PROJECT/ail-framework:6.6-lacus-tor` in that host’s `stack.env` and run `docker compose --env-file stack.env up -d` there. Caddy on that network must proxy to the AIL container’s 7000 and 7100 as in step 4.

## Caddy reverse proxy

The stack is on the `monitor` network so Caddy can reach `ail:7000`. The AIL Flask app uses HTTPS with a self-signed certificate; the Caddyfile uses:

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
