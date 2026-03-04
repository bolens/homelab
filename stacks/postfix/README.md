#! SMTP relay

Central **SMTP relay ("null client")** for your Docker stacks, based on [`boky/postfix`](https://github.com/bokysan/docker-postfix).  
Apps send mail to this container; it then relays via your real mail provider (SES, Mailgun, SMTP relay from your ISP, etc.).

**Website:** https://github.com/bokysan/docker-postfix  
**Docs:** https://github.com/bokysan/docker-postfix#readme  
**GitHub:** https://github.com/bokysan/docker-postfix  
**Docker image:** https://hub.docker.com/r/boky/postfix  
**Releases:** https://github.com/bokysan/docker-postfix/releases  

> This relay is for **outgoing mail from apps only**. It is not a full mailserver for end‑user inboxes.

## Quick start

1. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set at least:
     - `ALLOWED_SENDER_DOMAINS` (e.g. `yourdomain.com`).
     - `RELAYHOST` (e.g. `smtp.sendgrid.net:587` or `email-smtp.us-west-2.amazonaws.com:587`).
     - Optionally `RELAYHOST_USERNAME` / `RELAYHOST_PASSWORD` if your provider requires auth.
2. **Deploy:** `docker compose up -d` (from this directory), or add as a stack in Portainer and set the same vars in the stack **Environment**.
3. **Use from apps:**
   - Inside Docker (same `monitor` network): `smtp-relay:587`.
   - From outside / other hosts: `smtp.yourdomain.com:587` (see **Public access** below).

The stack uses the shared `monitor` network so other stacks (Infisical, Password Pusher, Linkwarden, etc.) can reach the relay by container name.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Internal only by default (no host port). Other stacks use `smtp-relay:587` on the `monitor` network. |
| **Network** | `monitor` (external) — shared with Caddy and app stacks. |
| **Image** | `boky/postfix:latest` |
| **Env** | `ALLOWED_SENDER_DOMAINS` (recommended), `RELAYHOST` (required), optional `RELAYHOST_USERNAME`, `RELAYHOST_PASSWORD`, `POSTFIX_myhostname`, `POSTFIX_message_size_limit`, `TZ`. See `stack.env.example` and upstream docs. |

### Example: Password Pusher

In `stacks/password-pusher/.env` (or Portainer stack Environment), point Password Pusher at the relay:

- For apps on the same Docker host (recommended):
  - `PWP__MAIL__SMTP_ADDRESS=smtp-relay`
  - `PWP__MAIL__SMTP_PORT=587`
  - `PWP__MAIL__SMTP_STARTTLS=true` (or `false` if you relay over plain TCP inside Docker and let the relay do TLS to the provider)

- From outside Docker (or if you want a single hostname everywhere):
  - `PWP__MAIL__SMTP_ADDRESS=smtp.yourdomain.com`
  - `PWP__MAIL__SMTP_PORT=587`

### Example: Infisical

In `stacks/infisical/.env` (or Portainer Environment):

- `SMTP_HOST=smtp-relay` (or `smtp.yourdomain.com` if you prefer the public hostname)
- `SMTP_PORT=587`
- `SMTP_FROM_ADDRESS=noreply@yourdomain.com`
- `SMTP_FROM_NAME=Infisical`

## Public access (`smtp.yourdomain.com`)

The relay itself is **not HTTP**; Caddy cannot proxy SMTP the same way it proxies web apps. Recommended approach:

- **Cloudflare Tunnel:** add a **Public Hostname** `smtp.yourdomain.com` with service `tcp://smtp-relay:587` (or `tcp://localhost:587` if you map the port on the host).
- **Direct port forward:** map port `587` on your router to the Docker host and map `587` on the host to the container if needed.

This stack does **not** publish any host ports by default so that Caddy / Cloudflare Tunnel (or your router) can control exposure.

When you hit `https://smtp.yourdomain.com` in a browser, Caddy will just return a simple message; SMTP clients must use port `587`.

## Caddy / DNS

- **DNS:** create `smtp.yourdomain.com` in Cloudflare pointing at your tunnel or host as you do for other services.
- **Caddy:** the `Caddyfile` defines `smtp.yourdomain.com` so:
  - HTTP (`:80`) host routing still works from the tunnel.
  - HTTPS certificates are issued via Cloudflare DNS for `smtp.yourdomain.com`.

There is no HTTP reverse proxy for the relay itself; apps talk SMTP directly to port `587`.

