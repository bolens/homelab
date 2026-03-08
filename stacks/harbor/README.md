# Harbor – container registry (pointer stack)

[Harbor](https://goharbor.io/) is a cloud-native container registry providing policies, RBAC, replication, scanning, and a web UI. Harbor is normally installed using its own installer, which generates a dedicated `docker-compose.yml` and `harbor.yml` config.

This stack acts as a **documentation pointer** in this repo so Harbor appears alongside other stacks, but it does **not** attempt to reimplement the full Harbor compose file.

**Restart after reboot:** When Harbor is installed in this repo at `stacks/harbor/harbor/`, `harbor/docker-compose.override.yml` already sets `restart: unless-stopped` for all services (and the proxy port/monitor network). If you install Harbor elsewhere, copy `docker-compose.override.yml.example` to that install directory as `docker-compose.override.yml`.

## How to deploy Harbor

Harbor uses its own installer and compose bundle. This repo does not provide a ready-to-deploy compose file.

### Step-by-step (offline installer in this directory)

If you have extracted the offline installer (e.g. `harbor-offline-installer-v2.15.0-rc1.tgz`) into this directory:

1. **Extract** (if not already done):
   ```bash
   cd stacks/harbor
   tar xzf harbor-offline-installer-v2.15.0-rc1.tgz
   cd harbor
   ```

2. **Create and edit config**:
   ```bash
   cp harbor.yml.tmpl harbor.yml
   # Edit harbor.yml – see key settings below
   ```

3. **Key settings in `harbor.yml`** (for Caddy in front):
   - `hostname`: your external hostname (e.g. `harbor.yourdomain.com`)
   - `harbor_admin_password`: change from default `Harbor12345`
   - `database.password`: change from default `root123`

   **Generate strong passwords** (run on your machine; do not commit outputs):
   ```bash
   # For harbor_admin_password (admin UI login)
   openssl rand -base64 32
   # For database.password (Postgres)
   openssl rand -base64 24
   ```
   - `data_volume`: e.g. `/data` or a path on your host
   - **For Caddy reverse proxy**: comment out the `https:` block and use HTTP only. Harbor will listen on port 80; Caddy terminates TLS and forwards to it.

4. **Prepare** (generates final `harbor.yml` and `docker-compose.yml`):
   - Ensure the port in `harbor.yml` matches what Caddy proxies to (default HTTP is 80; some installs use 8080 or 8880).
   ```bash
   sudo ./prepare
   ```

5. **Install**:
   ```bash
   sudo ./install.sh
   ```
   Optional: add `--with-trivy` for vulnerability scanning.

6. **Caddy**: Add a site block for `harbor.yourdomain.com` → `host.docker.internal:80` (or the host IP/port where Harbor listens). Harbor runs its own Docker Compose stack, so it is not on the `monitor` network; use `host.docker.internal` or the host’s IP.

7. **First login**: Default admin user is `admin`; use the password you set in `harbor_admin_password`. Change it after first login.

### Deploying via Portainer

1. **Download the official installer** on your Docker host (or a machine with Docker access where Portainer can deploy):
   - Follow the official Harbor installation docs to download the installer bundle (online or offline) on your Docker host.

2. **Generate configuration**
   - Use the installer’s `prepare` script to generate `harbor.yml` and `docker-compose.yml` in a dedicated directory (for example, `/opt/harbor`).
   - Configure:
     - External URL (e.g. `https://harbor.yourdomain.com`).
     - TLS settings (you can terminate TLS at Caddy and run Harbor HTTP-only internally, or let Harbor handle TLS).
     - Storage backend (filesystem, S3, etc.).

3. **Run Harbor**
   - Use the installer’s scripts (`./install.sh`, `docker compose up -d`, etc.) as documented upstream.

4. **Integrate with Caddy**
   - If you terminate TLS at Caddy, configure Caddy to reverse-proxy `harbor.yourdomain.com` to Harbor’s HTTP endpoint on the Docker host.

## Harbor behind Caddy

For `docker push` and `docker pull` to work when Harbor is behind Caddy, the proxy must:

1. **Forward X-Forwarded headers** – Harbor needs `X-Forwarded-Proto: https` and `X-Forwarded-Host` to handle auth and redirects.
2. **Disable buffering** – Large image layers must stream; buffering causes "authorize header needed" or EOF errors.

### Caddy configuration

Use this pattern in your Caddyfile (see `stacks/caddy/Caddyfile.example`):

```caddyfile
harbor.yourdomain.com {
    tls { ... }
    reverse_proxy host.docker.internal:8880 {
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-Host {host}
        flush_interval -1
        transport http {
            write_buffer 0
            read_buffer 0
        }
    }
}
```

Replace `host.docker.internal:8880` with your Harbor HTTP endpoint (host IP and port). Harbor’s default HTTP port is 80; use 8880 if your installer configured it that way.

### Harbor `harbor.yml` settings

When Caddy terminates TLS:

- **`hostname`**: Your external hostname (e.g. `harbor.yourdomain.com`). Must match the Caddy host.
- **`https`**: Comment out or remove the `https:` block. Harbor listens on HTTP only; Caddy handles TLS.
- **Port**: Harbor typically listens on 80 for HTTP. Ensure Caddy’s `reverse_proxy` target matches (e.g. `host.docker.internal:80` or `:8880`).

After changing `harbor.yml`, run `./prepare` and restart Harbor. Reload Caddy after Caddyfile changes.

### Verify

```bash
docker login harbor.yourdomain.com
docker push harbor.yourdomain.com/homelab/myimage:latest
```

---

## Harbor behind Caddy

For `docker push` and `docker pull` to work when Harbor is behind Caddy, the proxy must:

1. **Forward X-Forwarded headers** – Harbor needs `X-Forwarded-Proto: https` and `X-Forwarded-Host` to handle auth correctly.
2. **Disable buffering** – Large image layers must stream; buffering causes "authorize header needed" or EOF errors.

The `Caddyfile.example` includes a Harbor block with the required settings. It uses `proxy:8080` when Harbor's `docker-compose.override.yml` attaches the proxy to the `monitor` network.

**Harbor `harbor.yml` settings when behind Caddy:**

- `hostname`: must match your Caddy hostname (e.g. `harbor.yourdomain.com`).
- **Comment out** the `https:` block – Caddy terminates TLS; Harbor listens on HTTP.
- `http.port`: typically `80` (or `8880` if you changed it). The Caddy `reverse_proxy` target port must match.

After changing Caddy config, reload: `caddy reload --config /path/to/Caddyfile` or restart the Caddy container.

## mDNS and local access (bypass Cloudflare for large images)

Cloudflare free tier limits request body size (~100 MB), so large `docker push`/`pull` via a Cloudflare-proxied hostname (e.g. `harbor.yourdomain.com`) can fail. Use a **local hostname** that resolves only on your LAN so traffic never goes through Cloudflare.

The `Caddyfile.example` already defines `harbor.home` and `harbor.local` with the same reverse-proxy and `request_body { max_size 0 }` settings. Use one of the options below so that hostname resolves to your Caddy/Harbor host.

### Option 1: mDNS (Avahi) so `harbor.local` works

On the **host that receives Harbor traffic** (the machine where Caddy runs): use Avahi to advertise **`harbor.local`** in addition to your existing hostname, so you can reach Harbor for large pushes without changing the main hostname or going through Cloudflare.

**Recommended: generic mDNS alias template (any stack)**

Use the shared template so one unit file works for Harbor and every other stack. From the `docker/` repo root:

1. **Install Avahi** (if not already): `avahi-daemon`, `avahi-utils`. Ensure `avahi-daemon` is enabled and running.

2. **Install the template once** and enable the `harbor` alias (and any other stack) on the host where Caddy runs:
   ```bash
   # Install template (once)
   sudo cp scripts/avahi-alias@.service /etc/systemd/system/
   sudo systemctl daemon-reload

   # Enable harbor.local (and others as needed)
   sudo systemctl enable --now avahi-alias@harbor.service
   # e.g. also: avahi-alias@gitea.service, avahi-alias@nextcloud.service, …
   ```
   See [documents/SHARED-RESOURCES.md](../documents/SHARED-RESOURCES.md) (mDNS aliases) for the full list. For a **Harbor-only** unit, you can instead use `stacks/harbor/avahi-harbor-alias.service` as before.
   Check: from another machine on the LAN, `ping harbor.local` or `avahi-resolve -n harbor.local` should resolve to the Caddy host’s IP.

3. **Harbor and Caddy**: In Harbor’s `harbor.yml`, set `hostname` to the hostname you use in the browser. You can keep the public hostname (e.g. `harbor.yourdomain.com`) there; Caddy serves both that and `harbor.local` (see `Caddyfile.example`). Run `./prepare` and restart Harbor if you change it; ensure Caddy is configured for `harbor.local` (and `harbor.home`) with the same block and `request_body { max_size 0 }`.

4. **On clients**: Use `https://harbor.local` for login and as the registry when on the LAN. Large pushes/pulls bypass Cloudflare.

**Alternative (without the unit file):** If you prefer not to use the service, you can run once (and keep running) on the Caddy host:  
`avahi-publish -a -R harbor $(hostname -I | awk '{print $1}')`. Or set the machine’s hostname to `harbor` (not recommended if you want to keep your current hostname).

**If `avahi-alias@harbor` fails** with `Failed to resolve host name 'harbor.local': Timeout reached`, use the **static Avahi hosts file** instead (see [SHARED-RESOURCES.md](../documents/SHARED-RESOURCES.md) → mDNS aliases): add `LAN_IP  harbor.local` to `/etc/avahi/hosts`, restart avahi-daemon, disable the alias unit. **Note:** many systems do not resolve `/etc/avahi/hosts` on the *same* machine that runs Avahi; other LAN devices should resolve `harbor.local`. On the Caddy host itself, add `LAN_IP  harbor.local` to **`/etc/hosts`** if you need to resolve it there.

### Troubleshooting: https://harbor.local doesn’t work

1. **Resolution** – From a LAN client (or the Caddy host): `avahi-resolve -n harbor.local` and `ping harbor.local`. If this fails, mDNS isn’t advertising `harbor` (unit not running, or use `/etc/avahi/hosts` as above).
2. **Caddy** – Your **live** Caddyfile (not only the example) must have a server block for `harbor.local` (and optionally `harbor.home`) with `reverse_proxy` to Harbor and `request_body { max_size 0 }`. Reload after edits: `caddy reload --config /path/to/Caddyfile`.
3. **Harbor proxy** – Caddy’s block uses `proxy:8080` when Harbor is on the `monitor` network as service `proxy`. If Harbor runs elsewhere (e.g. host installer), point Caddy at that (e.g. `host.docker.internal:80`).
4. **TLS / `tlsv1 alert internal error`** – If resolution and ping work but `curl -k https://harbor.local` fails with a TLS error:
   - Your **live** Caddyfile must include a block for `harbor.local` (and optionally `harbor.home`) with `tls internal` and the same `reverse_proxy` as in `Caddyfile.example`. If that block is missing, Caddy may be serving a different vhost and the handshake can fail.
   - Reload or restart Caddy so it issues the internal cert for `harbor.local`: from the Caddy stack dir run `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` or `docker compose restart caddy`. Then try again.
   - Check Caddy logs when you hit `https://harbor.local`: `docker logs <caddy_container> 2>&1 | tail -30` to see certificate or upstream errors.
   - Browsers will show a cert warning for `tls internal`; accept it to continue.
5. **Firewall** – Port 443 to the Caddy host must be open from the client.

### docker push: `connection refused` to harbor.local:443

If you see `dial tcp <IP>:443: connect: connection refused` when pushing:

1. **Who is &lt;IP&gt;?**  
   - If &lt;IP&gt; is the **machine where you run `docker push`** (e.g. your laptop), then **harbor.local is resolving to the wrong host**. It must resolve to the **Caddy host** (the server that runs the Caddy container). Fix: On the machine where you push, set `/etc/hosts` or your LAN DNS so `harbor.local` → Caddy host’s IP. Or run `docker push` from the Caddy host and use `harbor.local` there (with `harbor.local` in that host’s `/etc/hosts` pointing to 127.0.0.1 or the host’s LAN IP).  
   - If &lt;IP&gt; is the **Caddy host**, then nothing is listening on 443 on that box.

2. **Caddy listening on 443 (on the Caddy host):**  
   - `docker ps | grep caddy` — Caddy container must be running.  
   - `ss -tlnp | grep 443` or `sudo ss -tlnp | grep 443` — something must be bound to 443 (usually the Docker proxy).  
   - From the Caddy host: `curl -k -s -o /dev/null -w "%{http_code}" https://127.0.0.1/` — should return 200 or 301/302.  
   If Caddy is not running, start it from the Caddy stack dir: `docker compose up -d`. If the host firewall blocks 443, open it (e.g. `sudo ufw allow 443` then `sudo ufw reload`).

3. **Push from the Caddy host** (avoids DNS): On the server that runs Caddy, add to `/etc/hosts`: `127.0.0.1 harbor.local`. Then `docker login harbor.local` and `docker push harbor.local/homelab/torbot:latest`. The Docker client will connect to 127.0.0.1:443 where Caddy is published.

### Docker login: `x509: certificate signed by unknown authority`

When Caddy uses `tls internal` for `harbor.local`, the Docker daemon does not trust that certificate. Make Docker trust the CA:

1. **Create the certs directory** (use the exact hostname you use for `docker login`):
   ```bash
   sudo mkdir -p /etc/docker/certs.d/harbor.local
   ```
2. **Extract the CA from the chain** (run from a machine that can reach `https://harbor.local`):
   ```bash
   echo | openssl s_client -connect harbor.local:443 -showcerts 2>/dev/null | \
     awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/ { print }' > /tmp/harbor-chain.pem
   # Use the last certificate in the chain (root CA)
   awk '/BEGIN CERTIFICATE/{n++} n>1{print}' /tmp/harbor-chain.pem | \
     sudo tee /etc/docker/certs.d/harbor.local/ca.crt > /dev/null
   ```
   If that leaves `ca.crt` empty or wrong, copy the **root** certificate (the last block in `harbor-chain.pem`) into `ca.crt` by hand.

   **When Caddy uses `tls internal`:** Docker needs the **root** CA, not the intermediate. If you already have a cert in `ca.crt` but still get "certificate signed by unknown authority", replace it with Caddy’s root (run from the host that runs Caddy):
   ```bash
   docker exec caddy cat /data/caddy/pki/authorities/local/root.crt | sudo tee /etc/docker/certs.d/harbor.local/ca.crt > /dev/null
   ```
   Then restart Docker (step 3).
3. **Restart Docker**: `sudo systemctl restart docker`
4. **Log in**: `docker login harbor.local`

**Alternative:** Use Option 3 (direct by IP / `localhost`) and, if Harbor is HTTP internally, add that address to Docker’s `insecure-registries` in `/etc/docker/daemon.json` so you don’t need to trust the internal CA.

### Option 2: Local DNS override (e.g. Pi-hole, AdGuard, router)

Keep using your public hostname (e.g. `harbor.yourdomain.com`) in Harbor and Caddy. On your **local DNS** (Pi-hole, AdGuard Home, or router DNS):

- Add an **A record**: `harbor.yourdomain.com` → IP of the host that runs Caddy (or Harbor if direct).

Then, when devices on the LAN resolve `harbor.yourdomain.com`, they get the local IP and traffic stays on the LAN. Off-LAN devices still resolve via public DNS (e.g. Cloudflare) if you use that for the domain.

### Option 3: Direct by IP or `localhost`

From a machine on the same host as Harbor, use `localhost` or the host’s LAN IP as the registry (e.g. `docker login localhost:8880` or `https://192.168.x.x`). If Harbor listens on HTTP only internally, add that address to Docker’s `insecure-registries` in `/etc/docker/daemon.json`. This avoids Cloudflare but only works from that host or when you use the IP explicitly.

## Notes

- The `docker-compose.yml` in this directory is intentionally a minimal placeholder and does **not** define Harbor services. Always use the official Harbor installer and compose bundle.
- Once deployed, Harbor can act as the registry backend for your homelab (including CI from the `woodpecker-ci` stack) and as a pull-through/cache for external images, depending on your configuration.
