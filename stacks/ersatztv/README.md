# ErsatzTV

ErsatzTV Legacy creates scheduled television channels from an existing media
library. It exports M3U playlists and XMLTV schedules for Dispatcharr, Plex,
Jellyfin and other IPTV clients.

**Website:** https://ersatztv.org\
**Docs:** https://ersatztv.org/docs/\
**GitHub:** https://github.com/ErsatzTV/legacy\
**Docker image:** https://github.com/ErsatzTV/legacy/pkgs/container/legacy\
**Releases:** https://github.com/ErsatzTV/legacy/releases

## Setup

1. Set `ERSATZTV_MEDIA_PATH` in private `stack.env` to the existing media root.
   Verify its filesystem source and type before preparation. Neither preparation
   nor Compose creates a missing media directory.
2. Run `./prepare-stack.sh`, then review `stack.env` and `caddy_snippet.conf`.
   Preparation preserves existing files, synchronizes the generated `.env` mirror
   and ensures `ingress-admin` and `media-services`. It never starts containers.
3. Configure the private ingress names and, if needed, the protected tunnel
   hostname described below. Keep private hostnames out of committed examples.
4. Deploy with `docker compose up -d` and verify health and media access.

The image is pinned to the reviewed Legacy release and immutable digest. The
container publishes no host ports, drops Linux capabilities and disables new
privileges. CPU, memory, process and log limits are explicit. Optional GPU
acceleration requires a separately reviewed device/driver override. It is not
enabled by preparation.

For NVIDIA hosts with NVIDIA Container Toolkit, enable the reviewed optional
`docker-compose.nvidia.yml`, select a GPU index or UUID with `ERSATZTV_GPU_ID`,
and deploy with both Compose files. Alternatively, copy that override to the
ignored `docker-compose.override.yml` after preserving any existing override.
The override grants one NVIDIA GPU with video, compute and utility capabilities.
Select an NVENC FFmpeg profile in the application and apply it to each channel.
Verify an actual hardware encode and channel playback; the health warning alone
does not establish that acceleration works. Keep the bundled FFmpeg and Next
versions matched to the pinned supported Legacy release.

## Environment and storage

| Variable | Required | Description |
| --- | --- | --- |
| ERSATZTV_MEDIA_PATH | Yes | Existing mounted media root, read-only at `/media` |

Timezone and locale come from optional `../../shared.env`. Re-run preparation
after editing `stack.env` to refresh `.env`. Do not put Plex tokens or API keys
in committed files.

The `ersatztv_config` volume preserves the SQLite database, configuration,
artwork and search index. `/transcode` uses a disposable 2 GiB memory filesystem.
Media remains in its original filesystem and is mounted read-only. Long-running
or high-bitrate streams may need an explicitly sized scratch-storage override.

## Authentication and tunnel ingress

The selected release has no built-in username/password form login. Optional
OIDC protects the UI, and the management API uses `X-Etv-Api-Key`; API keys alone
do not protect the browser UI. Protect the complete public management hostname
with [Cloudflare Access](../../documents/ACCESS-SSO.md).

1. Create a self-hosted Access application for the exact management hostname.
   Attach a restricted existing owner policy. Do not use an Everyone Allow or
   Bypass policy. Keep default-deny behavior for other visitors.
2. Add the tunnel hostname with service `http://caddy:80`. Enable connector-side
   Access JWT validation using that application's audience and team name.
3. Replace the example connector source address in the private Caddy snippet
   with its actual fixed address. The public HTTP route accepts only that
   connector. Other clients receive HTTP 403. Do not add a public HTTPS origin
   route that bypasses Access.
4. Publish DNS only after those protections are configured. Confirm anonymous
   public requests require Access login and direct origin requests are denied.

The example also provides private TLS names for trusted administration and
playback. Both proxy routes explicitly use HTTP/1.1. Use the private service URL
for playlist, schedule and stream traffic; Access browser sessions are not a
playback credential for Dispatcharr or Plex.

## Plex library and Dispatcharr integration

1. Connect the Plex media source in ErsatzTV and enable synchronization for
   selected movie and television libraries. The [Plex stack](../plex/README.md)
   exposes `http://plex:32400` through its private proxy on `media-services`.
2. For playback from disk, replace Plex's `/data` path prefix with `/media` in
   ErsatzTV's Plex path replacements. Verify actual media access. Alternatively,
   use the default Plex streaming mode.
3. Build Smart Collections from library metadata, such as genre or show, then
   create channels, schedules and playouts. Smart Collections update their
   matching content automatically. They do not invent additional stations.
4. Copy the M3U and XMLTV URLs from ErsatzTV's UI, using private
   `http://ersatztv:8409` service addressing. Add them as a Standard M3U account
   and XMLTV source in [Dispatcharr](../dispatcharr/README.md). Both services
   share `ingress-admin`.
5. Create channels from those streams and map their ErsatzTV guide identities.
   Assign unused stable channel numbers and include them in the existing Plex
   export profile. Preserve all existing channel UUIDs and numbers.
6. Refresh the existing Plex tuner lineup and guide, then verify playback with
   picture and sound. Plex uses Dispatcharr's HDHomeRun output and a separate
   XMLTV guide and requires Plex Pass. Preserve existing DVR identities and rules.

When updating Plex's device channel map through its API, submit the complete
existing mapping together with the additions and the intended enabled set.
The update replaces guide bindings. Compare every original binding afterward;
enabled flags alone do not establish guide preservation. Normalize numeric
identifiers before comparing mappings. Assert unique device identifiers and
compare the number of returned mapping rows with that unique count; converting
a duplicate list to a dictionary can conceal a missing binding. Verify every
expected custom station is actually enabled after adding or renumbering it.
Reserve unused numbers between library stations and later groups when planning the output lineup.
Changing Dispatcharr output numbers also requires refreshing the tuner channel
list and updating Plex's complete guide mapping; ErsatzTV source numbers can stay
unchanged.

### Library-powered network and creator collections

The [portable collection presets](channel-logos/channel-presets.json) describe
network, studio, director and franchise filters. They contain no deployment IDs.
Resolve the intended Movies and TV library IDs locally, and fence the complete
query with the exact `library_id`, media `type` and quarantine exclusion.
Map `shows` to `show_title`, `network` to `show_network`, movie `tag` to
`tag_full`, and `title_and_year` to `title_and_year_search`. `show_tag` is the
matching episode field for ordinary Plex show labels. A network genre condition
applies to its network branch; a whole-pool show-genre exclusion stays outside
the union. The NBC Comedy preset excludes animation/anime because Plex's `NBC`
network tag can also identify a Japanese broadcaster.

These channels play the owner's library. They are not live feeds from the named
networks. FX/FXX, Comedy Central, HBO/Max, Showtime, AMC, NBC comedy, Apple TV,
Prime Video and Netflix use native Plex network tags plus reviewed series-title
fallbacks. Network tags catch future series; title fallbacks catch future episodes
when network metadata is missing. Do not infer a broadcast network from a generic
production studio such as Sony Pictures Television or Universal Television.
Keep future imports eligible through verified metadata or intentional Plex labels.

Don Bluth, James Cameron and Martin Scorsese use director metadata, with reviewed
film aliases where needed. A24 uses studio metadata, a reviewed catalog and an
optional `ETV A24` Plex label because a distributor may be absent from the studio
field. Stargate Command TV selects only episodes of the three named Stargate
series. Episode stations rotate show groups with chronological episodes and
multipart-story preservation. Movie stations shuffle complete films. Verify
actual programme titles instead of grouping the guide into channel-name blocks.

The example lineup keeps favorites first, followed by movie genres, family/studio
collections, directors, franchises, seasonal programming, television collections,
networks and cartoons. Its current custom range is 100–208, leaving 209–299 for
future additions before multiviews at 300+. Preserve source IDs and original
non-library numbers when changing these output positions.

### Channel artwork

See [logo source notes](channel-logos/README.md) for the reference marks and
geometry used in the studio and franchise refinements. The
[example lineup manifest](channel-logos/lineup.json) records current display names,
artwork slugs and grouped guide positions. Refresh complete tuner mappings after
reordering output numbers, then compare station UUIDs, programmes and recording
rules separately from those changed positions.

`channel-logos/` contains editable SVG originals and 768 × 384 PNG exports for
95 stations, including personalized nighttime and morning cartoons, Halloween
and holiday movies,
television genres, movie decades, studio and franchise films, sports movies,
network-themed cartoons, fighting movies, classic cinema, nature documentaries,
bedtime cartoons, seasonal film/episode stations, Portlandia, Teenage Mutant
Ninja Turtles, LEGO adventures, Alien/Predator, Marvel multiverse films, adult
animation films, Mission: Impossible, the 2010s/2020s movie decades, Anime Action,
Unexplained, Mindbender Cinema, Wes Anderson Cinema, Illumination, Blue Sky,
Sony Animation, LAIKA/Aardman, Spielberg, Tim Burton, Nolan, Ridley Scott and
Villeneuve, Amblin, Blumhouse, Legendary, New Line, Warner Animation and Josh Gates. The 2:1 artwork puts a large symbol beside the station name to use more of a guide's horizontal space.
Use a recognizable motif for each theme, with enough space between strokes to
read at guide size. Keep detailed features secondary to the main silhouette.
Check target channel names and IDs against the live inventory before installing
artwork; older SVG titles may contain descriptive text.
For concurrent authorized lineup maintenance, retain the original baseline and
verify only the other operation's exact reviewed delta. Preserve its profile
choices and remaining Plex mappings; do not restore an obsolete export count.
Upload the PNGs as channel logos in ErsatzTV and Dispatcharr. Preview small guide
thumbnails as well as full-size artwork when changing the originals. Use names
that distinguish movie collections from television series. Update the artwork
when renaming a station, and preserve its source number and channel identity.
Save artwork changes through the application so its cached XMLTV channel list
refreshes. Verify the exported icon URL and its actual image bytes as well as
the visible logo; a changed database path alone does not prove the guide uses it.

Library names use tokenized matching: a quoted name can also match a longer
name. To bind a station to one library, resolve and use its exact `library_id`
from the current inventory. Do not copy internal IDs between installations. Apply
that boundary to every branch, including title/show aliases and helper
collections. Test a same-named foreign library as well as a longer library name.

Preview each Smart Collection against the complete indexed library. Title
punctuation affects token matching: a prefix such as `title:scooby*` also
finds hyphenated and colon-suffixed titles. Check franchise variants explicitly.
Decade queries use compact `release_date` bounds such as `[20100101 TO 20191231]`.
When a verified film has a year but no release date, retain the date-range rule
and add a scoped title/year fallback; do not silently omit that film.
For multipart stories, review all parts when rating-based filters include only
one installment. Broad Marvel programming should also account for legacy Hulk,
Big Hero 6 and LEGO Marvel adaptations without broadening the MCU-only station.

Check literal title tokens with the native index: punctuation can require a prefix
or an exact title/year alias. LEGO movie rules should include crossover specials,
while broader Marvel collections stay separate from MCU-only programming.
Keep family animation guarded against known incorrectly tagged live-action films.
Morning Cartoons uses a Saturday-morning-style mix of children's cartoon
episodes throughout the day. Apply an explicit `type:episode` boundary to its
complete query, including title aliases; family animation films belong in their
separate movie stations. Keep mature anime in the appropriate anime stations.
Use shuffled show groups with chronological playback within each group and
Multiple mode's multi-episode group size. This gives each show a turn while
keeping multipart stories together. Chronological order retains season-zero
cartoon shorts; Season, Episode order excludes them in the pinned release.
Keep normal guide entries and no custom block title. Verify contiguous playout
and XMLTV entries, then compare Plex's
actual show names, episode names and airtimes. Channel-name placeholder blocks
can represent scheduling gaps even when the guide imported successfully.
Apply the quarantine exclusion outside each complete television query, including
curated show lists. Simplify obsolete movie branches when a station has become
episode-only, then verify native-index membership is preserved.

Josh Gates: Expedition TV rotates the reviewed Expedition Unknown, Expedition X,
Expedition Files and Josh Gates Tonight series, including the separately titled
Hunt for Extraterrestrials miniseries. Its Smart Collection also admits future
Destination Truth episodes and the separately titled Search for the Afterlife,
Megalodon, Shark Secrets and Expedition: Back to the Future series. Match explicit
series titles inside the selected TV library and episode type, with the quarantine guard applied to the entire pool.
Do not use an `Expedition*` wildcard, which also admits unrelated series. The
schedule shuffles show groups, keeps episodes chronological within each group
and preserves multipart stories. Use actual episode titles in the guide.

Keep Family Toon Theater animation-only. Family Movie Matinee selects live-action
G/PG and suitable television-rated family films. Exclude animation except for
explicitly reviewed live-action/animation hybrids. Require the selected Movies
library and the global quarantine guard on every branch.
Air Bud and Buddies films belong in family programming and fitting seasonal
channels, not Sports Cinema. Apply the franchise exclusion outside the complete
sports union, even when a film has a valid Sport genre. Use token-aware terms
such as `title:(air AND bud*)` for colon-suffixed Air Bud sequels; a quoted
`"Air Bud"` phrase alone misses `Bud:` under the native whitespace analyzer.
A family-genre `buddies*` guard covers future themed additions without excluding
unrelated titles such as Buddy or The Grand Budapest Hotel.
Review holiday plot matches for character names such as “Lloyd Christmas” and
incidental prologues; use scoped title/year exclusions for verified false matches.

Sitcom Shuffle keeps scripted comedy separate from nonfiction and talk programming.
Apply `show_genre` exclusions for documentary, reality and talk-show categories
outside the complete comedy query. Prime Crime TV focuses on live-action crime;
exclude inherited animation genres outside its complete query. Preserve the
source genres and retain those series in their fitting cartoon, documentary,
variety and franchise stations. Test future imports and confirm that every other
current member survives either change.

Episode filters use inherited `show_genre` and `show_content_rating` fields;
plain episode genre/rating fields can omit otherwise eligible shows.
An incomplete index or stale media availability can hide existing library items;
verify the index and file state before suggesting that the operator add them.
When same-titled remakes have conflicting year or genre metadata, inspect the
actual media before excluding it. Correct a confirmed bad match, genre or
release year in Plex first, preserving the item's identity, files and watch
history. Remove temporary item-ID exceptions after verifying the corrected
metadata in the native search index. Keep exact title/year aliases for genuine
alternate titles, unrated compilations and future imports. Avoid a broad title
alias that also admits unrelated remakes.
After a replacement import, verify the new Plex identity and accessible media
path before removing the retired entry from ErsatzTV's trash. Rebuild any
playouts that still reference the missing item, refresh the downstream guide,
and verify the replacement's native search memberships and video/audio decoding.
Studio branding and credited production names can also differ. Include legacy studio aliases and verified
co-production exceptions when defining a studio station.

Review the complete current studio pool when building fallback aliases. Keep
known film title/year pairs eligible when an import lacks its production credit;
avoid deriving new brand membership from unrelated distribution credits.
For example, Amblin includes `Jurassic Park III (2001)` and Legendary includes
`Jurassic World: Fallen Kingdom (2018)` even when Plex supplies only Universal
as the studio. These production memberships are confirmed by the
[Amblin catalog](https://amblin.com/movie/jurassic-park-iii/) and
[Legendary catalog](https://www.legendary.com/film/jurassic-world-fallen-kingdom/).
Keep the primary Plex studio intact and use the reviewed title/year fallback.
Match the year stored by Plex when release-year conventions differ. Keep both
reviewed `300 2006` and `300 2007` aliases for Legendary rather than loosening
the rule to a title-only search. Amblin also includes
[Monster House](https://amblin.com/movie/monster-house/) and
[The Last Voyage of the Demeter](https://amblin.com/movie/the-last-voyage-of-the-demeter/).
Legendary includes [Dracula Untold](https://www.legendary.com/film/dracula-untold/)
and [Steve Jobs](https://www.legendary.com/film/steve-jobs/) through exact
title/year fallbacks when Plex lists a different production credit.
Seasonal compilations can belong to more than one holiday station when their
actual stories fit each theme. Use exact titles to keep similarly named horror
adaptations outside family seasonal pools.

For known recommendations with alternate production credits, add exact
`title_and_year_search` aliases alongside studio rules. Keep release years in
those aliases to distinguish remakes and similarly named films. Test future
titles against synthetic metadata with an unknown studio, then verify real
imports after the enabled Plex library synchronizes. Genre and decade stations
continue to follow the imported ratings, genres and release dates.
Choose the library refresh interval in the application settings. A one-hour
interval reduces the wait for newly imported films; verify collection membership
and the generated playout after synchronization. Existing future guide entries
can persist until the schedule is rebuilt. Resolve the actual channel and schedule
references before rebuilding: helper collections may have no separate station. Seasonal filters can combine curated
movie title/year aliases with holiday episode titles from selected shows.
Parenthesize each complete existing query as well as each new branch before
joining them with `OR`. Classic Lucene parsing can otherwise keep an earlier
`AND` clause required and turn the new branch into an optional match. Verify
new aliases with synthetic metadata that does not satisfy the earlier branch.
Keep opt-out labels outside the complete union so later aliases cannot bypass
them. Sports Cinema keeps its existing sport documentaries. Apply a documentary
exclusion only to new curated movie-alias branches when needed, rather than
removing documentary matches from the whole station. Check both membership
additions and removals before applying a query change. Parenthesize each show/title branch and avoid loose prefixes such as `easter*`, which also match unrelated words such as
"Eastern". Verify every seasonal collection has playable content before exporting
it. Keep future recommendations in the filter even while their files are absent.

Audit additions against the same index using both the previous and proposed
queries. Retain existing matches and review the actual additions by title.
For family animation, include child-appropriate television ratings explicitly
and whitelist reviewed unrated specials by title and year. Do not admit every
unrated animated film. Workplace and network collections may need explicit
series aliases when the credited studio or primary network differs from the
station theme. Preserve source identities, output numbers and artwork when
expanding programming without renaming a station.

For franchise stations, test known films with unknown studio metadata and
reject unrelated films from the same credited producer. Exact title/year aliases
can supplement a studio rule or replace one that describes a producer rather
than the franchise. Exclude making-of documentaries where the station promises
narrative films. Network cartoon exceptions should retain the animation and
rating guards used by the main rule. Check similarly named remakes separately
when a station has a historical scope. Remove an existing match only after
reviewing and recording why it falls outside that scope, then verify that the
intended original still matches. A theme station can mix films and episodes when
its schedule supports both; confirm a new film reaches the generated playout.
For network cartoons, use exact title/year rules for reviewed series tie-ins
alongside the episode rule. Keep animation, documentary and quarantine guards
so live-action adaptations and making-of films do not enter that movie branch.

With the pinned v26.11.3 scanner, Plex tag edits can leave the integration ETag
unchanged, and existing movie years and release dates are not refreshed by an
ordinary scan. Verify the imported fields after source corrections. A bounded
reconciliation requires a verified application backup and must preserve all
other metadata and channel identities. Startup also skips rebuilding an index
whose version is unchanged. Verify corrected search results rather than
assuming a restart refreshed them. Saving a Smart Collection query automatically refreshes its dependent playouts
in this release. That refresh can replace internal programme-row IDs even when
all media, timing and playback fields stay unchanged. Verify those programme
fields and channel identities separately from disposable row IDs. Regenerate
playouts when further changes require it, then refresh the downstream guides.

Plex labels import as tags. Movie-capable collections can exclude
`tag_full:"ETV Quarantine"`, while Sports Cinema can additionally exclude
`tag_full:"ETV Sports Exclude"`. Match the exact label spelling. These guards
keep a damaged copy or a reviewed curation exception out of rotation without
changing legitimate source genres. A zero-duration file can prevent the scanner
from importing its new label, so verify the tag and actual search membership.
Any required cache reconciliation follows the verified-backup workflow above.
Clear quarantine only after a replacement is verified.

For a strictly limited personal station, use manual collections containing the
explicit show identities and reviewed related movie identities. Show references
expand to new episodes without letting unrelated series enter through metadata
changes. Verify every scheduled item against the allowed identities.

For an even mix of bedtime shows, use one schedule item per show rather than
shuffling every episode in one pool. Otherwise a long series receives more
slots. Shuffle the schedule items for variety and use Shuffle in Order for a
serialized show whose story should remain in sequence. Keep multipart episodes
together. Check the generated guide to prove the intended mix and ordering.

### Plex special-episode guide collisions

Compare source episode identities with Plex's actual guide, including specials.
Source XMLTV represents a season-zero episode such as `S00E07` with a negative
`-1` season component in `xmltv_ns`. Affected Plex parsers can merge that identity
with `S02E07`, substituting one episode's title for the other at the correct airtime.
Dispatcharr can preserve the source title and season correctly while Plex still
shows the collision. Check the wire XMLTV and Plex episode GUID separately from
channel mapping and guide coverage.

Preserve correct source metadata, files and recurring recording rules when this
happens. Do not renumber source episodes or omit legitimate specials to hide a
consumer error. The [optional Dispatcharr compatibility mode](../dispatcharr/README.md#plex-season-zero-episode-identities)
omits the invalid negative namespace only when an existing, matching season-zero
onscreen label supplies the correct identity. It preserves native metadata and
normal episode numbering. Do not replace the negative season with a blank value:
Plex interprets that as season one. Keep mismatches visible in the correctness
observer until distinct normal/special titles and recording behavior pass actual
Plex verification after import completion.

### Station presentation and calendar specials

Short silent IDs can reuse the existing channel PNGs without adding files to
the media library. Store generated clips beneath the configuration volume's
`presentation/station-ids` directory and add only that directory as a local
Other Videos library path. Use three-second H.264/AAC clips with silent stereo
audio and brief fades. Verify each clip's duration, video and audio decoding
before scanning it. Create a separate manual collection and Count-mode pre-roll
filler preset for each station, with one ID and watermarks disabled on the ID.
Keep IDs hidden within the corresponding programme's guide group; do not use
a custom block title. Preview the real XMLTV and Plex airings after rebuilding.

The selected presentation applies IDs to Morning Cartoons, Movie Night, Family
Toon Theater, Family Movie Matinee, Halloween Horror, Holiday Movie Mix, Spooky
Toons & Tales, Winter Wonderland, Thanksgiving Table, Summer Vacation and
Spring & Easter. Both nighttime stations remain free of filler and overlays.
Other enabled stations use their own logo for ten seconds every fifteen minutes,
at 12% width and 55% opacity near the top right, inside the source-content area.
Use an intermittent Channel Logo watermark so later artwork updates propagate
without creating another watermark for each station. Verify the generated Next
playout's graphics timing and actual output; saving the database alone does not
update an already generated engine playout.

Movie Night can use alternate classic schedules on Saturdays and Sundays:
Halloween in October, Thanksgiving in November, holiday films in December,
spring films in March and April, and summer films in June through August.
Retain its ordinary schedule as the default for all other dates. Calendar
selection follows the application's configured timezone, inherited from the
shared environment; do not silently change that timezone during a schedule edit.
Use movie-only Smart Collections derived from the existing scoped seasonal
queries. Preserve library and quarantine boundaries on the complete expression,
and update the derived rules whenever their owning seasonal rules change.
New imported matches join automatically. Each film retains its ordinary guide
title and artwork, with the Movie Night ID attached to each alternate schedule.

Trailers and short-film pre-rolls require suitable local assets and a separately
reviewed pool. Do not substitute arbitrary episodes or extract material from
feature films merely to populate filler. Leave those presets absent when no
eligible local assets are available.

Nature & Wildlife combines a curated documentary series list with
`show_genre:documentary`. Do not exclude animation globally: documentary
reconstructions can legitimately carry both genres. If Plex briefly shows the
previous station's programmes after renumbering, compare the native XMLTV,
Dispatcharr guide and Plex provider grid before changing a correct collection.

For remote Plex clients, use an anonymously reachable image URL for each logo.
With Dispatcharr's `cachedlogos=false` guide option, an HTTP logo URL is retained;
a local file instead falls back to a cache URL based on the guide request host.
A guide fetched through loopback therefore needs a public image URL that serves
only the artwork. Keep the media playlist, guide and stream routes private.

Do not point Plex or Dispatcharr at the public Access-protected hostname. Do not
route playback through Cloudflare Tunnel. Playlist import, a healthy container
or a populated guide alone does not prove video playback.

## Verification and troubleshooting

### Continuous correctness and stable guides

The [optional Dispatcharr host maintenance](../dispatcharr/README.md#optional-ersatztv-correctness-and-recovery)
can include ErsatzTV in its verified daily backups and compare native, Dispatcharr
and Plex programme fields. Private recipes record the complete channel/schedule
definitions, source filters, strict personal-station rules and output identities.
Reconcile derived seasonal rules through a private dry-run plan and the guarded
apply command; routine monitoring never changes the lineup.

For a seven-day rolling guide, set both playout and XMLTV days to build to seven
and clear each playout's Daily Rebuild Time. The native scheduler continues
playouts hourly and at startup. Preserve already scheduled media and airings
while appending new days; verify their actual programme fields after extension.
A longer horizon means new eligible imports may wait for unscheduled future
slots. Refresh only affected channels when intentionally changing curation, and
check active viewing and DVR commitments first. Keep all device bindings and
recording rules intact when refreshing downstream guides. Check the published
XMLTV horizon as well as database playouts before refreshing Dispatcharr and
Plex. Initial subtitle extraction shares the native background queue and can
delay guide publication while the cache fills.

The maintained H.264/AAC NVENC profile can use LoudNorm at -18 LUFS while retaining
its existing audio format, rate and channel layout. Test source clips with
different levels and inspect encoded output before enabling it broadly. Audio
format normalization and loudness normalization are separate profile settings.
English Forced subtitle selection with Next text-subtitle Burn mode places
translations into the picture before Dispatcharr's remux. Verify the selected
track, a rendered subtitle frame, and ordinary picture/audio playback. Enable
embedded subtitle extraction as well: Next ignores embedded text tracks until
the native extraction worker has prepared them. It processes upcoming scheduled
media rather than extracting the entire library at once. Keep
default/full subtitles disabled unless separately chosen. Incorrect source
forced flags should be reviewed against the actual track in Plex metadata.

- Confirm `docker compose ps` reports healthy and the root UI responds inside
  the container. Check startup logs privately for database or scanner errors.
- Inspect the media mount source and read-only flag. Missing content may indicate
  an absent remote filesystem, permissions or a wrong Plex path replacement.
- Verify collections contain media, playouts cover the present time, and XMLTV
  channel IDs match Dispatcharr's imported streams.
- Probe a scheduled stream and play it through the intended Plex client. Check
  both picture and sound and compare the displayed guide with the current item.
- An Access redirect on a private playlist URL means the public hostname was
  used. A public 502 means Caddy cannot reach the application or its network.
- No media-specific GPU is passed through by default. Start with CPU settings
  and measure actual stream resource use before enabling acceleration.

## Backup, update and recovery

Before changing an existing deployment, record the running image identity,
configuration, media mount and channel/collection/playout counts. Stop ErsatzTV
before copying the entire configuration volume, or use an application-consistent
SQLite backup together with its remaining configuration and index files.
Preserve private `stack.env`, `.env`, overrides and the Caddy snippet as well.
Keep backups private and outside Git. Media remains under its existing backup
policy because this stack only reads it.

Restore the backup to a separate location. Compare file integrity and check the
restored SQLite database with `PRAGMA integrity_check` and baseline row counts.
Do not proceed with an update if restoration is incomplete. Back up and verify
affected Dispatcharr/Plex state separately before changing their integration.

After updating, verify health, configuration and station preservation, guide
output and actual playback. Compare library identities, sync selections and prior
media IDs separately from scanner-owned timestamps, which can advance during
normal synchronization. Verify that those timestamps do not regress. If verification fails, stop the updated service and
restore the verified state with the prior compatible image. An older image alone
may not read a migrated database. Verify recovery before resuming service.
Remove only this operation's temporary backup and restore copies after successful
verification. Keep established backup generations. Never use volume deletion as
an update or recovery step.
