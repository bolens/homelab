# Cowrie

Cowrie is a medium-to-high interaction SSH and Telnet honeypot that logs brute-force attacks and shell interaction.

**Website:** https://cowrie.readthedocs.io
**GitHub:** https://github.com/cowrie/cowrie

## Usage

Exposes fake SSH (port 2222) and Telnet (port 2223) services to attract attackers. Logs are written locally and optionally shipped to Splunk via HEC. Pairs well with a log aggregation stack (Splunk, Loki, Graylog).

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. To ship logs to Splunk, uncomment and set COWRIE_OUTPUT_SPLUNK_HOST and COWRIE_OUTPUT_SPLUNK_TOKEN.
3. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| COWRIE_OUTPUT_SPLUNK_HOST | No | None | Splunk HEC hostname for log forwarding |
| COWRIE_OUTPUT_SPLUNK_TOKEN | No | None | Splunk HEC token (openssl rand -hex 16) |

## Notes

- Bind port 22 on a public interface with caution; use firewall rules to avoid locking yourself out.
- Cowrie fakes a Linux shell, do not expose on a port where your real SSH runs.
- JSON logs land in `./var/log/cowrie/` by default; mount a volume to persist them.
