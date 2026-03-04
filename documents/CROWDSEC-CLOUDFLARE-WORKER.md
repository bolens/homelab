# CrowdSec + Cloudflare Workers bouncer

This guide shows how to take **decisions from your CrowdSec engine** (running in the `stacks/crowdsec` stack) and **enforce them at Cloudflare’s edge** using the **Cloudflare Workers bouncer**.

- Requests from bad IPs can be **blocked or challenged at Cloudflare** before they reach your tunnel or Caddy.
- This complements, not replaces, Cloudflare Access / SSO and your existing Caddy configuration.
- Examples below are **sanitized** – replace placeholder tokens, keys, and hostnames with your own values on the host. Do **not** commit those secrets to git.

---

## When to use this

Use the Cloudflare Workers bouncer if:

- You already expose services through **Cloudflare Tunnel** or `*.yourdomain.com` DNS.
- You want CrowdSec detections (SSH brute force, HTTP abuse, scanners, etc.) to result in **Cloudflare firewall actions** (block or challenge).
- You prefer bans to happen at the **edge** instead of only on your homelab host.

If you only ever access services on your LAN and don’t use Cloudflare for them, you may not need this bouncer.

---

## Prerequisites

- **CrowdSec stack running** from this repo (`stacks/crowdsec`):
  - LAPI is exposed on the host as `http://127.0.0.1:8080/` via the compose file.
  - You’ve configured at least some **acquisitions** (Caddy logs, SSH logs, Docker logs, etc.) and installed appropriate **collections**.
- **Cloudflare**:
  - A Cloudflare account that manages the zones you want to protect (e.g. your homelab domain).
  - A Cloudflare **API token** with permissions for Workers, Workers KV, Zones, and Firewall rules.
- **Linux host**:
  - The same machine that runs Docker and the CrowdSec container.
  - Ability to install packages and run `systemctl` (or equivalent service manager).

> All tokens and keys in this guide are examples only. Keep real values on your host under `/etc/crowdsec/bouncers/` or a secrets manager – never in this repo.

---

## 1. Install the Cloudflare Workers bouncer

On the Docker host (not in a container), install the **Cloudflare Workers bouncer** package:

```bash
# Example for Debian/Ubuntu
sudo apt update
sudo apt install crowdsec-cloudflare-worker-bouncer

# Example for RHEL/CentOS/Fedora
sudo yum install crowdsec-cloudflare-worker-bouncer
```

See the official docs for up‑to‑date package names and supported distributions:

- Cloudflare Workers bouncer docs: https://docs.crowdsec.net/u/bouncers/cloudflare-workers/

---

## 2. Create a Cloudflare API token

In the Cloudflare dashboard (SANITIZED outline):

1. Go to **My Profile → API Tokens**.
2. Create a token with:
   - Permissions to manage **Workers**, **Workers KV**, **Zones**, and **Firewall rules**.
   - Scope limited to the account/zones you want to protect.
3. Copy the token (for example: `CLOUDFLARE_API_TOKEN_EXAMPLE`).

Keep this token safe on the host; you will **not** commit it to git.

---

## 3. Generate the bouncer configuration

Run the bouncer once in **config generation** mode to discover your accounts/zones and create a base config:

```bash
sudo crowdsec-cloudflare-worker-bouncer \
  -g CLOUDFLARE_API_TOKEN_EXAMPLE \
  -o /etc/crowdsec/bouncers/crowdsec-cloudflare-worker-bouncer.yaml
```

This:

- Contacts Cloudflare using the API token.
- Writes a YAML config describing your accounts, zones, and the Workers/KV resources it will use.

Review the generated file:

```bash
sudo vi /etc/crowdsec/bouncers/crowdsec-cloudflare-worker-bouncer.yaml
```

Do **not** hardcode secrets from this file into this repo.

---

## 4. Register the bouncer with CrowdSec (LAPI key)

Your Workers bouncer needs a **LAPI key** to authenticate to the CrowdSec Local API.

From the CrowdSec host (either on the host if `cscli` is installed there, or inside the `crowdsec` container via `docker compose exec`):

```bash
# Example: add a new bouncer and get a raw key
sudo cscli -oraw bouncers add cloudflare-workers-bouncer
```

This prints a key such as:

```text
cloudflare-workers-bouncer  0123456789abcdef0123456789abcdef
```

Copy the key value (not the name).

---

## 5. Wire the bouncer to CrowdSec LAPI

Edit `/etc/crowdsec/bouncers/crowdsec-cloudflare-worker-bouncer.yaml` and set the CrowdSec section to point at your LAPI:

```yaml
crowdsec:
  lapi_url: "http://127.0.0.1:8080/"
  lapi_key: "REPLACE_WITH_LAPI_KEY_FROM_CSCLI"
```

Leave the `cloudflare` section (accounts/zones, Workers, KV) as generated unless you have specific needs.

Save the file and exit.

---

## 6. Start the bouncer (daemon mode)

Daemon mode keeps a small Go process running on the host that:

- Polls CrowdSec LAPI for new/expired decisions.
- Synchronizes IPs into Cloudflare Workers/KV and firewall rules.

Start and enable the service:

```bash
sudo systemctl start crowdsec-cloudflare-worker-bouncer
sudo systemctl enable crowdsec-cloudflare-worker-bouncer
```

Check that it is running without errors:

```bash
sudo systemctl status crowdsec-cloudflare-worker-bouncer
```

You should see logs indicating:

- Successful connection to CrowdSec LAPI.
- Successful setup of Workers, KV store, and Cloudflare firewall rules.

---

## 7. How this interacts with your homelab

Once the Workers bouncer is running:

- **CrowdSec** analyzes logs (Caddy, SSH, Docker containers) and emits decisions (`ban`, `challenge`, etc.).
- The **Workers bouncer** syncs those decisions to Cloudflare.
- Requests from banned IPs are **blocked or challenged at Cloudflare’s edge** before they reach:
  - Your Cloudflare Tunnel,
  - Your Caddy instance,
  - Your Docker host and apps.

This works alongside:

- **Cloudflare Access / Zero Trust** rules for SSO.
- **Caddy** routing and TLS.

CrowdSec decisions are just another signal feeding Cloudflare’s firewall.

---

## 8. Maintenance and safety

- To **change** Cloudflare configuration (zones, actions, etc.), edit the YAML file and, if necessary, run the bouncer’s cleanup/init flows as described in the official docs.
- To **rotate** your LAPI key:
  - Remove/re‑add the bouncer with `cscli bouncers delete/add`.
  - Update `lapi_key` in the bouncer config.
  - Restart the service.
- To **disable** the Workers bouncer but keep CrowdSec running locally, stop and disable the service:

  ```bash
  sudo systemctl disable --now crowdsec-cloudflare-worker-bouncer
  ```

All sensitive values (Cloudflare tokens, LAPI keys) stay on the host in `/etc/crowdsec/bouncers/` or a similar secure location and are **never committed to this git repo**.

