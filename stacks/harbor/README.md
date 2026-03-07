# Harbor – container registry (pointer stack)

[Harbor](https://goharbor.io/) is a cloud-native container registry providing policies, RBAC, replication, scanning, and a web UI. Harbor is normally installed using its own installer, which generates a dedicated `docker-compose.yml` and `harbor.yml` config.

This stack acts as a **documentation pointer** in this repo so Harbor appears alongside other stacks, but it does **not** attempt to reimplement the full Harbor compose file.

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

## Notes

- The `docker-compose.yml` in this directory is intentionally a minimal placeholder and does **not** define Harbor services. Always use the official Harbor installer and compose bundle.
- Once deployed, Harbor can act as the registry backend for your homelab (including CI from the `woodpecker-ci` stack) and as a pull-through/cache for external images, depending on your configuration.
