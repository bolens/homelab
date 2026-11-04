# Alertmanager

Prometheus Alertmanager for routing alerts (email, webhooks, chat, etc.) based on labels. Use it together with the Prometheus stack in this repo to turn metrics into actionable notifications.

**Website:** https://prometheus.io/docs/alerting/latest/alertmanager/
**Docs:** https://prometheus.io/docs/alerting/latest/overview/
**Docker image:** https://hub.docker.com/r/prom/alertmanager
**GitHub:** https://github.com/prometheus/alertmanager

## Quick start

1. Ensure **Prometheus** is already running and scraping your targets.
2. Copy `stack.env.example` → `stack.env` and adjust if needed (optional: set `ALERTMANAGER_CONFIG_PATH` for Portainer).
3. Create private `secrets/gotify-webhook-token` matching the Gotify stack GOTIFY_BRIDGE_TOKEN, readable by Alertmanager. Copy `alertmanager.yml.example` to `~/.config/alertmanager/alertmanager.yml` (create the directory if needed). Edit that file to add receivers (email, webhooks, chat).
4. Start the stack:

   ```bash
   docker compose up -d
   ```

5. Expose Alertmanager via Caddy (e.g. `https://alertmanager.yourdomain.com`) using the example site block in the main Caddyfile; internally it listens on port `9093`.

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Via Caddy only (no host port; reverse-proxy to `alertmanager:9093`)    |
| **Config**  | Copy `alertmanager.yml.example` to `~/.config/alertmanager/alertmanager.yml` (or set `ALERTMANAGER_CONFIG_PATH` to the absolute path). Edit that file for receivers and routes. |
| **Volume**  | `alertmanager_data` (Alertmanager state: silences, notification log)   |
| **Network** | Internal `telemetry` for Prometheus/Gotify adapter; `ingress-admin` for Caddy; `mail-clients` for SMTP |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale.     |

**Portainer:** Set `ALERTMANAGER_CONFIG_PATH` in the stack's Environment to the **absolute path** of your `alertmanager.yml` on the host (e.g. `/home/youruser/.config/alertmanager/alertmanager.yml`), since `HOME` may be unset.

### Integrating with Prometheus

- Add an `alerting` block in your Prometheus config so it knows where to send alerts. The main repo's `stacks/prometheus/prometheus.yml.example` includes this; if you use that file, Prometheus already points at `alertmanager:9093`. Add alert rules (e.g. `rule_files` or recording rules) as needed.
- Ensure the **Alertmanager** and **Prometheus** stacks are on `telemetry`.

### Receivers

The example routes all five notification categories through the authenticated internal **Gotify adapter** at `http://gotify-alertmanager:8080/alertmanager/<channel>`. Deploy [Gotify](../gotify/README.md) on `telemetry`, configure its five application tokens, and set the private `secrets/gotify-webhook-token` file to the same bearer secret as GOTIFY_BRIDGE_TOKEN. The adapter preserves firing/resolved status, labels, annotations, and severity priority. Its port is not published. Keep receiver names, grouping, inhibition, SMTP fallbacks, and route timings during migration.

Other options (edit your copy at `~/.config/alertmanager/alertmanager.yml`):

- **Email**: Use `email_configs` with your **postfix** SMTP relay stack (e.g. `smarthost: smtp-relay:587`). For **internal-only** (no external delivery), deploy the **mailpit** stack and set Postfix `RELAYHOST=mailpit:1025`; alerts will appear in the Mailpit web UI. See [stacks/postfix/README.md](../postfix/README.md#internal-only-mailing-mailpit) and [stacks/mailpit/README.md](../mailpit/README.md).
- **Other webhooks**: Chatbots, PagerDuty, Opsgenie, etc.

For advanced routing (inhibition, grouping by environment, etc.) see the official Alertmanager documentation.
