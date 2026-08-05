# Glance – self-hosted dashboard

[Glance](https://github.com/glanceapp/glance) is a lightweight dashboard for RSS, weather, markets, Docker status, custom widgets, and more. Configuration is YAML (`config/glance.yml`). This stack runs Glance behind Caddy on the shared `ingress-public` network; there are no host port bindings.

**Website / repo:** https://github.com/glanceapp/glance  
**Configuration docs:** https://github.com/glanceapp/glance/blob/main/docs/configuration.md  
**Docker image:** https://hub.docker.com/r/glanceapp/glance  

## Quick start

1. From this directory, run `./prepare-stack.sh` (creates `stack.env` from the example, copies the Caddy snippet template, downloads a starter `config/glance.yml`, and creates `assets/user.css` if missing). Or copy `stack.env.example` → `stack.env` and create `config/` yourself.
2. Edit `config/glance.yml` (widgets, feeds, theme). Optional: add secrets or tunables to `stack.env`; Glance can reference them in YAML via environment substitution (see upstream docs).
3. Replace the placeholder hostname in `caddy_snippet.conf` (from the `.example`) and reload Caddy so `https://glance.example.com` (your real hostname) proxies to `glance:8080`.
4. Deploy:

   ```bash
   docker compose up -d
   ```

5. Open the site in a browser (via Caddy). The app listens on **8080** inside the container.

## Configuration

| Item        | Details |
| ----------- | ------- |
| **Access**  | Via Caddy → `glance:8080` |
| **Network** | `ingress-public` (external) |
| **Image**   | `glanceapp/glance:latest` |
| **Config**  | `./config` → `/app/config` (`glance.yml` required; entrypoint uses `/app/config/glance.yml`) |
| **Assets**  | `./assets` → `/app/assets` (e.g. `user.css` for custom CSS) |
| **Caddy**   | See `caddy_snippet.conf.example` (placeholder `glance.example.com`) |

## Notes

- **DNS / ad blockers:** Many widgets trigger outbound lookups; Pi-hole / AdGuard rate limits can cause timeouts. Raise the DNS rate limit or reduce widgets if pages hang (see upstream README “Common issues”).
- **Dark Reader:** Can break some widgets; disable for your Glance hostname if layout looks wrong.
- **Backups:** Copy `./config` (and optional `./assets`) if you care about your layout and CSS.

## Portainer

Add stack from this directory; ensure `stack.env` exists and `config/glance.yml` is present (run `./prepare-stack.sh` on the host first, or bind-mount a config directory). No published ports; terminate TLS and route traffic with Caddy.
