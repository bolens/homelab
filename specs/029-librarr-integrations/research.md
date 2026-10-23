# Librarr compatibility research

Inspected upstream release **v1.4.1**, commit
`d7f4db91a4c6b157ad0dd10e87b98842799ae586`, on 2026-10-23.
Source: <https://github.com/JeremiahM37/librarr/tree/v1.4.1>.

- Registry manifest for `ghcr.io/jeremiahm37/librarr:v1.4.1` resolves to
  `sha256:30fddf1a1e77eb9fc94120cea83e165858a7790857276903a45e7c2b52ddb5f8`.
  Its configuration declares Linux amd64 and user `librarr`; no multi-platform
  index was returned. The Dockerfile creates UID 1000 and includes BusyBox wget.
- `internal/config/config.go` owns exact environment keys and settings-file
  precedence: UI-saved settings override environment variables on restart.
- `internal/search/zlibrary.go` and `internal/download/direct.go` implement
  authenticated direct downloads using operator-supplied endpoint and credentials.
- `internal/torznab/xml.go` labels direct DownloadURL enclosures as BitTorrent;
  its MD5 fallback points at `/api/download/nzb/`, without a matching download
  route in `internal/api/router.go`. This does not implement a direct-file
  download client for Bookshelf. Do not enable the reverse indexer connection.
- `internal/download/watcher.go` supports qBittorrent/Transmission and SABnzbd.
  There is no NZBGet client. Shared `/data` paths work with this repository's
  qBittorrent mount; use `http://gluetun:8080` on `torrents` because the client
  shares Gluetun's network namespace and has no separate network endpoint.
- `internal/organize/targets.go` triggers Kavita, Komga and Audiobookshelf scans.
  Its Calibre operation copies files, without `calibredb` or metadata registration.
  Leave Calibre and duplicate Kavita/Komga copy destinations unset; readers scan
  the organized Librarr outputs directly.
- `internal/sources/load.go` accepts a local JSON registry; errors fall through
  to network defaults. Prepare a valid registry before launch and back it up separately from
  the application state. A minimal reviewed example enables public-domain/catalog services;
  Z-Library remains explicitly operator-configured.

Repository examples establish integration contracts, not live provider or reader
acceptance. No image was pulled and no container was started for this research.
