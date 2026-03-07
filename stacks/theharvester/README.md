# theHarvester (REST API)

Classic OSINT tool to collect emails, subdomains, hosts, open ports, and banners from multiple public sources (search engines, PGP servers, Shodan, etc.). This stack runs the **REST API** variant (`restfulharvest`) so you can query theHarvester over HTTP from other tools and scripts.

**Website:** https://github.com/laramies/theHarvester  
**Docs:** https://github.com/laramies/theHarvester/wiki  
**GitHub:** https://github.com/laramies/theHarvester  
**Docker image:** https://hub.docker.com/r/secsi/restfulharvest  
**Releases:** https://github.com/laramies/theHarvester/releases  

## Quick start

1. **Prepare** (creates `stack.env` from template if missing):

   ```bash
   ./prepare-stack.sh
   # or: cp stack.env.example stack.env
   ```

2. **(Optional) Set timezone / proxies** in `stack.env`.

3. **Deploy:**

   ```bash
   docker compose up -d
   ```

4. **Access REST API via Caddy** at your hostname (e.g. `https://theharvester.yourdomain.com`). The service listens on port 80 inside the container.

## Portainer

Stacks → Add stack → **Repository** → Compose path `stacks/theharvester/docker-compose.yml`. Ensure the stack has access to the `monitor` network. Add env vars from `stack.env.example` if needed.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse proxy to `theharvester:80`) |
| **Network** | `monitor` (external) so Caddy can reach the API |
| **Image** | `secsi/restfulharvest:latest` (RAUDI-updated image for theHarvester REST API) |
| **Storage** | theHarvester runs stateless; results are returned in the HTTP response (JSON) |

The underlying theHarvester tool still requires API keys for some data sources (Shodan, etc.). Refer to the upstream docs for how to configure those in the REST container (config file and/or environment variables).

## Example usage

SANITIZED examples (replace hostnames and targets for real use).

- **List available endpoints / docs** (if exposed by the image):

  ```bash
  curl https://theharvester.example.com/docs
  ```

- **Run a basic domain search** (example only; check upstream REST docs for the exact schema):

  ```bash
  curl -X POST https://theharvester.example.com/api/search \
    -H "Content-Type: application/json" \
    -d '{
      "domain": "example.com",
      "sources": ["bing", "shodan"],
      "limit": 500
    }'
  ```

## Caddy reverse proxy

Add a site block in your Caddyfile (placeholder hostname; use your real hostname in your local Caddyfile):

```
theharvester.yourdomain.com {
  reverse_proxy theharvester:80
}
```

Keep the container on the `monitor` network so Caddy can resolve `theharvester`. For internal-only access use `tls internal` and your internal hostname (e.g. `theharvester.home`).

## CLI usage

This stack focuses on the **REST API**. If you prefer pure CLI usage, you can:

- Use the upstream `theharvester` Docker images directly, or  
- Install theHarvester on your host and call it with `theHarvester -d example.com -b bing,shodan -l 500`.

