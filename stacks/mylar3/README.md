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
The worker recovery patch bounds ComicTagger runs to 180 seconds and retains the
original on timeout. Network failures while finding another DDL mirror are
retried three times without terminating the queue thread. The import-integrity
patch preserves Mylar's native issue-1 fallback for unnumbered one-shots. Resume
requests append only when the saved file matches the requested offset and the
server returns HTTP 206 with that starting offset;
a server that ignores Range restarts the partial file instead of corrupting it by
appending a full response. Requeued transfers are marked Queued so an interrupted
item cannot obscure the active download's progress. The queue table refreshes
with the active-download poll and shows measured percentages, `0%` for queued
items, `100%` for completed items, and `Unknown` when the provider supplies no
total size. Failed items show `--`. Percentage sorting is numeric, and polling
preserves the current page and scroll position.

Regression check against source copied from the pinned image:
`python3 config/test_ddl_fix.py /path/to/mylar/source` (requires `webserve.py`
and `getcomics.py`, plus `queues/ddl.py`; makes no network requests or changes
to that source). Run `python3 config/test_worker_fix.py /path/to/mylar/source`
against source with the DDL patch applied, including `cmtagmylar.py`, to verify
tagging timeouts and bounded network retries.

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
Awaiting post-processing is shown only for a matching entry actually in the
post-processing queue. Active runs and finished runs have distinct labels; other
completed downloads show that their import is unconfirmed instead of claiming
they are queued. Pack downloads are not marked imported based on one member issue. Explicit
integer issue lists and ranges show how many members have a Downloaded or Archived
record and a nonempty library file. Missing files and ambiguous membership prevent
a fully imported label. Unspecified annuals, collected editions, and unknown member
lists remain unconfirmed. Finished processing runs also use the existing retained
Activity journal, and new runs retain their exact DDL ID and processing receipt.
A restart or newer processing activity does not turn a finished pack back into a
waiting item, even when extraction changes its folder name. The health probe counts new byte high-water marks and completed downloads.
Switching mirrors or shrinking the queue alone cannot clear a stall warning.

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
library import.

**Try NZB instead** requests a replacement for one inactive, single-issue DDL
entry. The native serialized search uses only enabled, unblocked NZB providers
and retains native pacing and candidate validation. Packs, active or duplicate
work, and already imported issues are rejected. The original DDL entry is held
before the search; a definite no-result restores it, while confirmed NZB acceptance
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
