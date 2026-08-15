# n8n

Workflow automation: connect apps, APIs, and services with a visual editor. Self-hosted alternative to Zapier/Make. Uses SQLite by default (data in Docker volume); optional Postgres for scaling.

**Website:** https://n8n.io  
**Docs:** https://docs.n8n.io/  
**GitHub:** https://github.com/n8n-io/n8n  
**Docker image:** https://hub.docker.com/r/n8nio/n8n  
**Releases:** https://github.com/n8n-io/n8n/releases  

## Quick start

1. Ensure `ingress-public`, `mail-clients`, `telemetry`, and
   `media-automation` exist (or run `./prepare-stack.sh`).
2. Copy `stack.env.example` to `stack.env`, set **N8N_HOST** and
   **WEBHOOK_URL** to the URL where you’ll reach n8n behind Caddy, and set a
   random **N8N_RESTART_GATEWAY_TOKEN**. Both URL variables must match your
   Caddy hostname.
3. Start: `docker compose up -d` from this directory (or deploy as stack in Portainer).
4. Open the URL above; create the owner account on first visit.

## Portainer

The stack is Portainer-friendly with env defaults for TZ/locale, `ingress-public` for Caddy, and `mail-clients` for SMTP. Set **N8N_HOST** and **WEBHOOK_URL** in the stack Environment (e.g. `https://n8n.yourdomain.com`).

## Configuration

| Item | Details |
|------|---------|
| **Ports** | None; access only via Caddy (`reverse_proxy n8n:5678` on `ingress-public`). |
| **Volumes** | `n8n_data` → `/home/node/.n8n` (SQLite DB, encryption key, workflows). Back this up. |
| **Network** | `ingress-public` for Caddy; `mail-clients` for SMTP; `telemetry` for ntfy; `media-automation` for starter health checks; private `docker-control` for the restart gateway. |
| **Env** | **N8N_HOST** and **WEBHOOK_URL** required when behind Caddy. Optional: `N8N_ENCRYPTION_KEY` (e.g. `openssl rand -hex 32`) so credentials survive volume recreation. For TZ/locale and shared resources (e.g. SMTP relay), see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md) and [ENV-VARS.md](../../documents/ENV-VARS.md). |

## Health monitoring with restart approval

The importable
[`workflows/uptime-kuma-restart-approval.json`](workflows/uptime-kuma-restart-approval.json)
implements this operator-controlled path:

```text
Uptime Kuma DOWN webhook -> validate mapping/cooldown -> ntfy approval
  -> expiring n8n Wait URL -> restart-only gateway -> recovery probe -> ntfy result
```

The starter mapping covers Sonarr, Radarr, Prowlarr, and Bazarr. These are
stateless application processes with existing HTTP checks and are lower-risk
first targets than databases, storage, ingress, download clients, n8n, Uptime
Kuma, or ntfy. A restart is never automatic: the workflow waits up to 15
minutes for an ntfy action and suppresses duplicate requests for 30 minutes.

### Security model

n8n does **not** mount the Docker socket. The `restart-gateway` companion is
the only service with socket access and exposes only `POST /v1/restart` on the
private `docker-control` network. It requires a bearer token and rejects any
container absent from `N8N_RESTART_ALLOWLIST`. The gateway cannot be reached
through Caddy and is not published on a host port.

Docker socket access is still security-sensitive: a bug in the gateway could
affect the host. Keep the allowlist small, do not place other containers on
`docker-control`, and do not add infrastructure or stateful services without a
specific recovery runbook.

The private `docker-control` network uses `10.250.5.0/28` explicitly so it can
be created even when Docker's automatic bridge address pools are exhausted.
Keep that subnet aligned with the host's Docker network plan and do not reuse
it for another network.

### Install the workflow

1. Generate a gateway token and put it only in the uncommitted `stack.env`:

   ```bash
   openssl rand -hex 32
   ```

2. Set `N8N_RESTART_ALLOWLIST`. Container names must match exactly. Deploy or
   recreate the n8n stack only when you are ready; repository validation does
   not perform this operational step.
3. In n8n, create an **HTTP Header Auth** credential named
   `Restart Gateway Bearer`:
   - Name: `Authorization`
   - Value: `Bearer <the same N8N_RESTART_GATEWAY_TOKEN>`
4. Import the workflow JSON. Open **Restart allowlisted container** and select
   the credential created above.
5. Open **Configure and validate event**. Change the ntfy topic if desired.
   Monitor-map keys must equal the lowercase Uptime Kuma monitor names.
6. Activate the workflow, then copy the production URL from **Uptime Kuma
   webhook**. Do not use n8n's temporary test URL.
7. In Uptime Kuma, create a Webhook notification pointed at that production
   URL, use `POST` with JSON, and assign it to the mapped monitors. Send a test
   notification before enabling failure notifications.
8. Subscribe to the configured topic (`homelab-approvals` by default) in the
   ntfy app. Approval buttons must be able to reach `WEBHOOK_URL`; use a URL
   reachable from the phone, normally through the same authenticated ingress
   used for n8n.

If ntfy requires authentication, add authentication to both ntfy HTTP Request
nodes after import. Do not embed its token in the workflow JSON.

### Add another restart target

All three controls must agree; otherwise the request is rejected or recovery
checking is misleading:

1. Add the exact Docker container name to `N8N_RESTART_ALLOWLIST`.
2. Add a monitor mapping in **Configure and validate event**, including a URL
   n8n can reach.
3. If using an internal container URL, attach n8n to that service's existing
   network in Compose and update `prepare-stack.sh`, `stack.yaml`, and this
   README. Prefer an existing narrow network over a new shared network.

Never add `n8n`, `n8n-restart-gateway`, `caddy`, `ntfy`, `uptime-kuma`, a
database, a storage service, or a container whose restart could interrupt an
active write. For those systems, use a service-specific recovery workflow.

### Triage and audit

Start with the n8n execution for the alert. Each node shows the normalized
monitor name, chosen container, approval decision, gateway response, and
recovery request. Then use this sequence:

| Symptom | Check | Likely fix |
|---|---|---|
| No execution | Uptime Kuma notification history and production webhook URL | Activate the workflow; replace a test URL; verify ingress policy permits Kuma. |
| Execution ends at validation | `reason` from **Configure and validate event** | Match the monitor name, send only DOWN events, or wait for the cooldown. |
| No ntfy message | `http://ntfy:80` reachability and topic subscription | Deploy ntfy on `telemetry`; configure ntfy auth if enabled. |
| Buttons fail | n8n `WEBHOOK_URL` and the waiting execution | Use a phone-reachable HTTPS URL; confirm the 15-minute wait has not expired. |
| Gateway returns 401 | n8n Header Auth credential | Make its bearer value match the uncommitted gateway token. |
| Gateway returns 403 | Gateway allowlist and exact container name | Update `N8N_RESTART_ALLOWLIST`, then recreate only this stack. |
| Gateway returns 404 | Docker container name | Compare against the actual Compose `container_name`; do not guess a service name. |
| Recovery check fails | Target health URL and n8n network membership | Correct the port/path or attach n8n to the target's narrow network. |

Gateway logs intentionally contain container names and HTTP results, but never
the bearer token. n8n execution data is the approval audit trail. Retain it
according to your normal n8n execution-pruning policy. A successful Docker
restart does not prove application recovery; Uptime Kuma remains the source of
truth for ongoing availability.

## Email (SMTP)

To send emails from workflows (e.g. **Send Email** node), configure SMTP in n8n: **Settings** → **Community nodes** / **Credentials** → add an SMTP credential. Use the shared Postfix relay:

- **Host:** `smtp-relay`
- **Port:** `587`
- **Secure:** off (STARTTLS is negotiated)
- **User / Password:** leave empty when using the internal relay (no auth)

For **internal-only** (Mailpit): deploy [stacks/postfix](../postfix/README.md) and [stacks/mailpit](../mailpit/README.md) with `RELAYHOST=mailpit:1025`. All emails appear in the Mailpit web UI at `https://mailpit.yourdomain.com`; none are delivered externally. See [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

## Caddy

Use `reverse_proxy n8n:5678`. Add blocks for `n8n.home` / `n8n.local` (local TLS) and your public host (e.g. `n8n.yourdomain.com`). See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example).

## Optional: local files for workflows

To use the **Read/Write Files from Disk** node with a host directory, add a bind mount in `docker-compose.yml`:

```yaml
volumes:
  - n8n_data:/home/node/.n8n
  - ./local-files:/files
```

Create `local-files` on the host; in n8n use path `/files`.

## Start

`docker compose up -d` from this directory.
