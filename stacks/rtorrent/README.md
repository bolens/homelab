# rTorrent

Standalone rTorrent service for manual torrent downloads. It stores session
state in `rtorrent_data` and downloads in the shared external
`torrents_manual` volume.

## Prepare and deploy

```bash
./prepare-stack.sh
docker compose up -d
```

The preparation script creates the `torrents` network and
`torrents_manual` volume when Docker is available. Peer traffic uses host port
`49160` over TCP and UDP. This stack has no web interface; use the separate
Flood or ruTorrent stack when a browser UI is needed.
