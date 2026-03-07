# ntopng

Network traffic analytics and flow monitoring. This stack runs ntopng with host networking so it can observe traffic on the Docker host’s interfaces.

**Website:** https://www.ntop.org/products/traffic-analysis/ntop/  
**Docs:** https://www.ntop.org/guides/ntopng/  
**Docker image:** https://hub.docker.com/r/ntop/ntopng  

## Quick start

1. From this directory, copy `stack.env.example` → `stack.env` and adjust `TZ` / locale if needed.
2. Start the stack:

   ```bash
   docker compose up -d
   ```

3. By default ntopng listens on `http://localhost:3000` on the Docker host (because of `network_mode: host`).
4. Optionally add a Caddy site block that proxies to `host.docker.internal:3000` if you want to access the UI via HTTPS and/or Cloudflare Tunnel.

## Configuration

| Item        | Details                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| **Access**  | Host networking; web UI on `http://<host-ip>:3000` by default          |
| **Volume**  | `ntopng_data` (ntopng state, flows, preferences)                       |
| **Network** | `network_mode: host` to see real interfaces (no `monitor` network)     |
| **Env**     | See `stack.env.example` and `documents/ENV-VARS.md` for TZ/locale.     |

Consult the ntopng docs for configuring interfaces, flows, and data retention. Be mindful of privacy when exposing ntopng externally; if you put it behind Caddy and Cloudflare Tunnel, protect the hostname with Cloudflare Access.

