# Kali Linux

Kali Linux is a Debian-based distribution packed with offensive security and penetration testing tools.

**Website:** https://www.kali.org
**GitHub:** https://github.com/kalilinux/kali-docker

## Usage

CLI container run interactively with `docker compose run`. It has no web, VNC, or RDP service.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Review `KALI_WORKSPACE_PATH`.
3. Run interactively: `docker compose run --rm kali bash`.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| KALI_WORKSPACE_PATH | No | ~/security-lab/kali | Writable local workspace |

## Notes

- TZ and locale come from shared.env.
- The definition grants only `NET_RAW`, drops all other capabilities, and enables no privileged mode.
- No persistent service — use `docker compose run --rm` for interactive sessions.
