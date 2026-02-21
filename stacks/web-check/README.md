# Web-Check

🕵️‍♂️ All-in-one OSINT tool for analysing any website. Comprehensive, on-demand open source intelligence for any website.

**Website:** https://web-check.xyz  
**GitHub:** https://github.com/Lissy93/web-check

## Quick start

1. Deploy: `docker compose up -d`
2. Access via Caddy (e.g. https://webcheck.yourdomain.com). No host port is exposed; the stack is on the `monitor` network for reverse-proxy.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `web-check:3000`) |
| **Network** | `monitor` — so monitoring tools can reach it |
| **Image** | `lissy93/web-check:latest` |
| **DNS** | 8.8.8.8, 1.1.1.1 (so TLS Observatory and other external APIs resolve) |

## Features

Web-Check provides comprehensive website analysis including:
- IP information and geolocation
- SSL certificate chain analysis
- DNS records (A, AAAA, MX, TXT, etc.)
- Security headers and configurations
- Technology stack detection
- Performance metrics
- Security analysis (HSTS, CSP, etc.)
- And much more...

## Optional API Keys

For enhanced features, you can add API keys to `.env` (copy `.env.example` → `.env`):
- `GOOGLE_CLOUD_API_KEY` - Quality metrics via Lighthouse
- `REACT_APP_SHODAN_API_KEY` - Associated hostnames (Shodan)
- `REACT_APP_WHO_API_KEY` - Comprehensive WhoIs records
- `URL_SCAN_API_KEY` - urlscan.io integration
- `BUILT_WITH_API_KEY` - BuiltWith technology detection

See `.env.example` for the template.

## TLS checks (tls-cipher-suites, tls-security-config, tls-client-support)

These use Mozilla’s TLS Observatory (`tls-observatory.services.mozilla.com`), which is archived and may be retired. The stack sets explicit DNS (8.8.8.8, 1.1.1.1) so the container can resolve that hostname; if you still see `getaddrinfo ENOTFOUND`, the service may no longer be available and those checks will fail until web-check supports an alternative (see [web-check#276](https://github.com/Lissy93/web-check/issues/276)).

## Start

## Troubleshooting

**Important:** `REACT_APP_*` environment variables (like `REACT_APP_SHODAN_API_KEY` and `REACT_APP_WHO_API_KEY`) are client-side React variables that must be available at **build time**. Since we're using the pre-built Docker image (`lissy93/web-check:latest`), these variables won't work even if set in `.env` - the React app was already built without them.

If you need Shodan or WhoAPI features, you'll need to build web-check from source with the API keys included, or wait for web-check to add backend API endpoints that proxy these calls.

For detailed troubleshooting information, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

## Start

From this directory: `docker compose up -d`.
