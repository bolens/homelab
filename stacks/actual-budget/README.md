# Actual Budget – envelope-style budgeting

[Actual Budget](https://actualbudget.org/) is a local-first, open-source budgeting app with envelope-style budgeting and optional sync. This stack runs the **Actual sync server** so you can use the desktop/mobile app with cloud sync. No host ports; put it behind Caddy.

**Website:** https://actualbudget.org/  
**Docs:** https://actualbudget.org/docs/  
**GitHub:** https://github.com/actualbudget/actual  
**Docker image:** https://hub.docker.com/r/actualbudget/actual-server  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Optionally set `TZ`.
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Server listens on port `5006` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://actual-budget.yourdomain.com` → `actual-budget:5006`
   - In the Actual desktop/mobile app, set the server URL to your Caddy URL (e.g. `https://actual-budget.yourdomain.com`).

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `actual-budget:5006`)                            |
| **Network** | `monitor` (for Caddy) + default                                             |
| **Images**  | `actualbudget/actual-server:latest`                                         |
| **Storage** | `actual_budget_data` (sync data)                                            |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `actual-budget.yourdomain.com` → `actual-budget:5006` |

For encryption and multi-user setup, see the [Actual server docs](https://actualbudget.org/docs/config).

## Portainer

Add stack from this directory; ensure `stack.env` exists. No host ports; use Caddy to expose the service.
