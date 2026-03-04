# SpiderFoot

Automated OSINT tool with 180+ modules for domains, IPs, emails, BTC addresses, usernames and more. Aggregates data from many sources (DNS, breaches, Shodan, GreyNoise, cloud buckets, social media, etc.) into a single web UI.

**Website:** https://www.spiderfoot.net  
**Docs:** https://github.com/smicallef/spiderfoot/wiki  
**GitHub:** https://github.com/smicallef/spiderfoot  
**Docker image:** https://hub.docker.com/r/spiderfoot/spiderfoot  
**Releases:** https://github.com/smicallef/spiderfoot/releases  

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

4. **Access via Caddy** at your chosen hostname (for example, `https://spiderfoot.bolens.dev`). See the Caddy example below.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `spiderfoot:5001`) |
| **Network** | `monitor` (external) so Caddy can reach the container |
| **Image** | `spiderfoot/spiderfoot:latest` (pin a tag if you prefer) |
| **Storage** | Named volume `spiderfoot-data` at `/var/lib/spiderfoot` for scans, config and API keys |

Inside the app you can add API keys (Shodan, Have I Been Pwned, GreyNoise, etc.) under **Settings → API Keys**. Those keys are stored inside the `spiderfoot-data` volume.

## Caddy reverse proxy

Example Caddy vhost (SANITIZED example hostnames):

```
spiderfoot.home, spiderfoot.local {
  tls internal
  reverse_proxy spiderfoot:5001
}
```

In your real setup, use the hostname you expose via Cloudflare/Tunnel (for example `spiderfoot.bolens.dev`) and keep the container on the `monitor` network so Caddy can resolve `spiderfoot`.

## Start

From this directory:

- **With env file:** `docker compose --env-file stack.env up -d`  
- **Without env file:** `docker compose up -d` (uses default timezone)

