# Librarr

Book, audiobook and manga acquisition with direct downloads, Prowlarr search,
and optional qBittorrent downloads. Existing library managers remain independent.

**Upstream:** <https://github.com/JeremiahM37/librarr>
**Image:** <https://github.com/JeremiahM37/librarr/pkgs/container/librarr>
**Inspected release:** [v1.4.1](https://github.com/JeremiahM37/librarr/releases/tag/v1.4.1)

## Setup

1. Copy `stack.env.example` to `stack.env`. Set `LIBRARR_CONFIG_PATH` to local
   application storage and `LIBRARR_MEDIA_PATH` to the existing media root used by
   qBittorrent. Set the administrator login and generate two distinct API keys.
   Keep `stack.env` private. Choose `PUID` and `PGID` for the owning media user;
   Compose sets `user:` directly because this image has no LinuxServer init.
2. Verify the media directory is on the expected mounted filesystem and writable
   by that user. Preparation refuses missing media paths; Compose also refuses
   to create missing bind sources. Do not create a replacement for an absent
   remote mount. On a verified mount, create these new, dedicated directories as
   the media owner before enabling readers:

   ```text
   librarr/ebooks
   librarr/manga
   audiobooks/Librarr
   downloads/torrents/librarr/ebooks
   downloads/torrents/librarr/audiobooks
   downloads/torrents/librarr/manga
   ```

3. Run `./prepare-stack.sh`. It creates missing local config storage, copies the
   public sources example to ignored `sources.json`, preserves existing files,
   ensures default external networks, and synchronizes `stack.env` to `.env`.
   It never starts containers. Verify config ownership matches `PUID`/`PGID` and
   restrict configuration and environment files to their owner. Do not recursively
   change ownership on existing shared media.
4. Review `sources.json`. The example includes Gutenberg, Open Library, LibriVox
   and Standard Ebooks. Librarr reads this local registry instead of fetching a
   changing remote source list. A malformed or missing registry can make upstream
   fall back to remote defaults: keep the local file valid and back it up.
5. Configure `caddy_snippet.conf` and import it into your Caddy configuration.
   Default Compose has no host port. The example includes optional public routes;
   enable them only with the intended access policy and app authentication.
6. For a deployment, from this directory:

   ```bash
   docker compose --env-file stack.env up -d
   ```

The image is pinned by release and manifest digest. The inspected published image
is **Linux amd64**; other hosts need a separately reviewed upstream build.
Application state stays on local storage at `/config`, including SQLite and
`settings.json`. Media is bound at `/data`. The writable root mount gives Librarr
access to that whole media tree; retain the dedicated output paths below and do
not configure it to reorganize another application's collection.

## Compatible stacks

| Stack | Connection | Setup and limits |
| --- | --- | --- |
| Prowlarr | Librarr queries `http://prowlarr:9696` on `media-automation` | Set `PROWLARR_URL` and its API key. Keep book categories enabled. Do not add Librarr back as a Prowlarr indexer: that creates recursive searches. |
| qBittorrent + Gluetun | `http://gluetun:8080` on `torrents` | Set `TORRENT_CLIENT`, `QB_URL`, `QB_USER` and `QB_PASS`. Both stacks must bind the same host media root at `/data`. |
| Kavita | Dedicated read-only ebook and manga roots; optional scan API | Select the reader override below and add separate libraries; set credentials and exact library IDs for scan notifications. |
| Komga | Dedicated read-only manga root; optional scan API | Select its reader override and add a separate manga library; set credentials and the library ID. |
| Audiobookshelf | Existing audiobook mount, plus optional scan API | `AUDIOBOOK_DIR=/data/audiobooks/Librarr` appears under `/audiobooks/Librarr` when its configured root is the same media tree. Set `ABS_URL`, token and the existing audiobook library ID. |
| Bookshelf / Readarr | Reviewed manual import | Its existing `/data` mount sees `/data/librarr/ebooks`. Select a known book and use Manual Import after review; keep the original copy. This is not automatic monitored-book fulfillment. |
| Calibre-Web | Reviewed upload/import | Download an organized EPUB from Librarr and use Calibre-Web's enabled upload flow, or use supported `calibredb add` after verified backup and rehearsal. Raw copies do not register in `metadata.db`. |
| NZBGet | Optional SABnzbd API adapter | Select `docker-compose.nzbget.yml` and configure the dedicated category/path mapping below. The native Librarr Download button sends NZBs to the existing NZBGet. |

Librarr assigns `librarr-ebooks`, `librarr-audiobooks` and `librarr-manga` torrent
categories. Their save paths are `/data/downloads/torrents/librarr/{ebooks,audiobooks,manga}`.
Imports copy the payload; automatic torrent removal is disabled so seeding can
continue. qBittorrent downloads traverse Gluetun, but Librarr's direct downloads
and metadata requests use its ordinary container egress. Network membership
alone does not send Librarr traffic through a VPN.

Z-Library direct ebook links are not torrents or NZBs. Although Librarr exposes
`/torznab/api`, the inspected release does not translate those downloads into a
compatible Bookshelf download-client workflow. Leave that connection disabled.
Do not feed its mixed direct-download results into qBittorrent or NZBGet.

## Optional reader setup

In Kavita's and Komga's own `stack.env`, set `LIBRARR_MEDIA_PATH` to the identical
host root configured here. Existing library bindings and IDs remain unchanged.
Select the appropriate override in each reader stack:

```bash
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.librarr.yml up -d
```

Kavita gains `/data/librarr-books` and `/data/librarr-manga`; create separate Book
and Manga libraries rooted there. Komga gains `/data/librarr-manga`; create a
separate non-overlapping library. Do not add `/data` as a reader library root or
point these libraries at Calibre exports. The overrides require existing output
directories, mount them read-only, and never modify media or the readers' databases.
Their existing Caddy routes remain unchanged.

For scan APIs, explicitly ensure the readers' existing `ingress-public` network
exists and select Librarr's additional network:

```bash
docker network inspect ingress-public >/dev/null
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.readers.yml up -d
```

This adds Librarr to the reader ingress network, allowing direct API access to
Kavita `:5000`, Komga `:25600` and Audiobookshelf `:80`. It also permits lateral
network access to other members; no host port or public route is added by the
override. Configure only the chosen integrations and their exact library IDs in
`stack.env` or the authenticated UI. Unset IDs can trigger broader Kavita scans.
Leave `KAVITA_LIBRARY_PATH`, `KAVITA_MANGA_LIBRARY_PATH`, `KOMGA_LIBRARY_PATH` and
`CALIBRE_LIBRARY_PATH` unset: readers already see the organized output, and
additional copying could duplicate books or overwrite another writer's files.

Kavita/Komga may also scan normally without Librarr's scan credentials. Reader
preparation does not activate these overrides or create their missing media paths.
Use all previously selected reader overrides as well when building its deployment
command; do not accidentally replace an existing provider or coordination override.

## Z-Library

Set `ZLIBRARY_ENABLED=true`, an independently verified `ZLIBRARY_URL`, and your
`ZLIBRARY_EMAIL` / `ZLIBRARY_PASSWORD` in the ignored environment file, or use
Librarr's authenticated settings UI. No provider address or account is supplied.
Provider availability, account limits and a successful authorized download must be
checked after configuration; repository validation cannot establish them.

Librarr handles authentication, search and downloading itself. Ebooks are organized
under `/data/librarr/ebooks`, where the optional Kavita mount can read them.
The upstream source registry and endpoint are part of the trust boundary because
the service sends provider credentials to that endpoint.

## Settings and verification

Upstream persists UI changes in `/config/settings.json`, which overrides environment
values on restart. Compose defaults do not forcibly reset previously saved settings.
Review the authenticated settings after changing credentials, paths, import mode or
scheduler flags. Initial examples disable scheduling, automatic acquisition,
author monitoring, wishlist cleanup and automatic upgrades.

After a configured deployment, verify:

- `/health` returns success and the configured login protects the UI and API.
- Prowlarr and qBittorrent connection tests succeed without a reverse search loop.
- A permitted test download reaches its intended dedicated directory with readable
  ownership, retained torrent payload and the expected category.
- Each enabled reader sees that specific file and scan notifications target the
  intended library; confirm existing catalogs and reading progress are preserved.

A passing health check alone does not verify sources, downloaded content or reader
imports. `/metrics` is available for optional internal Prometheus collection;
this change does not add a live scrape target or monitor.

## Backup, upgrade and recovery

Before a live update, record the image digest, settings, database counts and
existing library baseline. Quiesce Librarr and back up the complete local config
bind (including SQLite WAL/SHM companions), `sources.json`, environment and ingress
configuration privately outside Git. Preserve any media the operation can modify;
a routine image update does not require copying unrelated libraries. Restore to
an isolated location and verify file integrity and every SQLite database before
updating. Back up each reader's state before enabling or changing its libraries.

After updating, compare catalog records and file inventory with the baseline and
check authentication, an allowed acquisition and selected reader behavior. On
missing or corrupt data, stop the updated service and restore the verified state
with its prior image/configuration. A previous binary may not read migrated state.
Do not remove state or volumes as routine rollback. Remove only temporary copies
created for that operation after successful verification.

If a download finishes but a reader is empty, check the selected override, matching
host roots, UID/GID and dedicated library ID before changing credentials. For a
Calibre-Web discrepancy, verify registration in `metadata.db`; adding loose files
or rescanning Kavita does not register a Calibre book.

## Flood / rTorrent

The optional `docker-compose.flood.yml` runs a restricted Transmission RPC adapter
for Librarr v1.4.1 against Flood's existing rTorrent socket. Select Flood's matching
`docker-compose.librarr.yml` first, preserving original overrides, images, accounts
and state. Both stacks must see the same dedicated download directories at
`/data/downloads/librarr/{ebooks,audiobooks,manga}`. Set unique `BRIDGE_USER` and
`BRIDGE_PASSWORD` values, the actual external rTorrent state volume name, and its
UID/GID. Select this override alongside Librarr's base Compose definition.

The adapter publishes no host port or ingress and joins only `torrents`. Its
read-only state volume contains an administrative Unix socket, so protect adapter
credentials. It requires Basic authentication and a session handshake, rejects
arbitrary RPC and deletion, and lists only torrents whose Librarr category and
exact dedicated save path match. Server enforcement protects unrelated torrents.
This is a limited protocol adapter, not a full Transmission implementation.

UI-saved settings override environment configuration. Verify the effective client,
paths, copy imports and disabled automatic torrent removal before acquisition.
The connection test must reach the original daemon. A submitted torrent must
appear in Flood and reach the expected mounted directory before being counted as
downloaded. Adapter boundary tests run with:

```sh
python3 -m unittest discover -s stacks/librarr/flood-adapter -v
```

For Bookshelf supplementation, inventory monitored missing ebooks, exclude owned
and queued books, and select unambiguous title/author/format matches. Keep private
acquisition receipts to make retries idempotent. Register completed files through
Bookshelf's supported manual-import flow using copy mode. A file on the media
mount alone does not fulfill a Bookshelf book. Skip uncertain editions and report
pending, unavailable and imported items separately. Provider credentials remain
operator supplied.

The one-shot `bookshelf_supplement.py` helper defaults to review mode. Supply
internal service URLs, an owner-only JSON keys file with `bookshelf_api_key` and
`librarr_api_key`, and an owner-only receipt directory. `--limit` bounds each pass.
Inspect candidate receipts before `--apply`; the apply pass rechecks ownership and
queues. An intent receipt is written before submission, and uncertain submissions
require review instead of automatic retry. Rejections count as failures; existing
receipts are reported as `receipt_blocked`, separately from owned or queued books.
The helper requires full title and author evidence and rejects conflicting author
metadata. It does not schedule itself or
claim that accepted downloads have finished or been imported. Copy-import completed
files through Bookshelf and verify their book IDs separately.

## NZBGet downloads from Librarr

Librarr v1.4.1 speaks SABnzbd's API. The optional `docker-compose.nzbget.yml`
provides only its required version, addurl, queue and history operations and
forwards them to NZBGet's JSON-RPC API. No black-hole directory is needed.
The adapter has no host port or ingress route and joins only `media-automation`.
It requires an independent random `SABNZBD_API_KEY` and private NZBGet credentials.
A restricted NZBGet account can submit and poll; an add-only account cannot poll.
Existing downloader clients and their categories remain independent.

Verify NZBGet's actual `DestDir`, `AppendCategoryDir`, and category settings first.
With `DestDir=/downloads/completed` and `AppendCategoryDir=yes`, the unconfigured
category `librarr` writes under `/downloads/completed/librarr`. If category settings
already exist, verify their destination or choose a new dedicated category.
The default mapping assumes NZBGet binds the same host media root's
`downloads/usenet` directory at `/downloads`, while Librarr sees the media root at
`/data`. Thus files reside at `downloads/usenet/completed/librarr/<release>` on
that host media filesystem. Set `NZBGET_COMPLETED_ROOT` and `LIBRARR_NZB_ROOT`
together for other layouts; mapping does not create mounts or move files.
NZBGet's temporary/intermediate download directory remains its existing one.

Generate the adapter key separately, enter credentials privately, and select the
additional override alongside every previously selected override. For Flood plus
NZBGet, for example:

```bash
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.flood.yml -f docker-compose.nzbget.yml up -d
```

UI-saved settings take precedence. Set Librarr's SABnzbd URL to
`http://librarr-nzbget-adapter:8080`, its API key to the adapter key and its category
to the configured `NZBGET_CATEGORY`. Run the SABnzbd connection test. Select a known
NZB result and verify its returned ID appears in NZBGet and Librarr Downloads.
Direct ebook links remain direct downloads; torrents still use the configured
torrent client. The adapter does not convert one protocol into another.

Only jobs with the dedicated category and adapter duplicate-key prefix are
reported. Completion requires an ordinary successful NZB history status, no failed
script/move stage, and a destination below the configured dedicated root. Manual
success overrides and warnings are not automatically imported. Native Librarr
v1.4.1 moves supported NZB media into its organized library even when
`IMPORT_MODE=copy`; the completed-download copy is not retained. Torrent seeding
payloads remain intact, and subsequent Bookshelf imports should still use copy
mode. Deletion and arbitrary API modes are rejected;
manage cancellation in NZBGet itself. A network error after submission can leave
an accepted job: inspect NZBGet before retrying. Native duplicate protection is
preserved. This does not automatically register completed files in Bookshelf;
use its supported reviewed copy-import flow above.

Before changing live Librarr settings, back up and verify its complete state as
above. Adding the adapter requires no NZBGet restart or image update when its
existing category/path behavior already matches. If that behavior needs changing,
first back up its configuration and queue state, verify an isolated restore, and
coordinate the shared downloader's lifecycle with its other clients. Preserve all
previously selected overrides when recreating Librarr or rolling back.
