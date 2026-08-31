# Unbound

Unbound is a validating, recursive, caching DNS resolver for private DNS resolution in your homelab.

**Website:** https://nlnetlabs.nl/projects/unbound/about/
**GitHub:** https://github.com/NLnetLabs/unbound

## Usage

Unbound runs as a recursive DNS resolver on `dns-services`, providing fast and private DNS
for other containers and LAN clients. Point Pi-hole, AdGuard Home, or router DNS upstream to this
service. No web UI; configure via `unbound.conf` inside the `unbound_data` volume.

## Setup

1. Copy `stack.env.example` to `stack.env` (no required values).
2. Ensure the `dns-services` Docker network exists before deploying.
3. Customize Unbound configuration in the `unbound_data` volume after first start if needed.
4. Deploy: `docker compose up -d`

## Environment variables

No required environment variables. TZ/locale are provided by `shared.env`.

## Notes

- The local Alpine 3.24 image preserves the existing `/opt/unbound` configuration layout while
  running the current packaged Unbound release. `unbound-control` requires
  `control-enable: yes` in `unbound.conf` to work.
- Health check uses `drill example.com @127.0.0.1`; ensure `drill` is available in the image.
- Resource limits: 128 MB RAM, 0.25 CPU, increase in compose for high-traffic environments.
- Container listens on the internal Docker network only; map port 53 explicitly if LAN access needed.
