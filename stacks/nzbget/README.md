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
except for numbered `CD`, `Disc`, and `Disk` folders used by multi-disc releases.
Disc labels such as `CD 1 - Original Mixes` and `Disc 2 (Remixes)` are also
retained in full. Tracks with identical numbers and filenames stay in their
separate disc folders, preserving different mixes without renaming the tracks.
Filename collisions within the same disc still fail rather than overwrite a file.
Nested numbered disc folders retain their hierarchy.
This flattening pass also handles release folders created earlier by NZBGet's
built-in unpacker and removes directories left empty afterward.
After successful extraction, `.accurip`, `.jpg`, `.log`, `.m3u`,
`.m3u8`, `.md5`, `.nfo`, `.nzb`, `.pdf`, `.pls`, `.png`, `.sfv`, `.srr`, `.toc`, and
`.txt` sidecar files are removed, along with `.url` shortcuts, while audio and
music-video files are retained. Cleanup also runs when NZBGet's built-in
unpacker has already removed the archive before this extension starts.
Files left with obfuscated or missing extensions are identified from their
content first, including files carrying a sidecar extension such as `.txt` or
`.nfo`. Recognized media receives an extension instead of being deleted. This includes
tagless MP3, ADTS AAC, and AIFF audio. MP3 and AAC recognition requires two
consecutive valid frame headers rather than a single sync marker.
Recognized images and PDF booklets, including files without extensions, flow
through the normal cleanup rules. Unknown files
are retained. Cleanup removes a file with a sidecar extension only when its
content is a recognized image or PDF document, or the entire file is readable text.
Scene `.nfo` files containing CP437 box art are also recognised when all other
content is printable ASCII or ordinary text whitespace. The fallback is limited
to `.nfo`, drawing glyphs and the CP437 black square; unsupported binary content
remains protected.
Binary `.srr` recovery sidecars are recognised by the ReScene marker and valid
bounded application header. Unknown or malformed binary files with that suffix
remain retained, and cue references continue to protect files from cleanup.

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
retained. Recognition accepts UTF-8 lists up to 1 MiB with local audio paths;
it does not fetch URLs or infer completeness from unrelated text.
Cue sheets are retained because album-image releases need them to identify
individual tracks. The extension does not split album images into track files.
Cue `FILE` references are updated when tracks move or gain extensions. Quoted
and unquoted filenames, Windows path separators, case differences, UTF-8 with
or without a BOM, UTF-16 with a BOM in either byte order, and Windows-1252 cue
sheets are supported. LF, CRLF, and CR line endings are preserved. A missing,
ambiguous, or unsafe reference fails processing and leaves the original release
intact. Files referenced by a cue sheet are protected from sidecar cleanup.
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

This check uses bounded metadata reads. Untagged files, absent numeric totals and
other formats cannot establish completeness. Totals are interpreted per disc;
ambiguous tags, intentionally partial downloads or album-wide totals spread across
discs may require manual correction. Already overwritten tracks require a backup
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
download directories. It also refuses to clean a release down to zero files.
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

Recovery validates the journal, saved originals, and current output checksums
before moving files. It refuses corrupted backups, unsafe paths, and changed
outputs. After restoring and verifying every original file and archive, it
removes that operation's workspace. An interrupted recovery can be resumed with
the same command. Ordinary recovery write failures roll back the recovery
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
read-only `/etc/nzbget/unpack-passwords.txt` file. Keep
`config/unpack-passwords.txt` limited to non-sensitive release passwords; do
not commit private credentials.

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
