# Calibre-Web

Web UI for an existing Calibre library: browse, read, and download eBooks. Uses your Calibre database (`metadata.db`) and book files. Supports OPDS, optional ebook conversion (Docker mod), and Google OAuth.

**Homepage:** https://github.com/janeczku/calibre-web
**Docker (LinuxServer):** https://docs.linuxserver.io/images/docker-calibre-web

Access via Caddy at **https://calibre-web.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env`, set `CALIBRE_BOOKS_PATH`, and optionally set `PUID`, `PGID`, or `UMASK`.
2. From the stack directory: `docker compose up -d`.
3. Open the web UI. On first run you'll be asked for the Calibre database path: set **/books** (or the path where your `metadata.db` lives inside the container).
4. Default login: **admin** with the image's default password, change immediately in Admin → Edit user.

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars from `stack.env` if needed → deploy.

## Library

`CALIBRE_BOOKS_PATH` is bind-mounted at `/books` and defaults to
`/mnt/unraid/media/books`. The directory must contain `metadata.db` and your
book files. On first setup in the UI, set the database path to **/books**.

`KAVITA_CALIBRE_EXPORT_PATH` is mounted at `/kavita-export`. Export books with
Calibre's Save-to-Disk layout, then configure Kavita's Book library to scan
`/data/calibre-books`. This keeps Kavita out of Calibre's private database
layout and embeds current Calibre metadata in the exported copies.

The host can automate the export with
`scripts/calibre-kavita-sync.sh`. The matching systemd service and daily timer
are in `scripts/systemd/calibre-kavita-sync.*`. The job preserves native EPUBs and converts AZW3, then MOBI only when EPUB is
absent. It locks overlapping runs and verifies the mounted filesystems, stable
registered inventory, exported IDs and book integrity before removing stale
exports and requesting a Kavita scan.

By default, only books registered in `metadata.db` are exported. Downloading
files into the library directory does not register them. Set
`CALIBRE_INCLUDE_UNREGISTERED_EPUBS=true` to also export conservative new-work
EPUB candidates without importing them into Calibre or changing source files.
Install `scripts/calibre-catalog-import.py` as
`/usr/local/libexec/calibre-catalog-import`, or set `CALIBRE_IMPORT_PLANNER` to
its installed path. Exact binary duplicates, existing titles/ISBNs, ambiguous
editions and unreadable metadata are excluded. The job checks candidate and
catalog stability before publication. Unsupported unregistered formats still
require review.

Set `CALIBRE_NORMALIZE_LEGACY_EPUBS=true` to convert exported copies with
unsupported package versions to EPUB 2. Original source books are preserved.
Without this option, unsupported package versions stop publication. For a count discrepancy, use the
read-only `scripts/calibre-catalog-import.py /path/to/library` planner. Its stdout
contains counts; an optional `--manifest` requires an existing owned `0700`
directory outside Git and writes a new `0600` review file containing private
paths and metadata. Review candidates, back up and verify a restore of the
catalog, application state and affected files, then rehearse supported
`calibredb add` against a separate copy. Preserve existing book IDs, UUIDs and
paths to retain Calibre-Web shelves and progress. The planner never imports.

The host export helper defaults `CALIBRE_SOURCE_MOUNT` and
`KAVITA_EXPORT_MOUNT` to `/mnt/unraid/media`. Set them to the exact covering
mount points for your library and export destination when different. It refuses
to create directories when those mounts are absent. `KAVITA_SYNC_LOCK` defaults
to `/run/lock/calibre-kavita-sync.lock`; all invocations must use the same lock.
`CALIBRE_EXPORT_UID` and `CALIBRE_EXPORT_GID` default to `1000`. Set these in the
service environment together with the existing container, path and export-user
overrides as needed.

## Optional automatic Calibre registration

The host coordinator `scripts/calibre-kavita-catalog-runner.py` can register clear
new EPUB works before the daily export. It is disabled unless
`CALIBRE_AUTO_REGISTER=true`. It uses checksum-validated ISBNs, normalizing
ISBN-10/13. Imports pass the validated canonical ISBN explicitly and verify it
against the resulting catalog. Conservative title/author matching applies when
ISBN is absent. Different
or conflicting editions are held for review. Calibre notes and recycle-bin
contents are excluded.

Install the planner, transaction helper, coordinator and export helper as
root-owned files under `/usr/local/libexec`. Use the matching example drop-in
under `scripts/systemd/calibre-kavita-sync.service.d/`. Configure the exact media
and backup mounts, library path, container names and private backup state path.
The coordinator requires the LinuxServer Calibre-Web supervised service and the
Calibre 9.16 Docker mod. Another Calibre minor version refuses operations until
preservation behavior has been checked. Native Calibre commands use a temporary
writable configuration directory. Their process-local wrapper prevents automatic
recycle-bin expiry even during list/export commands, preserving existing trash
without changing the library retention setting.

When candidates exist, it pauses the configured download writer and Calibre-Web
application, verifies a full backup and isolated restore, rehearses the import
in separate state and checks existing IDs, media, ISBNs and permissions before
updating the real catalog. It restores the prior catalog after a recoverable
failure. Uncertain recovery retains backups and keeps writers paused for repair.
Successful catalog runs remove only their temporary copies, resume the original
services and publish a complete verified export before requesting Kavita's scan.
The root-only state directory retains the latest review plan, counts and private
failure diagnostics. No new public service or port is created.

The normal export remains catalog-based. Leave
`CALIBRE_INCLUDE_UNREGISTERED_EPUBS=false` when keeping both applications aligned.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `calibre-web:8083`) |
| **Network** | `ingress-public` for dedicated Caddy-to-service traffic |
| **Images** | `lscr.io/linuxserver/calibre-web:latest` |
| **Storage** | `calibre_web_config`, `${CALIBRE_BOOKS_PATH}` → `/books`, `${KAVITA_CALIBRE_EXPORT_PATH}` → `/kavita-export`; `UMASK=002` keeps shared files group-writable |

## Caddy reverse proxy

Add a site block for the Calibre-Web hostname (e.g. `calibre-web.yourdomain.com`):

```
calibre-web.yourdomain.com {
	reverse_proxy calibre-web:8083
}
```

## Health and monitoring

Calibre-Web does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://calibre-web.yourdomain.com`) in Uptime Kuma.

## Optional: ebook conversion

For in-app conversion (e.g. EPUB to PDF), add to `stack.env` (x86-64 only):

```
DOCKER_MODS=linuxserver/mods:universal-calibre
```

Then in Calibre-Web Admin → Basic Configuration → External Binaries, set the path to Calibre E-book converter to `/usr/bin/` (directory) or `/usr/bin/ebook-convert` as per LinuxServer docs.
