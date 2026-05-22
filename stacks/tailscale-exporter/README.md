# tailscale-exporter

tailscale-exporter is a Prometheus exporter that exposes Headscale node and network metrics.

**GitHub:** https://github.com/davidsbond/tailscale-exporter

## Usage

This exporter scrapes your Headscale server over gRPC and exposes metrics on port 9250 for Prometheus.
It runs on the `monitor` network alongside Prometheus and Headscale stacks.
The Caddy snippet exposes the metrics endpoint at tailscale-exporter.home / tailscale-exporter.local for internal access only.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Run `./prepare-stack.sh` to copy env and Caddy snippet files.
3. Generate a Headscale API key: `headscale apikeys create` and set `HEADSCALE_API_KEY`.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| HEADSCALE_ADDRESS | Yes | headscale:50443 | gRPC address of the Headscale server |
| HEADSCALE_API_KEY | Yes | *** | Headscale API key for authentication |
| HEADSCALE_INSECURE | No | false | Skip TLS verification for gRPC connection |

## Notes

- Keep this exporter internal-only; do not expose metrics publicly.
- Both this stack and the Headscale stack must share the same Docker network.
- Set `HEADSCALE_INSECURE=true` only if Headscale uses a self-signed cert on the gRPC port.
