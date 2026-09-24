# Komga

Self-hosted comics and manga server: organize, browse, and read CBZ, CBR, PDF, and EPUB in the browser. OPDS support for apps like Tachiyomi; multi-user with reading progress and library-level permissions.

**Homepage:** https://komga.org  
**Docs:** https://komga.org/docs  
**GitHub:** https://github.com/gotson/komga  
**Docker:** https://hub.docker.com/r/gotson/komga  

Access via Caddy at **https://komga.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env`; confirm the comic and manga paths. Set `JAVA_TOOL_OPTIONS` only if the library needs a larger JVM heap.
2. From the stack directory: `docker compose up -d`.
3. Open the web UI, create the first user, then add separate libraries rooted at `/data/comics` and `/data/manga`.

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars from `stack.env` if needed → deploy.

## Library

The shared libraries are mounted read-only. Mylar3 can organize `/data/comics`
through its own writable media mount; Komga scans the same host directory
without modifying it. Keep `/config` on the local `komga_config` volume because
Komga does not support its database on NFS or CIFS. Library roots must not
overlap, so use `/data/comics` and `/data/manga`, never `/data`.

## Automatic comic conversion

The optional `docker-compose.normalizer.yml` override converts CBR/RAR, CB7/7z,
CBT/TAR, ZIP, and gzip/bzip2/xz/Zstandard TAR comics to CBZ. It also repairs
non-ZIP archives mislabeled `.cbz`. It copies page bytes and sidecars without
re-encoding images. PDF and EPUB stay in their native formats. Encrypted,
multipart, ACE, damaged, and unsafe archives are retained with an error report.
Page-image formats remain unchanged and must also be supported by Komga.

The worker uses `ghcr.io/bolens/homelab-comic-normalizer`, built from a digest-pinned
`archiving-utils` base and waits for files to remain
stable for two minutes. Conversion runs serially. Every archive member is checked
before publication, with a 2 GiB expanded-size limit and 10,000-member limit.
Original archives and receipts remain in separate recovery
storage, outside the scanned libraries. Existing CBZ destinations are never
overwritten, except when replacing the verified source itself because its CBZ
extension is incorrect. Container timestamps and compression metadata may change.

For an indexed book whose filename changes, Komga's native upgrade API transfers
metadata, reading progress, and read-list membership to a replacement book ID.
An interrupted or ambiguously accepted upgrade is retained for review rather
than submitted twice. Missing API connectivity prevents new conversions.

1. Verify the media mounts, then create a separate local recovery directory,
   for example `install -d -m 700 normalizer-state` in this stack directory.
   Set `NORMALIZER_STATE_PATH` in `stack.env` if using a different location.
2. Set `PUID` and `PGID` to the media owner. With a verified backup and Komga
   stopped, ensure its existing `komga_config` volume is writable by that user.
   The override runs both services as this user, including on NFS with root squash.
3. Run `./prepare-normalizer.sh`. It preserves existing configuration, requires
   existing media/state directories, and does not start containers.
4. Create a Komga administrator API key for this integration and put it in the
   ignored `normalizer.json`. Restrict that file to its owner with `chmod 600`.
   The key authorizes library scans, analysis, and book upgrades. Back it up
   privately with the reader configuration.
5. Disable Komga's automatic CBZ conversion and extension repair for these
   libraries so the worker owns format changes and preserves originals first.
6. Optionally set `MYLAR_CONFIG_PATH` to Mylar's directory containing `config.ini`
   and `mylar.db`, then add `"mylar": {"url": "http://mylar3:8090",
   "config_dir": "/mylar"}` to `normalizer.json`. The worker reads that directory
   read-only and uses Mylar's API to recheck only affected series after conversion.
7. Deploy from the checkout with both files:

   ```sh
   docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.normalizer.yml up -d
   ```

This override deliberately gives Komga writable library access for its native
upgrade operation and a read-only view of prepared archives. The worker also
has writable library access, a read-only root filesystem, no Linux capabilities,
no Docker socket, and no exposed port. It joins `ingress-public` for Komga and
`media-automation` for optional Mylar requests. Keep the default Compose file
alone for the original read-only reader deployment.

Inspect `docker compose ... logs comic-normalizer` and the recovery directory's
`status.json` for conversion errors. Container health checks worker liveness, conversion errors, and stale scans. Each `jobs/*/receipt.json` records source
and output digests, member inventories, API state, and replacement book IDs.
Back up this directory; it contains the retained originals. Do not delete a
pending receipt or retry a submitted upgrade without checking reader state.
To stop automation, stop `comic-normalizer`. Restore a selected original from its
receipt after stopping writers and verifying its saved checksum. Do not restore
an old reader database over newer reading progress to undo one conversion.

Regression tests use disposable archives and a separately installed converter:

```sh
ARCHIVING_UTILS_BIN=/path/to/archiving-utils/bin/archiving-utils python3 normalizer/test_normalize.py
```

## Completed-download maintenance

After enabling the normalizer and its Mylar integration, optionally add
`docker-compose.maintenance.yml` after the normalizer override. Set
`MYLAR_COMPLETED_PATH` to the existing completed-comics directory and
`MYLAR_DDL_CACHE_PATH` to Mylar's existing DDL cache, then run
`./prepare-maintenance.sh`. This adds write access to that directory for the
worker. Only the cache is writable under Mylar's configuration directory. Set
`maintenance.ddl_cache` to `/ddl-cache` and `maintenance.enabled` to `true` in the private `normalizer.json`.
Mylar must have the reliability API enhancements and automatic failed-download handling
enabled. The default scan interval is 300 seconds with a 600-second stability
window. Start only the worker with all three Compose files:

```bash
docker compose --env-file stack.env -f docker-compose.yml -f docker-compose.normalizer.yml -f docker-compose.maintenance.yml up -d --no-deps comic-normalizer
```

Cleanup waits for Mylar's post-processing worker to be idle. It validates stable
archives in completed downloads and the DDL cache, then compares them with matching, READY Komga library files. It removes a
completed copy only when ordered page names and hashes match and every extra
source file is preserved. Added library metadata is allowed. Different editions,
unmatched names, unsupported formats, symlinks, and files changing during a scan
are retained. Library files are never removed by maintenance.

HTML responses saved as comics and confirmed decoder corruption are copied to `maintenance/quarantine` under
`NORMALIZER_STATE_PATH`. The worker verifies its SHA-256 before removing the
completed copy. Receipts record the source, recovery copy, and retry outcome.
A unique Mylar release mapping can trigger one native failed-release replacement
search. Ambiguous mappings remain for manual review. An interrupted API request
is recorded as `retry_unconfirmed` and is never blindly repeated.

Active or queued DDL files are excluded, even when their size stops changing.
Quarantined originals have no automatic expiry. Review receipts before removing
them. Preserve the entire state directory in backups. `maintenance-status.json`
records checks, retained-file warnings, and errors. Docker health fails on errors
or stale checks. Add a Docker Container monitor for the worker's actual container
name in Uptime Kuma, with your existing notification routes, to show these faults
on its dashboard. No additional public endpoint or credentials are needed there.

Repository CI runs the conversion and maintenance regressions inside the pinned
converter image with no network or live mounts. To run maintenance checks locally
with the same archiving-utils executable:

```bash
ARCHIVING_UTILS_BIN=/path/to/archiving-utils/bin/archiving-utils python3 normalizer/test_maintenance.py
```

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `komga:25600`) |
| **Network** | `ingress-public` for dedicated Caddy-to-service traffic |
| **Images** | `gotson/komga:1.27.1` (digest-pinned in Compose) |
| **Storage** | Local `komga_config`; `${KOMGA_COMICS_PATH}` → `/data/comics` and `${KOMGA_MANGA_PATH}` → `/data/manga`, both read-only |

## Caddy reverse proxy

Add a site block for the Komga hostname (e.g. `komga.yourdomain.com`):

```
komga.yourdomain.com {
	reverse_proxy komga:25600
}
```

## Health and monitoring

Komga does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://komga.yourdomain.com`) in Uptime Kuma.

## Media preparation prerequisite

Verify the configured media directories exist on the intended filesystem before
running preparation. The helper refuses to create missing media paths. Directory
existence alone does not verify the remote mount; check its source and access.

The maintenance worker also publishes a bounded filename-only report to Mylar's
**Import problems** view using the existing primary API key. Deploy the corresponding
Mylar image before restarting an updated maintenance worker. Reports identify
unmatched files, validation failures, and quarantine retry status without sending
credentials or download URLs. Active `.mylar-unpack-*` staging directories are excluded.

The maintenance report also supplies Mylar's **Post-processing** monitor with up to
50 conversion receipts or failures, including original format, output format, and
verification phase. It reads existing recovery receipts and preserves the conversion
workflow. Reports expose filenames and fixed status labels, without private paths
or raw errors. Metadata is reported as preserved, since normalization does not retag
comics. Update the Mylar image before restarting the maintenance worker.


### Automatic recovery of unmatched imports

Maintenance also checks settled files against explicit Mylar issue identifiers,
bounded ZIP ComicInfo metadata, and exact series/year/issue filenames. Ambiguous
editions and conflicting evidence remain on Import problems. This does not guess
from similar titles, add series, or change failed-release blacklisting.

To enable submission, set `maintenance.auto_import` to `true` and set
`maintenance.mylar_ddl_cache` to the same DDL cache directory **as seen inside
Mylar** (for example `/config/mylar/cache`). The normalizer uses its existing
`maintenance.ddl_cache` mount for this shared directory. Verify both paths refer
to the same files before enabling it. Deploy the updated Mylar report labels first.
Portable examples leave automatic submission disabled.

Recovery submits at most one validated CBZ/CBR per idle maintenance cycle, using a
hash-verified copy in an isolated `.mylar-recovery-*` cache directory. Originals
stay in place for existing verified duplicate cleanup. Attempt receipts under
`maintenance/imports` prevent automatic repeat submissions, including after a
restart or lost response. A submission still unresolved after 30 minutes requires
review; queued does not mean imported. Other archive formats remain for conversion
and review. Staging directories are excluded from ordinary completed-file scans.
Do not delete attempt receipts to retry without checking Mylar history and its
post-processing queue first.

Recovery uses Mylar's local-cache processing mode so NZBGet path remapping does not
redirect the staged copy. The Mylar image preserves that mode through the queue's
optional download-info field. The client accepts the native plain-text forceProcess
acknowledgment; an unknown response still requires review rather than resubmission.

### Guided matching and series aliases

With maintenance and Mylar integration configured, the worker publishes bounded
candidate proposals for ambiguous imports to Mylar's **Import problems** and
**Activity** pages. Follow the proposal link, compare series/year/issue evidence,
select a candidate explicitly, then confirm. Candidate ranking is a suggestion,
not permission to import. This explicit action is separate from the optional
`maintenance.auto_import` setting for automatic unique matches.

Worker-owned source tokens and versions distinguish same-named files and reject
changed sources. Guided submission validates the archive and stages at most one
CBZ/CBR copy per idle maintenance cycle in the existing shared DDL cache. Originals
remain in place. Other formats must be converted before submission. The configured
`maintenance.mylar_ddl_cache` path must identify that cache inside Mylar, just as
for automatic recovery. The existing read-only Mylar configuration mount supplies
the primary API key; browser requests never supply source paths.

**Save an exact series alias** is available only with an explicit, consistent source
series/start-year scope and matching selected issue/year evidence. It remains
inactive until source/library content equivalence confirms the import. Later files
use the alias only for that exact scope and a unique eligible issue; conflicting
evidence remains for review. Review or disable confirmed aliases from Activity.
Submitted does not mean imported, and an uncertain response is not automatically
resubmitted. Preserve guided proposal/command receipts with the entire worker
state directory and Mylar's private `workflow.sqlite` journal.

Deploy the updated Mylar image before the maintenance worker. Missing guided API
support leaves existing receipts intact. Preparation preserves private settings;
no new environment variable, public service, mount, credential or worker concurrency
is required. Mylar's Activity page also reports cooldown waits, intake pauses and
DDL/NZB handoff state; see its [workflow controls](../mylar3/README.md#activity-and-workflow-controls).

## Worker image updates

`COMIC_NORMALIZER_IMAGE` selects the published worker image. It includes the Python
worker and converter, so deployments need only the Compose files, private JSON
configuration, and existing media/state mounts. Preparation still uses the tracked
JSON example. No source-code bind mount is required. Linux amd64 is verified.
Select a `sha-<full-commit>` tag or digest as described in
[custom image builds](../../documents/CUSTOM-IMAGES.md).

Before updating, stop library writers and verify a backup and isolated restore of
reader/Mylar databases, configuration, worker state (including retained originals),
and affected media. Pull the chosen image and recreate only `comic-normalizer`
with the same Compose overrides. Verify baseline records, media hashes, worker
receipts and health before removing temporary update backups. Restore the previous
image and verified backup if data is missing or corrupt. Keep routine backups.

Build locally from the repository root with
`docker build -t homelab-comic-normalizer:local stacks/komga/normalizer`.
The build runs disposable archive regressions; the final image excludes tests
and example configuration. Private runtime JSON is excluded from its build context.
