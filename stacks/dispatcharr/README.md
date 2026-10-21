# Dispatcharr

Dispatcharr is a self-hosted stream routing and EPG management tool for organizing IPTV channels and playlist sources.

**GitHub:** https://github.com/Dispatcharr/Dispatcharr
**Docs:** https://dispatcharr.github.io/Dispatcharr-Docs/
**Docker image:** https://github.com/Dispatcharr/Dispatcharr/pkgs/container/dispatcharr
**Releases:** https://github.com/Dispatcharr/Dispatcharr/releases

## Usage

Access the browser UI through Caddy. Dispatcharr manages M3U playlists and EPG
sources, then exports HDHomeRun, M3U and XMLTV outputs. Plex uses the HDHomeRun
tuner output with a separate XMLTV guide. It cannot use an M3U URL as a tuner.

## Setup

1. Run `./prepare-stack.sh`, then review `stack.env` and `caddy_snippet.conf`.
2. Adjust `DISPATCHARR_LOG_LEVEL` if needed. Shared timezone and locale values
   come from the optional `../../shared.env`.
3. Keep `ingress-admin` available for Caddy. The base stack publishes no host
   port and needs no GPU, host networking, privileged mode or Docker socket.
4. Choose whether to enable the same-host Plex connection below, then deploy
   with `docker compose up -d`.
5. Open the UI and create the first admin account. Dispatcharr provides its
   own form login. Initialize it over a trusted local connection before making
   the UI public. Leave reverse-proxy authentication disabled when using form login.

The all-in-one container runs PostgreSQL, Redis and application workers.
`dispatcharr_data` persists the complete `/data` directory, including database
state and application configuration. CPU, memory, process and log limits are
declared in Compose. The health check reads the setup-status API, which queries
PostgreSQL and works both before and after the admin account exists.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DISPATCHARR_LOG_LEVEL | No | info | Application logging verbosity |
| DISPATCHARR_PLEX_PORT | No | 9191 | Loopback port when the optional Plex override is enabled |
| DISPATCHARR_RECORDINGS_PATH | With storage override | None | Existing host directory mounted at `/data/recordings` |

Re-run preparation after editing `stack.env` to refresh its generated `.env`
interpolation mirror. Existing environment files, Caddy configuration and
application data are preserved. Preparation does not start containers or
enable the optional port.

## Plex and iptv-org

The [Plex stack](../plex/README.md) runs with host networking. It cannot resolve
the `dispatcharr` Docker service name. When both services run on the same host,
explicitly enable the loopback-only connection:

```bash
cp docker-compose.plex.yml docker-compose.override.yml
./prepare-stack.sh
docker compose up -d
```

The override is ignored by Git. Review an existing override before changing it.
The resulting tuner address is `http://127.0.0.1:9191/hdhr/`, with XMLTV at
`http://127.0.0.1:9191/output/epg`. If you change `DISPATCHARR_PLEX_PORT`, use
that port in both URLs. No LAN or public port is published. A Plex server on a
different host needs its own explicitly restricted private network connection.

When using a channel profile, copy both its HDHR and XMLTV links from the
Channels page. For example, a profile named `Plex Free TV` uses
`/hdhr/Plex%20Free%20TV` and `/output/epg/Plex%20Free%20TV`. Verify the tuner and
guide contain the same selected channel set. Keep the existing Plex DVR and
device identities when replacing an unscoped guide with a profile-specific one.

1. In Dispatcharr's **M3U & EPG Manager**, add a Standard M3U account. For a US
   starter source use `https://iptv-org.github.io/iptv/countries/us.m3u`.
   Other countries, languages and categories are listed in
   [iptv-org's playlists](https://github.com/iptv-org/iptv/blob/master/PLAYLISTS.md).
2. Select groups, refresh the account, and create a small set of channels from
   the imported streams. Test both video and audio before exporting to Plex.
3. Add XMLTV guide data and map it to the channels. The playlist does not
   contain program schedules. [iptv-org/epg](https://github.com/iptv-org/epg)
   supplies tools for fetching schedules. Dispatcharr can generate placeholder
   listings for channels without guide data, but those are not real schedules.
4. In Plex, open **Settings > Live TV & DVR** and add the HDHomeRun tuner
   manually using the local HDHR URL. This requires Plex Pass. Supply the
   local XMLTV URL when selecting guide data, then review the channel mapping.
   Follow the [upstream Plex setup guide](https://dispatcharr.github.io/Dispatcharr-Docs/getting-started/#plex).
5. Open a channel in Plex and confirm video and audio playback. A healthy
   container and an imported playlist do not prove that a stream plays.

For remote Plex clients, append `?cachedlogos=false` to the profile XMLTV URL.
Plex may load channel artwork directly in the client. The default cached logos
inherit the export request's origin, so a guide fetched from loopback can give
clients unreachable `127.0.0.1` logo URLs and blank channel labels. Direct logos
keep the guide private while using public upstream image URLs. Verify names,
image reachability and the unchanged tuner/mapping set after refreshing Plex.
Channels without logos should retain their text label.

Some HLS sources advertise several video variants and subtitle tracks in one
manifest. If Plex chooses the wrong tracks or fails during subtitle conversion,
create an FFmpeg stream profile that selects one video and one optional audio
track instead of copying every track:

```text
-fflags +genpts+discardcorrupt -user_agent {userAgent} -i {streamUrl} -map 0:v:0 -map 0:a:0? -c copy -sn -dn -mpegts_flags +pat_pmt_at_frames+resend_headers+initial_discontinuity -f mpegts pipe:1
```

This profile copies the selected codecs and drops subtitles and data tracks.
It does not convert unsupported codecs. Verify a moving picture and audible
sound in the actual Plex client, since source probing alone is insufficient.

Keep existing Plex DVRs and recording schedules intact. Back up Plex's
configuration and database before adding or changing tuners. The integration
does not require changing Plex's image, media mounts or Remote Access settings.

## DVR storage and provider VOD

Recordings default to `/data/recordings` inside the application volume. To keep
large recordings on an existing media share, use a dedicated directory such as
`media/dvr/dispatcharr`, separate from managed movie and TV libraries:

1. Verify the media share is mounted from its intended source and accessible.
   Create the dedicated directory with ownership appropriate for the application
   and the export's permissions. Do not create it over a missing remote mount.
2. Set `DISPATCHARR_RECORDINGS_PATH` in `stack.env` and re-run preparation.
3. Deploy with both optional overrides when Plex runs on this host:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.plex.yml \
     -f docker-compose.storage.yml up -d
   ```

   Alternatively, merge the reviewed `ports` and `volumes` entries into the
   ignored `docker-compose.override.yml`. Do not replace an existing override
   without preserving its settings. The storage bind refuses to create a
   missing source directory.
4. In **Settings > DVR**, choose recording templates beneath `/data/recordings`.
   Lowercase `tv/` and `movies/` subdirectories fit a lowercase media layout.
   Schedule a short recording, play it back and verify the file is on the
   intended filesystem. Back up recordings separately from PostgreSQL state.

Existing recordings in the named volume must be backed up, copied to the new
directory and verified before enabling the bind. The new mount hides any files
at the old `/data/recordings` location. Rollback must preserve recordings written
after the move as well as the prior application state.

Provider VOD is separate from DVR storage. Add an **Xtream Codes** account with
movie/series catalogs, enable **VOD Scanning**, select **VOD - Movies** and
**VOD - Series** groups, and refresh. Account permissions must allow VOD access.
The iptv-org M3U contains live streams and supplies no provider VOD catalog.
Dispatcharr does not scan the DVR folder as a local VOD library. See the
[upstream VOD guide](https://dispatcharr.github.io/Dispatcharr-Docs/vods/).

## Ingress and authentication

`caddy_snippet.conf.example` is self-contained and uses HTTP/1.1 upstream
transport. It includes local TLS names and placeholder HTTPS/Cloudflare Tunnel
routes. Replace placeholders only in the ignored runtime snippet. The
Cloudflare DNS token belongs in Caddy's environment, not this stack.

For a tunnel, route the selected hostname to `http://caddy:80`. The public
hostname serves the management UI with Dispatcharr's form login. Cloudflare
Access is optional and is not needed by the local Plex connection.

Form login does not protect every tuner or playlist endpoint. The public
example blocks `/hdhr`, `/output` and direct live-stream URLs. These stay
available over the private connection. Public browser stream previews using
those URLs are blocked too; use Plex or a trusted local connection for playback.
Do not send Plex playback through the Cloudflare Tunnel. Review Dispatcharr's
network-access settings before exposing any other output.

## Verification and troubleshooting

- Check `docker compose ps` and the configured health check. The setup-status
  response must contain a boolean `superuser_exists`, regardless of its value.
- With the Plex override enabled, confirm the local HDHR discovery and lineup
  endpoints respond and the XMLTV output contains your selected channels.
- Confirm the public UI loads with valid TLS and its management API requires
  login. Public tuner and playlist endpoints should return HTTP 403.
- If Plex cannot find the tuner automatically, enter its network address
  manually. Docker bridge discovery does not cross into Plex's host network.
- Empty lineups require channels created from streams, not just an imported
  M3U account. Check source availability and geographic restrictions when
  playback fails. Guide placeholders do not prove EPG coverage.
- The all-in-one image also supports FFmpeg stream profiles. Increasing stream
  concurrency or transcoding may require adjusting the resource limits. GPU
  access remains an explicit operator choice.

## Plugins

The [official plugin registry](https://dispatcharr.github.io/Plugins/) includes
IPTV Checker for feed checks, Stream-Mapparr for matching backup streams, and
EPG Janitor for finding missing schedules and reviewing guide matches. Install
through **Find Plugins** to retain managed versions and checksum verification.
Plugins execute application code and belong in the application-state backup.

Start with manual checks and matching previews. Keep automatic deletion,
renaming, stream replacement, and anonymous usage reporting disabled unless
explicitly chosen. Verify executable paths inside the selected image when
configuring IPTV Checker. Adding a plugin does not supply streams or schedules.

## Optional host maintenance

`maintenance/` contains opt-in host jobs for a Dispatcharr/Plex installation.
They use the existing Docker CLI and native database tools, not a Docker socket
mounted into an application container. They require the operator's explicit
configuration and privileged Docker access. Preparation does not install or
start these jobs.

1. Copy `maintenance/config.example.json` outside Git, restrict it to mode
   `0600`, and set the actual paths and expected mount source/type pairs. Keep
   the state directory under an existing application-data filesystem included
   in the ordinary encrypted backup. The runner refuses a missing or different
   recording/state mount instead of creating a local substitute.
2. Install `runner.py`, `django_adapter.py`, `policy.py` and `ersatztv.py` together in a
   root-owned directory. Review the two service examples, set their executable
   and configuration paths, and install the timers only after manual checks.
3. In IPTV Checker, retain scheduled probing, alternate-stream checks and
   quality suffixes. Disable its immediate scheduled deletion, dead-channel
   renaming/moving and recovery actions. Include `IPTV quarantine` in its group
   scope so quarantined streams get checked again. The runner reads completed
   checker results and owns quarantine/recovery, without patching plugin code.
4. A complete failed check moves an unprotected channel to `IPTV quarantine`
   and adds `[Unavailable]`. Deletion requires fourteen elapsed days and failed
   observations on at least three distinct UTC dates. Same-day retries do not
   count. Any working alternate clears the failure history and restores the
   original name/group. Missing, skipped, cancelled and partially checked
   alternatives cannot establish a dead channel. Weekly probing therefore
   requires at least three separate weekly runs before deletion.
5. Enabled channels in `protected_profiles`, groups beginning with `Local news -`, and
   channels with recordings or recurring rules are protected from deletion.
   A missing or renamed protected profile refuses maintenance. Profile
   membership and channel numbers are preserved during quarantine.
6. Run `runner.py backup --config /path/to/private.json`, then `runner.py check
   --config /path/to/private.json`. The daily timer runs at 02:20 America/Denver,
   before a typical 03:00 encrypted backup. Adjust it for another schedule.
   The check timer runs every fifteen minutes.

The backup job creates a PostgreSQL logical dump, restores it into an isolated
temporary database and checks application counts. It also snapshots Plex
databases with Plex SQLite and verifies separate restore copies, plus copies
application uploads, identity files, plugin code, scripts and the selected
private configuration. A file manifest is checked against a separate restore
copy. Only verified generations are retained; the default keeps seven. Failed
runs never remove successful generations. This is the consistent database and
configuration layer of recovery. Recordings, Plex artwork and other complete
application files still need the ordinary filesystem backup. Do not restore a
dump over a live service; preserve compatible images, stop the affected writer
and use an isolated recovery procedure first.

For bounded recording retention, create dedicated Plex DVR libraries using
the [Plex DVR override](../plex/README.md#dedicated-dvr-storage). Put only those
library IDs in `dvr_library_ids`, and select those libraries when scheduling
recordings. The job applies defaults once to each new series rule there:
five unplayed episodes and removal seven days after watching. The first check
records existing rule identities without changing them. Existing rules
and all other libraries are excluded. One-off/movie recordings retain their
native Plex policy. Plex's DVR settings control recording padding and
commercial detection; use skip markers to preserve footage rather than cutting
detected commercials. The helper does not impose retention on Dispatcharr's
recording files.

`alerts.yml` monitors guide freshness, recording failures, backup verification
age, recording mount/free space and missing/failed maintenance reports. Enable
the [Node Exporter textfile override](../node-exporter/README.md#host-generated-metrics),
copy the rules into Prometheus's mounted rules directory, add that file to
`rule_files`, validate and reload. Existing Alertmanager receivers remain in
control. Metrics contain fixed health values and counts, without credentials,
stream URLs or program titles. Check `systemctl status dispatcharr-backup` and
`dispatcharr-maintenance` after installation; a timer alone does not prove a
successful backup.

### Optional ErsatzTV correctness and recovery

The `ersatztv` maintenance option defaults to `null`. To enable it, set this
object in the private maintenance configuration, using identities resolved from
the current deployment. The numeric IDs below are examples, not discovery rules:

```json
{
  "container": "ersatztv",
  "config_root": "/path/to/ersatztv-config",
  "config_mount": {"fstype": "btrfs", "source": "/dev/mapper/apps"},
  "network": "ingress-admin",
  "recipe_file": "/path/to/private/ersatztv-recipes.json",
  "account_id": 1,
  "source_id": 1,
  "dvr_id": "1",
  "monitor_window_hours": 2,
  "restrictions": [],
  "derived": []
}
```

The observer verifies the container's existing configuration mount before using
it, and reads the API key from that private configuration. It publishes no new
port and does not mount a Docker socket into a container. Add the recipe file
and private service configuration to `configuration_files` so the existing
verified daily backup includes them.

Export a new mode-0600 recipe with `runner.py recipes-export --config
/path/to/private.json`. Export refuses an existing destination so it cannot
silently accept drift. The private recipe records channel definitions, filters,
manual collections, schedules, artwork references, presentation, output bindings
and explicit content restrictions. It contains installation-specific identities;
keep it outside Git and do not copy its IDs to another installation.

The existing check timer compares complete programme start/end times, titles and
episode subtitles across native XMLTV, Dispatcharr and Plex for every recipe
station over the configured window. Missing coverage, duplicate rows, gaps,
overlaps, changed mappings, restricted content and definition drift produce
numeric metrics. A successful import timestamp alone does not pass correctness.
Plex window filters use `endsAt>` and `beginsAt<` as parameter names; URL
encoding supplies the separating equals sign. Including an equals sign in the
name makes Plex ignore the window and can exhaust the response limit on a
large guide. The observer refuses truncated responses.
The existing alerts include low guide horizon and missing verified ErsatzTV
backups. Programme titles, endpoints and credentials are excluded from metrics.

Derived rules identify a source Smart Collection, its movie-only target and the
selected Movies library ID. `runner.py recipes-reconcile --config
/path/to/private.json` writes a private plan without changing the application.
Adding `--apply` permits only those derived changes and refuses independently
edited targets, active viewing or any scheduled recordings. It verifies a
current ErsatzTV recovery copy before applying, updates the recipe only after
checking persistence, and retains recovery data on uncertain failures. It does
not reset schedules or run automatically from the check timer. Saving a query
can itself refresh dependent native schedules, so the recording/viewing guard
applies even without an explicit reset command.

The optional daily backup uses SQLite's online backup API and before/after asset
hashes while playback continues. It includes required private configuration,
artwork, templates and station-ID clips. It excludes rebuildable search indexes,
Next/guide output and diagnostic logs. An isolated SQL/assets restore is checked
for every generation; prove index rebuilding and representative application use
on a network-disconnected restore when enabling or upgrading this workflow.
The backup binds the original image identity. Restoring credentials and database
files does not authorize starting an unisolated recovery instance.

Portable fixtures run without Docker or live configuration:

```bash
python3 -m unittest discover -s stacks/dispatcharr/maintenance -p 'test_*.py'
```

## Backup, update and recovery

Preserve `stack.env`, the private Compose override, the Caddy snippet and the
entire `dispatcharr_data` volume outside Git. The database contains account
information and source configuration, which may include provider credentials.

Before an image or configuration update, record the current image identity and
baseline account, channel, stream and source counts. Use a PostgreSQL logical
dump for a running database, or stop this service before copying the complete
volume. Do not copy PostgreSQL's live data directory as an ordinary file backup.
Restore the backup into an isolated database or service and verify readability,
application records and any uploaded files before proceeding.

After updating, verify login, channel and source preservation, HDHR/XMLTV output
and playback through Plex. An older image may not read an upgraded PostgreSQL
data directory. Roll back with the verified compatible image and restored state,
not just an older image tag. Remove only this operation's temporary backup and
restore copies after verification. Never use `docker compose down -v` as an
update or recovery step.

### Supplemental guides and channel organization

Additional public sources include [Plex US FAST XMLTV](https://github.com/matthuisman/i.mjh.nz/tree/master/Plex)
and [EPGTalk](https://github.com/acidjesuz/EPGTalk). Import only the needed guide,
refresh it, and review channel identity, region, current program intervals and
stream origin before mapping. Keep a working real mapping when supplementing
fallback channels. Matching display names alone can confuse regional feeds,
FAST variants and full OTA stations. No public source guarantees every channel
has a schedule.

Use genre groups for created channels rather than playlist/provider names.
Keep requested local news in `Local news - <city>`, and separate other US local
stations and community access from general entertainment. Preserve those local
group prefixes because the quarantine policy uses them for protection. Use the group filter with alphabetical
channel-name sorting when browsing Dispatcharr. Keep channel numbers and UUIDs
stable when Plex already uses them. Plex's DVR guide follows its channel
numbers and does not inherit Dispatcharr's group filters or table sorting.
Repair malformed imported display names explicitly rather than publishing raw
playlist attributes as channel names.

For an explicitly requested Plex reorder, reserve unused number blocks for
library channels, mosaics, local news, national news and genres. Keep local
stations together by city and use the chosen network preference within each
city. Sort genre channels alphabetically and leave room for additions. Change
only Dispatcharr's output numbers, preserving source station numbers, channel
UUIDs, streams, guide assignments and profile memberships. Capture an old-to-new
number map and restore-verify Dispatcharr and Plex backups first. Serialize the
change with other lineup writers, refresh the tuner and guide, and apply the
complete channel mapping. Verify every selected channel is still enabled with
the correct name and guide identity. Retain the existing DVR and recording rules.

When replacing FAST channels with library stations, compare actual available
content and scheduled guide entries before disabling a channel. A franchise's
movie station does not replace its television series, and a generic genre
station does not establish ownership of a particular show's episodes. Disable
reviewed overlaps in the Plex export profile rather than deleting their source
channels. Keep their numbers, UUIDs, guide bindings and streams for recovery.
A separate alternatives profile can retain those memberships outside Plex;
include that profile in maintenance's `protected_profiles` to prevent automatic
dead-stream deletion. Preserve unrelated profiles and multiview source channels.

### ErsatzTV program posters in Plex

Channel logos and program posters are separate. ErsatzTV builds program image
URLs from the host used to fetch its XMLTV guide. Docker service names can work
for Dispatcharr while host-networked Plex cannot resolve them. Plex 1.43.5 also
rejects private-address provider images in its photo transcoder, even when the
server can fetch those images directly. See the [Plex staff explanation](https://forums.plex.tv/t/pms-1-43-5-photo-transcoder-refuses-locally-hosted-cast-images-from-custom-metadata-provider/944043).

The optional `docker-compose.library-artwork.yml` override installs a guarded
nginx bridge through a wrapper around the original entrypoint. Enable it alongside
`docker-compose.plex.yml` only when ErsatzTV is reachable as `ersatztv:8409` on
a shared Docker network. Set `DISPATCHARR_LIBRARY_ARTWORK_ORIGIN` to the existing
public HTTPS Dispatcharr origin. The bridge adds no host port or data directory.
Preparation does not activate it.

Apply the ingress example's private-output matcher before enabling the bridge.
It keeps `/__library/*`, guides, tuner output and playback private. Only exact
poster, thumbnail and logo image paths are public. nginx accepts GET/HEAD only,
uses a fixed ErsatzTV backend and accepts no caller-supplied target URL. This
makes artwork anonymously reachable like the existing channel logo endpoint,
without exposing ErsatzTV administration, playlists or playback.

Back up and restore-verify Dispatcharr/Plex state and the operator's Compose and
ingress files. Change the existing ErsatzTV EPG source URL, preserving its ID and
channel bindings, to `http://127.0.0.1:9191/__library/xmltv.xml`. This private source
URL uses Dispatcharr's internal port. It emits the configured HTTPS image origin.
Keep the ErsatzTV playlist and stream URLs unchanged.

Docker DNS resolves the backend again after container recreation. The installer
refuses an unreviewed nginx template. Review it when changing the pinned image
rather than bypassing the hash guard. The wrapper installs only the guarded
locations, then executes the original `/app/docker/entrypoint.sh` with its
arguments. The image contains an unused custom-init directory, so mounting a hook
there does not activate the bridge.

Refresh that EPG source, invalidate generated XMLTV cache after import, and reload
the existing Plex guide without replacing its tuner or mapping. Verify movie and
episode image bytes through Plex's photo transcoder and inspect both hub rows.
Compare channel identities, enabled mappings and recording rules. Check public
image GETs succeed while guide, stream and invalid artwork paths remain denied,
and image POSTs fail. Roll back the source URL and override with the verified prior
configuration if any check fails. Preserve Movie/Series categories. A blank poster
alone does not justify changing program classification.

### Multiview and DVR metadata plugins

[Multiview](https://github.com/swvn-dispatch/dispatcharr-multiview) can generate a
separate mosaic channel while keeping its source channels available individually.
Install its matching PyAV dependency through the plugin action, then start with
720p, 24 fps, software `ultrafast`, four inputs and a single audio source. Verify
moving video in every tile, audible selected-source audio and resource use. A
valid output codec alone can conceal disconnected tiles. Prefer tested station
news feeds in the operator's requested network order. Generated mosaic guide
entries describe the layout and are not real program schedules.

The process limit is 1,024 for the all-in-one database, workers and media
threads. Multiview can exhaust a 512-thread limit when layouts overlap, even
with CPU quota headroom. Start with at most two simultaneous mosaic streams in
its generated M3U account and verify memory use before increasing concurrency.

For several layouts, reuse standalone station channels and keep a named layout
per city or network. Skip unavailable feeds instead of substituting national
news under a local station name. Use the requested network order for city
tiles and select one audio source explicitly. Test each tile through the HDHR
route after switching layouts. A thirty-second channel shutdown grace period can help
shared inputs survive quick switches. For real-time feeds, avoid requiring a
measured FFmpeg speed of exactly 1.0x. For copy profiles whose source timestamps
make this statistic unreliable, a buffering-speed threshold of zero disables
that heuristic. Packet timeout, retry and failover checks still apply. Restart
affected streams after changing it, since
each input manager captures that value at startup. Recheck XMLTV after source refreshes
finish, because invalidating a chunk cache during export can leave a partial
response. Regenerate the cache through the native invalidation helper and verify
a complete XML document before refreshing Plex.

For public HLS feeds that need Streamlink, use an explicit `best` profile.
`--no-config --no-plugin-sideloading --stdout {streamUrl} best` avoids unrelated
per-user configuration and plugin-directory lookups. Some feeds benefit from normalizing MPEG-TS headers, tracks and timestamps.
The optional
[public-HLS remux bridge](helpers/public-hls-ts.py) runs Streamlink into FFmpeg
with stream copy, bounded child-process cleanup and no shell pipeline. Install
the reviewed file in `/data/scripts/public-hls-ts.py` and use a profile command
of `python` with parameters `/data/scripts/public-hls-ts.py {streamUrl}`. The
persistent `/data` backup must include this script. Preparation does not install
it or activate the profile. Keep an independently
configured profile for authenticated services or operator extensions.

A reviewed [Multiview 0.5.0 compatibility patch](patches/README.md) handles large
forward source timestamp jumps that can leave a tile blank while audio plays.
It is an explicit operational workaround and is not applied by preparation.

The plugin uses port 9292 inside the container. Leave its optional dashboard
disabled and do not publish that port when Dispatcharr alone consumes its
playlist and stream. The normal HDHR/Plex path can carry the generated channel.
Use the Proxy stream profile for an already encoded MPEG-TS mosaic rather than
reprocessing it with an HLS-specific input profile. Keep stable channel numbers
when adding it to an existing Plex DVR. Plex channel-map updates require the
complete existing mapping set; preserve it when adding channels and verify the
resulting enabled set.

[Clapparr](https://github.com/v8eta/clapparr) writes NFO sidecars, posters and
thumbnails for Dispatcharr DVR recordings. Configure the existing recording
root, automatic processing after remux completion, air-date title fallback and
no overwrites. Keep fuzzy artwork matching disabled for local news. Its preview
action can check the scope without modifying existing files. This does not add
sidecars to recordings made by Plex's own DVR. Plex consumption of NFO files
requires a compatible NFO agent and season/episode filenames, with the plugin's
documented watch-state synchronization limitation. Preserve existing library
agents when only configuring sidecar generation.

[Twitcharr](https://github.com/eliasbruno124-dev/Twitcharr) uses the container's
Streamlink installation and anonymous Twitch metadata. The operator selects
channels or discovery rules; installation does not require Twitch credentials.
