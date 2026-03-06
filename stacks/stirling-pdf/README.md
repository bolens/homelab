# Stirling-PDF – PDF tools

[Stirling-PDF](https://www.stirlingpdf.com/) is a web-based PDF toolkit: merge, split, rotate, watermark, OCR, convert to/from images, and more. This stack runs Stirling-PDF behind Caddy. No host ports; access via Caddy.

**Website:** https://www.stirlingpdf.com/  
**Docs:** https://docs.stirlingpdf.com/  
**GitHub:** https://github.com/Stirling-Tools/Stirling-PDF  
**Docker image:** https://hub.docker.com/r/stirlingtools/stirling-pdf  

## Quick start

1. **Environment**
   - From this directory: copy `stack.env.example` → `stack.env`.
   - Optionally set `TZ`.
2. **Deploy**

   ```bash
   docker compose up -d
   ```

3. **Access**
   - Stirling-PDF listens on port `8080` inside the container.
   - Put it behind Caddy on the `monitor` network, e.g.:
     - `https://stirling-pdf.yourdomain.com` → `stirling-pdf:8080`

## Configuration

| Item        | Details                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Access**  | Via Caddy (reverse-proxy to `stirling-pdf:8080`)                             |
| **Network** | `monitor` (for Caddy) + default                                             |
| **Images**  | `stirlingtools/stirling-pdf:latest`                                         |
| **Storage** | Optional OCR tessdata volume                                                |
| **Caddy**   | See [stacks/caddy/Caddyfile.example](../caddy/Caddyfile.example) for `stirling-pdf.yourdomain.com` → `stirling-pdf:8080` |

Image variants: `latest-fat` (extra tools), `latest-ultra-lite` (minimal). See [Stirling-PDF Docker](https://docs.stirlingpdf.com/Installation/Docker%20Install/).

## Portainer

Add stack from this directory; ensure `stack.env` exists. No host ports; use Caddy to expose the service.
