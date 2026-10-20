# Harbor – container registry (pointer stack)

[Harbor](https://goharbor.io/) is a cloud-native container registry providing policies, RBAC, replication, scanning, and a web UI. Harbor is normally installed using its own installer, which generates a dedicated `docker-compose.yml` and `harbor.yml` config.

This stack acts as a **documentation pointer** in this repo so Harbor appears alongside other stacks, but it does **not** attempt to reimplement the full Harbor compose file.

**Restart after reboot:** The override example sets `restart: unless-stopped` for the listed services and attaches the proxy to `ingress-admin` without a host port. For a fresh installation, copy it into the actual installer directory as `docker-compose.override.yml`. For an existing installation, review and merge the example into the existing override; repository preparation does not replace it.

## How to deploy Harbor

Harbor uses its own installer and compose bundle. This repo does not provide a ready-to-deploy compose file.

### Step-by-step (offline installer in this directory)

This example targets the whole [Harbor v2.15.4 release](https://github.com/goharbor/harbor/releases/tag/v2.15.4), including `harbor-offline-installer-v2.15.4.tgz` and its matching proxy. Verify the installer SHA-256 against the [official release metadata](https://api.github.com/repos/goharbor/harbor/releases/tags/v2.15.4) and verify its published signing bundle before extraction. These steps are for a fresh installation; use [the upgrade procedure](#upgrading-the-installer-bundle) for existing state. Do not extract over an existing installer directory.

1. **Extract** (if not already done):
   ```bash
   cd stacks/harbor
   tar xzf harbor-offline-installer-v2.15.4.tgz
   cd harbor
   ```

2. **Create and edit config**:
   ```bash
   cp -n harbor.yml.tmpl harbor.yml
   cp -n ../docker-compose.override.yml.example docker-compose.override.yml
   # Edit harbor.yml and review the override – see settings below
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
   - **For Caddy reverse proxy**: set `external_url: https://harbor.yourdomain.com`, matching your chosen hostname; comment out the installer's `https:` block. Caddy terminates TLS and reaches the generated proxy at container port 8080. The override removes the installer's host-port publication.
   - Review the [2.15.4 security defaults](#security-options-in-2154) before running preparation.

4. **Prepare** (reads `harbor.yml` and generates component configuration and `docker-compose.yml`):
   - Harbor's generated proxy listens on container port 8080. The override
     attaches it to `ingress-admin` without publishing a host port.
   - First run the repository wrapper from the parent stack directory to
     create the external `ingress-admin` network before any installer start.
     After upstream preparation, rerun the wrapper to apply the generated
     nginx configuration's narrow read ACL.
   ```bash
   (cd .. && ./prepare-stack.sh)
   sudo ./prepare
   (cd .. && ./prepare-stack.sh)
   ```

5. **Install**:
   ```bash
   sudo ./install.sh
   ```
   Optional: add `--with-trivy` for vulnerability scanning.

6. **Caddy**: Attach Harbor's proxy to `ingress-admin` and route
   `harbor.yourdomain.com` to `proxy:8080`. Do not publish the proxy on the
   host.

7. **First login**: Default admin user is `admin`; use the password you set in `harbor_admin_password`. Change it after first login.

### Deploying via Portainer

1. **Download the official installer** on your Docker host (or a machine with Docker access where Portainer can deploy):
   - Follow the official Harbor installation docs to download the installer bundle (online or offline) on your Docker host.

2. **Generate configuration**
   - Use the installer's `prepare` script to generate `harbor.yml` and `docker-compose.yml` in a dedicated directory (for example, `/opt/harbor`).
   - Configure:
     - External URL (e.g. `https://harbor.yourdomain.com`).
     - TLS settings (you can terminate TLS at Caddy and run Harbor HTTP-only internally, or let Harbor handle TLS).
     - Storage backend (filesystem, S3, etc.).

3. **Run Harbor**
   - Before any start, run this repository's `./prepare-stack.sh` from
     `stacks/harbor` to ensure the override's external `ingress-admin` network
     exists. For the in-repository installer layout, run it after upstream
     preparation as well to restore nginx's configuration read ACL.
   - Use the installer's scripts (`./install.sh`, `docker compose up -d`, etc.) as documented upstream.

4. **Integrate with Caddy**
   - If you terminate TLS at Caddy, attach Harbor's proxy to `ingress-admin` and
     reverse-proxy `harbor.yourdomain.com` to `proxy:8080`.

## Harbor behind Caddy

For `docker push` and `docker pull` to work when Harbor is behind Caddy, the proxy must:

1. **Forward X-Forwarded headers** – Harbor needs `X-Forwarded-Proto: https` and `X-Forwarded-Host` to handle auth and redirects.
2. **Disable buffering** – Large image layers must stream; buffering causes "authorize header needed" or EOF errors.

### Caddy configuration

Use this pattern in your Caddyfile (see `stacks/caddy/Caddyfile.example`):

```caddyfile
harbor.yourdomain.com {
    tls { ... }
    reverse_proxy proxy:8080 {
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

The `proxy:8080` target uses Harbor's service name on the shared `ingress-admin`
network and is not directly reachable through a host port.

### Harbor `harbor.yml` settings

When Caddy terminates TLS:

- **`hostname`**: Your external hostname (e.g. `harbor.yourdomain.com`). Must match the Caddy host.
- **`https`**: Comment out or remove the `https:` block. Harbor listens on HTTP only; Caddy handles TLS.
- **Port**: Caddy reaches Harbor's generated proxy at `proxy:8080` on
  `ingress-admin`; no host port is required.

After changing `harbor.yml`, run `./prepare` and restart Harbor. Reload Caddy after Caddyfile changes.

From `stacks/harbor`, run this repository's `./prepare-stack.sh` after upstream
`./prepare`; it ensures `ingress-admin` exists and, for the in-repository installer
layout, restores the narrow read ACL required by Harbor's nginx UID 10000 without
making its generated configuration world-readable. It preserves existing
`stack.env`, Caddy snippets and override files, and refreshes only the generated
`.env` mirror. Its reference override is copied at the stack root, not installed
into `harbor/`; review and copy/merge the override into the actual installer
directory yourself. It does not migrate `harbor.yml` or start Harbor.

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

The `Caddyfile.example` includes a Harbor block with the required settings. It uses `proxy:8080` when Harbor's `docker-compose.override.yml` attaches the proxy to the `ingress-admin` network.

**Harbor `harbor.yml` settings when behind Caddy:**

- `hostname`: must match your Caddy hostname (e.g. `harbor.yourdomain.com`).
- **Comment out** the `https:` block – Caddy terminates TLS; Harbor listens on HTTP.
- `http.port`: controls Harbor's generated host-facing configuration, but the
  local override removes that publication. Caddy targets `proxy:8080`.

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
   See [documents/SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) (mDNS aliases) for the full list. For a **Harbor-only** unit, you can instead use `stacks/harbor/avahi-harbor-alias.service` as before.
   Check: from another machine on the LAN, `ping harbor.local` or `avahi-resolve -n harbor.local` should resolve to the Caddy host's IP.

3. **Harbor and Caddy**: In Harbor's `harbor.yml`, set `hostname` to the hostname you use in the browser. You can keep the public hostname (e.g. `harbor.yourdomain.com`) there; Caddy serves both that and `harbor.local` (see `Caddyfile.example`). Run `./prepare` and restart Harbor if you change it; ensure Caddy is configured for `harbor.local` (and `harbor.home`) with the same block and `request_body { max_size 0 }`.

4. **On clients**: Use `https://harbor.local` for login and as the registry when on the LAN. Large pushes/pulls bypass Cloudflare.

**Alternative (without the unit file):** If you prefer not to use the service, you can run once (and keep running) on the Caddy host:
`avahi-publish -a -R harbor $(hostname -I | awk '{print $1}')`. Or set the machine's hostname to `harbor` (not recommended if you want to keep your current hostname).

**If `avahi-alias@harbor` fails** with `Failed to resolve host name 'harbor.local': Timeout reached`, use the **static Avahi hosts file** instead (see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) → mDNS aliases): add `LAN_IP  harbor.local` to `/etc/avahi/hosts`, restart avahi-daemon, disable the alias unit. **Note:** many systems do not resolve `/etc/avahi/hosts` on the *same* machine that runs Avahi; other LAN devices should resolve `harbor.local`. On the Caddy host itself, add `LAN_IP  harbor.local` to **`/etc/hosts`** if you need to resolve it there.

### Troubleshooting: https://harbor.local doesn't work

1. **Resolution** – From a LAN client (or the Caddy host): `avahi-resolve -n harbor.local` and `ping harbor.local`. If this fails, mDNS isn't advertising `harbor` (unit not running, or use `/etc/avahi/hosts` as above).
2. **Caddy** – Your **live** Caddyfile (not only the example) must have a server block for `harbor.local` (and optionally `harbor.home`) with `reverse_proxy` to Harbor and `request_body { max_size 0 }`. Reload after edits: `caddy reload --config /path/to/Caddyfile`.
3. **Harbor proxy** – Caddy's block uses `proxy:8080` when Harbor is on the `ingress-admin` network as service `proxy`. If Harbor runs elsewhere (e.g. host installer), point Caddy at that (e.g. `host.docker.internal:80`).
4. **TLS / `tlsv1 alert internal error`** – If resolution and ping work but `curl -k https://harbor.local` fails with a TLS error:
   - Your **live** Caddyfile must include a block for `harbor.local` (and optionally `harbor.home`) with `tls internal` and the same `reverse_proxy` as in `Caddyfile.example`. If that block is missing, Caddy may be serving a different vhost and the handshake can fail.
   - Reload or restart Caddy so it issues the internal cert for `harbor.local`: from the Caddy stack dir run `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` or `docker compose restart caddy`. Then try again.
   - Check Caddy logs when you hit `https://harbor.local`: `docker logs <caddy_container> 2>&1 | tail -30` to see certificate or upstream errors.
   - Browsers will show a cert warning for `tls internal`; accept it to continue.
5. **Firewall** – Port 443 to the Caddy host must be open from the client.

### docker push: `connection refused` to harbor.local:443

If you see `dial tcp <IP>:443: connect: connection refused` when pushing:

1. **Who is &lt;IP&gt;?**
   - If &lt;IP&gt; is the **machine where you run `docker push`** (e.g. your laptop), then **harbor.local is resolving to the wrong host**. It must resolve to the **Caddy host** (the server that runs the Caddy container). Fix: On the machine where you push, set `/etc/hosts` or your LAN DNS so `harbor.local` → Caddy host's IP. Or run `docker push` from the Caddy host and use `harbor.local` there (with `harbor.local` in that host's `/etc/hosts` pointing to 127.0.0.1 or the host's LAN IP).
   - If &lt;IP&gt; is the **Caddy host**, then nothing is listening on 443 on that box.

2. **Caddy listening on 443 (on the Caddy host):**
   - `docker ps | grep caddy`, Caddy container must be running.
   - `ss -tlnp | grep 443` or `sudo ss -tlnp | grep 443`, something must be bound to 443 (usually the Docker proxy).
   - From the Caddy host: `curl -k -s -o /dev/null -w "%{http_code}" https://127.0.0.1/`, should return 200 or 301/302.
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

   **When Caddy uses `tls internal`:** Docker needs the **root** CA, not the intermediate. If you already have a cert in `ca.crt` but still get "certificate signed by unknown authority", replace it with Caddy's root (run from the host that runs Caddy):
   ```bash
   docker exec caddy cat /data/caddy/pki/authorities/local/root.crt | sudo tee /etc/docker/certs.d/harbor.local/ca.crt > /dev/null
   ```
   Then restart Docker (step 3).
3. **Restart Docker**: `sudo systemctl restart docker`
4. **Log in**: `docker login harbor.local`

**Alternative:** Use Option 3 (direct by IP / `localhost`) and, if Harbor is HTTP internally, add that address to Docker's `insecure-registries` in `/etc/docker/daemon.json` so you don't need to trust the internal CA.

### Option 2: Local DNS override (e.g. Pi-hole, AdGuard, router)

Keep using your public hostname (e.g. `harbor.yourdomain.com`) in Harbor and Caddy. On your **local DNS** (Pi-hole, AdGuard Home, or router DNS):

- Add an **A record**: `harbor.yourdomain.com` → IP of the host that runs Caddy (or Harbor if direct).

Then, when devices on the LAN resolve `harbor.yourdomain.com`, they get the local IP and traffic stays on the LAN. Off-LAN devices still resolve via public DNS (e.g. Cloudflare) if you use that for the domain.

### Option 3: Local Caddy hostname

Use `harbor.local` (or another split-DNS hostname) through Caddy. Direct
host-IP and `localhost` access are intentionally unavailable because Harbor's
proxy has no published host port.

## Notes

- No maintained `docker-compose.yml` is supplied here. Always use the official Harbor installer and its generated compose bundle.
- Once deployed, Harbor can act as the registry backend for your homelab (including CI from the `woodpecker-ci` stack) and as a pull-through/cache for external images, depending on your configuration.

## Security options in 2.15.4

The [2.15.4 release](https://github.com/goharbor/harbor/releases/tag/v2.15.4)
reverses two 2.15.3 defaults. Review them in the existing private `harbor.yml`
before migration/preparation; this repository does not set either option for you.

- `network.allow_private_network_access` defaults to **true**. Outbound webhooks
  and Slack notifications may reach private, loopback, link-local and cloud
  metadata addresses. Set it to **false** to enable the outbound destination
  guard when internal receivers are not required. A configuration already
  migrated by 2.15.3 may contain an explicit false value; preserve that choice
  unless the operator deliberately changes it. See the [upstream change](https://github.com/goharbor/harbor/pull/24082).
- `content_trust.legacy_signer_pull_enabled` defaults to **true**. Under an
  enabled content-trust policy, a push-authorized token client with a cosign or
  notation User-Agent can pull an unsigned subject manifest to create its first
  signature. The User-Agent is spoofable; it does not replace push authorization.
  Set the option to **false** for strict content-trust enforcement on these
  pulls, accepting that existing signing workflows may then need adjustment.
  This exemption does not bypass the vulnerability-prevention policy. See the
  [signer change](https://github.com/goharbor/harbor/pull/24086) and
  [installer setting](https://github.com/goharbor/harbor/pull/24101).

For example, merge these **explicit restrictions** only after checking that they
match your intended webhook destinations and signing workflow; do not replace
the rest of `harbor.yml` or its secrets:

```yaml
network:
  allow_private_network_access: false
content_trust:
  legacy_signer_pull_enabled: false
```

Use YAML booleans. Preserve existing overrides, regenerate with the matching
installer, and inspect the generated core/jobservice environment for the intended
`HARBOR_ALLOW_PRIVATE_NETWORK_ACCESS` and core
`CONTENT_TRUST_LEGACY_SIGNER_PULL_ENABLED` values. Test both permitted and denied
webhook/signing cases. Do not put these settings in `stack.env` and assume Harbor
will consume them: that file is a repository preparation placeholder.

## Upgrading the installer bundle

The example targets **2.15.4**. Updating only `proxy.image` is insufficient:
core, jobservice, registry, database and optional components must come from the
same reviewed installer release. Components can have their own version tags;
retain the installer's generated selections rather than retagging every image
with the Harbor version. See the [official upgrade guide](https://goharbor.io/docs/2.15.0/administration/upgrade/).
Its documented migration path starts at 2.12.0; older installations need the
applicable earlier upgrade steps first.

1. Record the actual installation version, complete component images, storage
   locations and private configuration. Quiesce registry writers and background
   jobs, and follow upstream's stop procedure without deleting persistent
   volumes. Back up the complete installer/configuration, `harbor.yml`, generated
   files, overrides, certificates, signing keys, database and artifact storage
   outside Git. Include external database/object storage where configured; do
   not assume all state is under the default `/data` path. Verify an isolated
   restore using the prior installer/images before proceeding.
2. Extract the verified whole 2.15.4 installer into a separate directory. Carry
   forward the existing private configuration and run the target release's
   documented `prepare migrate` procedure. Review both security options above
   explicitly. Migration of `harbor.yml` is separate from the database schema
   migration that core performs when the upgraded deployment starts.
3. Review regenerated component configuration and compose together with the
   existing override, preserving storage, TLS, secrets, ingress and optional
   components. Match the override proxy to `goharbor/nginx-photon:v2.15.4` and
   confirm the effective proxy publishes no host ports and remains reachable
   only through the intended Caddy network. Run the matching installer with the
   same optional components, such as Trivy; do not apply this example as a
   stand-alone proxy update.
4. Verify service health, login, project/repository/artifact counts and metadata,
   representative pulls/pushes, signing, webhooks and configured replication.
   Review 2.15.3's [push-replication regression](https://github.com/goharbor/harbor/releases/tag/v2.15.3)
   where relevant; a proxy version change does not prove that path. Compare
   persistent data with the baseline. If verification fails, stop the new
   deployment and restore the verified state with all prior images/installer;
   a proxy-tag rollback alone cannot undo a database migration. Retain the
   verified backup while any preservation check is inconclusive, and remove
   only this operation's temporary copies after successful verification.

This is a portable source example. No installer migration, running bundle,
security setting or restored deployment has been verified by changing these
tracked files.
