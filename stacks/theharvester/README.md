# theHarvester (REST API)

Classic OSINT tool to collect emails, subdomains, hosts, open ports, and banners from multiple public sources (search engines, PGP servers, Shodan, etc.). This stack runs the **REST API** variant (`restfulharvest`) so you can query theHarvester over HTTP from other tools and scripts.

**Website:** https://github.com/laramies/theHarvester  
**Docs:** https://github.com/laramies/theHarvester/wiki  
**GitHub:** https://github.com/laramies/theHarvester  
**Docker image:** https://hub.docker.com/r/secsi/restfulharvest  
**Releases:** https://github.com/laramies/theHarvester/releases  

## Quick start

1. **Copy env template** (optional):

   ```bash
   cp stack.env.example stack.env
   ```

2. **(Optional) Set timezone / proxies** in `stack.env` (for example to control logs or outbound proxies for theHarvester).

3. **Deploy:**

   From this directory:

   ```bash
   docker compose up -d
   ```

   The compose file already uses `env_file: [stack.env]`, so `docker compose up -d` is sufficient after you create `stack.env`. You can also run:

   ```bash
   docker compose --env-file stack.env up -d
   ```

4. **Access REST API via Caddy** at your chosen hostname (for example, `https://theharvester.yourdomain.com`). The REST service listens on port 80 inside the container.

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

Example Caddy vhost (SANITIZED example hostnames):

```
theharvester.home, theharvester.local {
  tls internal
  reverse_proxy theharvester:80
}
```

In your real setup, use the hostname you expose via Cloudflare/Tunnel (for example `theharvester.yourdomain.com`) and keep the container on the `monitor` network so Caddy can resolve `theharvester`.

## CLI usage

This stack focuses on the **REST API**. If you prefer pure CLI usage, you can:

- Use the upstream `theharvester` Docker images directly, or  
- Install theHarvester on your host and call it with `theHarvester -d example.com -b bing,shodan -l 500`.

