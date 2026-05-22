# Dionaea + ConPot

Dionaea and ConPot are multi-protocol malware and industrial-control honeypots that capture exploits, payloads, and ICS/SCADA probe traffic.

**GitHub (Dionaea):** https://github.com/DinoTools/dionaea
**GitHub (ConPot):** https://github.com/mushorg/conpot

## Usage

Runs both honeypots as separate containers, each listening on a range of emulated service ports. Logs and captured binaries are stored in mounted volumes. Pairs well with a SIEM or log shipping stack for alert correlation.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. No required environment variables — TZ and locale come from shared.env.
3. Deploy: `docker compose up -d`

## Environment variables

No required environment variables. TZ and locale are inherited from shared.env.

## Notes

- Dionaea captures malware binaries in the configured bistreams volume — review and isolate regularly.
- ConPot emulates Siemens S7, Modbus, SNMP, and HTTP SCADA interfaces.
- Expose honeypot ports via firewall rules rather than binding directly to 0.0.0.0 in production.
- Do not run on the same host as production services sharing the same ports.
