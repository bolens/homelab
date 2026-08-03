# Atomic Red Team

Atomic Red Team is a library of small, portable adversary-simulation tests mapped to MITRE ATT&CK techniques.

**Website:** https://atomicredteam.io
**GitHub:** https://github.com/redcanaryco/atomic-red-team

## Usage

Run tests interactively via `docker compose run` inside the container. No web UI. Used in homelabs to validate detection rules, SIEM alerts, and endpoint security tools.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Review `ATOMIC_WORKSPACE_PATH`.
3. Build once with `docker compose build atomic-red-team`.
4. Run with `docker compose run --rm atomic-red-team pwsh`.

## Environment variables

`ATOMIC_WORKSPACE_PATH` holds local working files; the test library is included in the locally built image.

## Notes

- CLI-only tool; use `docker compose run` rather than `up -d`.
- Tests can generate real malicious-looking activity — run only in isolated lab environments.
- Invoke-AtomicRedTeam PowerShell module is the primary interface inside the container.
