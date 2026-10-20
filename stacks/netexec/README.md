# NetExec

NetExec (formerly CrackMapExec) is a network pentesting framework for enumerating and attacking Active Directory and network services.

**Website:** https://www.netexec.wiki
**GitHub:** https://github.com/Pennyw0rth/NetExec

## Usage

CLI-only tool run on demand for network enumeration, credential testing, and lateral movement tasks
in a pentest or homelab AD environment. Run interactively via `docker compose run`.

## Setup

1. Run `./prepare-stack.sh` and review `NETEXEC_WORKSPACE_PATH`.
2. Build once with `docker compose build netexec`.
3. Run: `docker compose run --rm netexec <nxc args>`.

No required environment variables.

## Build compatibility

The selected NetExec source expects the `certipy-ad` distribution. Its upstream
Git dependency tracks a fork whose current metadata has been renamed to
`certipy-nxc`, which breaks installation of this older NetExec revision. The build
pins that one dependency to compatible fork commit
`069e03113095aa02772aa3d8debea90654933fe4` (Certipy 5.1.0), also selected by the
upstream lock before the rename migration. The checked rewrite preserves every
other dependency declaration and refuses an unexpected source layout. Builds run
`pip check` and `nxc --help`; upgrading NetExec requires reviewing this compatibility
pin together with its application changes.

## Notes

- TZ and locale come from shared.env.
- Uses ordinary bridge networking and a writable local workspace.
- No persistent service, use `docker compose run --rm` for each invocation.
- Tool is under active development; pin image tags if reproducibility matters.
