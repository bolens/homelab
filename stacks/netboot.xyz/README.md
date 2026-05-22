# netboot.xyz

netboot.xyz is a network boot utility that lets you PXE-boot into dozens of OS installers and live environments from a single menu.

**Website:** https://netboot.xyz
**Docs:** https://netboot.xyz/docs/
**GitHub:** https://github.com/netbootxyz/netboot.xyz

## Usage

Runs a TFTP/HTTP server that serves PXE boot menus to hosts on your LAN. DHCP is configured to point
PXE clients at this server. The web UI lets you customize menus and manage local asset caching.
Typically deployed on the same network segment as your lab DHCP server.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set TZ to your local timezone.
3. Point your DHCP server's next-server / boot-file options at this host's IP and `netboot.xyz.kpxe`.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TZ | Yes | America/New_York | Timezone for the container |

## Notes

- The web UI is typically on port 3000; TFTP on UDP 69; HTTP assets on port 80.
- DHCP integration is required on the host network for PXE to work — host networking mode may be needed.
- Local asset caching avoids re-downloading large ISOs on every boot.
