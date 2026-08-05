# ruTorrent

LinuxServer.io ruTorrent deployment with persistent configuration and the
shared `torrents_manual` download volume.

## Prepare and deploy

```bash
./prepare-stack.sh
docker compose up -d
```

Review `stack.env` before deployment. The preparation script creates the
required `ingress-admin` and `torrents` networks and the external
`torrents_manual` volume when Docker is available.

The web interface listens on container port `80` and is intended to be reached
through Caddy. Peer traffic uses host port `49161` over TCP and UDP.
