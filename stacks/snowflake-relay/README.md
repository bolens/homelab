# Snowflake Relay

Snowflake is a Tor pluggable transport proxy that helps censored users reach the Tor network via WebRTC.

**Website:** https://snowflake.torproject.org
**GitHub:** https://github.com/keroserene/snowflake

## Usage

Runs as a background relay daemon with no web UI. The container connects to the Tor broker and forwards WebRTC traffic from censored users. No interaction needed after deployment.

## Setup

1. Copy `stack.env.example` to `stack.env` and adjust optional values.
2. No required environment variables, defaults work out of the box.
3. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| STUN_URL | No | stun:stun.l.google.com:19302 | STUN server used for WebRTC NAT traversal |
| LOG | No | info | Log verbosity level |

## Notes

- Running a Snowflake proxy helps censored users; it does not route exit traffic, low legal risk.
- Requires outbound UDP (WebRTC) to be unrestricted on your firewall.
- No inbound port forwarding is required; the proxy initiates outbound connections.
