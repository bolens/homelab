#! Mailpit

Local **SMTP catcher** for development and testing. Receives all mail on port 1025 and displays it in a web UI (port 8025). No external delivery—ideal for internal-only mailing when combined with the Postfix relay.

**Website:** https://mailpit.axllent.org  
**Docs:** https://mailpit.axllent.org/docs/  
**GitHub:** https://github.com/axllent/mailpit  
**Docker image:** https://hub.docker.com/r/axllent/mailpit  

## Quick start

1. **Deploy:** `docker compose up -d` (from this directory).
2. **Use with Postfix:** In `stacks/postfix/stack.env`, set `RELAYHOST=mailpit:1025` for internal-only mode. Restart the postfix stack.
3. **View mail:** Open `https://mailpit.yourdomain.com` (via Caddy; replace with your hostname).

Mailpit and Postfix share `mail-services`. Mailpit also joins `proxy-ingress` for its web UI. Apps send to `smtp-relay:587`; Postfix relays to Mailpit; Mailpit catches everything.

## Configuration

| Item | Details |
|------|---------|
| **SMTP** | Port 1025 (no auth, no TLS) |
| **Web UI** | Port 8025 (behind Caddy at `mailpit.yourdomain.com`) |
| **Network** | `mail-services` for SMTP; `proxy-ingress` for the web UI |
| **Image** | `axllent/mailpit:latest` |

No host ports by default; access via Caddy for the web UI and via Docker network for SMTP.

## Dependencies

- **Postfix:** For internal-only mode, deploy both Mailpit and Postfix. Set Postfix `RELAYHOST=mailpit:1025`. See [stacks/postfix/README.md](../postfix/README.md#internal-only-mailing-mailpit).
