# CrowdSec (Security Engine)

CrowdSec is a collaborative, open-source intrusion prevention system. It analyzes logs from your services, detects aggressive IPs and known attack patterns, and uses curated blocklists and community telemetry to help you block malicious traffic before it reaches your apps.

This stack runs the **CrowdSec Security Engine** in a container with persistent data volumes. It is designed to be a central decision engine that you can later pair with one or more **bouncers** (firewall, reverse proxy, CDN, etc.).

**Website:** https://www.crowdsec.net/  
**Docs:** https://docs.crowdsec.net/  
**GitHub:** https://github.com/crowdsecurity/crowdsec  
**Docker image:** https://hub.docker.com/r/crowdsecurity/crowdsec  
**Releases:** https://github.com/crowdsecurity/crowdsec/releases  

## Quick start

1. **Prepare** (creates `stack.env` from template if missing):

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

2. **(Optional)** Edit `stack.env` to set `TZ`, `GID`, or `COLLECTIONS` (e.g. `crowdsecurity/linux`, `crowdsecurity/caddy`).

3. **Deploy:**

   ```bash
   docker compose up -d
   ```

4. **Verify** the engine is running:

   ```bash
   docker compose logs -f crowdsec
   ```

   You should see the engine starting, hub sync, and loaded parsers/scenarios.

5. **LAPI** – no host port; Caddy is the single entrypoint. Reach it at:

   - **From browser / host:** `https://crowdsec.home` or `https://crowdsec.yourdomain.com` (ensure the host resolves the name, e.g. via AdGuard or `/etc/hosts`).
   - **From containers on `monitor`:** `http://crowdsec:8080` (Prometheus, bouncers, cscli in Docker).

   Example (from host, if crowdsec.home resolves): `curl https://crowdsec.home/metrics`

   Protect the public hostname with Cloudflare Access or keep it internal-only; LAPI has no built-in auth.

## Configuration

| Item        | Details |
|------------|---------|
| **Access** | Via Caddy only (no host port). Internal: `https://crowdsec.home`; public: `https://crowdsec.yourdomain.com`. Other containers on `monitor`: `http://crowdsec:8080`. |
| **Network** | `monitor` (external) so Caddy and Prometheus reach `crowdsec:8080`. |
| **Storage** | Named volumes: `crowdsec-config` for `/etc/crowdsec` (hub, parsers, scenarios, profiles) and `crowdsec-data` for `/var/lib/crowdsec/data`. The data volume is **required** for CrowdSec 1.7+ to start. |
| **Logs**   | This stack does **not** hardcode any log mounts. You decide which logs to feed to CrowdSec (Docker containers, Caddy logs, system logs, etc.) and configure acquisitions accordingly. |

The compose file also mounts `/var/run/docker.sock` read-only into the container so you can use the **Docker data source** if desired. You still need to configure acquisitions for Docker in CrowdSec (`acquis.yaml` or `cscli`), as described in the official docs.

## Config file (acquis)

CrowdSec reads **log acquisition** config from `acquis.yaml` on the host, mounted into the container (same pattern as the Prometheus stack’s config file).

- **Default path:** `~/.config/crowdsec/acquis.yaml`  
  Run `./prepare-stack.sh` once: it creates that directory and copies `acquis.yaml.example` there if the file doesn’t exist.
- **Override:** set `CROWDSEC_ACQUIS_PATH` in `stack.env` to the full path to your acquis file (e.g. `/home/youruser/.config/crowdsec/acquis.yaml`).  
  **Portainer:** you must set `CROWDSEC_ACQUIS_PATH` to the **absolute** path to the acquis file on the host, because `$HOME` is not available in that context.
- Edit the acquis file to add or remove log sources (Docker containers, file paths, etc.), then restart CrowdSec.

The repo provides `acquis.yaml.example` with example Docker sources (Caddy, smtp-relay). Copy it to your config path and adjust container names and labels to match your stacks.

## Feeding logs into CrowdSec

CrowdSec only becomes effective once it can analyze logs from your services. Common patterns in a homelab:

- **Reverse proxy logs** (Caddy, Traefik, NGINX).  
- **SSH / system logs** from the Docker host.  
- **Application logs** for internet-exposed services.

How you wire logs in is up to you and your logging setup. The upstream docs cover several options:

- Bind-mount specific log directories from the host into the container (e.g. `/var/log/…`).  
- Use the Docker data source to watch container logs via the Docker API.  
- Forward logs from syslog/journald to files or a central log collector that CrowdSec can read.

See:

- Docker installation guide: https://docs.crowdsec.net/u/getting_started/installation/docker/  
- Docker data source: https://docs.crowdsec.net/docs/next/log_processor/data_sources/docker  

In all cases, ensure the user/group CrowdSec runs as can read the relevant log files (use `GID` and volume permissions accordingly).

## Hub collections and scenarios

By default this stack sets:

- `COLLECTIONS=${COLLECTIONS:-crowdsecurity/linux}`

in `docker-compose.yml`. You can override `COLLECTIONS` in `stack.env` to pull in collections that match your environment (for example, Caddy or web application stacks).

To manage the hub from inside the container:

```bash
docker compose exec crowdsec cscli hub list
docker compose exec crowdsec cscli hub update
docker compose exec crowdsec cscli collections install crowdsecurity/linux
docker compose exec crowdsec cscli collections install crowdsecurity/ssh
```

The commands above are SANITIZED examples; pick collections that correspond to the services you actually run and the logs you feed into CrowdSec.

## Bouncers (firewalls, reverse proxies, CDN)

This stack only runs the **engine** and Local API. To actually block malicious IPs, you need one or more **bouncers** that query LAPI and enforce decisions:

- **Host / firewall bouncer** (e.g. iptables, nftables).  
- **Reverse proxy bouncer** (for Caddy, NGINX, etc.).  
- **CDN / WAF integration** using CrowdSec blocklists and curated threat intelligence (for example, feeding CrowdSec blocklists into an edge firewall or CDN).

Bouncers on the Docker host use the Caddy URL (e.g. `https://crowdsec.home`); bouncers in Docker on the `monitor` network use `http://crowdsec:8080`. Refer to CrowdSec official bouncer documentation for setup details.

For **Cloudflare edge protection**, use the **Cloudflare Workers bouncer** so CrowdSec decisions are enforced as Cloudflare firewall actions. See `documents/CROWDSEC-CLOUDFLARE-WORKER.md` in this repo for a step‑by‑step setup guide (daemon mode on the host, tokens and keys stored only under `/etc/crowdsec/bouncers/`).

## Exposure, SSO, and Caddy

- LAPI is exposed **only via Caddy** (no host port): `https://crowdsec.home` / `https://crowdsec.yourdomain.com`.
- Protect the public hostname with **Cloudflare Access** or keep it internal-only; LAPI has no built-in auth.
- Containers on the `monitor` network (e.g. Prometheus, bouncers) use `http://crowdsec:8080` directly.

## Portainer

Stacks → Add stack → **Repository** → Compose path `stacks/crowdsec/docker-compose.yml`. Add env vars from `stack.env.example` if needed. Set **`CROWDSEC_ACQUIS_PATH`** to the **absolute path** to your `acquis.yaml` on the host (e.g. `/home/youruser/.config/crowdsec/acquis.yaml`), since the default uses `$HOME` which is not set in Portainer’s environment. Deploy; LAPI is reached via Caddy (https://crowdsec.yourdomain.com or your internal hostname) or from containers on the same Docker network at `http://crowdsec:8080`.

## References

- CrowdSec product overview: https://www.crowdsec.net/  
- CrowdSec Docker install docs: https://docs.crowdsec.net/u/getting_started/installation/docker/  
- Docker data source docs: https://docs.crowdsec.net/docs/next/log_processor/data_sources/docker  

