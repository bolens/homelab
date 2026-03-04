# SimpleLogin

Email alias service: create unlimited aliases (e.g. `shop@yourdomain.com`) that forward to your real inbox. Reply anonymously, block spam per alias, integrate with Bitwarden/1Password. Self-hosted fork of the Proton-owned SimpleLogin app.

**Website:** https://simplelogin.io  
**Docs:** https://simplelogin.io/docs  
**GitHub:** https://github.com/simple-login/app  
**Docker image:** https://hub.docker.com/r/simplelogin/app  
**Releases:** https://github.com/simple-login/app/releases  

## Quick start

1. **Prepare DKIM key** (required for signing outgoing mail):
   ```bash
   mkdir -p data
   openssl genrsa -traditional -out data/dkim.key 1024
   chmod 600 data/dkim.key
   ```
   Add the corresponding public key to DNS as `dkim._domainkey.${EMAIL_DOMAIN}` (see [SimpleLogin docs](https://github.com/simple-login/app#dkim)).

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

4. **Deploy:** `docker compose up -d` (or add stack in Portainer and set env vars in the stack Environment).

5. **Access:** Open via Caddy (e.g. https://simplelogin.home). Create your first account. To grant premium (unlimited aliases):  
   `docker exec -it simplelogin-db psql -U simplelogin simplelogin -c "UPDATE users SET lifetime = TRUE;"`

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `simplelogin:7777`) |
| **Network** | `simplelogin` (internal: app, db, email-handler, job-runner); `monitor` (Caddy → web app) |
| **Image** | `simplelogin/app:latest` (pin a tag for production) |
| **Env** | Uses `environment:` with `${VAR}` substitution (Portainer-compatible; no `env_file`) |
| **Storage** | Named volumes: `simplelogin-data` (/sl), `simplelogin-upload`, `simplelogin-pg-data`. DKIM key: `./data/dkim.key` (bind mount) |

## Sending mail (outbound)

To send transactional and forwarding emails via your existing relay (e.g. the `postfix` stack):

- Set `POSTFIX_SERVER=smtp-relay` (or the hostname of your SMTP relay on the same Docker network).
- Set `POSTFIX_PORT=587` if your relay listens on 587 (e.g. boky/postfix submission).

Ensure the relay allows the `EMAIL_DOMAIN` / `SUPPORT_EMAIL` domain in `ALLOWED_SENDER_DOMAINS` (see postfix stack README).

## Receiving mail (inbound)

Receiving mail for aliases (MX → your server) requires an MTA (e.g. Postfix) that accepts mail for `EMAIL_DOMAIN` and delivers to the **email handler** container. The handler listens on port **20381** inside the `simplelogin` network. This stack does not include that MTA; you need to:

- Point MX for `EMAIL_DOMAIN` to the host that runs the MTA.
- Configure the MTA to deliver to `simplelogin-email:20381` (when the MTA runs in Docker on the same network) or to the host’s published 20381 port if the MTA is on the host.

See [SimpleLogin self-hosting](https://github.com/simple-login/app#run-simplelogin-docker-containers) for Postfix relay/transport maps and DNS (SPF, DKIM, DMARC).

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

From this directory: `docker compose up -d`.  
In Portainer: Stacks → Add stack → paste the compose, set required env vars in **Environment**, deploy.
