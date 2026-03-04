# Holehe (web UI)

Holehe checks if an email address is registered on many websites using their “forgot password” flows, without sending emails to the target. This stack wraps the **holehe-web** FastAPI app to provide a simple web UI and CSV export.

**Website:** https://github.com/sds-osint/holehe-web  
**Docs:** https://github.com/sds-osint/holehe-web#readme  
**GitHub:** https://github.com/sds-osint/holehe-web (web UI); core tool: https://github.com/megadose/holehe  

## Quick start

1. **Clone the upstream holehe-web repo** (required once):

   ```bash
   ./clone-repo.sh
   ```

   This creates `./repo` with the FastAPI app and frontend.

2. **Copy env template** (optional):

   ```bash
   cp stack.env.example stack.env
   ```

3. **(Optional) Set timezone** in `stack.env` if you don’t want the default:

   ```bash
   TZ=America/Denver
   ```

4. **Build and deploy:**

   From this directory:

   ```bash
   docker compose up -d
   ```

   The compose file already uses `env_file: [stack.env]`, so `docker compose up -d` is sufficient after you create `stack.env`. You can also run:

   ```bash
   docker compose --env-file stack.env up -d
   ```

5. **Access via Caddy** at your chosen hostname (for example, `https://holehe.yourdomain.com`). See the Caddy example below.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `holehe-web:8000`) |
| **Network** | `monitor` (external) so Caddy can reach the container |
| **Image** | Built locally from `./repo` (upstream `sds-osint/holehe-web`) |
| **Storage** | In-memory; results are downloaded as CSV from the UI |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED example hostnames):

```
holehe.home, holehe.local {
  tls internal
  reverse_proxy holehe-web:8000
}
```

In your real setup, use the hostname you expose via Cloudflare/Tunnel (for example `holehe.yourdomain.com`) and keep the container on the `monitor` network so Caddy can resolve `holehe-web`.

## CLI vs web

- For **web-based checks** and CSV export, use this stack (holehe-web).  
- For **pure CLI scripts**, you can also run Holehe directly:

  ```bash
  # Example only – run on your host
  pip install holehe
  holehe test@example.com
  ```

Use Holehe only for lawful and ethical purposes; respect the upstream project’s license and disclaimer.

