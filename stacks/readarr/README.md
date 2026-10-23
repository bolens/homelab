# Bookshelf (Hardcover)

Bookshelf is a Readarr revival for managing ebook or audiobook collections with
Usenet and torrents. This stack uses its Hardcover-backed image for higher-quality
metadata.

**GitHub:** https://github.com/pennydreadful/bookshelf

**Docker image:** https://github.com/pennydreadful/bookshelf/pkgs/container/bookshelf

## Quick start

1. **Shared networks and torrent download volume** (if not already created):
   ```bash
   docker network create usenet
   docker network create torrents
   mkdir -p /mnt/unraid/media/books /mnt/unraid/media/downloads/{usenet,torrents}
   ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set `TZ`, `PUID`, and `PGID`.
   - Confirm `READARR_MEDIA_PATH` (default `/mnt/unraid/media`).
   - Set `HARDCOVER_AUTH` to the complete Hardcover API token, including the
     `Bearer` prefix.
   - Generate `RREADING_GLASSES_POSTGRES_PASSWORD` with
     `openssl rand -hex 32`.
3. **Deploy**
   - From this directory:
     ```bash
     docker compose --env-file stack.env up -d
     ```
4. **First run**
   - Access Bookshelf via Caddy (for example `https://readarr.home` or `https://readarr.yourdomain.com`).
   - Configure:
     - **Download client**: NZBGet and/or qBittorrent.
     - **Indexers**: from Prowlarr/NZBHydra 2.
     - **Root folder**: `/data/books`.
     - **NZBGet remote path mapping**: host `nzbget`, remote
       `/downloads/`, local `/data/downloads/usenet/`.

## Migrating from Readarr

The Hardcover image is not compatible with an existing Readarr database. This
stack therefore mounts a new `bookshelf_config` volume at `/config`; it does not
reuse or delete the old `readarr_config` volume. Reconfigure the new instance
from scratch, including its root folder, download clients, indexers, and library.
The retained old volume allows rollback to the previous image and configuration.

Do not copy `readarr.db` into the new volume. Bookshelf's `softcover` image is the
backward-compatible option for an in-place Readarr database, but it uses Goodreads
rather than Hardcover metadata.

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `readarr:8787`)         |
| **Networks** | `ingress-admin`, `usenet`, `torrents`, plus default                         |
| **Image**  | `ghcr.io/pennydreadful/bookshelf:hardcover-v0.4.21.182`                 |
| **Env**    | `TZ`, `PUID`, `PGID`, `READARR_MEDIA_PATH`, optional `READARR__*` |
| **Storage**| `bookshelf_config` → `/config`, `${READARR_MEDIA_PATH}` → `/data`; use `/data/books` and `/data/downloads/*` |

Bookshelf uses the private `rreading-glasses:8788` endpoint for metadata. The
metadata proxy uses the supplied Hardcover token and stores its cache in the
`rreading_glasses_data` PostgreSQL volume. Neither service publishes a host
port. The upstream `hardcover` and PostgreSQL major-version tags intentionally
track compatible updates; review release notes before pulling newer images.

The local rreading-glasses image is built from pinned upstream commit
`a2939b625d91389d3f0a3e58cbc3bfa7ebb8390a`. The included patch reduces its
hard-coded Hardcover GraphQL batch size from 25 to 1 because the hosted API
rejects larger combined queries with `top_level_limit_exceeded` or rate-limit
responses. It retries transient HTTP 429 and Hardcover-specific rate-limit HTTP
403 responses with bounded backoff instead of returning an empty search result.

The search-cache patch keeps successfully hydrated search metadata in the existing
work and edition cache. This avoids fetching the same details again when Bookshelf
loads its result cards or another search finds the same book. Complete, nonempty
search results are cached for 15 minutes. Empty, partial, failed, and cancelled
searches are retried on the next request. Cold searches still depend on Hardcover
and the one-request-per-second queue. Both patches apply to the pinned source;
the image build runs the search-cache regression tests before compiling.

To use the CI image, remove the metadata service's `build:` block and set its
`image:` to `ghcr.io/bolens/homelab-rreading-glasses:latest` or a commit tag from
[custom-image CI](../../documents/CUSTOM-IMAGES.md). Local builds remain the default.

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
readarr.home, readarr.local {
  tls internal
  reverse_proxy readarr:8787
}
```

## Media preparation prerequisite

Verify the configured media directories exist on the intended filesystem before
running preparation. The helper refuses to create missing media paths. Directory
existence alone does not verify the remote mount; check its source and access.

## Librarr companion

[Librarr](../librarr/README.md) provides a separate direct-download acquisition
path. With the same host media root, this stack can see its organized ebook
output at `/data/librarr/ebooks`. Use Bookshelf's Manual Import for reviewed files
and retain the source copy. Bookshelf's existing indexers and download clients
remain the monitored-book automation path.

Do not add Librarr's mixed Torznab feed as a Z-Library indexer: the inspected
Librarr v1.4.1 feed does not translate authenticated direct ebook downloads into
Bookshelf's torrent/Usenet download-client workflow. File visibility does not
establish an automatic successful import or fulfillment.
