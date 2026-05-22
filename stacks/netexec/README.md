# NetExec

NetExec (formerly CrackMapExec) is a network pentesting framework for enumerating and attacking Active Directory and network services.

**Website:** https://www.netexec.wiki
**GitHub:** https://github.com/Pennyw0rth/NetExec

## Usage

CLI-only tool run on demand for network enumeration, credential testing, and lateral movement tasks
in a pentest or homelab AD environment. Run interactively via `docker compose run`.

## Setup

1. Copy `stack.env.example` to `stack.env` — no required variables at this time.
2. No persistent service needed; run on demand.
3. Run: `docker compose run --rm netexec <nxc args>`

No required environment variables.

## Notes

- TZ and locale come from shared.env.
- Requires network access to target hosts; use host networking or a dedicated pentest network.
- No persistent service — use `docker compose run --rm` for each invocation.
- Tool is under active development; pin image tags if reproducibility matters.
