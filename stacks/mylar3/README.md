# Mylar3

Automated comic book downloader (CBR/CBZ) for Usenet and torrents. Tracks
series, fetches new issues via NZBGet or qBittorrent, and organizes them into
`/data/comics`.

**Homepage:** https://mylarcomics.com  
**GitHub:** https://github.com/mylar3/mylar3  
**Docker (LinuxServer):** https://docs.linuxserver.io/images/docker-mylar3  

Access via Caddy at **https://mylar3.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env` (optional: set `PUID`, `PGID`, `TZ`).
2. Confirm `MYLAR3_MEDIA_PATH` (default `/mnt/unraid/media`).
3. Ensure the **usenet** and **torrents** networks exist (same as Sonarr/Radarr). Create them if needed: `docker network create usenet` and `docker network create torrents`. For external networks/volumes and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
4. From the stack directory: `docker compose --env-file stack.env up -d`.
5. In the web UI: add download clients (NZBGet at `nzbget:6789`,
   qBittorrent at `qbittorrent:8080`), add indexers, then set Comic Location
   to `/data/comics`. Set **NZBGet Download Directory** to
   `/data/downloads/usenet/completed/comics`. Enable the API and generate its key
   under Settings so the container can check worker health.

**Portainer:** Set the environment variables and ensure the external networks
exist. The published image includes the fixes and interface enhancements; no
checkout or source-code bind mounts are needed on the Docker host.

## Integration with Komga

Point Mylar3's Comic Location at `/data/comics`. Komga can continue mounting
the corresponding host directory independently.

Komga's optional [comic normalizer](../komga/README.md#automatic-comic-conversion)
can normalize CB7, CBT, and other archive formats already in the shared library.
Its optional Mylar integration rechecks affected series after changing a file's
extension. This complements Mylar's download post-processing; it does not add
new search providers or change the supported download formats in Mylar itself.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `mylar3:8090`) |
| **Networks** | `ingress-admin` (Caddy), `usenet`, `torrents` (download clients) |
| **Images** | `ghcr.io/bolens/homelab-mylar3:latest` |
| **Storage** | `mylar3_config` → `/config`, `${MYLAR3_MEDIA_PATH}` → `/data` |

## Caddy reverse proxy

Add a site block for the Mylar3 hostname (e.g. `mylar3.yourdomain.com`):

```
mylar3.yourdomain.com {
	reverse_proxy mylar3:8090
}
```

## Health and monitoring

The published image includes patches from `config/` to handle missing DDL
download sizes without breaking the queue page and to reject HTTP errors or
HTML responses before saving them as comic archives. The build-time patching is idempotent and
marks downloads Failed when their mirrors are exhausted. The build checks the expected
upstream source before patching. When changing the pinned base, verify the patches
against its source; remove them once upstream handles these cases. It does
not increase Mylar's single DDL worker or post-processing concurrency.
The tagger-timeout adapter bounds ComicTagger runs to 180 seconds and retains the
original on timeout. Network failures while finding another DDL mirror are
retried three times without terminating the queue thread. The unnumbered-issue adapter
preserves Mylar's native issue-1 fallback for unnumbered one-shots. Resume
requests append only when the saved file matches the requested offset and the
server returns HTTP 206 with that starting offset;
a server that ignores Range restarts the partial file instead of corrupting it by
appending a full response. Requeued transfers are marked Queued so an interrupted
item cannot obscure the active download's progress. The queue table refreshes
with the active-download poll and shows measured percentages, `0%` for queued
items, `100%` for completed items, and `Unknown` when the provider supplies no
total size. Failed items show `--`. Percentage sorting is numeric, and polling
preserves the current page and scroll position.
Queue and history labels use the saved release title, matching the active download
even when a pack is linked to one issue or its legacy pack flag is missing. Entries
without a release title retain their catalog label. This does not change issue
links, pack membership, or import status.

Unknown DDL mirror types fail the current attempt without reusing another
transfer's result. Manual Resume prefers the staged `.part` file and starts a
fresh request when no saved bytes exist.

The adapters are organized by responsibility rather than delivery batch. See the
[module map](config/MODULES.md) for their source ownership, dependency order, and
focused tests. `config/apply_patches.py` owns the ordered adapter list used by both
the image build and isolated verification.

The image also rolls back failed SQLite writes before retrying, preserves explicit
catalog volume 1, and keeps years that are part of a series title during filename
matching. Recovery for an unnumbered collected edition requires one actual catalog
issue, an exact title or ordinary alias, and one main comic file. Conflicting
issue numbers, annual aliases, variants, and supplemental annotations are not
collapsed into that issue.

Story-arc searches queue every eligible missing entry with its arc identity and
preserve already imported issues and annuals. TalkHard pull-list navigation uses
Wednesday release weeks across year boundaries, including valid week 53. Legacy
and file-pull modes retain their existing stored week identities.

The image adds authenticated `getHealth` and `reportFailedDownload` API
commands. Both require the primary API key. Keep Mylar's API enabled. The Docker
probe checks enabled workers every 60 seconds and reports a failure when a worker
is down or an active download/post-processing backlog makes no progress for 15 minutes.
When every pending DDL provider is cooling and no transfer is active, health reports
the expected retry time instead. It allows two minutes after cooldown expiry for
work to resume, but one continuous hour without useful progress still alerts,
even if cooldowns keep extending. Invalid cooldown state also fails visibly.
New queue arrivals do not reset that timer. Idle queues are healthy. Docker marks
the container unhealthy after three failed probes. Completed files that cannot be
imported also trigger a backlog warning and need review.

In Uptime Kuma, add a **Docker Container** monitor for `mylar3` using the existing
read-only Docker host, under **Critical Containers**, and attach your notification
routes. Keep the HTTPS monitor for web access. Worker failures then appear in
Kuma's dashboard and Docker's health state without publishing the health API.

Enable **Failed Download Handling** and **Automatically Retry Failed Downloads**
in Mylar. The optional Komga maintenance worker uses native failed-release handling
only when one download record maps unambiguously to an issue. See
[completed-download maintenance](../komga/README.md#completed-download-maintenance).

Before changing the image, pull the candidate explicitly, then run:

```bash
./verify-image.sh IMAGE_REFERENCE
```

The gate copies public application source inside an isolated container, applies
all build-time patches, and runs DDL, tagging-timeout, and health regressions. It has
no network or live configuration mounts. Repository CI runs the same gate against
the pinned image. A source mismatch fails the gate and requires patch review.
After deployment, also check `/check_ActiveDDL`, queue progress, and library data
preservation. The offline gate cannot verify a download provider's availability.

## Queue control and import problems

The image includes queue control. The queue table
shows received bytes, recent speed, seconds since progress, attempts, and cooldown
status. Completed individual issues show **Post-processed; in library** once Mylar
records them as Downloaded or Archived and their recorded library file exists. The **Download / import status** column keeps completed items clear of retry
notation. Their download attempt count remains available in a tooltip, with no
provider cooldown.
Queued labels follow the current pause setting and provider cooldown deadline,
so an expired cooldown does not remain displayed from an earlier blocked attempt.
The attempt count records attempts already used, not time spent waiting.
Awaiting post-processing is shown only for a matching entry actually in the
post-processing queue. Active runs and finished runs have distinct labels; other
completed downloads show that their import is unconfirmed instead of claiming
they are queued. Pack downloads are not marked imported based on one member issue. Explicit
integer issue lists and ranges show how many members have a Downloaded or Archived
record and a nonempty library file. Missing files and ambiguous membership prevent
a fully imported label. Without a verified member inventory, unspecified annuals, collected editions, and
unknown member lists remain unconfirmed. Finished processing runs also use the existing retained
Activity journal, and new runs retain their exact DDL ID and processing receipt.
A restart or newer processing activity does not turn a finished pack back into a
waiting item, even when extraction changes its folder name. The health probe counts new byte high-water marks and completed downloads.
Switching mirrors or shrinking the queue alone cannot clear a stall warning.

Active DDL progress and stall tracking resolve provider temporary filenames against
the download directory, including Pixel basenames and staged `.part` files. A brief
absence during setup or handoff is shown as waiting for file activity; it does not
imply that the download needs restarting. Retry diagnostics still track stalled
transfers independently.

DDL Queue Management keeps the active transfer visible when its size is unknown,
with an indeterminate progress bar. Failed refreshes retain the last snapshot and
disable active-download actions until fresh status arrives. Requests do not overlap,
and polling pauses in hidden tabs. The queue becomes labeled cards on small screens,
with a sort selector, while larger screens retain the full table. Queue-wide actions
are separate from active-download controls. Removing an entry uses an inline
Remove / Cancel confirmation in its row; Escape cancels. Aborting a download or
clearing the queue still asks for confirmation. Workflow pages use compact charcoal
buttons with white labels, with larger touch targets on touch devices.

Each release gets six attempts across restarts and mirror changes. Two consecutive
failures on a provider cause a 15-minute cooldown for that provider. HTTP 429 starts
the cooldown immediately. Other eligible providers continue. An explicit Restart
or Resume resets that release's attempt budget, while the provider cooldown remains.
Review the reason before restarting exhausted releases.

When every previously observed GetComics download host is still cooling down,
new searches temporarily try enabled, unblocked NZB indexers first. Their relative
order is preserved, and DDL remains a fallback if NZB searches find nothing.
Existing queued downloads are not re-snatched or removed. The next search after
any host's cooldown expires uses the saved provider order again, without a restart
or configuration write. An enabled independent external DDL server or AirDC++
source retains the normal order because GetComics cooldowns do not cover it.
Missing or unreadable cooldown data also leaves the normal order unchanged.

At worker startup, persisted Queued and Downloading records are reconciled with
items already in memory. Interrupted records become Queued and are added once.
Eligible main-server partials resume when automatic DDL resume is enabled. Completed
records are not re-downloaded. Keep **DDL Auto Resume** enabled to preserve transfer
progress across planned restarts.

Main-server HTTP transfers use `.part` files. Size headers, resume offsets, and
archive integrity must pass before promotion. Validation runs in a child process
with a 180-second limit. ZIP packs are validated before extraction and their comic
archives are validated before the complete folder is published. RAR and 7z validation
require the decoder tools in the candidate image. Unsupported or failed validation
retains the source. Conflicting partials receive `.retained-<timestamp>` suffixes,
and unsuccessful pack extraction remains in `.mylar-unpack-*` directories. These
recovery files have no automatic expiry and should be reviewed before removal.

Use **Import problems** from the main **Manage** page or DDL Queue Management to see stable unmatched downloads,
validation failures, quarantine/replacement status, releases that exhausted their
attempts, and issues left Snatched for over 24 hours. The optional Komga maintenance
worker publishes file reports through the primary-key `reportImportProblems` API.
Missing or stale reports are labeled. Recovery states use readable labels and can
be filtered. **Refresh report** reloads the latest saved report without starting a
new scan or replacement search. Ambiguous imports with candidate proposals link
to Activity for explicit issue selection; viewing the report never assigns an
issue or deletes files. It uses the existing Mylar login and ingress.

`ddl-control.json` and `import-problems.json` live in Mylar's existing data directory.
Back them up with the application database and configuration. Invalid control state
fails visibly instead of silently resetting attempt budgets. No new public port,
Docker access, credentials, or media mount is required.

## Media preparation prerequisite

Verify the configured media directories exist on the intended filesystem before
running preparation. The helper refuses to create missing media paths. Directory
existence alone does not verify the remote mount; check its source and access.

## Post-processing monitor

Open **Post-processing** from Manage, DDL Queue Management, or Import problems.
The authenticated page at `postProcessing` shows worker availability, processing
lock state, active runs and elapsed time, the first 100 waiting items, up to 50
recent run observations, and recent confirmed imports. The monitor does not consume
queue entries, change concurrency, or offer destructive queue controls. A finished
run is separate from an import confirmed by Mylar history and a Downloaded issue.

Status refreshes every five seconds without overlapping requests. Failed refreshes
retain the last snapshot with a stale warning. Mylar does not provide a reliable
post-processing percentage. Active and recent run/tagging observations are held in
memory and reset on restart.

The archive table shows original and output formats, conversion outcomes, and
metadata changes observed around Mylar's tagger. ZIP metadata comparisons read
bounded ComicInfo.xml and ComicBookInfo blocks. They establish added, updated,
unchanged, or removed metadata, not whether individual field values are correct.
Uninspected original metadata is labeled explicitly. Library normalization reports
preservation, since it converts archives without retagging them.

The optional Komga maintenance worker includes a bounded conversion summary in its
existing primary-key `reportImportProblems` call. Mylar stores it privately as
`archive-processing.json` alongside its other reports. Missing or stale reports are
labeled. Deploy the updated Mylar image before restarting the maintenance worker.
No new ports, credentials, environment values, or mounts are required.


## Desktop layout

The image adds a shared layout override for screens at least 1,000 pixels
wide. Header, content, footer, and library tables use the available width with
consistent outer margins. Table wrappers allow horizontal scrolling when their
contents cannot fit, and page action buttons wrap onto additional lines.

At 1,600 pixels and wider, the post-processing monitor places active and waiting
work side by side. Narrower screens retain the native compact layout. The override
preserves the selected theme and does not change queue or processing behavior.


Import problems also accepts maintenance recovery states: automatic import
submitted, submission needing review, and matched formats needing conversion.
Submission retains the source and does not establish successful library import.
Configure opt-in automatic matching recovery in the Komga maintenance worker.

Desktop navigation at 1,200 pixels and wider adds a Library link and a Queues menu
for Activity, DDL, post-processing, and import problems. The menu supports keyboard activation,
Escape to close, outside-click dismissal, and a current-page indicator. Page actions
stay near the left-aligned heading. Wide tables give names and diagnostic text more
space, and post-processing summaries use aligned cards and balanced queue panels.

## Activity and workflow controls

Open **Activity** from Manage or the Queues menu. The authenticated `activity`
page combines search/provider results, download, conversion, tagging and processing
observations. History survives restarts in private `workflow.sqlite` beside Mylar's
database. It retains up to 5,000 events and 30 days, with 100 events per page and
issue/stage filters. This starts recording new observations, not a historical
backfill. Older pages pause automatic updates; failed refreshes retain the last
snapshot with a stale warning. Finished processing is separate from confirmed
library import. Library confirmation requires a nonempty file at the tracked series
location. Annual imports contribute to progress and recent-import observations;
missing files do not release download ownership.

**Try NZB instead** requests a replacement for one inactive, single-issue DDL
entry. The native serialized search uses only enabled, unblocked NZB providers
and retains native pacing and candidate validation. Packs, active or duplicate
work, and already imported issues are rejected. The original DDL entry is held
before the search; a definite no-result restores only that entry without requeueing another active DDL, while confirmed NZB acceptance
keeps it held. Partial files and retry history remain. Automatic handoff is off by
default; enabling it starts with a two-hour waiting threshold and considers at most
one eligible issue per scheduler cycle.

Uncertain downloader responses remain held across restarts to prevent repeated
sends. Activity exposes both DDL handoffs and ordinary NZB submissions needing
review. Check the downloader and post-processing queues before checking the
confirmation box. Keep the hold if accepted work exists; allow retry or restore
DDL only after verifying no queued or active work remains. Do not delete journal
records to bypass a hold.

**Resolve import matches** shows candidate series, start year, issue number,
existing status, and agreeing/conflicting evidence from the optional Komga worker.
Regular issues and non-deleted annuals use the same guided admission and release
checks. Annual IDs resolve to their parent series; deleted annuals cannot fall back
to a regular-issue record with the same ID. Archived intent is preserved.
No candidate is selected automatically. Confirming a candidate submits a
source-version-bound request; a changed source requires a new review. A requested
series alias covers only the displayed exact source series/start-year pair and
activates after confirmed import. Aliases require matching issue/year evidence,
remain visible, and can be disabled. See
[guided matching](../komga/README.md#guided-matching-and-series-aliases) for worker
prerequisites and preserved-source behavior.

**Intake settings** pause new searches and snatches when processing or storage
limits are reached. Defaults enable intake control at 50 pending items, resume at
20, and use 5/8 GiB free-space pause/resume thresholds. The separate thresholds
prevent repeated pause/resume switching. Existing transfers and processing drain
normally, deferred searches stay queued, and no retry budget is consumed by a
pause. Missing or unreadable configured storage stops new intake and reports the
reason; it never creates a replacement directory. Change these settings in Activity,
not environment variables.

Activity and Post-processing have section links for reaching review controls and
conversion details directly. Activity history scrolls within a bounded region,
with a stage selector and clear-filter action. Requests show feedback beside their
controls, and unchanged import-review controls preserve keyboard focus during refresh.
Import problems can clear its recovery and text filters together. All four queue
workflow pages use native-style buttons with explicit readable colors for normal,
hover, focus, pressed, and disabled states.

Workflow uses existing configuration/state volumes, login, primary-key worker API
and ingress. Mutations require POST and a session-bound CSRF token. Back up the
whole Mylar data directory, including `workflow.sqlite` and existing control files.
Deploy the Mylar image before its matching maintenance worker image. No additional
service, port, credential, mount or concurrency is introduced.

## Image updates and rollback

`MYLAR3_IMAGE` selects the published image. Use a `sha-<full-commit>` tag or digest
from [custom image builds](../../documents/CUSTOM-IMAGES.md) for repeatable deployments.
Linux amd64 is the verified platform. Updates use the container image; Mylar's
in-application updater can overwrite these enhancements and should remain disabled.

Scope service interruptions to the update. For a Mylar-only interface change, keep
NZBGet and Komga running and stop only Mylar while backing up its configuration and
application state. Use an application-consistent backup for any shared media the
operation could change; do not stop unrelated services as a blanket precaution.
Verify an isolated restore before updating. Pull the selected image and recreate
only Mylar. Check database integrity, baseline issue records and media hashes,
container health, and the DDL and post-processing pages. If data is missing or
corrupt, stop writers and restore the verified backup and previous image. Remove
temporary update backups only after preservation checks pass; retain routine backups.

For a local build from the repository root:

```sh
docker build -t homelab-mylar3:local stacks/mylar3
```

The build runs the source compatibility gate. The final image contains patched
application files and the health probe, without patch scripts or regression tests.

Reviewed import holds can be released from Activity after checking both downloader
and processing queues. Late submissions from the released command are rejected.
A new explicit choice can then stage a fresh verified copy while retaining the old
receipt. For an already downloaded but unmatched NZB, choose **Use existing archive
for guided import** on its submission or handoff card. This does not queue another
search. A handoff's original DDL stays inactive as **Source review**.

## Verified packs and supplements

Enable **Verify pack members with the maintenance worker** in Activity only after
setting `maintenance.pack_import` and `maintenance.auto_import` to `true` in the
matching worker configuration. Mylar hands new DDL packs to that worker before
native anchor-based processing. Existing completed packs with retained sources
are also inventoried. Keep both sides enabled together; disabling the worker
while leaving Mylar's setting on retains new packs pending worker recovery.

Activity's **Packs and extras** section records each original format, catalog
identity, classification and outcome. It survives DDL history cleanup. Submitted
imports remain pending until page bytes and non-metadata sidecars match the
library. Changed or missing library files invalidate completion. DDL completion evidence
is independent of the bounded recent-history display. Related cover
collections, short cover-only archives, named extras and alternate scans are kept
in a sibling `Series - Extras` folder, without a regular issue identity. Legitimate
short comics are not rejected merely for having few pages. Ambiguous relationships
and conflicting print/digital evidence require review.

Missing exact catalog entries are requested through Mylar's native catalog
adapter. Existing statuses and deleted annual intent are preserved. An annual
with a verified catalog link to its parent can be added under that series;
otherwise an exact annual volume is tracked separately. Catalog uncertainty is
retained for review rather than repeatedly adding or submitting work. Temporary
read-only lookup failures allow up to five attempts with increasing delays, starting
at five minutes. A persisted write intent prevents retries from repeating an
uncertain catalog addition. Legacy uncertain receipts remain held for review. Pack number
ranges no longer mark inferred issue lists Snatched or overwrite them on failure.
Annual filename IDs resolve against annual records, and processing ownership is
released on empty input, errors and normal completion. Startup retains unfinished
series entries when they have issue or annual records, preserving catalog refresh
intent and parent relationships.

The existing `workflow.sqlite` also retains pack/member and catalog receipts.
Prior ComicInfo metadata and non-comic pack credits stay in the worker's
private recovery state. Verified pack sources can be cleaned after all members are accounted for. Back up both state locations. No additional public route,
credential, mount, port or processing concurrency is introduced. Deploy Mylar
before the updated worker, then enable the two opt-in settings after preservation
checks. Keep NZBGet and Komga running during this scoped update.

### DDL download scheduling

DDL Queue Management combines two independent preferences. **Download type** chooses
mixed singles and packs, singles before packs, packs before singles, or alternating.
**Sort by** chooses oldest queued first, newest queued first, oldest release first,
or newest release first. The selected sort applies within each type group, or to
each type's next item while alternating. Mixed applies it across all items.
Existing type preferences retain their behavior with oldest queued first.

Queued order uses persisted local arrival order. Existing entries are seeded in
their current queue order, and cooldowns and retries do not change age.
**Download next** overrides both preferences for one eligible entry, with provider
cooldowns still applying. **Pause new downloads** holds the next start without
interrupting an active download or NZB work. Preferences persist in the workflow
database and take effect at the next transfer boundary. The default remains mixed
with oldest queued first.

Release order uses the issue's store release date, falling back to its cover date.
For explicit pack issue ranges, oldest/newest use the earliest/latest known member
date. Other packs use the linked issue date when available. Unknown dates follow
known dates in both directions, with queue arrival order breaking ties. These
options do not use the series start year or change the saved queued-order options.

Use **View order → Download queue order** above the table to follow those saved
preferences. The estimate places active transfers first, then eligible queued
downloads, provider cooldowns, unscheduled entries and history. Position labels
show each queued entry's place. The view refreshes after preference or priority
changes and remains usable while paused. Changing the view never changes the
download preference.

Queue table reads time out after ten seconds and retry through normal polling,
retaining existing rows while disabling stale actions. Preference saves merge
atomically, so concurrent Activity and queue changes preserve unrelated settings.
Split-download IDs retain their exact identity in processing history and NZB
handoff requests.

Manage, Activity, Import problems and Post-processing use the same fluid frame
and wrapping toolbars as the DDL queue. Library and Queues navigation remains
available on smaller screens. Manage's scan form and status panel stack without
overlap; wide report tables scroll inside focusable, labeled regions. Compact
gray controls retain their existing appearance.

## Modern tagger migration

The [migration plan](../../specs/011-mylar-modern-tagger/plan.md) covers a pinned
modern ComicTagger runtime, metadata preservation, failure recovery, and an optional
DDL discovery transport. The image now includes ComicTagger **1.6.0b11.dev0** in an
isolated `/opt/comictagger` environment. Mylar continues using its existing vendored
1.3.5 tagger. Settings → Quality & Post Processing → Metadata Tagging includes a
**ComicTagger backend** selector. **Legacy (default)** remains available during the
migration. **Modern (experimental)** is available as an explicit opt-in after
native writer coordination, live canary, crash recovery and rollback acceptance.
Select it and save settings to test it, or select Legacy and save to switch back.
Modern supports CBZ ComicRack metadata. ComicBookLover writes, conversion-only
tagging and link-based automatic placement report unsupported without changing
preferences or falling back. Let the normalizer own format conversions.
The server rejects invalid selections before changing settings. Backend changes apply
to the next tagging job, never to a job already running. Editing the configuration
to select an unavailable backend reports unsupported tagging instead of silently
using Legacy.

The image build tests the real modern CLI offline with generated CBZs, including
annual/variant metadata, Unicode, volume 1, archive comments and unrelated members.
The modern CLI clears inherited Python configuration and disables user-site imports
so Mylar's vendored legacy modules cannot shadow its pinned dependencies.
The CLI protocol helper reports only a staged save; it does not claim a verified
library import. Publication, startup recovery, native ownership and live rollback have passed
the [acceptance checks](../../specs/011-mylar-modern-tagger/validation.md).
Native manual tagging now recognizes an explicit verified in-place result and skips
its legacy temporary-file copy/delete branch. Automatic imports reject non-string
results before placement. The monitor accepts verified added/updated/unchanged and
specific failure outcomes. These guards preserve legacy paths and do not select the
modern backend. The choice persists as `Metatagging.tagger_backend` in the existing
config volume. No environment variable, mount or ingress change is required.
The native-package service provides bounded ComicVine
lookup, automatic staging and recovery admission before each job. Native routing uses
the v2 journal; annuals resolve their release volume rather than parent-series metadata.
Requests remains the archive transfer transport. Discovery has a separate opt-in described below.

The archive helper reconciles ComicInfo into a new CBZ and reopens it to check page
and sidecar hashes, comments, permissions and the exact XML. Existing notes, unknown
fields and page bookmarks survive unless explicitly replaced. Unchanged metadata
produces no output. When the CLI output already matches the approved metadata and
preserves every original ZIP member attribute, reconciliation copies that verified
archive instead of decompressing and recompressing its pages. Overrides or changed
attributes use the full rebuild. Both paths retain content checks, source-race
detection, durable staging and publication recovery. ComicVine pacing is unchanged.
Verification rejects ambiguous metadata/member names, corrupt
entries and changed sources. Current Modern limits are 4 GiB per archive and
in total unpacked data, 512 MiB per non-metadata member, 4,096 members, an 8 MiB
central directory and 256 KiB ComicInfo. ZIP64 and split archives are unsupported.
These limits apply only to Modern; Legacy retains its existing behavior.

The standalone v1 compatibility publisher uses a private versioned journal and same-filesystem staging.
It verifies page bytes before atomic Linux file exchange, then verifies the displaced
source before recording a commit. Restart recovery never blindly repeats a CLI run
or file exchange. Conflicts retain the original copy and displaced file for review.
Operation tokens and source paths have separate locks; old completed receipts do not
block newer jobs. Hardlinked files, extended attributes/ACLs and filesystems without
atomic exchange are unsupported. Native Modern jobs instead select the verified v2 NFS publisher described below.
Unfinished commit cleanup rechecks source identity/permissions and displaced contents;
unknown or malformed receipts are retained without interpreting them as failed jobs.
The startup recovery API streams pending results, skips cleaned history without
rehashing comics, and reports active locks as busy. Its caller must finish the scan
and keep modern admission closed on conflicts, invalid receipts, I/O errors or busy
jobs. Native startup performs this recovery before database maintenance and scans,
including when the selected backend is Legacy.
Core helpers ship under `/opt/mylar3-fixes` and in Mylar's package. The lookup and
service modules ship only in Mylar's package. Startup recovery runs before scans
for either selected backend. Upgrading retains existing settings and defaults to Legacy.

Runtime and Python build dependencies have exact versions and SHA-256 locks. Build
tools stay outside the final image. ICU 70 comes from the pinned Ubuntu base. Package
license files and selected corresponding source archives are retained under
`/opt/comictagger`; the build rejects version/hash drift in those sources. See
[tagger-NOTICES.md](tagger-NOTICES.md). Dependabot is configured for the runtime and
build requirements files. The first bot run could not fetch referenced `.lock` files,
so hashes now live directly in `requirements.txt` and `requirements-build.txt`.
GitHub's dependency graph has successfully evaluated both corrected files. A
subsequent version-update job remains to be observed.
Review native build-package pins monthly and whenever changing the base digest.

The published image is currently built/tested for linux/amd64. A Python wheel's
arm64 availability alone is not proof of an arm64 build. No services need restarting
solely to inspect the bundled runtime.

The service preserves the automatic download source and returns a verified
disposable CBZ for native placement. Manual jobs return an in-place receipt. Existing
ComicInfo with overwrite disabled skips lookup and tagging entirely. ComicVine
lookup uses private temporary credential files, a 45-second process deadline,
bounded responses and validated issue/volume identities. Redirects and retries are
disabled. Each provider request waits the configured 2–10 second interval.
Conflicting recovery receipts block new work. Private staging receipts track automatic
outputs through native placement. Cleanup removes a disposable output only when its
recorded content matches and its unchanged original still exists; uncertain or sole
remaining copies stay private for review. This does not claim a successful import.
Manual in-place publication preserves supported ACLs and user attributes exactly.
Automatic imports retain the existing native destination permission policy: cache
copies preserve file bytes and mode, without transplanting download ACLs or xattrs.
Automatic link-based placement reports unsupported tagging and keeps the original
import path; a library softlink must never reference disposable staging.

Mylar initializes private `media-writer` protocol state beside `config.ini`. Its
post-processing owner and complete manual-tagging calls hold the shared writer
lock through publication and cleanup. The normalizer can opt into the matching
[coordination override](../komga/README.md#coordination-with-mylar). Pending worker
recovery prevents admission, including after a worker crash. Include this state
in application backups and never replace it while either writer can run. Library
files are not copied for this configuration change. Renames, moves, deletion (including
the API), series imports and rescans also take this lock. The separate durable tagger
fence blocks the normalizer after a Mylar crash until publication recovery succeeds.
Recovery directories are identity-bound; missing or replaced state fails closed.

Deploy matching Mylar and normalizer images together while idle when coordination is
enabled. The normalizer durably defers Mylar rescan notifications until after releasing
its lock. An older worker can otherwise deadlock with guarded rescans, and does not
honor the new tagger fence. Do not roll back to an older image with pending publication
receipts: recover with the matching image first, or restore the verified pre-change
application state and affected canary files while writers are stopped. Live rollout,
canary and old-image rollback checks passed before exposing Modern as an opt-in.


The native NFS publisher uses separate version-2 receipts, retaining
the original inode before publishing through a no-clobber link. It preserves and
reads back supported ACLs and user attributes; it never silently substitutes for
atomic exchange. Its source filename can be temporarily absent until recovery, so
startup/scanner coordination is mandatory and old-image rollback checks must pass
before selection. Older readers reject its receipts without modifying them. No new
mount, port or privilege is required. Keep the matching normalizer coordination
enabled when both applications can write the library.

### Optional DDL discovery transport

Settings → Download settings → DDL providers includes **DDL discovery transport**.
Requests remains the default. **Curl (experimental)** uses the pinned curl_cffi
0.16.3 runtime under `/opt/ddl-transport` for provider pages and cookie discovery.
Archive transfers always retain Requests, including resume validation, retries,
provider cooldowns, NZB fallback and queue ordering. Changing the preference takes
effect at the next outer discovery operation. An active operation keeps its owner.
Select Requests and save to revert without restarting Mylar.

Curl discovery runs in isolated child processes, with an 8 MiB response limit,
a 1 MiB request-body limit, no transport retries and a bounded request deadline.
Scoped cookies, explicit proxies and TLS verification pass through the adapter.
Unsupported or unavailable choices fail explicitly without silently switching.
The dependency lock is `requirements-ddl.txt`. Installed license notices remain in
the isolated environment. See [ddl-NOTICES.md](ddl-NOTICES.md).
No additional port, mount, privilege or preparation step is required. The preference
persists as `DDL.ddl_discovery_backend` in the existing config volume.

Full curl archive streaming is deliberately unavailable. The pinned package's
streaming queue is unbounded under a slow consumer, so it fails the required
backpressure gate. The bounded local evaluator is `config/evaluate_ddl_streaming.py`.
It does not establish multi-gigabyte, stalled-server or restart/resume acceptance.

### Recovery durability limits

Publication flushes candidate data and attributes, its workspace, and the local
intent journal before displacing a source. It flushes each rename/link boundary
and records a durable terminal result before deleting retained copies. Startup
reconciles pending work before admitting writers or scans. Simulated process exits
and storage-flush failures verify recovery and copy retention. Persistent I/O
failures require review and retain evidence rather than reporting success.

No real power-loss test is performed. Recovery depends on the filesystem and NFS
server honoring acknowledged flushes. Process interruption tests do not prove
storage-controller caches or server power-loss durability.


### Converted comic metadata queue

The matching normalizer can opt into [automatic tagging after conversion](../komga/README.md#automatic-tagging-after-conversion).
Its primary-key `queueConvertedTag` API request follows the existing series rescan.
Mylar durably queues the exact converted path and digest, waits for a unique
downloaded catalog issue, and fills missing ComicInfo with Modern. Existing XML,
page bytes, extras and supported file attributes are preserved. Annuals use their
release volume. Settings must enable post-processing, metadata and Modern
ComicRack-only tagging. Unsupported settings wait without changing preferences.

The existing post-processing worker runs these jobs when its download import
queue is idle. **Post-processing → Converted comic tagging** shows up to 100
recent durable jobs, including waiting, retry, review and verified completion.
Transient tagging failures allow six attempts; an unmatched catalog path waits
up to 24 hours. Small terminal identities remain in `workflow.sqlite` to suppress
old notification replays. Recovery checks the stored publication receipt before
another attempt, including after a crash between publication and queue completion.
Keep this journal with existing application backups. The API acknowledges
admission, not completed tagging. No new public endpoint, mount or privilege is
introduced. Deploy Mylar before the producer and retain prior images/state until
health and catalog/file preservation have been verified. Run a Komga metadata
rescan after tagging to refresh its displayed metadata.
