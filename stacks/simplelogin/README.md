# SimpleLogin

Email alias service: create unlimited aliases (e.g. `shop@yourdomain.com`) that forward to your real inbox. Reply anonymously, block spam per alias, integrate with Bitwarden/1Password. Self-hosted fork of the Proton-owned SimpleLogin app.

**Website:** https://simplelogin.io  
**Docs:** https://simplelogin.io/docs  
**GitHub:** https://github.com/simple-login/app  
**Docker image:** https://hub.docker.com/r/simplelogin/app  
**Releases:** https://github.com/simple-login/app/releases  

## Quick start

1. **Prepare DKIM keys** (required for signing outgoing mail):
   ```bash
   mkdir -p data
   openssl genrsa -traditional -out data/dkim.key 1024
   chmod 600 data/dkim.key
   openssl rsa -in data/dkim.key -pubout -out data/dkim.pub
   ```
   Add the public key to DNS as `dkim._domainkey.${EMAIL_DOMAIN}` (see [SimpleLogin docs](https://github.com/simple-login/app#dkim)).

2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `URL` (e.g. `https://simplelogin.home` or `https://simplelogin.yourdomain.com`).
   - Set `EMAIL_DOMAIN`, `EMAIL_SERVERS_WITH_PRIORITY`, `SUPPORT_EMAIL`.
   - Set `FLASK_SECRET`: `openssl rand -hex 32`
   - Set `POSTGRES_PASSWORD`.

3. **First-time: migration and init**
   ```bash
   docker compose run --rm simplelogin flask db upgrade
   docker compose run --rm simplelogin python init_app.py
   ```

4. **Deploy:** `docker compose --env-file stack.env up -d` (env vars must be available at compose parse time). In Portainer: add the stack and set env vars in **Environment**.

5. **Access:** Open via Caddy (e.g. https://simplelogin.home). Create your first account. To grant premium (unlimited aliases):  
   `docker exec -it simplelogin-db psql -U simplelogin simplelogin -c "UPDATE users SET lifetime = TRUE;"`

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `simplelogin:7777`) |
| **Network** | `simplelogin` (internal: app, db, email-handler, job-runner); `monitor` (Caddy → web app) |
| **Image** | `simplelogin/app:latest` (pin a tag for production) |
| **Env** | `env_file: stack.env` + `environment:` with `${VAR}` substitution. Run with `--env-file stack.env` so vars are available at parse time. |
| **Storage** | Named volumes: `simplelogin-data` (/sl), `simplelogin-upload`, `simplelogin-pg-data`. DKIM: `./data/dkim.key`, `./data/dkim.pub` (bind mounts) |

## Sending mail (outbound)

To send transactional and forwarding emails via the shared relay, set:

- `POSTFIX_SERVER=smtp-relay` (container name on `monitor` network)
- `POSTFIX_PORT=587`

Ensure the relay allows the `EMAIL_DOMAIN` / `SUPPORT_EMAIL` domain in `ALLOWED_SENDER_DOMAINS` (see [stacks/postfix/README.md](../postfix/README.md)).

For **internal-only** (Mailpit): deploy [stacks/postfix](../postfix/README.md) and [stacks/mailpit](../mailpit/README.md) with `RELAYHOST=mailpit:1025`. All emails appear in Mailpit’s web UI; none are delivered externally. See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

## Receiving mail (inbound)

Receiving mail for aliases (MX → your server) requires an MTA (e.g. Postfix) that accepts mail for `EMAIL_DOMAIN` (and any `OTHER_ALIAS_DOMAINS`) and delivers to the **email handler** container. The handler listens on port **20381** inside the `simplelogin` network. This stack does not include that MTA; you need to:

- Point MX for `EMAIL_DOMAIN` to the host that runs the MTA.
- Configure the MTA to deliver to `simplelogin-email:20381` (when the MTA runs in Docker on the same network) or to the host’s published 20381 port if the MTA is on the host.

See [SimpleLogin self-hosting](https://github.com/simple-login/app#run-simplelogin-docker-containers) for Postfix relay/transport maps and DNS (SPF, DKIM, DMARC).

## Multiple alias domains

To allow aliases on more than one domain, set `OTHER_ALIAS_DOMAINS` in `stack.env`:

```
OTHER_ALIAS_DOMAINS=["otherdomain.com"]
```

Users can then create aliases like `shop@EMAIL_DOMAIN` and `shop@otherdomain.com`. Each domain needs MX records pointing to your mail receiver (same as `EMAIL_DOMAIN`).

## Caddy reverse proxy

Example Caddy vhost (e.g. in your Caddyfile):

```
simplelogin.home, simplelogin.local {
  tls internal
  reverse_proxy simplelogin:7777
}
```

Ensure the stack is on the `monitor` network so Caddy can reach `simplelogin:7777`.

## Start

From this directory: `docker compose --env-file stack.env up -d`.  
In Portainer: Stacks → Add stack → paste the compose, set required env vars in **Environment**, deploy.
