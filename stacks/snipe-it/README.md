# Snipe-IT

IT asset management (hardware, software licenses, accessories, consumables). This stack runs Snipe-IT with a MariaDB backend and exposes the web UI via Caddy.

**Website:** https://snipeitapp.com/  
**Docs:** https://snipe-it.readme.io/  
**Docker image:** https://hub.docker.com/r/snipe/snipe-it  
**GitHub:** https://github.com/snipe/snipe-it  

## Quick start

1. From this directory, copy `stack.env.example` → `stack.env`.
2. Generate secrets and fill placeholders:

   ```bash
   # On your host (do NOT commit outputs)
   openssl rand -base64 32   # for APP_KEY
   openssl rand -hex 16      # for DB passwords
   ```

   - Set `APP_KEY` to a strong random value.
   - Set `DB_PASSWORD` and `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD` in `stack.env` (and/or override defaults in the compose file).

3. Start the stack:

   ```bash
   docker compose up -d
   ```

4. Expose Snipe-IT via Caddy (e.g. `https://snipe-it.yourdomain.com`) using the example site block in the Caddyfile; internally it listens on port `80`.
5. Complete the web-based installer and create the first admin user.

## Configuration

| Item        | Details                                                                                  |
| ----------- | ---------------------------------------------------------------------------------------- |
| **Access**  | Via Caddy only (no host port; reverse-proxy to `snipeit:80`)                            |
| **Volumes** | `snipeit_storage` (uploads, storage), `snipeit_db` (MariaDB data)                        |
| **Network** | `monitor` — shared with Caddy and other app stacks                                      |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale and Snipe-IT settings |

### SMTP

For outbound email (password resets, notifications), use the shared Postfix relay. In `stack.env`:

- `MAIL_HOST=smtp-relay` (container name on `monitor` network)
- `MAIL_PORT=587`
- `MAIL_ENCRYPTION=tls`
- `MAIL_USERNAME` / `MAIL_PASSWORD` — leave empty for the internal relay (no auth)
- `MAIL_FROM_ADDR` / `MAIL_FROM_NAME` — set to match `ALLOWED_SENDER_DOMAINS` in Postfix

For **internal-only** (Mailpit): deploy [stacks/postfix](postfix/README.md) and [stacks/mailpit](mailpit/README.md) with `RELAYHOST=mailpit:1025`. All emails appear in Mailpit’s web UI; none are delivered externally. See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) and [stacks/postfix/README.md](postfix/README.md).

