# Alertmanager

Prometheus Alertmanager for routing alerts (email, webhooks, chat, etc.) based on labels. Use it together with the Prometheus stack in this repo to turn metrics into actionable notifications.

**Website:** https://prometheus.io/docs/alerting/latest/alertmanager/  
**Docs:** https://prometheus.io/docs/alerting/latest/overview/  
**Docker image:** https://hub.docker.com/r/prom/alertmanager  
**GitHub:** https://github.com/prometheus/alertmanager  

## Quick start

1. Ensure **Prometheus** is already running and scraping your targets.
2. Copy `stack.env.example` → `stack.env` and adjust if needed (optional: set `ALERTMANAGER_CONFIG_PATH` for Portainer).
3. Copy `alertmanager.yml.example` to `~/.config/alertmanager/alertmanager.yml` (create the directory if needed). Edit that file to add receivers (email, webhooks, chat).
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
| **Network** | `monitor` — shared with Caddy, Prometheus, Grafana, cAdvisor, etc.     |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale.     |

**Portainer:** Set `ALERTMANAGER_CONFIG_PATH` in the stack's Environment to the **absolute path** of your `alertmanager.yml` on the host (e.g. `/home/youruser/.config/alertmanager/alertmanager.yml`), since `HOME` may be unset.

### Integrating with Prometheus

- Add an `alerting` block in your Prometheus config so it knows where to send alerts. The main repo’s `stacks/prometheus/prometheus.yml.example` includes this; if you use that file, Prometheus already points at `alertmanager:9093`. Add alert rules (e.g. `rule_files` or recording rules) as needed.
- Ensure the **Alertmanager** and **Prometheus** stacks are on the same Docker network (`monitor`).

### Receivers

The example config enables a **ntfy** webhook by default: alerts are sent to `http://ntfy:80/alerts`. Deploy **stacks/ntfy** on the `monitor` network and subscribe to the topic `alerts` in the ntfy app (or set `NTFY_BASE_URL` and use `https://ntfy.yourdomain.com/alerts`). To use a different topic, change the path (e.g. `/homelab-alerts`).

Other options (edit your copy at `~/.config/alertmanager/alertmanager.yml`):

- **Email**: Use `email_configs` with your **postfix** SMTP relay stack (e.g. `smarthost: smtp-relay:587`). For **internal-only** (no external delivery), deploy the **mailpit** stack and set Postfix `RELAYHOST=mailpit:1025`; alerts will appear in the Mailpit web UI. See [stacks/postfix/README.md](../postfix/README.md#internal-only-mailing-mailpit) and [stacks/mailpit/README.md](../mailpit/README.md).
- **Other webhooks**: Chatbots, PagerDuty, Opsgenie, etc.

For advanced routing (inhibition, grouping by environment, etc.) see the official Alertmanager documentation.

