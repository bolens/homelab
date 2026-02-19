# Web-Check

🕵️‍♂️ All-in-one OSINT tool for analysing any website. Comprehensive, on-demand open source intelligence for any website.

**Website:** https://web-check.xyz  
**GitHub:** https://github.com/Lissy93/web-check

## Quick start

1. Deploy: `docker compose up -d`
2. Access: http://localhost:3000

## Configuration

| Item | Details |
|------|---------|
| **Port** | 3000 (mapped to container port 3000) |
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

For enhanced features, you can add API keys to `.env`:
- `GOOGLE_CLOUD_API_KEY` - Quality metrics via Lighthouse
- `REACT_APP_SHODAN_API_KEY` - Associated hostnames
- `REACT_APP_WHO_API_KEY` - Comprehensive WhoIs records

See `.env.example` for template. Copy it to `.env` and add your keys if desired.

## TLS checks (tls-cipher-suites, tls-security-config, tls-client-support)

These use Mozilla’s TLS Observatory (`tls-observatory.services.mozilla.com`), which is archived and may be retired. The stack sets explicit DNS (8.8.8.8, 1.1.1.1) so the container can resolve that hostname; if you still see `getaddrinfo ENOTFOUND`, the service may no longer be available and those checks will fail until web-check supports an alternative (see [web-check#276](https://github.com/Lissy93/web-check/issues/276)).

## Start

From this directory: `docker compose up -d`.
