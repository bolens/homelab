# Responder + mitm6

Responder and mitm6 are network penetration testing tools for LLMNR/NBT-NS/WPAD poisoning and IPv6 MitM attacks.

**GitHub (Responder):** https://github.com/lgandx/Responder
**GitHub (mitm6):** https://github.com/dirkjanm/mitm6

## Usage

This is a CLI-only security testing container for internal network assessments.
Run interactively with `docker compose run` on a host with network_mode host or appropriate privileges.
No web UI. Only use on networks you own or have explicit authorization to test.

## Setup

1. Copy `stack.env.example` to `stack.env` (no values required by default).
2. Run `./prepare-stack.sh` to prepare local files.
3. Build once with `docker compose build responder-mitm6`.
4. Use `docker compose run --rm responder-mitm6 bash` to enter the environment.

## Environment variables

No required environment variables. TZ/locale come from `shared.env`.

## Notes

- Use only on networks you are authorized to test. These tools perform active network poisoning.
- Host network mode (`network_mode: host`) is usually required for packet capture.
- The definition uses host networking with only `NET_ADMIN` and `NET_RAW`; it is not privileged.
