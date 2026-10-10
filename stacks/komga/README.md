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

## Readable import notifications

The optional `ghcr.io/bolens/homelab-komga` image keeps the pinned Komga server
and replaces its next-UI assets with a checked presentation patch. Set
`KOMGA_IMAGE` to a published digest to opt in. Successful imports show catalog
series and issue metadata instead of the worker's internal staging path. If the
metadata lookup fails or takes more than 1.5 seconds, the toast uses a cleaned
filename. Its Open action still targets the imported book. Failure notifications
also omit the source directory; detailed import history remains unchanged.

The image builds the UI from the checksum-verified Komga 1.28.1 source and locked
npm dependencies. Its patch fails if the expected upstream notification changes.
The server, import paths, library files, API contracts and legacy UI are unchanged.
For a live update, verify an isolated restore of Komga's configuration/database,
drain normalizer upgrades, update only Komga, and verify catalog and reader state.
Retain the previous image for rollback. No library copy is needed for this UI change.

## Library

The shared libraries are mounted read-only. Mylar3 can organize `/data/comics`
through its own writable media mount; Komga scans the same host directory
without modifying it. Keep `/config` on the local `komga_config` volume because
Komga does not support its database on NFS or CIFS. Library roots must not
overlap, so use `/data/comics` and `/data/manga`, never `/data`.

## Coordination with Mylar

Use the optional `docker-compose.coordination.yml` after the normalizer override
when both applications can write the same comics. Matching Mylar images create a
private `media-writer` directory beside `config.ini` at startup. Set
`MYLAR_WRITER_STATE_PATH` to that existing directory on **local storage**, run
`./prepare-coordination.sh`, and set `"writer_state": "/mylar-writer"` in the
private `normalizer.json`. Both services must use the same owner UID. This adds
one narrow writable bind mount. The existing `/mylar` configuration mount stays
read-only, and Komga receives no coordination mount or configuration change.

Mylar post-processing, manual tagging, rescans, moves and deletions share an exclusive
lock with the worker's entire conversion/maintenance cycle. The worker skips busy
cycles without discarding existing error reports. A persistent recovery marker
remains while conversion receipts are unfinished, including asynchronous Komga
upgrades, ambiguous API timeouts and worker crashes. Mylar waits up to 180 seconds
for admission, then fails without running the blocked operation. Its result queue
still completes, allowing the caller to report failure rather than hang.

A matching worker reconciles its receipts before clearing the marker. A stored
identity binds the protocol to the worker state and jobs directories. Missing or
replaced recovery directories cannot be mistaken for an empty queue. Restoring to
new directories requires an idle, verified recovery and identity rebind before
resuming the worker. Missing,
linked, malformed or wrongly owned protocol state prevents writes. Do not delete
lock files or pending markers to clear a warning. If recovery cannot complete,
retain state and investigate the conversion receipts. An existing state directory
with a missing lock is rejected, including at startup, to avoid two lock owners.

Device numbers can change after a remount even when directory inodes are
unchanged. For `Normalizer recovery state identity changed`, follow Mylar's
[recovery binding checks](../mylar3/README.md#image-updates-and-rollback) for both
writers. Verify all conversion receipts are complete before rebinding. A matching
old device number and the exact current inode set distinguish this case from a
replaced recovery directory. Preserve retained originals and review copies.

Before enabling this override, drain existing worker upgrades and Mylar processing,
back up and restore-check both applications' affected state, and verify that both
mounts refer to the same directory. Deploy matching images and activate the worker
setting while idle. Update only `comic-normalizer` with `--no-deps` for worker-only
changes. An idle observation alone does not quiesce the worker: it can begin
another conversion during the container stop grace period. Acquire the existing
shared writer lock, verify recovery is clear, and quiesce the verified worker
process before stopping it. Release the shared lock before backing up state so
Mylar can continue. Keep Komga and NZBGet running. Never replace or restore coordination state
while either writer can run. Recovery or rollback must preserve pending markers
until asynchronous upgrades are verified complete. Existing installations keep
legacy worker behavior when `writer_state` is null or absent.

The source publication verifier reads the complete native correction census and
registration witnesses through the existing read-only configuration mount. Under
the shared writer it rechecks the candidate and every matched correct archive,
including all-row annual/deleted conflicts and physical path aliases. Its trusted
internal adapter requires explicit native-to-worker media root mappings and proves
that both config and coordination mounts refer to the same writer state. It makes
no API calls or registry writes. The worker Docker context contains generated
read-only native evidence definitions, checked by repository validation; regenerate
them with `python3 scripts/sync-publication-reader.py` after native reader changes.
Coordinated cycles validate complete authority before writing recovery bindings or
fences and recheck it before clearing the fence. They require explicit
`publication_roots` in the private normalizer configuration, for example
`[{"native":"/data/comics","worker":"/data/comics"}]` when those are the actual
native and worker library roots. Include every configured native library root;
the adapter never guesses a mapping or creates a missing mount. A missing marker,
incomplete census or missing mapping holds work. Initialize the matching native
authority through its restore-verified review protocol before worker admission.
Preparation preserves existing configuration and does not initialize authority.
Reader notifications now prepare bounded source/target/owner/census receipts under
the shared writer and dispatch scan/analyze/metadata refresh outside it. Changed
archives, owner/census or new native/worker publication work retain the request.
An uncertain reply is not automatically replayed. Coordinated conversion paths
without exact owned relocation or reviewed derivative lineage remain held.

Mylar HTTP calls are refused while the shared writer is held, including through
a different local lock registry. This prevents a guarded native API handler from
waiting for the calling worker's own lock. Local candidate checks remain under
exclusion; remote work must follow outside it and native final import must check
fresh evidence again. Fresh local owner/source checks now cover common/guided import, pack confirmation
and confirmed-comic pack cleanup. Ordinary duplicate cleanup additionally binds
the target's current exact native owner and protects all native catalog paths and
physical originals, including unregistered/deleted claims. It retains an exact
private original and immutable CAS receipt before unlink; changed proof or lost
acknowledgement stays held until fresh guarded reconciliation. Historical
supplement cleanup remains held for
reviewed derivative ownership. Coordinated common imports now persist a private
prepared receipt with exact source/stage bytes, native owner and complete census.
Dispatch requires native handoff protocol support from authenticated health.
After recovery fences clear, it rechecks those bindings under the writer,
records the attempt, releases the lock and submits to native Mylar. Uncertain
requests remain retained for review and are never automatically replayed. Native
Mylar independently checks its actual stage at submission and processing time.
Health and pending-work reads use a bounded immutable batch gathered before the
cycle lock. Missing batch results hold that work. Guided imports bind the exact
command and source version to native queue admission; a separate remote claim
cannot leave a staged import stranded. Pack catalog requests, verification
reports and guided acknowledgements use typed durable requests dispatched
outside the writer. Native Mylar independently verifies shared sources, current
catalog destinations and command bindings before recording an attempt. Lost
responses remain review holds. Pack cleanup waits for its acknowledged report,
and delayed reports cannot erase verified members. Extras placement rejects
registered payloads and protected originals before changing metadata. Remaining
mutation paths, reviewed derivative transitions and live acceptance are unfinished.
Keep the worker held until those contracts and matching image/live acceptance
are complete; this source change does not establish full prevention.

A separate tagger recovery marker also blocks worker admission after Mylar crashes.
Only Mylar may reconcile and clear that marker; worker recovery cannot bypass it.
Mylar's startup recovers publication before scans even when Legacy is selected.
After conversion is verified, the worker records a pending Mylar notification and
releases the lock before calling its guarded rescan API. Failed notifications remain
retryable without reconverting the archive. Notifications wait while any asynchronous
conversion still requires recovery.

Use matching Mylar and worker images for this protocol extension. Earlier workers
neither honor the tagger marker nor defer their rescan callback. Drain and verify
recovery before rollback; never switch an older writer onto pending v2 publication
state. Live coordination/canary/rollback acceptance still gates the Modern backend.

### Automatic tagging after conversion

With matching Mylar and worker images, set `"tag_converted": true` inside the
existing private `mylar` object to queue missing ComicInfo metadata after the
series rescan:

```json
"mylar": {
  "url": "http://mylar3:8090",
  "config_dir": "/mylar",
  "tag_converted": true,
  "refresh_reader_after_tagging": false
}
```

This opt-in requires the coordination override and nonempty `writer_state`.
It defaults to false. Mylar must have post-processing and Modern ComicRack
metadata enabled. Legacy or unsupported metadata settings leave jobs waiting
without switching backends. Existing ComicInfo is preserved even when manual
overwrite is enabled. Only an exact downloaded catalog path is eligible; extras,
ambiguous matches and changed archives require review instead of guessed tags.
Annual metadata uses its release volume.

The worker retains the rescan notification until Mylar acknowledges durable
admission. One failed notification does not block later receipts. Mylar's existing
post-processing worker handles one due tagging job while the download import
queue is idle. Requests survive restarts in `workflow.sqlite`, and a saved
publication token prevents repeating a committed tag operation. Provider failures
retry up to six attempts; unresolved catalog matches require review after 24 hours.
See **Manage → Post-processing → Converted comic tagging** for persistent status.

Deploy Mylar first, then the worker with `--no-deps`, and enable the opt-in only
after consumer verification. No additional mount, port, credential or dependency
is needed. Keep both applications' recovery state in backups. Existing completed
receipts are not bulk-retagged on upgrade; selected verified receipts can be
replayed operationally with their affected files preserved first. Set the independent `mylar.refresh_reader_after_tagging` boolean to `true` to
request Komga metadata refresh after Mylar confirms tagging is complete. It
defaults to `false` so other setups keep their own refresh schedule. The worker
polls the durable job without repeating its rescan or tagging, then requests Komga reanalysis for the verified replacement book ID.
Reanalysis refreshes the cached archive file list and schedules metadata import
after success, so newly added ComicInfo is discovered. A failed
request retains a retryable receipt; duplicate refresh requests are harmless.
Turning this setting off clears pending reader notifications without cancelling
Mylar tagging. When disabled, refresh Komga metadata manually or use its schedule. Turning the worker opt-in off stops new admissions; disable Mylar
metadata tagging to pause already admitted jobs.

### Scan Komga after completed additions

The normalizer can batch Komga library scans after new Mylar issues or annuals
reach their final library paths. Enable this independently of per-book metadata
refresh in the private `normalizer.json`:

```json
"reader_scan": {
  "enabled": true,
  "batch_size": 5,
  "max_wait_seconds": 300,
  "min_interval_seconds": 120
}
```

It defaults to disabled. Enabling requires shared writer coordination, the
read-only Mylar configuration mount (`mylar.config_dir`), and the existing Komga
administrator API key. Mylar, Komga and the worker must see the library at the
same absolute paths, normally `/data/comics`. No new port, mount or credential is
needed. Preparation preserves existing configuration; add the settings explicitly
when upgrading. Update only `comic-normalizer` with `--no-deps`.

On first activation, after acquiring its process lock, the worker records the
existing downloaded catalog even if a media writer is busy, without
opening archives or requesting scans. Subsequent additions must have a unique
Downloaded/Archived catalog entry, remain unchanged for `settle_seconds`, and be
CBZ files with one readable root `ComicInfo.xml`. Pending conversion, tagging or
metadata-repair receipts defer notification for their own paths; unrelated
conversions do not block completed additions. Missing, linked, ambiguous, untagged
or malformed files stay pending; a scan does not repair them. Deleted annuals are
excluded. Existing baseline books and untracked extras rely on existing conversion
notifications or scheduled scans.

The defaults request a scan after five ready additions, or flush a smaller batch
five minutes after its oldest item becomes ready. Requests are at least two
minutes apart, including retries after failures or restarts. Timing is evaluated
on worker cycles, so a busy writer or long conversion can delay a request. At most
50 new/pending archives are inspected each cycle, using only bounded ZIP directory
and ComicInfo reads; image pages are never decompressed for this check. Only the
unique library containing each ready file is requested. A scan covers that whole
library, so batching limits extra scan I/O; it does not limit Komga to those files.

`batch_size` accepts 1–100 and both timing settings accept 1–86400 seconds.
`reader-scan.json` persists the catalog baseline, pending additions and retry
pacing. `reader-scan-status.json` reports pending/ready counts and the last accepted
request; errors affect container health. Preserve these files with the normalizer
state. Corrupt state or changed catalog/root scope requires review and is never
silently reset. Disabling pauses notification and preserves queued state.

Reader book paths preserve literal filename punctuation, including `#`, `?`, and
percent signs. Only URI-form paths are URL-decoded before matching local files.

Komga's scheduled scans and conversion-recovery scans remain unchanged. The
independent `mylar.refresh_reader_after_tagging` setting still refreshes metadata
for an already indexed converted book. A successful scan request means Komga
accepted the job; discovery and analysis finish asynchronously in Komga.

## Automatic comic conversion

The optional `docker-compose.normalizer.yml` override converts CBR/RAR, CB7/7z,
CBT/TAR, ZIP, and gzip/bzip2/xz/Zstandard TAR comics to CBZ. It also repairs
non-ZIP archives mislabeled `.cbz`. It copies page bytes and sidecars without
re-encoding images. PDF conversion is a separate opt-in described below; EPUB stays native. Encrypted,
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

## Optional PDF reading copies

Set the following in private `normalizer.json` to convert PDF comics and art books:

```json
"pdf_conversion": {
  "enabled": true,
  "long_edge_pixels": 3200,
  "max_pages": 1000
}
```

This defaults to disabled. Preparation preserves existing configuration. The image
includes distribution Poppler, Pillow and fallback DejaVu fonts. No new mount,
credential, port or service is required. Deploy only `comic-normalizer` with
`--no-deps` and all existing overrides after verified state/config backup.

Each PDF page becomes one PNG, ordered numerically in a CBZ, with its complete
page layout, rotation and aspect ratio. Spreads remain spreads. The long edge
accepts 512–6000 pixels; page count accepts 1–1000. Rendering is a reading
derivative: searchable text, vectors, interactive forms, links, attachments and
original color information remain in the preserved PDF, not the CBZ. PNG adds no
lossy compression, but rasterization and scaling are not lossless PDF preservation.

The worker keeps the original PDF and a checksummed rendering receipt under
`pdf-derivatives` in existing recovery state. Every page is decoded and compared
with the CBZ inventory. Cache reuse verifies original, settings, output and
inventory. The existing expanded-byte limit applies; one preserved PDF renders per cycle outside the shared media writer lock with
a 60-second per-page and 600-second total limit. Encrypted, malformed, oversized
or failed PDFs remain for review. No partial CBZ replaces a library file. Interrupted private rendering is regenerated from the verified original; an altered
committed output requires review. Failed renders retry after one hour.

Library conversions use the existing Komga upgrade and Mylar notification flow.
Completed cache PDFs and PDF members of packs can use the existing unique import
matching when maintenance/auto-import or pack import is enabled. Metadata comes
from the established catalog, never guessed from PDF document properties. Cached
PDF originals are retained even after import. `.part` and retained partial
filenames are not automatically adopted. A manual recovery must first verify the
complete file and that its download is inactive.

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

If both ZIP archives contain root `ComicInfo.xml` and tagging changed only that
metadata, cleanup first retains the complete original archive under private
`maintenance/retained-originals` storage. Ordered page names and hashes and all
other source files must still match.
Publication identity fields, including issue, edition, date and catalog link,
must also agree; malformed or ambiguous XML remains for review.
The receipt binds the verified retained
original and current library hashes before removing the completed download and
confirming its import. Missing metadata, lost extras, insufficient storage, or
an unverifiable recovery copy keep the download in place. Retained originals
are recovery records and are not automatically deleted.

HTML responses saved as comics and confirmed decoder corruption are copied to `maintenance/quarantine` under
`NORMALIZER_STATE_PATH`. The worker verifies its SHA-256 before removing the
completed copy. Receipts record the source, recovery copy, and retry outcome.
When decoding fails without a dependency error, a file with a ZIP local-header
signature also receives a bounded check for its end record. A missing end record
confirms corruption even if the archive tool reports a generic format failure.
This check does not load the central directory or bypass decoder member limits.
ZIPs with an end-record signature and unexplained decoder failures remain for review.
A unique Mylar release mapping can trigger one native failed-release replacement
search. Ambiguous mappings remain for manual review. An interrupted API request
is recorded as `retry_unconfirmed` and is never blindly repeated.
Verified recovery copies carry the chosen issue ID in Mylar's native filename
marker, and post-processing receives that staged filename. The retained original
keeps its name and bytes. Conflicting or repeated markers require review.

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
| **Images** | `gotson/komga:1.28.1` (digest-pinned in Compose) |
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
or raw errors. Conversion itself reports preserved metadata. The separate converted-comic
tagging table reports Mylar follow-up results when that opt-in is enabled. Update the Mylar image before restarting the maintenance worker.


### Automatic recovery of unmatched imports

Maintenance also checks settled files against explicit Mylar issue identifiers,
bounded ZIP ComicInfo metadata, and exact series/year/issue filenames. Ambiguous
editions and conflicting evidence remain on Import problems. Ordinary loose-file recovery does not guess from similar titles or change failed-release
blacklisting. The separate opt-in pack workflow can add exact catalog entries.

A filename year can match the series start year or the issue publication year,
provided all available identity evidence selects exactly one catalog issue.
Explicit ComicInfo volume years still select the series start year. Pack members
whose filename uses the publication year can agree with a different ComicInfo
volume year when ComicInfo's publication year agrees with the filename. Conflicting
metadata, competing editions and uncertain prior submissions remain for review.
Different scans of a verified issue use its catalog parent when preserved as
extras, even when their filenames use the publication year.

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
select a candidate explicitly, then confirm. Regular issues and non-deleted annuals are supported; annual confirmation uses
the parent series path and the same content receipts as regular issues.
Candidate ranking is a suggestion,
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

### Verified pack recovery

Set `maintenance.pack_import` and `maintenance.auto_import` to `true`, then enable
**Verify pack members with the maintenance worker** in Mylar Activity. Both are
required. The default example leaves them disabled. The worker uses the existing
shared cache and state mounts, accepts completed pack work through the primary-key
API, and reports member outcomes to Activity's **Packs and extras** section.
Each capture binds the source and any extracted companion folder to a bounded
content manifest. The worker checks available sources before reusing an inventory
receipt; replacement bytes or added members cannot inherit earlier completion.
Legacy receipts require their original source hashes and member set to match.
Deploy matching Mylar and worker images before resuming this workflow.

Filename and metadata volume-year conflicts remain for review before catalog
lookup; an issue publication year is not treated as a volume start year.
Filename volume ordinals such as `v2` match only an explicitly matching catalog
`ComicVersion`; they are never discarded to guess between volumes. A unique
existing catalog match can prove an ordinal even when ComicInfo omits it;
unknown versions and competing matches remain for review. Full issues
with a cover-count annotation such as `(2 covers)` remain regular comics, while
short cover-only archives and named cover collections remain supplements.

The worker preserves retryable catalog responses across restarts and honors Mylar's
retry time. Only safe catalog reads retry automatically; ambiguous identities,
exhausted attempts and uncertain catalog writes remain held for review.

Pack inventories are retained under `maintenance/packs` in the existing state
directory. Outer archives use the pinned bounded extractor; comic members use the
existing CBZ converter. A pack inventory is limited to 2,000 files and 32 GiB of
member bytes, with the configured expanded-size limit applied to extraction and
each comic conversion. Unsupported or ambiguous members remain for review.
Only one verified issue import is submitted per idle maintenance cycle. A lost
acknowledgement never starts another import automatically.

Related named extras, cover collections, short cover-only archives and different
copies of an already imported issue are preserved as CBZ supplements in a sibling
`Series - Extras` folder. Their metadata identifies them as extras and omits the
regular issue Web identity. Original ComicInfo bytes remain in private receipts;
page bytes and other sidecars must survive. Small text/NFO/credit sidecars are
retained in private receipts rather than exposed as comic books. Unknown non-comic
members remain in the source for review.

Cleanup requires every inventoried member to be accounted for and fresh source
and destination verification. Unconfirmed imports, changing files and missing
library contents prevent removal. Completed member checks reuse unchanged file
identities; cleanup rechecks full hashes. The worker reports a verified cleanup
intent before removing any source. Interrupted cleanup resumes under its existing
receipt, preserving partial-removal history instead of creating a new generation.
A rejected cleanup report prevents source removal. Pack records remain in Mylar after DDL
queue history disappears. Preserve the whole worker state and Mylar data volume
in backups. A replaced quarantine entry is labeled resolved while its original
corrupt archive and retry history remain retained.

Cleaned packs with stale Mylar file identities use authenticated destination hash
revalidation without requiring retained sources or worker receipts. Worker report
refresh translates recorded destinations through the configured native/worker
mount mappings and checks their full hashes and current catalog ownership.
Rejected proofs preserve their original history and remain for review.

## Verified release naming

The optional worker policy uses dotted release names and a hyphen before the
scanner group, for example `Series.Name.v2.001.(2020).(Digital)-Group.cbz`.
Verified annual, collected-edition, variant, source and language labels remain in
the name. Unknown issue numbers, conflicting years, sidecars, duplicate reader
hashes and unproven catalog owners require review. Existing folders remain unchanged.
Unbracketed edition or variant annotations also require review, so rendering cannot
silently drop a release distinction. A Deluxe Edition collection cannot fulfill
the regular issue merely because stale embedded metadata names that issue.
A bracketed `#issue` block is omitted when it repeats the proven issue number;
a conflicting number remains for review. Edition and variant blocks remain intact.
Names help parsing; ComicInfo and exact catalog ownership still establish identity.
Review entries stay held during ordinary ticks and restarts. The explicit
`Naming.recovery_entry` operation requires a proven rejected native predecessor,
both private hash/CRC-verified copies, unchanged ownership and reader evidence.
Combined holds with shared hardlinks require an explicit fresh detached pair from the restore-verified backup; the old links remain intact.
Its version-2 request retains `retry_of`; fresh preparation and the ordinary
native/reader gates apply to the replacement without clearing old receipts.

Set `"release_naming": {"enabled": true, "batch_size": 1}` in the private worker
configuration after deploying matching Mylar and worker images. The default is
disabled. It requires the coordination override and absolute `writer_state` and
`mylar.config_dir`, plus the existing Mylar URL and primary API key configuration.
The worker includes Python xxhash to verify Komga's XXH3-128 content hash before a
move. No additional port, mount, credential or privilege is needed.

Automation records the existing library as its initial baseline and names new
catalog arrivals after metadata and reader analysis are ready. Native Mylar owns
the same-folder no-overwrite publication and catalog journal under the shared
writer lock. Interrupted publication fences every other media writer until its
verified recovery succeeds. The worker reconciles uncertain acknowledgements
through that journal rather than submitting the rename again.
Native publication also transfers existing confirmed DDL pack members through a
durable owner/path/hash proof, including metadata rewrites in the combined pass.
It preserves sidecars and leaves uncertain members for review. It verifies exact
archive hashes, reader pages and the API user's read progress before removing its
per-file temporary originals and restore copies. Compact receipts remain in
`/state/release-naming`. Komga's verified unique-hash restoration carries all-user
progress and readlist membership to the new path.

For existing files, run an isolated worker command with the same deployment mounts,
network and media UID while the normal worker and other media writers are quiescent:

```sh
python3 /app/normalize.py --naming-plan /state/release-naming-plan.json
python3 /app/normalize.py --naming-apply /state/release-naming-plan.json --naming-limit 1
```

For a combined rename/root-metadata plan, supply an explicit reviewed supplement
preview through the same planning command:

```sh
python3 /app/normalize.py --naming-plan /state/combined-plan.json --naming-reviewed-preview /state/reviewed-supplements.json
python3 /app/normalize.py --naming-apply /state/combined-plan.json --naming-limit 1
```

The private preview is a version-1 JSON object with `policy` (the exact verified
native supplement policy) and `reviews`. Each review has an absolute worker-side
`source`, its actual `source_sha256`, `status: "verified"`, the SHA-256 `evidence`
of its reviewed credit/supplement evidence, and `additions`, the proven per-field
additions from that preview. Use existing native supplementation rules to review
additions. Planning requires installed `combined_preview=1` support and joins every
approved additions map exactly to a fresh source/hash/policy-bound native preview.
Native derivation uses the existing supplement rules; planning does not approve
credits. Omit
unresolved credit deferrals and other unreviewed sources; they remain held in the
resulting manifest. A preview cannot register ownership or authorize publication.

Canonical names with nonempty approved additions retain the exact native naming
proposal/request and ready reader proof in the combined manifest. Canonical
files with empty approved additions remain unchanged and make no publication
request. Unsupported or mismatched additions remain held. Preparation reobserves
the native preview and complete current owner/census before creating any native
preservation pair, and binds that proof and the approved additions into the
immutable job. The input is bounded to 16 MiB and 10,000 unique source reviews; duplicate
JSON keys and unverified reviews are rejected. Apply rechecks source, reader,
policy and native publication authority. Native publication still verifies
unchanged-hash reader restoration before root metadata writes, and uncertain
responses use status without replay. The option does not enable the daemon or
change deployment configuration, mounts, networks or privileges.

Review the private manifest first. Apply validates fresh ownership, source and reader
state and verifies an isolated per-file preservation copy before publication. Run
again to continue a bounded batch. Reader restoration is asynchronous; the daemon
reconciles pending receipts after it resumes. Rebuild the manifest after a completed
pass to verify idempotence. Planning and application do not enable automation.

Before a live pass, verify backups and isolated restores of Mylar configuration,
its databases and writer state, worker configuration and receipts, and Komga's
configuration and databases. Record all-user read progress and readlist membership
for comparison after the pilot. Keep NZBGet running. Pause metadata writers and
reader scans that could overlap the pass. Rollback requires restoring affected
paths/catalog and compatible reader state while writers are stopped. Preserve
unresolved receipts, originals and pending markers, and never deploy an older image
while a release naming transaction remains pending.


With initialized publication protection, eligible lossless conversion uses a private prepared handoff and native Mylar publication. Dispatch runs after releasing the shared writer and before unrelated reader scans. An uncertain commit uses passive native status; fresh current owner, source, complete census and terminal proof precede reader notification. Completion requires a unique ready reader book with the exact target hash and page count. Existing reader-owned sources, unsupported PDF/member derivatives and old jobs remain held.

The coordinated combined rename/metadata pass binds one native original/restore pair to exact policy and naming facts. It renames first, verifies reader restoration at the unchanged archive hash, then requests native root metadata publication. New metadata hashes are accepted only through closed native lineage. Private native copies stay retained pending final cleanup acceptance. Matching `combined_cleanup=1` support permits only explicit retirement after fresh native and reader proof; an uncertain request uses passive status and cannot repeat deletion. The worker independently validates adopted nested-metadata families, preserving inherited rejected owners across original and derivative payloads. Deploy matching native and worker images with verified backups before enabling either path; final protected-library acceptance remains pending.


The worker reports fixed archive diagnostic status and reason only after ordinary
inventory refusal. It preserves the source and keeps the refusal terminal; no
diagnostic result permits import, retry, quarantine or publication. The matching
native `archive_diagnostics=1` capability describes installed diagnostics only.
The native and worker builds share exact pure ZIP preservation modules and
controls. Decoder verification and PDF conversion keep their existing separate
routes. Physical repair requires exclusive custody, native ownership and fresh
reader acceptance under the
[archive repair contract](../../specs/024-verified-archive-repair/contracts/archive-repair.md);
matching diagnostic images alone do not provide that authority.

The worker also refuses ordinary authority and Writer admission while native
negative-retirement pending state is present or inaccessible. Existing recovery
flags do not waive this hold. Native archive preparation/status builds private
repair evidence only, so the worker cannot submit or clean up an archive from that
result. Owning repair adoption and complete reader/native acceptance remain separate.

Explicit archive repair review requests use `Maintenance.enqueue_archive_repair`
with the exact native owner and prepared operation ID. The worker retains private
intent, attempt and acknowledgement records under its existing state directory.
Periodic dispatch releases Writer before contacting Mylar and rotates through
bounded batches so older review jobs cannot starve later jobs. A failed HTTP call
retains its attempt and leaves other maintenance work runnable; subsequent checks
use passive native status. Invalid journal or acknowledgement evidence remains a
refusal. A queued review is never an import or cleanup acknowledgement. This
transport adds no mount, setting, port or privilege; actual native adoption and
reader preservation require their separate checked recovery route.

The source includes a disabled ordinary-import continuity observer for owned rename and preserved metadata changes. During a marked maintenance cycle it collects selectors only; after all cycle work it obtains fresh strict admission, makes the authenticated native request outside the writer hold, and immediately verifies the original response bytes and complete mapped file/control facts. This observation remains process-local. It cannot complete a durable pack report, authorize retained-source cleanup, restore a lost witness after restart or grant reader acceptance. Matching native/worker images and actual transport acceptance are required before activation; existing mounts, ports, settings and privileges are unchanged.
