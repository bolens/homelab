# Atomic Red Team

Atomic Red Team is a library of small, portable adversary-simulation tests mapped to MITRE ATT&CK techniques.

**Website:** https://atomicredteam.io
**GitHub:** https://github.com/redcanaryco/atomic-red-team

## Usage

Run tests interactively via `docker compose run` inside the container. No web UI. Used in homelabs to validate detection rules, SIEM alerts, and endpoint security tools.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. No required environment variables — TZ and locale come from shared.env.
3. Deploy: `docker compose run --rm atomic-red-team bash`

## Environment variables

No required environment variables. TZ and locale are inherited from shared.env.

## Notes

- CLI-only tool; use `docker compose run` rather than `up -d`.
- Tests can generate real malicious-looking activity — run only in isolated lab environments.
- Invoke-AtomicRedTeam PowerShell module is the primary interface inside the container.
