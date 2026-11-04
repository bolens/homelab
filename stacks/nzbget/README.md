# NZBGet

High-performance Usenet downloader. NZBGet handles NZB downloads from Usenet providers and integrates with automation tools like Sonarr, Radarr, Lidarr, and Prowlarr.

**Website:** https://nzbget.com/
**Docs:** https://nzbget.com/documentation
**GitHub:** https://github.com/nzbgetcom/nzbget
**Docker image:** https://hub.docker.com/r/linuxserver/nzbget
**Releases:** https://github.com/nzbgetcom/nzbget/releases

## Quick start

1. **Shared networks and host paths**
   - Create the shared **usenet** network (once per host, if not already present):
     ```bash
     docker network create usenet
     mkdir -p /mnt/unraid/media/downloads/usenet
     ```
   For external volume naming and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).
2. **Environment**
   - Copy `stack.env.example` to `stack.env`.
   - Set:
     - `TZ` to your timezone.
     - `PUID` / `PGID` to the user/group that should own downloaded files.
     - Confirm `NZBGET_DOWNLOADS_PATH` (default `/mnt/unraid/media/downloads/usenet`).
     - Optionally `NZBGET_USER` / `NZBGET_PASS` (web UI credentials).
3. **Deploy**
   - From this directory:
     ```bash
     docker compose --env-file stack.env up -d
     ```
   - Or add the stack in Portainer, paste the compose, and set the same variables in the stack **Environment**.
4. **First run**
   - Access NZBGet via Caddy (for example `https://nzbget.home` or `https://nzbget.yourdomain.com`) and configure:
     - Your Usenet server(s).
     - Download directory (should be `/downloads` inside the container).
     - Under **Settings → Categories → music**, set **Extensions** to
       `UnpackMusicTar`. Keep the category's built-in **Unpack** option enabled
       for RAR and 7-Zip releases.

Before downloading music, protect audio and cue extensions from NZBGet's built-in
post-download and post-unpack renaming. Under **Settings → Download Queue**, add
these extensions to **RenameIgnoreExt**, preserving any existing entries:

```text
.flac,.mp3,.m4a,.aac,.ogg,.opus,.wav,.aif,.aiff,.alac,.ape,.wma,.mka,.cue
```

Alternatively, disable **PostDownloadRename** and **RenameAfterUnpack** if their
renaming is not needed for other categories. The built-in renamer runs before
post-processing extensions. It can rename multiple obfuscated music tracks to
one release filename, overwriting earlier tracks before this extension starts.
These settings are described in [NZBGet's configuration reference](https://github.com/nzbgetcom/nzbget/blob/develop/nzbget.conf).

The bundled `UnpackMusicTar` post-processing extension extracts ZIP and
tar-family music releases that NZBGet's built-in unpacker reports as "Nothing
to unpack." Extracted folder trees are flattened into the release directory,
except for numbered `CD`, `CDM`, `Disc`, and `Disk` folders used by multi-disc releases.
Numbered CD-maxi folders such as `CDM-1` and `CDM-2` keep their boundaries.
Disc labels such as `CD 1 - Original Mixes` and `Disc 2 (Remixes)` are also
retained in full. Tracks with identical numbers and filenames stay in their
separate disc folders, preserving different mixes without renaming the tracks.
Filename collisions within the same disc still fail rather than overwrite a file.
Nested numbered disc folders retain their hierarchy.
This flattening pass also handles release folders created earlier by NZBGet's
built-in unpacker and removes empty subdirectories inside the processed release.
It preserves the processing directory itself, its parents such as
`usenet/completed/music`, and sibling release directories. An empty music
category directory is retained.
After successful extraction, `.accurip`, `.ffp`, `.htm`, `.html`, `.jpg`, `.jpeg`, `.log`, `.lrc`, `.m3u`,
`.m3u8`, `.md5`, `.nfo`, `.nzb`, `.pdf`, `.pls`, `.png`, `.sfv`, `.srr`, `.toc`,
`.tif`, `.tiff`, and `.txt` sidecar files are removed, along with `.url` and `.website` shortcuts, while audio and
music-video files are retained. Cleanup also runs when NZBGet's built-in
unpacker has already removed the archive before this extension starts.
Single-IFD classic TIFF images require a valid raster directory and in-bounds strip or tile
payloads before cleanup. A file named `Thumbs.db` is removed only when its bounded
Windows v3 compound-file structure contains hashed JPEG thumbnail streams and no
other allocated content. Other database layouts, malformed files and cue-referenced
files stay protected. UTF-8 NFO text may contain nonbreaking spaces, and Windows-1252
AUDIOCHECKER logs use the same whole-file text validation as EAC logs.
Parenthesized `(CD1)` and `(CD2)` posting wrappers restore verified FLAC images and
cue sheets together into their disc folders. Wrapped `.accurip`, `.log` and `.txt`
reports require the complete posting filename and verified text content.
This includes `EnCrYpTnZb` posting wrappers. Wrapped cue sheets and unrecognised
content remain protected.

Files left with obfuscated or missing extensions are identified from their
content first, including files carrying a sidecar extension such as `.txt` or
`.nfo`. Recognized media receives an extension instead of being deleted. This includes
tagless MP3, ADTS AAC, and AIFF audio. MP3 and AAC recognition requires two
consecutive valid frame headers rather than a single sync marker.
FLAC audio preceded by a valid [ID3v2 header](https://id3.org/id3v2.4.0-structure)
is recognised from its underlying FLAC marker and STREAMINFO block. ID3v2.2,
2.3 and 2.4 tags up to 16 MiB are supported, including a validated 2.4 footer.
A misleading `.mp3` suffix is corrected to `.flac` when extension repairs are
enabled. The file bytes, including existing tags and artwork, stay unchanged.
Completeness checks read the underlying FLAC comments. Ordinary MP3 files and
unconfirmed or malformed wrappers keep their existing handling.
Recognized images and PDF booklets, including files without extensions, flow
through the normal cleanup rules. Unknown files
are retained. Cleanup removes a file with a sidecar extension only when its
content is a recognized image or PDF document, or the entire file is readable text. BOM-marked UTF-16 text, including Exact
Audio Copy logs, is supported in either byte order. Local UTF-16 playlists receive
the same completeness checks as UTF-8 playlists; retained playlists keep their
BOM and byte order when references change. Explicit `.m3u` and `.m3u8` playlists
also support Windows-1252 and preserve that encoding when references change.
Malformed UTF-16, binary
control characters and cue-referenced files remain protected.
Explicit `.txt` sidecars also support Windows-1252 text with full-file validation.
UTF-8 and BOM-marked UTF-16 `.txt` sidecars may contain Unicode left-to-right
marks. Other formatting controls still fail text validation.
Scene `.nfo` files support Windows-1252 text and CP437 box art with accented
letters, middle dots and the scene symbols `∙`, `¼`, `«`, `»`, `⌐`, `÷` and `≤`, plus nonbreaking spaces.
The entire file must pass the text checks. Binary
controls, undefined Windows-1252 bytes and unsupported CP437 glyphs remain
protected. Adjacent drawing glyphs keep malformed box art from being retried as
Windows text. Lyrics files with an `.lrc` suffix use the normal text cleanup rules.
CP437 scene `.nfo` files up to 64 KiB may also use BEL bytes as padding between
header labels and their colons, or SYN bytes in rows containing only drawing
glyphs and whitespace. Both forms require `Artist`, `Title` and `Tracks` headers
and adjacent drawing glyphs; the BEL form requires those headers to be padded.
BEL bytes elsewhere, SYN in text rows, other binary controls, oversized files
with these controls and cue-referenced files remain protected.
Binary SRR recovery sidecars are recognised by the ReScene marker and valid
bounded application header, including files with obfuscated names. Unknown or
malformed binary files remain retained. Named audio/video and cue-referenced
files remain protected.

Windows `desktop.ini` music-folder sidecars are removed only when the complete
payload is within 64 KiB and contains one `[.ShellClassInfo]` section with exactly
one `FolderType` of `MusicArtist` or `MusicAlbum` and one nonempty `MusicBuyUrl`.
UTF-8 and BOM-marked UTF-16 are supported, including one trailing NUL terminator.
Unknown fields, additional sections, duplicate keys, malformed text and arbitrary
INI files remain retained. Cue-referenced files stay protected. This also avoids
flattening conflicts between recognised folder sidecars.

Synology `@SynoEAStream` files are removed only when their complete payload is
an [AppleDouble v2](https://www.rfc-editor.org/rfc/rfc1740#appendix-B) header
within 64 KiB, containing FinderInfo/attributes and an empty resource fork.
The two entries must cover the payload exactly. Extended attributes must contain
only one bounded `com.apple.provenance` record with valid header, name, offsets,
lengths and padding. Other attributes stay retained. Data forks, nonempty resource
forks, unknown entries, gaps, trailing bytes and malformed headers are retained.
Recognised media and cue references remain protected, and metadata-only releases
still trigger the existing empty-output guard.

Obfuscated posting names ending in the scene hash, a `newzNZB` or `WtFnZb` tag,
and `yEnc` fields support UTF-8 and Windows-1252 SFV checksum lists and release
NFOs up to 64 KiB. The hash separator must be exactly `___` or `-_-_--_`.
NFO fields and numbered track rows can have drawing frames. CP437 NFOs
require consecutive drawing glyphs and a bounded printable alphabet. Checksum
lists require local audio paths and eight-digit hexadecimal CRCs on every
non-comment entry. Release NFOs require nonempty artist and album or title fields, at
least two additional release fields and a numbered track entry. Unstructured
text, unsafe checksum paths and unidentified binary files are retained. Binary
controls and unsupported legacy bytes fail recognition. The empty-output
guard still retains releases containing only disposable sidecars.

The same modern posting names also support posting-info text ending in the
exact `.::newz[NZB]::.` footer. Recognition requires exactly one `RELEASE:` field
matching the filename's release prefix, ignoring punctuation, case and an
optional terminal `xpost` label, plus exactly one valid `UPLOADED DATE:` in
`YYYY-Month-DD` form with a full English month name. Full-file text validation
and the 64 KiB limit still apply. Wrong identities, dates, duplicate fields,
trailing content and binary controls remain retained. Cue references stay
protected.

Legacy `[number]-[FULL]-[#a.b.flac@EFNet]` posting wrappers are also recognised
when the complete filename identifies an NFO or SFV, part counters and yEnc
fields. The same 64 KiB content and unsafe-path checks apply. These legacy NFOs
may use `Title:` in place of `Album:`, with artist, two other release fields and
a numbered track still required. Unknown wrappers, binary content and cue
references remain protected.

Exact short `~^newz[NZB]~` posting markers are removed even with obfuscated
filenames, allowing no line ending, LF or CRLF. Matching is bounded and requires
the complete payload. Similar text, named audio/video, cue and M3U files and
cue-referenced files remain protected. A marker-only release is retained by the
existing guard against deleting every file.

Obfuscated posting NFOs also support dotted field leaders without colons and
underscore-arrow fields with `Artist Name` and `Album Name` labels. They still
require artist and album/title, two additional populated metadata fields and a
numbered track entry.

Extensionless `about_album` and `album_info` posting sidecars, including a short
alphanumeric prefix on `album_info` such as `post_album_info`, are removed during
music post-processing before import. Recognition requires the entire file to be readable UTF-8 text within
64 KiB, with nonempty `Album:` and `Artist:` fields, a `Tracklist:` heading and a
numbered track entry. Unknown text, recognised media and cue references remain
protected. An info-only release remains retained by the guard against deleting
every file; this rule does not infer that missing audio was imported.

Zero-byte files with known audio extensions always fail validation before
cleanup or publication, even without track totals, with cleanup disabled, or
when optional audio decoding verification is off. Originals, archives and
sidecars remain available for repair. Empty unknown files are retained.

Local M3U-style playlists also provide completeness evidence when FLAC track
totals are absent. Existing local references establish the relationship; for
obfuscated files, numbered artist/title entries must match every surviving
track in one tagged, cue-free FLAC album/disc. Matching tolerates eight-digit
hexadecimal scene suffixes and featured-artist labels. Repeated ancillary
MusicBrainz tags do not invalidate album/track metadata; conflicting values
used for album identity or track positions remain ambiguous. Missing entries stop processing
before cleanup. Complete recognised lists, including extensionless files, are
removed during cleanup. Unknown, ambiguous, remote and unsafe M3U lists stay
retained. Recognition accepts UTF-8, BOM-marked UTF-16 and explicit Windows-1252 M3U
lists up to 1 MiB with local audio paths;
it does not fetch URLs or infer completeness from unrelated text.
A complete local `.m3u` or `.m3u8` can also establish disc boundaries for FLACs
without disc tags. The album artist must agree across the group, using track
artist only when album-artist tags are absent. Every same-folder track in one
tagged album must have a
three-digit `DTT` filename prefix matching its track number, with discs starting
at 1 and consecutive tracks starting at 1 within each disc. The playlist must
resolve exactly once to every track in that group. Missing identity tags,
partial or duplicate references, gaps, mixed album identities, conflicting
album-artist aliases and any explicit disc metadata or numbered disc folder
prevent this fallback. Existing track totals still apply within
each disc. Playlists used for this fallback remain retained even without strict
completeness, so repeat processing keeps the same evidence. This affects
validation only and preserves audio, tags and filenames.

Lettered vinyl-side prefixes such as `a1`, `a2` and `b1` use the same covering
playlist requirement when track tags restart at one on each side. Sides must
start at A and continue without gaps, with consecutive tracks starting at one
within each side. Every filename position must agree with its track tag. This
rule requires at least two sides, does not mix numbered-disc and lettered-side
prefixes, and keeps the existing identity, explicit-disc and cue-image guards.
The required playlist stays retained for retries. Audio, filenames and tags
remain unchanged.

Retained, resolvable playlists have their references updated whenever files move
or gain extensions, including cleanup-disabled helpers and cue-protected lists.
Same-folder playlist references also resolve when NZBGet has replaced each ASCII
space in a filename with a dot, including title-only names and cue-referenced
audio. Existing exact paths take precedence. Every entry must resolve to one
distinct audio file; collisions and partially missing lists fail before changes.
Other whitespace and nested path components are not inferred by this rule.
The same path resolution applies to playlists used for disc inference, which
must still cover exactly every track in the album group.
An unresolved retained M3U, or another recognised playlist with existing local
references, keeps folder structure and filenames unchanged because its references cannot be safely rewritten.

Disc-scoped `[PRiVATE]-[WtFnZb]` posting wrappers with an explicit `CD1`-style
component can restore verified FLAC and cue filenames into disc folders. The
optional `[N3wZ]` prefix is supported. Text logs and reports inside the same
wrapper must pass the complete text check before cleanup. Cue references are
validated against the restored names, collisions fail without publication, and
audio bytes remain unchanged. Malformed wrappers and unknown binary data are retained.

Windows-1252 EAC `.log` files require the `Exact Audio Copy` header and complete
printable text. Bounded CP437 NFOs also support the observed art-only arrow and
paragraph glyph bytes, plus framed backspace padding with a matching layout
credit and populated artist, title and track fields. Other control-byte payloads
remain protected. Structured modern posting sidecars can identify foobar2000
Dynamic Range Meter, AUDIOCHECKER and auCDtect reports, including UTF-16 reports
with a BOM, and the exact Demonoid download notice. Their posting filename,
report header and record structure must all match. Audio checksum rows in `.md5`
files are recognised as checksums rather than being mistaken for M3U entries.

Cue sheets are retained because album-image releases need them to identify
individual tracks. The extension does not split album images into track files.
Cue `FILE` references are updated when tracks move or gain extensions. A missing
local `.wav` reference declared as `WAVE` can resolve to a same-folder FLAC
with the same filename stem. Missing same-folder `.wav` and `.flac` references
declared as `WAVE` also support replacing each ASCII space with a dot when the
result identifies one confirmed FLAC. Exact filename stems take precedence, and
ambiguous aliases or references containing directories are not inferred.
Otherwise, missing local `.wav` and `.flac` references declared as `WAVE`
can use numbered filenames to match exact
performer, title and track tags within one fully tagged FLAC album/disc. A
present global cue album title must also match, allowing a trailing `(single)`
format annotation. For guest tracks, an explicit matching album artist can
identify the performer when the cue also supplies a matching global album title.
Conflicting album-artist aliases prevent that fallback. Numbered filenames may
include the track artist or the matched cue performer; guest artist tags are preserved.
Ambiguous aliases, mismatched versions, missing identity tags and references
containing directory paths keep failing without publication. Existing WAV and FLAC
references take precedence. Quoted
and unquoted filenames, Windows path separators, case differences, UTF-8 with
or without a BOM, UTF-16 with a BOM in either byte order, and Windows-1252 cue
sheets are supported. LF, CRLF, and CR line endings are preserved. A missing,
ambiguous, or unsafe reference fails processing and leaves the original release
intact. Files referenced by a cue sheet are protected from sidecar cleanup.
In strict completeness mode, track-file cue references alone do not prove the
album is complete. Cue-image evidence requires one `FILE` entry and multiple
`TRACK AUDIO` entries, including after reference repairs and on repeat runs.
It validates paths and file types before extraction, rejects duplicate archive
file paths before extraction can overwrite a track, refuses to overwrite
existing files, and removes each archive only after a successful extraction.
Other categories are ignored. Processing logs report retained media, removed
sidecars, repaired extensions, updated cue sheets, extracted archives, and
unidentified files. Unknown filenames are reported for review. Releases that
already match the plan skip staging and publication.

To inspect a selected release before processing it:

```bash
python3 stacks/nzbget/scripts/UnpackMusicTar/main.py --preview "/path/to/music/release"
```

Preview copies the release into temporary storage, extracts archives there, and
reports planned removals, moves, extension repairs, and cue changes. Source files
and their modification times remain unchanged. Temporary storage needs room for
the input copies and extracted contents. A retained recovery workspace must be
resolved before preview or processing can run.

### Music processing failures and recovery

Processing requires Linux and Python 3.11 or newer. The extension builds the
complete result in a private `.unpack-music-*` directory inside the release.
Existing files are staged with hard links where supported, with a copy fallback
that checks available space. Cleanup and extension repair happen before final
filename collision checks, so disposable covers from separate folders do not
block otherwise valid tracks. Matching disposable sidecar paths across separate
archives are also discarded, unless a cue references the conflicting file.
All supported archives, including nested ones,
must succeed before the result is published or any original archive is removed.

Failed, warning or deleted NZBGet downloads are skipped with exit code 95 before
cleanup, extraction or publication. Legacy PAR repair and unpack failure statuses
are also respected. This preserves diagnostic sidecars and archives for repair.
Manual runs without NZBGet status information keep the normal processing path.
Failure of an earlier unrelated extension does not by itself block processing.

Tagged FLAC tracks are checked within album/album-artist and disc groups. Disc
numbers and numbered disc folder ancestry keep repeated track numbering on
separate discs independent. Missing tracks, duplicate numbers, conflicting totals
or invalid numbers in a group with known totals fail before cleanup or publication.
The check includes albums with several surviving tracks, not just a lone file.
External cue references, embedded FLAC cues and embedded `CUESHEET` comments exempt
album images from track-file counting.

When totals are absent but every track in an album/disc has a valid number,
the sequence must start at one and contain no gaps or duplicates. A lone track
11 or two copies of track 10 fail before cleanup. A contiguous sequence cannot
prove that later tracks are present. Partial album downloads require manual review.

Nonempty `TRACKNUMBER`/`TRACK` and `TRACKTOTAL`/`TOTALTRACKS` values must
agree with slash totals such as `1/11`. Blank values fall through to other tags.
The same rules apply to `DISCNUMBER`/`DISC`, `DISCTOTAL`/`TOTALDISCS` and slash
disc totals. A declared two-disc album requires both discs. Separate edition
folders remain independent. Disc ancestry is limited to the selected release tree. Folder structure is retained when flattening would
merge separate album groups or numbered FLAC groups without album identities,
so another processing pass keeps the same grouping.

Set **RequireCompleteness** to `yes` to refuse audio whose final track count is
unproven. Its default is `no`. Each audio file needs a validated FLAC track total,
a reference from a complete local playlist, or cue-image evidence. A contiguous
prefix without totals fails in this mode. Playlists must cover every otherwise
unproven audio file. Playlist entries must resolve to distinct audio files, including case variants.
Obfuscated playlist matching uses the same reconciled track/disc tags as album
checks. Strict processing retains recognised playlists and updates their paths
after moves or extension repairs so retries keep the evidence. Names beginning
with spaces or `#` use `./` references. A rewrite that the playlist reader cannot
resolve fails before publication.
This setting also checks unchanged releases and applies with cleanup disabled.
It uses local evidence and cannot detect incorrect totals or omitted playlist
entries that leave a plausible, internally complete set.

Disc-labelled cue filenames can resolve DTT-prefixed FLAC exports when the disc,
track, tagged album, artist, title and complete filename identity agree. Ambiguous
references and different mix or release-group suffixes remain errors.
When metadata-based matching is ambiguous across discs in a flat release,
a cue filename ending in `CD1`, `Disc 1` or `Disk 1` selects that tagged disc. This requires an explicit
album title and performer in the cue header, consistent disc totals on every
candidate, and all declared discs present. Missing or conflicting disc tags
still fail before any files change.

Preview strict processing without changing a release:

```bash
python3 stacks/nzbget/scripts/UnpackMusicTar/main.py --preview "/path/to/music/release" --require-completeness
```

This check uses bounded metadata reads. Untagged files, ambiguous metadata and
other formats cannot establish completeness. Totals are interpreted per disc.
Whole-release totals across several discs are
accepted only when a matching NFO supplies an explicit CD-by-CD tracklist and a
local playlist covers every track. The NFO must identify the artist, album and
number of CDs; its numbered titles must match the tags. Both evidence files are
retained for repeatable processing. Local or release-wide track numbering is
supported; ambiguous tags and intentionally partial downloads require manual review.
Already overwritten tracks require a backup
or a new download; rerunning this extension cannot recover their audio.

Under **Settings → Extension Manager → Unpack Music Tar**, set **VerifyAudio** to
`yes` to decode recognised audio before cleanup and publication. The default is
`no`; the option requires `ffmpeg` in NZBGet's runtime. All audio streams in each
recognised audio file are decoded to a null output without rewriting the source.
An unavailable decoder, decoding error, empty output or ten-minute per-file timeout
fails safely and retains originals and archives. Unchanged releases are checked
when verification is enabled. Unknown files and video-only formats are not decoded;
this is a decoding check, not proof that all originally released samples are present.

Preview supports the same check:

```bash
python3 stacks/nzbget/scripts/UnpackMusicTar/main.py --preview "/path/to/music/release" --verify-audio
```

The extension rejects symlinks and special files in the release, concurrent
instances, files changed by another writer during preparation, and missing
download directories. It also refuses to clean a release down to zero files,
including cleanup-only helper calls with extraction disabled.
Extraction is limited to 20,000 entries per archive, 100 archives per release,
100 GiB of cumulative declared extracted data, and the available free space.
Encrypted ZIP archives and unsafe or conflicting archive paths fail processing.

An ordinary publication error rolls back the original files. If another writer
changes a published output, rollback preserves that file and retains recovery
data for manual review instead of deleting or overwriting the other writer's work.
An interrupted
publication or failed rollback retains the private workspace and blocks retries.
Stop other writers to the release before recovery. For a workspace produced by
version 1.15 or newer, select its exact path:

```bash
python3 stacks/nzbget/scripts/UnpackMusicTar/main.py --recover "/path/to/music/release/.unpack-music-example"
```

Successful publication records verified output checksums before deleting backups.
Restoring originals also records verified completion before deleting recovery
data. The recovery journal is removed last. If final cleanup fails or is interrupted,
`--recover` verifies those outputs and finishes cleanup without restoring removed
sidecars. Changed or missing outputs retain the workspace for manual review.
An empty workspace left after the final directory-removal failure can also be
removed by the same command.

Recovery validates the journal, saved originals, and current output checksums
before moving files. It refuses corrupted backups, unsafe paths, and changed
outputs. After restoring and verifying every original file and archive, it
removes that operation's workspace. An interrupted recovery can be resumed with
the same command. Ordinary restore failures roll back the recovery
attempt; an unresolved failure retains the workspace for review.

Legacy workspaces without checksums require manual recovery. Their
`recovery.json` lists original paths in order: entry `0` corresponds to
`originals/0`, entry `1` to `originals/1`, and so on. Preserve conflicting current
files before restoring each saved original to its recorded path. An original
not yet moved into `originals/` may still be at its original path. Verify all
originals before removing only that operation's workspace and retrying. A
workspace without a completed recovery record indicates preparation was
interrupted before publication; verify the originals before removing it.

The explicit commands exit with `0` on success, `1` on processing or recovery
failure, and `2` for invalid command arguments. Running without arguments keeps
NZBGet's category handling and post-processing exit codes (93/94/95).

The regression suite runs as part of `make validate`. To run it alone:

```bash
python3 -m unittest discover -s stacks/nzbget/scripts/UnpackMusicTar -p test_main.py
```

The stack also runs an idempotent LinuxServer initialization hook before
NZBGet starts. It restores the configured `PUID`/`PGID` on NZBGet's writable
config subdirectories, preventing Docker's nested read-only script mount from
leaving their parent directory owned by root after a container rebuild.

The built-in unpacker reads additional RAR and 7-Zip passwords from the
read-only `/etc/nzbget/unpack-passwords.txt` file when **Settings → Unpack →
UnpackPassFile** is set to that path. Set this option after first-run setup;
mounting the file alone does not enable it. Keep `config/unpack-passwords.txt` limited to release passwords, one per line;
keep it private and outside Git. After a successful music recovery, preserve any
newly verified password in this shared file as well as the job's settings.
Passwords attached to successful archive extractions can be recovered from their
`*Unpack:Password` history parameters. Deduplicate entries and preserve existing
values. Back up and verify the file before updating it, append in place to keep
the single-file bind mount attached to the same inode, then confirm the running
container sees the updated contents. No restart is needed for an in-place update.
An explicit password on a job takes precedence: NZBGet does not try the password
file for that job, so check job settings when diagnosing failed fallback attempts.

When auditing recent completions, also check Lidarr's `downloadFailed` history
since the previous audit. Failed-download handling can remove a job and its
source folder before it appears in NZBGet's visible history. Bind recovery to the
original download ID and release before retrying it. A password warning alone
does not establish whether already-extracted audio is complete; verify the audio
and keep unproven encrypted source material available for recovery.

This stack uses a **named config volume** (`nzbget_config`) and a **Usenet downloads bind mount** (`NZBGET_DOWNLOADS_PATH` → `/downloads`, shared with Sonarr/Radarr/Lidarr/Readarr).

## Configuration

| Item        | Details                                                                 |
|------------|-------------------------------------------------------------------------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `nzbget:6789`)          |
| **Networks** | `ingress-admin` (for Caddy/monitoring) and `usenet` (shared usenet network) |
| **Image**  | `lscr.io/linuxserver/nzbget:latest`                                    |
| **Env**    | `TZ`, `PUID`, `PGID`, `NZBGET_DOWNLOADS_PATH`, optional `UMASK`, `NZBGET_USER`, `NZBGET_PASS` |
| **Storage**| `nzbget_config` → `/config`, `${NZBGET_DOWNLOADS_PATH}` → `/downloads` |

## Caddy reverse proxy

Example Caddy vhost (SANITIZED hostnames):

```text
nzbget.home, nzbget.local {
  tls internal
  reverse_proxy nzbget:6789
}
```

For public access via Cloudflare Tunnel, add a corresponding `nzbget.yourdomain.com` block in your Caddyfile and Zero Trust Access app if you want SSO in front of the NZBGet UI.

## Integration with *arr and Prowlarr

- **Download client:** In Sonarr/Radarr/Lidarr/Readarr, add NZBGet as a download client:
  - Host: `nzbget`
  - Port: `6789`
  - URL base: (empty, unless you change it in NZBGet)
  - Category: set per-app (e.g. `tv`, `movies`, `music`, `books`) and configure NZBGet categories accordingly.
- **Path mapping:** Use `/downloads` as the download root in NZBGet and in your *arr apps so they see the same files via the shared host bind mount (`/mnt/unraid/media/downloads/usenet` by default).

## Comic download integrity

For the comics category, keep `Unpack=yes`. Check the downloader's integrity
settings: `CrcCheck=yes`, `ParCheck=auto`, `ParRepair=yes`, and `HealthCheck=park`.
Parity repair can recover damaged Usenet articles when enough recovery data is
available. It cannot repair every bad comic archive inside an otherwise valid
release. Mylar's failed-download handling and the optional
[completed-download maintenance worker](../komga/README.md#completed-download-maintenance)
handle those remaining failures and retain verified quarantine copies.
