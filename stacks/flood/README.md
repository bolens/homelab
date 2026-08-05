# Flood

Flood provides a web interface for the bundled rTorrent service. Both services
share the `torrents_manual` download volume and rTorrent socket volume.

## Prepare and deploy

```bash
./prepare-stack.sh
docker compose up -d
```

Review `stack.env` before deployment. The preparation script creates the
required `proxy-ingress` and `torrents` networks and the external
`torrents_manual` volume when Docker is available.

Flood listens on container port `3000` and is intended to be reached through
Caddy on the dedicated `proxy-ingress` network. Application state is stored in
`flood_data`; rTorrent state is stored in `rtorrent_data`.
