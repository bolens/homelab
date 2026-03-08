# Apache Guacamole

Clientless remote desktop gateway for **RDP**, **VNC**, and **SSH** accessible entirely through a modern HTML5 web browser—no client software required. Once deployed, you reach all your configured desktops and servers via a single Guacamole web UI.

**Website:** https://guacamole.apache.org/  
**Docs:** https://guacamole.apache.org/doc/gug/  
**GitHub:** https://github.com/apache/guacamole-client  
**Docker image:** https://hub.docker.com/r/guacamole/guacamole  
**Releases:** https://guacamole.apache.org/release-notes/  

## Quick start

1. **Config and env:** Run `./prepare-stack.sh` (creates `stack.env` from example and `~/.config/guacamole/guacamole.properties` from `guacamole.properties.example`). Or copy `stack.env.example` → `stack.env` and copy `guacamole.properties.example` to `~/.config/guacamole/guacamole.properties` (create the directory if needed).

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

5. **Initialize the database** (once, before first login). This creates the schema and the default user `guacadmin` / `guacadmin`:

   ```bash
   docker run --rm guacamole/guacamole:1.6.0 /opt/guacamole/bin/initdb.sh --postgresql | docker exec -i guacamole-postgres psql -U guacamole -d guacamole_db -f -
   ```

   **Change the default password** after first login (Settings → Preferences → Password).

6. **Access via Caddy** at your chosen hostname (e.g. `https://guacamole.yourdomain.com`). See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `guacamole.yourdomain.com` → `guacamole:8080`.

## Configuration

| Item        | Details |
|------------|---------|
| **Access** | Via Caddy only (no host ports; reverse proxy to `guacamole:8080`) |
| **Network** | Internal `guacamole` network for app + Postgres + guacd, plus external `monitor` network so Caddy can reach the web UI |
| **Images** | `guacamole/guacd:1.6.0`, `guacamole/guacamole:1.6.0`, and `postgres:16-alpine` |
| **Storage** | Named volume `guacamole_pg_data` for the Postgres database (users, connections, permissions) |
| **Auth** | By default, users and connections are stored in the Guacamole database; you can add LDAP/OIDC/etc. later via Guacamole extensions if desired (see upstream docs) |

## Caddy

| **Caddy** | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `guacamole.yourdomain.com` → `guacamole:8080`, plus local blocks `guacamole.home` / `guacamole.local`. |

## Start

From this directory:

- **Default:** `docker compose up -d` (compose already loads `../../shared.env` and `stack.env` via `env_file`)
- **Explicit env files:** `docker compose --env-file ../../shared.env --env-file stack.env up -d` (e.g. from repo root)
- **Without stack.env:** `docker compose up -d` will fail until `stack.env` exists with `POSTGRES_PASSWORD` set

## Troubleshooting

### Invalid login for guacadmin / guacadmin

If the default login fails after init, reset the stored password to the canonical hash:

```bash
docker exec -i guacamole-postgres psql -U guacamole -d guacamole_db <<'SQL'
-- Reset guacadmin password to "guacadmin" (canonical hash from 002-create-admin-user.sql)
UPDATE guacamole_user
SET
  password_hash = decode('CA458A7D494E3BE824F5E1E175A1556C0F8EEF2C2D7DF3633BEC4A29C4411960', 'hex'),
  password_salt = decode('FE24ADC5E11E2B25288D1704ABE67A79E342ECC26064CE69C5B3177795A82264', 'hex'),
  password_date = CURRENT_TIMESTAMP
FROM guacamole_entity
WHERE guacamole_entity.entity_id = guacamole_user.entity_id
  AND guacamole_entity.name = 'guacadmin';
SQL
```

Then try logging in again with **guacadmin** / **guacadmin** and change the password in the UI.

