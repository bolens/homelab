# IPTV reliability acceptance evidence

Implementation and live configuration were performed after the prospective spec,
plan and tasks were written. Private topology, credentials, database snapshots
and runtime configuration remain outside Git.

| Check | Evidence |
| --- | --- |
| Baseline recovery | Native PostgreSQL dump restored in isolation; native Plex SQLite snapshots restored and integrity-checked before live changes. |
| Matching guide | HDHR, profile XMLTV channel IDs and enabled Plex mappings agree on the same 450 channels. Original DVR and device identity retained. |
| Guide quality | Five exact local FAST guide mappings added through Roku/Pluto and twelve additional unambiguous current US FAST mappings. Three requested local feeds retain labeled fallback schedules rather than unrelated OTA schedules. |
| Alternate streams | Thirteen additional stream links across seven channels passed audio/video decoding. A hidden, disposable channel with a refused primary successfully decoded its backup; the fixture was removed. |
| Quarantine | Eleven synthetic fixtures cover independent failed days, elapsed-age admission, all-stream coverage, recovery, exclusions, crash replay, mount refusal, failed-backup retention and metric permissions under a private umask. |
| Recording defaults | Both DVR paths use one-minute pre-padding and two-minute post-padding. Plex uses non-destructive commercial markers and six-hour guide refreshes. Separate DVR libraries preserve shared media libraries. |
| Future series retention | Only new series rules targeting the configured dedicated DVR libraries are eligible for five-unplayed/seven-day-watched defaults. Existing rules are excluded. The first real series-rule mutation remains a first-use check because no recording rule was created solely for validation. Synthetic scope fixtures passed. One-off/movie recordings keep native policy. |
| Recurring recovery | Daily native database/configuration backup completed with isolated database/file restore checks. An encrypted Restic snapshot was restored separately and all manifest hashes matched. The refreshed recovery scope also includes installed job code, units and monitoring configuration. |
| Monitoring | Five native promtool scenarios passed: healthy, storage failure, guide failure, failed backup and missing report. Existing Alertmanager routes are reused; no synthetic external notification was sent. Collector ingestion closure is recorded with final checks below. |
| Preservation | Original Dispatcharr channel identities/numbers/names, user credentials, source identity and recording records preserved. All baseline physical Plex library records and recording rules preserved. |
| Repository contracts | Optional Plex DVR and Node Exporter textfile overrides passed isolated Compose fixtures without creating missing paths or opening ports. Python source lint passed. |

## Final checks

`make validate` passed, including repository Markdown/link checks, metadata,
preparation, generated output and native helper checks. Eleven maintenance
fixtures, two new optional Compose fixtures and five native promtool scenarios
passed. Live Prometheus ingests the successful maintenance metric and all five
IPTV rules are healthy and inactive. Both root timers are enabled.

The expanded daily generation passed native restore checks. Its encrypted Restic
restore matched all 115 file hashes. All 79,571 baseline physical Plex records,
existing DVR/device identities and recording rules survived. After the final follow-up preservation checks and native backup restore
verification, temporary operation backup/restore copies were removed. Scheduled
verified generations and encrypted Restic snapshots were preserved.

## Recovery behavior

The existing Restic container had a stale repository bind: the repository config
was readable on the host and failed with I/O errors inside the container. With
no backup writer active, restarting that same container restored access while
preserving its image, environment, mounts and repository config bytes. Scoped
encrypted backup/restore then succeeded. Existing retention was preserved.

When adding the Plex DVR mount, the base image selector was not cached locally.
The live private override retained the exact existing local image identity;
no image pull or upgrade was performed. Existing mount/environment contracts
were checked after recreation.

## Supplemental guide and organization follow-up

Two additional sources, Plex US FAST and EPGTalk US, imported successfully with
six-hour refreshes. Thirty-one reviewed current matches replaced fallback
mappings, including three Plex channels. Coverage is now 461 channels in the
full catalog and 354 of 450 in Plex. The other 96 Plex channels retain explicit
fallback listings. The EPGTalk local and FreeTV guides were inspected but not
added because they supplied no additional verified exact-feed Plex matches.

Genre corrections affected 118 channels, including starter channels, US local
stations, community channels and identifiable entries in generic groups.
Twelve display names were corrected, including requested city/news labels and
three malformed playlist-derived names. All 2,203 channel UUIDs and numbers,
profile memberships, user credentials, original sources and recording records
were verified after these changes. Plex group filtering remains separate from
Dispatcharr groups. No channel renumbering was performed.

## Plex blank-label repair

All 450 exported and native Plex channel records had names. The guide advertised
cached logo URLs on loopback, which remote clients could not load. The guide URL
now includes `cachedlogos=false`: 444 logos use public HTTPS addresses, six
channels have no logo, and none reference loopback. The existing DVR/device and
all channel mappings were checked unchanged. The guide itself remains fetched
privately over loopback. After refresh, the live Plex guide visibly rendered logos in the previously
blank rows and text labels where logos were absent. Dispatcharr name sorting
was set to ascending and observed in the loaded table. This browser preference
does not reorder Plex channels.

## Multiview and recording plugin follow-up

Official Multiview 0.5.0, Clapparr 1.3.0 and Twitcharr 1.3.2 were installed.
Multiview's PyAV dependency came from PyPI. The optional dashboard remains off,
with no new published port or GPU/device access. The requested network order is
NBC, ABC, CBS, FOX. Public streams embedded on the official 9NEWS, 11Alive and
KING 5 watch pages passed video/audio decoding, as did existing NBC TMJ4.
These NBC feeds are the selected four tiles, with Denver audio. Earlier city
channels, including Minneapolis and Denver CBS, remain separate channels.

Clapparr is enabled for the existing Dispatcharr recording root, automatic
missing-sidecar generation, representative 640-pixel thumbnails, air-date titles,
no overwrites and no fuzzy artwork guesses. Native preview found zero existing
recordings to modify. Its native packaged tests passed: 18 artwork-selection,
17 webhook and 12 ownership/Plex-refresh cases. Actual sidecar generation on a
future completed recording remains a first-use check. Twitcharr is installed,
with Streamlink present, for the operator's channel configuration.

Final mosaic acceptance used a 55-second encoded sample. Decoded frames at two
times differed in each tile, Denver audio was non-silent, and a separate
15-second test through the Plex tuner's actual Dispatcharr route succeeded.
The output is H.264 1280x720 with one AC3 audio stream. A live resource sample
was about 28% CPU and 1.64 GiB within the existing two-CPU/3-GiB container limits.
Normal station commercial-break slates remain part of the free feeds.

Plex now enables 455 channels. All original 450 complete channel mappings remain
byte-for-byte equal, with five additional entries: Denver CBS, the mosaic, and
NBC news feeds for Denver, Atlanta and Seattle. Existing Milwaukee NBC was reused.
The original DVR and device were retained. The added NBC stations use clearly
labeled fallback guide entries because exact FAST schedules were not found.
The mosaic's generated guide describes its layout; it is excluded from claims
of real schedule coverage.

## City and network expansion checks

The preservation baseline captured 2,208 existing channels and memberships,
credential/recording/source identity hashes, all 455 enabled Plex mappings and
79,576 physical-library metadata IDs. The expanded lineup has 18 standalone
city/network station feeds and ten mosaics, for 469 enabled Plex channels.
Native channel-map replacement preserved every original enabled mapping.
Five city mosaics follow NBC, ABC, CBS, FOX, skipping unavailable networks.
Four network mosaics include every verified market feed. The original four-city
mosaic retains Denver audio. Sanibel/Fort Myers currently has only FOX 4, so the
plugin's two-input minimum prevents a city mosaic there.

Tests found and corrected three concrete failures: malformed Uplynk playlists
worked through the existing Streamlink profile, concurrent encoders exhausted
the 512-thread container limit, and the 1.0x buffering threshold rejected valid
real-time input measured at 0.996x. The live and tracked process limit is now
1,024. Generated-account concurrency is two. Proxy shutdown grace is thirty seconds,
client initialization wait is fifteen seconds. The reported-speed buffering
heuristic is disabled with a zero threshold after both 1.0x and 0.8x produced
false buffering on timestamp discontinuities. Packet timeout, retry and
failover checks remain enabled.
Affected streams were stopped through the native channel service so new managers
use the changed threshold. CPU and memory limits remain two CPUs and 3 GiB.
The resource investigation found no OOM kill.

PBS research covered the main member stations in all six markets. Current
players declare DRM feeds without clear alternatives. Initial plain HLS update
notices and secondary WORLD/Create feeds were excluded as main PBS replacements.
No local main PBS feed passed admission, so no misleading PBS mosaic was added.

The final resource sample reached 574 threads/processes under the new 1,024
limit and 2.64 GiB of accounted container memory under the 3 GiB limit. No OOM
kill occurred. The Plex guide database contains 43 airings for each of the ten
mosaics, and the browser guide visibly shows their named listings. The native
recovery generation contains 447 hashed files, including the final public HLS
bridge and patched plugin. A separate encrypted Restic
snapshot was restored in isolation with every hash matching that generation.
A same-image Dispatcharr restart applied the saved proxy settings and cleared
old input workers. Existing channels, credentials, recordings, memberships and
Plex physical-library records passed preservation checks afterward.

Final acceptance: all ten layouts decoded through the HDHR profile's actual
stream URLs. Every configured tile was visible in sampled frames and each
selected audio track decoded with non-silent samples. City and network layouts
were tested separately, including the five-market NBC layout and five-market
FOX layout with Fort Myers. Denver/CBS and Minneapolis/FOX received longer
60-second repeat captures after compatibility changes. The original four-city
layout retains moving Denver video and Denver audio.

The Multiview 0.5.0 patch passed an isolated dry-run against the exact reviewed
source, syntax parsing and subsequent real-media acceptance. Its original
source hash is documented as a guard for future upgrades. The optional public
HLS bridge passed two isolated tests covering input rejection and child-process
cleanup, Ruff and the live media path. A raw FOX input probe identified MPEG-TS,
so the initial fMP4 mismatch hypothesis was not confirmed. The retained bridge
normalizes track selection, transport headers and timestamps without video
re-encoding. Built-in Streamlink and Twitcharr configuration remain unchanged.

## Explicit channel-number organization

The operator requested Library TV first, followed by multiviews and news.
A guarded first attempt refused concurrent station additions without writing.
After the other integration chat confirmed its lineup writes were complete,
a fresh baseline captured 2,235 Dispatcharr channels and 482 enabled Plex
mappings, including thirteen Library TV stations. The native recovery job
restore-verified PostgreSQL and Plex snapshots and 460 file hashes before the
number change.

The selected output numbers changed atomically to reserved blocks: Library TV
100–112, mosaics 120–129, requested city news 200–259, other US locals 260–289,
national news 300–339, weather 340–349, business 350–369 and genre blocks
400–989. Genre channels are alphabetical. Local city blocks follow Denver,
Milwaukee, Atlanta, Seattle, Minneapolis and Sanibel/Fort Myers, with available
networks in NBC, ABC, CBS, FOX order. Source ErsatzTV numbers remain 9001–9013.

All 482 selected tuner/XMLTV/Plex number sets agree, with original names and
stream URLs preserved. Every exported channel has guide entries. Channel IDs,
UUIDs, remaining fields, groups, memberships, stream bindings, plugins, users,
recordings, source identities, Plex DVR/device identities, recording rules and
physical-library IDs passed preservation checks. The 1,753 unselected channels
remain unchanged. Neither container was restarted or reconfigured. After the
post-mapping guide reload, the Plex UI visibly showed Library TV first, then
mosaics, with logos and populated listings. The existing evening gap in the
Morning Cartoons schedule remains outside this number-only change.

The repository gate `make validate` passed after the ordering procedure was
documented and Pages regenerated. The final check confirmed all 482 Plex guide
titles and sorted numbers match the plan, and the guide rebuild completed.
Temporary catalog/configuration and isolated verification copies were removed.
The private old-to-new channel map and compact receipts remain available;
verified recovery generations and retention remain unchanged.

## Library overlap cleanup

The operator requested both close duplicates and generic movie/TV/cartoon
channels covered by ErsatzTV, with replacement station changes if needed.
The current lineup already had 65 custom stations and 4,154 exported program
entries, with no empty custom guide channels. Those stations covered all
reviewed replacements, so no ErsatzTV station or collection changes were needed.
A current native Dispatcharr/Plex backup passed isolated restore verification
before the profile change.

The reviewed exclusions comprise 58 channels: 32 movie feeds, four series feeds,
four entertainment feeds, six comedy feeds, one classic movie feed, one animation
feed, nine kids feeds and one documentary feed. Portlandia has 77 library
episodes. The branded Totally Turtles feed was matched to the library's Teenage
Mutant Ninja Turtles series and the explicit Retro Cartoons collection member.
Community-access channels containing the word Community were rejected as false
show matches. Foreign-language, preschool, specialized curated feeds and dedicated
series without a verified local equivalent remain enabled. Movie-only franchise
stations were not treated as substitutes for their television series.

The Plex export now contains 476 selected channels, retaining all 65 custom
stations, news, local news, weather, sports and mosaics. Disabled memberships
remain enabled in a separate alternatives profile included in maintenance's
protected profiles, preserving reversible sources without exposing them in Plex.
The complete Plex mapping retains every remaining channel's original mapping
attributes, number and stream URL. Existing source channel records, UUIDs,
streams, groups, guides, plugin settings, users, recordings, unrelated profile
memberships and DVR/device identities were preserved. Concurrent artwork-only
updates from the other authorized chat were retained independently.

The final guide API and browser checks passed. All 476 guide channel titles and
IDs match the reduced tuner and mapping set, and all 58 alternatives are
protected from quarantine. Temporary configuration/catalog verification copies
were removed, preserving verified backup generations and the private channel
report. The documented profile procedure and regenerated Pages passed
`make validate`.


## Dedicated library replacements

The follow-up adds Portlandia at output 165 and Teenage Mutant Ninja Turtles at
166, using ErsatzTV source numbers 9066 and 9067. The artwork chat held its
runtime writes and supplied the two reviewed logos. Both stations use exact
library series queries, season/episode ordering, multipart preservation and a
random starting point. Their schedules contain only the intended series.

A fresh native Dispatcharr/Plex recovery generation passed restore verification.
ErsatzTV was stopped for a complete configuration/state backup. The isolated
restore matched file hashes, ownership and modes, and SQLite integrity and
foreign-key checks passed. An isolated append-only fixture passed before the
live change. ErsatzTV restarted with its original image and container settings.

The new schedules exported 178 Portlandia and 170 TMNT program entries. The
Dispatcharr library guide refresh had to follow completed schedule generation.
After that import completed, invalidating guide chunks restored a complete
XMLTV document. The full 478-channel Plex mapping preserves the original 476
mapping attributes. Both actual exported tuner URLs passed changing decoded
video-frame and audible-audio checks. All original 65 station, collection,
schedule and artwork rows and original media IDs survived unchanged. Existing
Dispatcharr records and memberships, Plex library IDs, DVR/device identities and
recording rules passed preservation checks. All three services were healthy.

Final counts are 67 custom stations, 478 enabled Plex channels and 58 protected
alternatives. The guide rebuild completed and the guide API titles and IDs match
the tuner export. Private receipts and the exclusions report remain outside Git.

The Plex browser visibly showed both new logos and episode listings immediately
before the multiview block. Temporary operation backup, isolated restore, database
snapshots and media probes were removed after acceptance. Existing backup
retention was preserved. The artwork chat received the final lineup and resumed
ownership of its deferred logo audit. `git diff --check` passed after this evidence
update. The earlier full repository `make validate` gate remains passing for the
profile procedure and generated Pages changes.


## Four additional approved genre overlaps

After reviewing the remaining library gaps, the operator explicitly approved
hiding Pluto TV Franchise Favorites (440), The Asylum (564), Classic TV Crime
Drama (702) and Classic TV Drama (703). A fresh native Dispatcharr/Plex backup
passed isolated restore verification before changing the four memberships.
The existing protected alternatives profile now retains 62 enabled alternatives.
All source channel records, current logo bindings, streams, guide assignments,
unrelated profile memberships and application settings were preserved.

The complete Plex mapping now enables 474 channels, including all 67 custom
stations. The exported tuner and XMLTV channel sets agree with the final Plex
guide after its rebuild. Every remaining mapping attribute, DVR/device identity,
recording rule and existing physical-library metadata ID was retained. All three
containers remained healthy with their original images, mounts and settings.
Temporary operation verification copies were removed and native backup retention
was preserved. The artwork chat received the final counts and release to continue
its separately requested vertical-alignment work.

The available guide listings identify missing classic series: Barnaby Jones,
original Hawaii Five-O, In the Heat of the Night, The Streets of San Francisco,
Diagnosis Murder, Hunter, original MacGyver, The Fugitive and Walker, Texas Ranger.
The guide title The Covenant describes a Walker episode rather than a movie.
Twin Peaks is already present. The Asylum's currently listed missing films are
2012: Supernova, Ardennes Fury, Meteor Apocalypse and Super Cyclone. All currently
listed Franchise Favorites films are already in the library. These observations
cover available guide listings, not a complete provider catalog. Private audit
and acceptance receipts remain outside Git. `git diff --check` passed.


## Plex program-card artwork

The operator's browser evidence showed custom programs already present in What's
On Now and Shows On Now, with blank poster cards. The exported XMLTV contained
program icons, but their Docker service hostname could not resolve from the
host-networked Plex container. A private relay made image GETs work from Plex's
container, while Plex's photo transcoder still rejected the same image with
curl code 42 and a pre-request callback refusal. Its public channel-image requests
worked. A Plex staff explanation confirms provider images must be publicly
reachable starting in Plex 1.43.5. This ruled out missing or corrupt JPEGs and
avoided speculative Movie/Series category changes.

The optional bridge preserves the existing library EPG source identity and uses
container-loopback XMLTV ingestion. It advertises only the existing public HTTPS
Dispatcharr image origin. Strict nginx paths relay poster, thumbnail and logo
GET/HEAD requests to the fixed ErsatzTV backend. Caddy allows only those exact
image paths while denying guides, tuner/stream outputs and other artwork paths.
No new listener, host port or public administration route was added. The original
entrypoint runs after a hash-guarded nginx installer. The image's shipped custom
init directory proved inactive, so a tested entrypoint wrapper replaced that
initial approach.

The fresh native Dispatcharr/Plex backup passed isolated restore verification,
and private Compose/ingress copies passed byte-for-byte restore checks. The
reviewed nginx fixture passed native syntax validation. The same pinned image
was retained through recreation. Public JPEG fetches and Plex photo-transcoder
requests passed for a movie and an episode. Real public requests with a normal
image-client user agent verified guide/tuner/invalid image paths and image POSTs
return 403. The initial Python-default user agent was separately blocked by
Cloudflare, so its 403 responses were not accepted as origin-policy proof.
Focused installer/optional-Compose tests and the full `make validate` gate passed.


The final guide rebuild completed. All 474 mapping attributes, existing channel
records and logos, streams, profile memberships, plugin settings, users and
recordings passed preservation checks. All 67 ErsatzTV channel definitions and
artwork records remained unchanged by this operation. Recording rules and DVR
identity were retained. A temporary verification file initially had root-only
ownership in the container; correcting that test-file ownership allowed the
native preservation check to complete without any application-data changes.
The browser visibly showed custom posters in both requested rows. No program
categories or Plex library matches were changed. Private screenshot and compact
receipts remain outside Git.

All three services passed final health checks. Operation configuration, database,
reviewed-source and image verification copies were removed after browser proof.
Native backup retention was preserved, and the artwork/content chat received the
new guide URL, startup/ingress contract and runtime release for its next pass.
