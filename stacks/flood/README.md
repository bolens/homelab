# Flood

Flood provides a web interface for the bundled rTorrent service. Both services
share the `torrents_manual` download volume and rTorrent socket volume.
rTorrent is built from Alpine's maintained package rather than the abandoned
`jesec/rtorrent` image.

## Prepare and deploy

```bash
./prepare-stack.sh
docker compose up -d
```

Review `stack.env` before deployment. The preparation script creates the
required `ingress-admin` and `torrents` networks and the external
`torrents_manual` volume when Docker is available.

Flood listens on container port `3000` and is intended to be reached through
Caddy on the dedicated `ingress-admin` network. Application state is stored in
`flood_data`; rTorrent state is stored in `rtorrent_data`.

## Session lock recovery

`Could not lock session directory` can indicate an active rTorrent instance or a
lock left by an old container. Identify every container mounting `rtorrent_data`
and confirm that the recorded lock owner and any other rTorrent process are gone.
Stop rTorrent and Flood before backing up their state and affected downloads.
Verify an isolated restore before removing only the proven stale
`session/rtorrent.lock`. Restart the existing containers and check rTorrent's
running state, restart count, session records, and Flood connectivity. Preserve
all torrent session files and downloads. Never remove a lock held by a running
instance.

## Persistent accounts

Flood must run with `--rundir=/data`. Its default runtime directory is under the
container user's home. Mounting `/data` without selecting it leaves accounts and
the session-signing secret in the disposable container layer. Before recreating
an older deployment, stop Flood and back up both `/data` and the actual runtime
directory. Verify isolated copies, then migrate the complete runtime into the
persistent volume with ownership matching UID/GID 1001. Preserve user hashes,
`flood.secret`, per-user settings, and connection configuration. Do not overwrite
a nonempty destination without reviewing both copies. Verify the same account
before and after recreation.

## Librarr downloads

Verify the intended remote mount before creating dedicated empty directories
`downloads/librarr/{ebooks,audiobooks,manga}`. Give the applications shared group
write access. Set `FLOOD_LIBRARR_DOWNLOADS_PATH` to that existing download root and
`LIBRARR_MEDIA_GID` to its group. Select `docker-compose.librarr.yml` alongside all
existing overrides. It adds a narrow bind to Flood and rTorrent at
`/data/downloads/librarr` and extends Flood's allowed paths. Existing `/downloads`
and torrent state remain in their original volumes. Do not rerun the recursive
initialization service. Deploy only `rtorrent` and `flood` with `--no-deps` after
verified backups. Keep the original compatible images.

Librarr's optional [Flood adapter](../librarr/README.md#flood--rtorrent) uses the
existing rTorrent Unix socket. No socket TCP port or public adapter route is added.
The adapter submits and reads only its configured categories and paths. It refuses
torrent removal. Bookshelf also supports a native Flood download client; use its
own dedicated tag if enabling it.
