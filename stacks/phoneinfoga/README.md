# PhoneInfoga

Phone number OSINT tool: looks up basic information about a phone number (country, carrier, line type, VOIP or mobile) and searches for web footprints using multiple search engines and sources. Exposes a web UI and REST API.

**Website:** https://sundowndev.github.io/phoneinfoga/  
**GitHub:** https://github.com/sundowndev/phoneinfoga  
**Docker Hub:** https://hub.docker.com/r/sundowndev/phoneinfoga

## Quick start

1. **Copy env template** (optional):

   ```bash
   cp stack.env.example stack.env
   ```

2. **(Optional) Set timezone** in `stack.env` if you don’t want the default:

   ```bash
   TZ=America/Denver
   ```

3. **Deploy:**

   From this directory:

   ```bash
   docker compose up -d
   ```

   The compose file already uses `env_file: [stack.env]`, so `docker compose up -d` is sufficient after you create `stack.env`. You can also run:

   ```bash
   docker compose --env-file stack.env up -d
   ```

4. **Access via Caddy** at your chosen hostname (for example, `https://phoneinfoga.yourdomain.com`). See the Caddy example below.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `phoneinfoga:5000`) |
| **Network** | `monitor` (external) so Caddy can reach the container |
| **Image** | `sundowndev/phoneinfoga:latest` |
| **Storage** | Stateless by default; results are generated per query in the UI/API |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED example hostnames):

```
phoneinfoga.home, phoneinfoga.local {
  tls internal
  reverse_proxy phoneinfoga:5000
}
```

In your real setup, use the hostname you expose via Cloudflare/Tunnel (for example `phoneinfoga.yourdomain.com`) and keep the container on the `monitor` network so Caddy can resolve `phoneinfoga`.

## Start

From this directory:

- **With env file:** `docker compose --env-file stack.env up -d`  
- **Without env file:** `docker compose up -d` (uses default timezone)

