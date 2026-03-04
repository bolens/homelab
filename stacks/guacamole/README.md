# Apache Guacamole

Clientless remote desktop gateway for **RDP**, **VNC**, and **SSH** accessible entirely through a modern HTML5 web browser—no client software required. Once deployed, you reach all your configured desktops and servers via a single Guacamole web UI.

**Website:** https://guacamole.apache.org/  
**Docs:** https://guacamole.apache.org/doc/gug/  
**GitHub:** https://github.com/apache/guacamole-client  
**Docker image:** https://hub.docker.com/r/guacamole/guacamole  
**Releases:** https://guacamole.apache.org/release-notes/  

## Quick start

1. **Copy env template**:

   ```bash
   cp stack.env.example stack.env
   ```

2. **Set database password** in `stack.env` (required):

   ```bash
   # Strong random password for the Guacamole Postgres database
   POSTGRES_PASSWORD=REPLACE_WITH_GENERATED_PASSWORD

   # Example generator (run on your machine, do NOT commit output):
   openssl rand -hex 32
   ```

   You can leave `POSTGRES_DB` and `POSTGRES_USER` at their defaults unless you need to change them.

3. **(Optional) Set timezone** in `stack.env`:

   ```bash
   TZ=America/Denver
   ```

4. **Deploy:**

   From this directory:

   ```bash
   docker compose up -d
   ```

   The compose file already uses `env_file: [stack.env]`, so `docker compose up -d` is sufficient after you create `stack.env`. You can also run:

   ```bash
   docker compose --env-file stack.env up -d
   ```

5. **Access via Caddy** at your chosen hostname (for example, `https://guacamole.bolens.dev`). See the Caddy example below.

## Configuration

| Item        | Details |
|------------|---------|
| **Access** | Via Caddy only (no host ports; reverse proxy to `guacamole:8080`) |
| **Network** | Internal `guacamole` network for app + Postgres + guacd, plus external `monitor` network so Caddy can reach the web UI |
| **Images** | `guacamole/guacd:1.6.0`, `guacamole/guacamole:1.6.0`, and `postgres:16-alpine` |
| **Storage** | Named volume `guacamole_pg_data` for the Postgres database (users, connections, permissions) |
| **Auth** | By default, users and connections are stored in the Guacamole database; you can add LDAP/OIDC/etc. later via Guacamole extensions if desired (see upstream docs) |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED example hostnames):

```
guacamole.home, guacamole.local {
  tls internal
  reverse_proxy guacamole:8080
}
```

In your real setup, use the hostname you expose via Cloudflare Tunnel and DNS (for example `guacamole.bolens.dev`) and keep the `guacamole` service on the `monitor` network so Caddy can resolve it.

## Start

From this directory:

- **With env file:** `docker compose --env-file stack.env up -d`  
- **Without env file:** `docker compose up -d` (uses default timezone and built‑in database defaults)

