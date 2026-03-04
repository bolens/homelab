# CrowdSec (Security Engine)

CrowdSec is a collaborative, open-source intrusion prevention system. It analyzes logs from your services, detects aggressive IPs and known attack patterns, and uses curated blocklists and community telemetry to help you block malicious traffic before it reaches your apps.

This stack runs the **CrowdSec Security Engine** in a container with persistent data volumes. It is designed to be a central decision engine that you can later pair with one or more **bouncers** (firewall, reverse proxy, CDN, etc.).

**Website:** https://www.crowdsec.net/  
**Docker install docs:** https://docs.crowdsec.net/u/getting_started/installation/docker/  
**Hub (collections, parsers, scenarios):** https://docs.crowdsec.net/docs/next/hub/overview  

## Quick start

1. **Copy env template** (optional):

   ```bash
   cp stack.env.example stack.env
   ```

2. **(Optional) Set timezone and hub collections** in `stack.env`:

   ```bash
   # Example only – adjust to your environment
   TZ=America/Denver
   GID=1000
   COLLECTIONS="crowdsecurity/linux"
   ```

3. **Deploy CrowdSec:**

   From this directory:

   ```bash
   docker compose up -d
   ```

   The compose file already uses `env_file: [stack.env]`, so `docker compose up -d` is sufficient after you create `stack.env`. You can also run:

   ```bash
   docker compose --env-file stack.env up -d
   ```

4. **Verify the engine is running:**

   ```bash
   docker compose logs -f crowdsec
   ```

   You should see the engine starting, hub sync, and information about loaded parsers and scenarios.

5. **Access the Local API (LAPI) from the host** (for `cscli` or bouncers on the host):

   The stack binds CrowdSec’s Local API port to `127.0.0.1:8080` on the host. From the **Docker host**, you can access it at:

   ```bash
   curl http://127.0.0.1:8080/metrics
   ```

   or configure bouncers to talk to `http://127.0.0.1:8080/` (SANITIZED example URL).

## Configuration

| Item        | Details |
|------------|---------|
| **Access** | No public HTTP UI. Only the Local API (LAPI) on `127.0.0.1:8080` is exposed on the host for bouncers and tooling. This stack is **not** behind Caddy and is not meant to be exposed on the Internet. |
| **Network** | Default per-stack Docker network (no `monitor` network needed, since there is no web UI). Other containers that need to talk to LAPI can be attached to this stack’s network or use the host loopback binding. |
| **Image**  | `crowdsecurity/crowdsec` (see Docker install docs for supported tags). |
| **Storage** | Named volumes: `crowdsec-config` for `/etc/crowdsec` (hub, parsers, scenarios, profiles) and `crowdsec-data` for `/var/lib/crowdsec/data`. The data volume is **required** for CrowdSec 1.7+ to start. |
| **Logs**   | This stack does **not** hardcode any log mounts. You decide which logs to feed to CrowdSec (Docker containers, Caddy logs, system logs, etc.) and configure acquisitions accordingly. |

The compose file also mounts `/var/run/docker.sock` read-only into the container so you can use the **Docker data source** if desired. You still need to configure acquisitions for Docker in CrowdSec (`acquis.yaml` or `cscli`), as described in the official docs.

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

The `http://127.0.0.1:8080/` binding is intended for such bouncers running on the Docker host or on the same Docker network. Refer to CrowdSec’s official bouncer documentation for setup details for each environment.

## Exposure, SSO, and Caddy

- This stack **does not expose a web UI** and does not have a hostname like `crowdsec.yourdomain.com`.  
- There is no need to wire CrowdSec through Caddy or Cloudflare Access; the Local API is meant for internal bouncers and admin tooling only.  
- If you later deploy a dashboard or UI that talks to CrowdSec (for example, a metrics dashboard), treat that separately and keep CrowdSec’s LAPI internal-only.

## References

- CrowdSec product overview: https://www.crowdsec.net/  
- CrowdSec Docker install docs: https://docs.crowdsec.net/u/getting_started/installation/docker/  
- Docker data source docs: https://docs.crowdsec.net/docs/next/log_processor/data_sources/docker  

