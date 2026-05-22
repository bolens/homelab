# Kali Linux

Kali Linux is a Debian-based distribution packed with offensive security and penetration testing tools.

**Website:** https://www.kali.org
**GitHub:** https://github.com/kalilinux/kali-docker

## Usage

CLI (and optionally GUI via VNC/RDP) container used for pentesting, CTFs, and security research in an
isolated homelab environment. Run interactively with `docker compose run` or keep running for VNC access.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set KALI_PASSWORD to a strong password (generate: `openssl rand -base64 16`).
3. If using a GUI image, access via VNC or RDP on the configured port.
4. Run interactively: `docker compose run --rm kali bash`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| KALI_PASSWORD | Yes | — | VNC/RDP password for GUI image access |

## Notes

- TZ and locale come from shared.env.
- The default kali-rolling image is CLI only; pull a kali-desktop-* image for GUI access.
- Run with --privileged or specific capabilities if tools require raw socket/network access.
- No persistent service — use `docker compose run --rm` for interactive sessions.
