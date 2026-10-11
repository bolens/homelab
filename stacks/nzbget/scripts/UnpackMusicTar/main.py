#!/usr/bin/env python3
"""Safely unpack music archives that NZBGet's built-in unpacker missed."""

from __future__ import annotations

import errno
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from dataclasses import dataclass

SUCCESS = 93
FAILURE = 94
SKIPPED = 95
ARCHIVE_SUFFIXES = (
    ".tar",
    ".tar.gz",
    ".tgz",
    ".tar.bz2",
    ".tbz2",
    ".tar.xz",
    ".txz",
    ".zip",
)
# Keep the complete disc label, including mix/edition descriptions. Flattening
# these folders would collide when separate discs use the same track filename.
DISC_DIRECTORY = re.compile(
    r"^(?:cd|disc|disk)[ _.-]*\d+(?:[ _.-]+.*|[\[(].*)?$", re.IGNORECASE
)
UNWANTED_SUFFIXES = {
    ".accurip",
    ".jpg",
    ".log",
    ".m3u",
    ".m3u8",
    ".md5",
    ".nfo",
    ".nzb",
    ".pdf",
    ".pls",
    ".png",
    ".sfv",
    ".srr",
    ".toc",
    ".txt",
    ".url",
}
MEDIA_SIGNATURES = (
    (b"fLaC", ".flac"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"ID3", ".mp3"),
    (b"OggS", ".ogg"),
    (b"%PDF-", ".pdf"),
)
KNOWN_MEDIA_SUFFIXES = {
    ".aac", ".aif", ".aiff", ".alac", ".ape", ".avi", ".flac", ".jpeg", ".m4a",
    ".m4v", ".mka", ".mkv", ".mov", ".mp3", ".mp4", ".ogg", ".opus",
    ".wav", ".webm", ".wma", ".wmv",
}
IMAGE_SUFFIXES = {".jpg", ".png"}
CLEANUP_SIGNATURE_SUFFIXES = IMAGE_SUFFIXES | {".pdf"}
MAX_MEMBERS = 20000
MAX_ARCHIVES = 100
MAX_EXPANDED_BYTES = 100 * 1024**3
CUE_FILE = re.compile(
    r'^(?P<prefix>[\ufeff \t]*FILE[ \t]+)(?:"(?P<quoted>[^"\r\n]+)"|(?P<plain>[^ \t\r\n]+))'
    r'(?P<tail>[ \t]+[^\r\n]+\r?)$', re.IGNORECASE | re.MULTILINE
)


def is_archive(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in ARCHIVE_SUFFIXES)


def detected_suffix(path: Path) -> str | None:
    with path.open("rb") as stream:
        header = stream.read(4096)
    for signature, suffix in MEDIA_SIGNATURES:
        if header.startswith(signature):
            return suffix
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return ".wav"
    if header.startswith(b"FORM") and header[8:12] in (b"AIFF", b"AIFC"):
        return ".aiff"
    # Require two consecutive frames, not just a sync-like pair of bytes.
    for offset in range(min(1024, len(header))):
        frame = audio_frame(header, offset)
        if frame:
            suffix, length = frame
            following = audio_frame(header, offset + length)
            if following and following[0] == suffix:
                return suffix
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return ".m4a" if header[8:12] in (b"M4A ", b"M4B ") else ".mp4"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return ".webm" if b"webm" in header else ".mkv"
    # A readable prefix does not prove the whole file is a disposable sidecar.
    return None


def audio_frame(data: bytes, offset: int) -> tuple[str, int] | None:
    if offset + 7 > len(data) or data[offset] != 0xff:
        return None
    second, third, fourth = data[offset + 1:offset + 4]
    # ADTS: sync, layer zero, valid sampling-frequency index and frame length.
    if second & 0xf6 == 0xf0 and (third >> 2) & 15 < 13:
        length = ((fourth & 3) << 11) | (data[offset + 4] << 3) | (data[offset + 5] >> 5)
        minimum = 7 if second & 1 else 9
        if length >= minimum:
            return ".aac", length
    # MPEG Layer III: reject reserved version, bitrate and sample-rate fields.
    version, layer = (second >> 3) & 3, (second >> 1) & 3
    bitrate_index, sample_index = third >> 4, (third >> 2) & 3
    if second & 0xe0 != 0xe0 or version == 1 or layer != 1 or not 1 <= bitrate_index <= 14 or sample_index == 3:
        return None
    bitrates = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320) if version == 3 else (
        0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
    sample_rate = (44100, 48000, 32000)[sample_index] // (1 if version == 3 else 2 if version == 2 else 4)
    length = (144000 if version == 3 else 72000) * bitrates[bitrate_index] // sample_rate + ((third >> 1) & 1)
    return ".mp3", length


@dataclass
class ProcessingPlan:
    targets: dict[Path, Path]
    cues: dict[Path, bytes]
    removed: list[Path]
    repaired: list[Path]
    unknown: list[Path]
    media: int

    @property
    def changed(self) -> bool:
        return bool(self.removed or self.cues or any(source != target for source, target in self.targets.items()))


def tree_files(directory: Path, exclude: Path | None = None) -> list[Path]:
    """Inventory without following links or accepting special files."""
    files = []
    def walk_error(error: OSError) -> None:
        raise error

    for parent, directories, names in os.walk(directory, followlinks=False, onerror=walk_error):
        directories[:] = [name for name in directories if Path(parent) / name != exclude]
        for name in directories + names:
            path = Path(parent) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError(f"links and special files are not allowed: {path}")
            if stat.S_ISREG(mode):
                files.append(path)
    return sorted(files)


def check_targets(targets: list[Path], root: Path) -> None:
    seen: set[Path] = set()
    for target in targets:
        target.relative_to(root)
        for part in (target, *target.parents):
            if part == root:
                break
            if part.is_symlink():
                raise ValueError(f"symlink destination is not allowed: {part}")
        if target in seen:
            raise FileExistsError(f"refusing to overwrite existing path: {target}")
        seen.add(target)
    for target in seen:
        if any(parent in seen for parent in target.parents):
            raise ValueError(f"file conflicts with a directory: {target}")


def archive_members(members: list[tuple[str, bool, int]], destination: Path) -> int:
    targets: dict[Path, bool] = {}
    expanded = 0
    if len(members) > MAX_MEMBERS:
        raise ValueError("archive contains too many entries")
    for name, is_directory, size in members:
        relative = PurePosixPath(name)
        if (relative.is_absolute() or PureWindowsPath(name).drive
                or ".." in relative.parts or "\\" in name):
            raise ValueError(f"unsafe path in archive: {name}")
        target = destination / relative
        if target == destination and not is_directory:
            raise ValueError(f"unsafe file path in archive: {name}")
        if target in targets and not (targets[target] and is_directory):
            raise ValueError(f"duplicate path in archive: {name}")
        targets[target] = is_directory
        if not is_directory:
            if size < 0:
                raise ValueError(f"negative file size in archive: {name}")
            expanded += size
    for target in targets:
        if any(parent in targets and not targets[parent] for parent in target.parents):
            raise ValueError(f"file conflicts with a directory in archive: {target.name}")
    if expanded > MAX_EXPANDED_BYTES or expanded > shutil.disk_usage(destination).free:
        raise ValueError("archive exceeds the extraction size limit or available disk space")
    return expanded


def validate_members(archive: tarfile.TarFile, destination: Path) -> int:
    members = []
    for member in archive:
        if len(members) >= MAX_MEMBERS:
            raise ValueError("archive contains too many entries")
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"links and special files are not allowed in archive: {member.name}")
        members.append(member)
    return archive_members([(m.name, m.isdir(), m.size) for m in members], destination)


def validate_zip_members(archive: zipfile.ZipFile, destination: Path) -> int:
    members = archive.infolist()
    for member in members:
        mode = stat.S_IFMT(member.external_attr >> 16)
        if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError(f"links and special files are not allowed in archive: {member.filename}")
        if member.flag_bits & 1:
            raise ValueError("encrypted ZIP archives are not supported")
    return archive_members([(m.filename, m.is_dir(), m.file_size) for m in members], destination)


def flattened_target(path: Path, source: Path, destination: Path) -> Path:
    relative = path.relative_to(source)
    discs = [part for part in relative.parts[:-1] if DISC_DIRECTORY.fullmatch(part)]
    return destination.joinpath(*discs, path.name)


def is_text_sidecar(path: Path) -> bool:
    """Check the entire file before treating an explicit sidecar suffix as text."""
    with path.open("rb") as stream:
        bom = stream.read(2)
    encoding = "utf-16" if bom in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        with path.open(encoding=encoding) as stream:
            while chunk := stream.read(65536):
                if any(not char.isprintable() and char not in "\t\r\n\f" for char in chunk):
                    return False
    except UnicodeDecodeError:
        if encoding == "utf-16" or path.suffix.casefold() != ".nfo":
            return False
        # Scene NFOs often use CP437 box art. Limit the fallback to printable
        # ASCII plus drawing glyphs, rather than interpreting arbitrary binary
        # bytes as printable characters in a single-byte encoding.
        drawing = False
        with path.open("rb") as stream:
            while chunk := stream.read(65536):
                for byte, char in zip(chunk, chunk.decode("cp437")):
                    if byte >= 128:
                        if not ("\u2500" <= char <= "\u259f" or char == "\u25a0"):
                            return False
                        drawing = True
                    elif not char.isprintable() and char not in "\t\r\n\f":
                        return False
        return drawing
    return True


def is_srr_sidecar(path: Path) -> bool:
    """Recognise the bounded ReScene marker/application header, not its suffix alone."""
    with path.open("rb") as stream:
        header = stream.read(7)
        if len(header) != 7 or header[:3] != b"iii":
            return False
        flags = int.from_bytes(header[3:5], "little")
        size = int.from_bytes(header[5:7], "little")
        if flags not in (0, 1) or size < 7:
            return False
        rest = stream.read(size - 7)
        if len(rest) != size - 7:
            return False
        if not flags:
            return size == 7
        return size >= 9 and int.from_bytes(rest[:2], "little") == size - 9


def is_album_info_sidecar(path: Path) -> bool:
    """Recognise bounded posting metadata, never arbitrary extensionless text."""
    if not re.fullmatch(r"(?:[a-z0-9]{1,32}_)?album_info", path.name, re.IGNORECASE):
        return False
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if not raw or len(raw) > 65536:
        return False
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    if any(not char.isprintable() and char not in "\t\r\n\f" for char in text):
        return False
    return (all(re.search(r"^[ \t]*" + field + r"[ \t]*:[ \t]*\S[^\r\n]*\r?$", text,
                          re.IGNORECASE | re.MULTILINE) for field in ("Album", "Artist"))
            and re.search(r"^[ \t]*Tracklist[ \t]*:[ \t]*\r?$", text, re.IGNORECASE | re.MULTILINE) is not None
            and re.search(r"^[ \t]*\d{1,3}[ .)-]+\S[^\r\n]*\r?$", text, re.MULTILINE) is not None)


def disposable(path: Path) -> bool:
    suffix = path.suffix.casefold()
    if suffix not in KNOWN_MEDIA_SUFFIXES | {".cue", ".m3u", ".m3u8"}:
        # Only the complete short posting marker is disposable, never a prefix.
        with path.open("rb") as stream:
            if stream.read(15) in {b"~^newz[NZB]~", b"~^newz[NZB]~\n", b"~^newz[NZB]~\r\n"}:
                return True
    if not suffix and is_album_info_sidecar(path):
        return detected_suffix(path) is None and playlist_entries(path) is None
    if suffix not in UNWANTED_SUFFIXES:
        return False
    # Playlist disposal needs the whole release, including files from later
    # archives. Never discard a duplicate before completeness is established.
    if path.suffix.casefold() in {".m3u", ".m3u8"} or playlist_entries(path) is not None:
        return False
    suffix = detected_suffix(path)
    if suffix is None and path.suffix.casefold() == ".srr" and is_srr_sidecar(path):
        return True
    return suffix in CLEANUP_SIGNATURE_SUFFIXES or (suffix is None and is_text_sidecar(path))


def extension_target(path: Path) -> Path:
    if path.suffix.casefold() in KNOWN_MEDIA_SUFFIXES:
        return path
    suffix = detected_suffix(path)
    if not suffix or (suffix in CLEANUP_SIGNATURE_SUFFIXES and path.suffix.casefold() in UNWANTED_SUFFIXES):
        return path
    return path.with_name(path.name + suffix)


def read_cues(files: list[Path], root: Path) -> dict[Path, tuple[str, str, dict[str, Path]]]:
    cues = {}
    by_relative = {path.relative_to(root).as_posix(): path for path in files}
    for cue in files:
        if cue.suffix.casefold() != ".cue":
            continue
        if detected_suffix(cue) is not None:
            continue
        data = cue.read_bytes()
        encoding = ("utf-16-le" if data.startswith(b"\xff\xfe") else
                    "utf-16-be" if data.startswith(b"\xfe\xff") else
                    "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8")
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            encoding = "cp1252"
            text = data.decode(encoding)
        if any(not char.isprintable() and char not in "\t\r\n\f\ufeff" for char in text):
            raise ValueError(f"unsupported or non-text cue sheet: {cue.name}")
        references = {}
        for line in text.splitlines():
            match = CUE_FILE.fullmatch(line)
            if re.match(r"^[\ufeff \t]*FILE[ \t]", line, re.IGNORECASE) and not match:
                raise ValueError(f"unsupported FILE entry in cue sheet: {cue.name}")
            if not match:
                continue
            name = match.group("quoted") or match.group("plain")
            portable = name.replace("\\", "/")
            if PurePosixPath(portable).is_absolute() or PureWindowsPath(name).drive:
                raise ValueError(f"absolute FILE reference in cue sheet: {cue.name}")
            target = (cue.parent / portable).resolve()
            target.relative_to(root)
            relative = target.relative_to(root).as_posix()
            if relative not in by_relative:
                candidates = [value for key, value in by_relative.items() if key.casefold() == relative.casefold()]
                if len(candidates) != 1:
                    raise ValueError(f"missing or ambiguous FILE reference in cue sheet: {cue.name}: {name}")
                target = candidates[0]
            if target.suffix.casefold() == ".cue" or is_archive(target):
                raise ValueError(f"invalid FILE reference in cue sheet: {cue.name}")
            references[name] = target
        cues[cue] = (encoding, text, references)
    return cues


def flac_album_metadata(path: Path) -> tuple[dict[str, str], bool]:
    """Read bounded FLAC comments; skip artwork without loading it (RFC 9639)."""
    tags: dict[str, str] = {}
    embedded_cue = False
    with path.open("rb") as stream:
        if stream.read(4) != b"fLaC":
            return tags, embedded_cue
        for _ in range(128):
            header = stream.read(4)
            if len(header) != 4:
                return {}, False
            kind, length = header[0] & 127, int.from_bytes(header[1:], "big")
            if stream.tell() + length > path.stat().st_size:
                return {}, False
            if kind == 5:
                embedded_cue = True
            if kind == 4:
                if length > 1024**2:
                    return {}, False
                data = stream.read(length)
                offset = 0
                def field() -> bytes:
                    nonlocal offset
                    if offset + 4 > len(data):
                        raise ValueError("truncated FLAC comment")
                    size = int.from_bytes(data[offset:offset + 4], "little")
                    offset += 4
                    if offset + size > len(data):
                        raise ValueError("truncated FLAC comment")
                    value = data[offset:offset + size]
                    offset += size
                    return value
                try:
                    field()  # Vendor string.
                    if offset + 4 > len(data):
                        return {}, False
                    count = int.from_bytes(data[offset:offset + 4], "little")
                    offset += 4
                    if count > 10000:
                        return {}, False
                    for _ in range(count):
                        key, separator, value = field().decode("utf-8").partition("=")
                        if separator:
                            key = key.upper()
                            single_value_keys = {
                                "ALBUM", "ALBUMARTIST", "ALBUM ARTIST", "ARTIST", "TITLE", "TRACK", "TRACKNUMBER",
                                "TRACKTOTAL", "TOTALTRACKS", "DISC", "DISCNUMBER", "DISCTOTAL", "TOTALDISCS", "CUESHEET",
                            }
                            if key in single_value_keys and key in tags and tags[key] != value:
                                if key in {"TRACK", "TRACKNUMBER", "TRACKTOTAL", "TOTALTRACKS",
                                           "DISC", "DISCNUMBER", "DISCTOTAL", "TOTALDISCS"}:
                                    if not value.strip():
                                        continue
                                    values = {"previous": tags[key], "incoming": value}
                                    positions = key in {"TRACK", "TRACKNUMBER", "DISC", "DISCNUMBER"}
                                    try:
                                        number, total = metadata_position(
                                            values, ("previous", "incoming") if positions else (),
                                            () if positions else ("previous", "incoming"), key)
                                    except ValueError as error:
                                        raise RuntimeError(f"conflicting repeated FLAC {key} tags; retaining all files") from error
                                    value = (number + ("/" + total if total else "")) if positions else total
                                else:
                                    return {}, False
                            tags[key] = value
                except (ValueError, UnicodeDecodeError):
                    return {}, False
            else:
                stream.seek(length, os.SEEK_CUR)
            if header[0] & 128:
                return tags, embedded_cue
    return {}, False


def metadata_position(tags: dict[str, str], names: tuple[str, ...],
                      total_names: tuple[str, ...], label: str) -> tuple[str, str]:
    """Reconcile nonempty aliases and slash totals without letting blanks mask evidence."""
    positions = []
    totals = [tags.get(name, "").strip() for name in total_names]
    for name in names:
        value = tags.get(name, "").strip()
        if value:
            position, separator, total = value.partition("/")
            positions.append(position.strip())
            if separator:
                totals.append(total.strip())

    def reconcile(values: list[str]) -> str:
        values = [value for value in values if value]
        normalized = {str(int(value)) if re.fullmatch(r"[0-9]{1,5}", value) else value
                      for value in values}
        if len(normalized) > 1:
            raise ValueError(f"conflicting FLAC {label} metadata aliases; retaining all files")
        return next(iter(normalized), "")

    return reconcile(positions), reconcile(totals)


def album_directory(path: Path, root: Path) -> Path:
    parent = root
    for part in path.relative_to(root).parts[:-1]:
        parent = parent / part
        if DISC_DIRECTORY.fullmatch(part):
            return parent.parent
    return path.parent


def check_album_tracks(files: list[Path], protected: set[Path], root: Path) -> set[Path]:
    groups: dict[tuple, list[tuple[Path, str, str]]] = {}
    discs: dict[tuple, list[tuple[str, str]]] = {}
    proven = set(protected)
    for path in files:
        if detected_suffix(path) != ".flac":
            continue
        tags, embedded_cue = flac_album_metadata(path)
        disc, disc_total = metadata_position(tags, ("DISCNUMBER", "DISC"),
                                             ("DISCTOTAL", "TOTALDISCS"), "disc")
        ancestry = tuple(part.casefold() for part in path.parent.relative_to(root).parts if DISC_DIRECTORY.fullmatch(part))
        album = tags.get("ALBUM", "").strip().casefold()
        artist = (tags.get("ALBUMARTIST") or tags.get("ALBUM ARTIST", "")).strip().casefold()
        base = album_directory(path, root)
        # A shared album name alone must not combine independent edition folders.
        discs.setdefault((album or str(base), artist, str(base)), []).append((disc, disc_total))
        if path in protected or embedded_cue or tags.get("CUESHEET"):
            proven.add(path)
            continue
        number, total = metadata_position(tags, ("TRACKNUMBER", "TRACK"),
                                          ("TRACKTOTAL", "TOTALTRACKS"), "track")
        key = (album or str(path.parent), artist, disc, ancestry, str(base))
        groups.setdefault(key, []).append((path, number, total))
    for records in discs.values():
        totals = {int(total) for _, total in records if re.fullmatch(r"[0-9]{1,5}", total) and int(total) > 0}
        if not totals:
            continue
        if len(totals) != 1:
            raise ValueError("conflicting FLAC disc totals within an album; retaining all files")
        total = totals.pop()
        numbers = {int(number) for number, _ in records if re.fullmatch(r"[0-9]{1,5}", number)}
        if any(not re.fullmatch(r"[0-9]{1,5}", number) for number, _ in records) or numbers != set(range(1, total + 1)):
            raise ValueError(f"incomplete album: missing or invalid discs of {total}; retaining all files")
    for records in groups.values():
        totals = {int(total) for _, _, total in records if re.fullmatch(r"[0-9]{1,5}", total) and int(total) > 0}
        if not totals:
            # Track positions establish a lower bound even without a declared total.
            if any(total for _, _, total in records) or not all(
                       re.fullmatch(r"[0-9]{1,5}", number) and int(number) > 0
                       for _, number, _ in records):
                continue  # Untagged or ambiguous positions cannot establish a sequence.
            numbers = [int(number) for _, number, _ in records]
            if len(set(numbers)) != len(numbers):
                raise ValueError("duplicate FLAC track numbers within an album/disc; retaining all files")
            if sorted(numbers) != list(range(1, len(numbers) + 1)):
                raise ValueError(
                    f"incomplete album/disc: numbered tracks have gaps before track {max(numbers)} "
                    "without a declared total; retaining all files. Obtain a complete release; "
                    "post-processing cannot restore tracks absent from the download"
                )
            continue  # A contiguous prefix cannot prove that later tracks are present.
        if len(totals) != 1:
            raise ValueError("conflicting FLAC track totals within an album/disc; retaining all files")
        total = totals.pop()
        numbers = [int(number) for _, number, _ in records if re.fullmatch(r"[0-9]{1,5}", number)]
        if len(numbers) != len(records) or any(number < 1 or number > total for number in numbers):
            raise ValueError("missing or invalid FLAC track numbers within an album/disc; retaining all files")
        if len(set(numbers)) != len(numbers):
            raise ValueError("duplicate FLAC track numbers within an album/disc; retaining all files")
        if len(numbers) != total:
            detail = (f"only one audio file remains, tagged track {numbers[0]} of {total}" if len(numbers) == 1 else
                      f"album/disc has {len(numbers)} of {total} tagged tracks")
            raise ValueError(
                f"incomplete album: {detail}; retaining all files. "
                "Check NZBGet RenameIgnoreExt / RenameAfterUnpack before downloading again; "
                "earlier renaming can overwrite tracks before this script starts"
            )

        proven.update(path for path, _, _ in records)
    return proven


AUDIO_SUFFIXES = {
    ".aac", ".aif", ".aiff", ".alac", ".ape", ".flac", ".m4a", ".mka", ".mp3", ".ogg", ".opus", ".wav", ".wma",
}


def verify_audio_files(plan: ProcessingPlan) -> None:
    audio = [source for source, target in plan.targets.items()
             if target.suffix.casefold() in AUDIO_SUFFIXES or detected_suffix(source) in AUDIO_SUFFIXES]
    if not audio:
        return
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("VerifyAudio requires ffmpeg in the NZBGet runtime; retaining all files")
    for path in audio:
        command = [executable, "-nostdin", "-hide_banner", "-v", "error", "-xerror",
                   "-err_detect", "explode", "-protocol_whitelist", "file,pipe", "-threads", "1", "-i", str(path.resolve()),
                   "-map", "0:a", "-abort_on", "empty_output", "-f", "null", "-"]
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=600, check=False)
        except subprocess.TimeoutExpired as error:
            raise ValueError(f"audio verification timed out: {path.name}; retaining all files") from error
        if result.returncode:
            raise ValueError(f"audio decoding verification failed: {path.name}; retaining all files")
    print(f"[INFO] Audio decoding verified: {len(audio)} files")


def playlist_reference(line: str) -> PurePosixPath | None:
    line = line.strip()
    if not line or line.startswith("#") or any(not char.isprintable() for char in line):
        return None
    entry = PurePosixPath(line.replace("\\", "/"))
    if (entry.is_absolute() or PureWindowsPath(line).drive or ":" in line
            or ".." in entry.parts or entry.suffix.casefold() not in AUDIO_SUFFIXES):
        return None
    return entry


def playlist_entries(path: Path) -> list[PurePosixPath] | None:
    """Recognise bounded local M3U text, never arbitrary text or remote paths."""
    if path.suffix.casefold() in KNOWN_MEDIA_SUFFIXES | {".cue"}:
        return None
    if path.stat().st_size > 1024**2 or detected_suffix(path) is not None:
        return None
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")
    except UnicodeDecodeError:
        return None
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entry = playlist_reference(line)
        if entry is None:
            return None
        entries.append(entry)
        if len(entries) > MAX_MEMBERS:
            return None
    minimum = 1 if path.suffix.casefold() in {".m3u", ".m3u8"} else 2
    if len(entries) < minimum or len(set(entries)) != len(entries):
        return None
    return entries


def playlist_title(value: str) -> str:
    # Scene filenames replace punctuation with underscores and '&' with 'and'.
    words = re.findall(r"[^\W_]+", value.casefold())
    return "".join(word for word in words if word not in {"and", "feat", "ft", "featuring"})


def check_playlists(files: list[Path], protected: set[Path],
                    covered: set[Path] | None = None,
                    references: dict[Path, dict[PurePosixPath, Path]] | None = None,
                    validate: bool = True) -> set[Path]:
    recognised = set()
    audio = [path for path in files if detected_suffix(path) in AUDIO_SUFFIXES
             or path.suffix.casefold() in AUDIO_SUFFIXES]
    for playlist in files:
        entries = playlist_entries(playlist)
        if entries is None:
            continue
        available: dict[str, set[Path]] = {}
        for path in audio:
            if path.is_relative_to(playlist.parent):
                for target in (path, extension_target(path)):
                    available.setdefault(target.relative_to(playlist.parent).as_posix().casefold(), set()).add(path)
        exact = [entry.as_posix().casefold() in available for entry in entries]
        if all(exact):
            resolved = [available[entry.as_posix().casefold()] for entry in entries]
            if any(len(matches) != 1 for matches in resolved) or len({next(iter(matches)) for matches in resolved}) != len(entries):
                raise ValueError(f"ambiguous playlist: {playlist.name}; entries must reference distinct audio files; retaining all files")
            if covered is not None:
                for entry in entries:
                    matches = available[entry.as_posix().casefold()]
                    if len(matches) == 1:
                        covered.update(matches)
            if references is not None and all(len(available[entry.as_posix().casefold()]) == 1 for entry in entries):
                references[playlist] = {entry: next(iter(available[entry.as_posix().casefold()])) for entry in entries}
            recognised.add(playlist)
            continue
        if playlist in protected:
            continue
        # Obfuscated files can still be related through numbered artist/title
        # entries, but only for one fully tagged, cue-free FLAC album/disc.
        candidates = [path for path in audio if path.parent == playlist.parent]
        if not candidates or any(path in protected or detected_suffix(path) != ".flac" for path in candidates):
            if validate and any(exact):
                raise ValueError(f"incomplete playlist: {playlist.name}; missing audio entries; retaining all files")
            continue
        identities = set()
        matched = []
        for path in candidates:
            tags, embedded = flac_album_metadata(path)
            track, _ = metadata_position(tags, ("TRACKNUMBER", "TRACK"), ("TRACKTOTAL", "TOTALTRACKS"), "track")
            if embedded or tags.get("CUESHEET") or not tags.get("ALBUM") or not tags.get("ARTIST") or not tags.get("TITLE"):
                break
            if not re.fullmatch(r"[0-9]{1,5}", track):
                break
            disc, _ = metadata_position(tags, ("DISCNUMBER", "DISC"), ("DISCTOTAL", "TOTALDISCS"), "disc")
            identities.add((tags["ALBUM"].strip().casefold(),
                            (tags.get("ALBUMARTIST") or tags.get("ALBUM ARTIST", "")).strip().casefold(), disc))
            expected = playlist_title(tags["ARTIST"] + " " + tags["TITLE"])
            matches = [index for index, entry in enumerate(entries)
                       if len(entry.parts) == 1
                       and (match := re.fullmatch(r"([0-9]{1,5})[ _.-]+(.+)", entry.stem))
                       and int(match[1]) == int(track)
                       and any(playlist_title(stem) == expected for stem in
                               (match[2], re.sub(r"-[0-9a-fA-F]{8}$", "", match[2])))]
            if len(matches) != 1:
                break
            matched.append(matches[0])
        else:
            if len(identities) == 1 and len(set(matched)) == len(candidates):
                if len(matched) != len(entries):
                    if not validate:
                        continue
                    raise ValueError(f"incomplete playlist: {playlist.name}; {len(matched)} of {len(entries)} tracks present; retaining all files")
                if references is not None:
                    references[playlist] = {entries[index]: path for path, index in zip(candidates, matched)}
                if covered is not None:
                    covered.update(candidates)
                recognised.add(playlist)
                continue
        if validate and any(exact):
            raise ValueError(f"incomplete playlist: {playlist.name}; missing audio entries; retaining all files")
    return recognised


def plan_tree(root: Path, *, flatten: bool = True,
              extensions: bool = True, cleanup: bool = True,
              require_completeness: bool = False) -> ProcessingPlan:
    files = tree_files(root)
    for path in files:
        if path.suffix.casefold() in AUDIO_SUFFIXES and path.stat().st_size == 0:
            raise ValueError(f"empty audio file: {path.name}; retaining all files")
    cues = read_cues(files, root)
    protected = {target for _, _, refs in cues.values() for target in refs.values()}
    proven = check_album_tracks(files, protected, root) if cleanup or require_completeness else set()
    covered: set[Path] = set()
    playlist_refs: dict[Path, dict[PurePosixPath, Path]] = {}
    playlists = check_playlists(files, protected, covered, playlist_refs, validate=cleanup or require_completeness)
    available_names = {target.as_posix().casefold() for path in files for target in (path, extension_target(path))}
    if any(path not in playlist_refs and (path.suffix.casefold() in {".m3u", ".m3u8"}
           or any((path.parent / entry).as_posix().casefold() in available_names
                  for entry in playlist_entries(path) or [])) for path in files):
        # Unknown retained playlists may contain references we cannot safely rewrite.
        flatten = extensions = False
    if require_completeness:
        unresolved = [path for path in files if (detected_suffix(path) in AUDIO_SUFFIXES
                      or path.suffix.casefold() in AUDIO_SUFFIXES) and path not in proven | covered]
        if unresolved:
            raise ValueError(f"RequireCompleteness: final track count is unproven for {len(unresolved)} audio files; retaining all files")
    # Keep distinct unknown album groups stable across repeated processing.
    unknown_groups: dict[Path, set[Path]] = {}
    numbered_unknown = False
    album_boundaries: dict[tuple, set[Path]] = {}
    for path in files:
        if detected_suffix(path) != ".flac":
            continue
        tags, _ = flac_album_metadata(path)
        if tags.get("ALBUM", "").strip():
            key = (tags["ALBUM"].strip().casefold(),
                   (tags.get("ALBUMARTIST") or tags.get("ALBUM ARTIST", "")).strip().casefold())
            album_boundaries.setdefault(key, set()).add(album_directory(path, root))
            continue
        numbered_unknown |= bool(tags.get("TRACKNUMBER") or tags.get("TRACK"))
        parent = flattened_target(path, root, root).parent
        unknown_groups.setdefault(parent, set()).add(path.parent)
    if (any(len(parents) > 1 for parents in album_boundaries.values())
            or (numbered_unknown and any(len(parents) > 1 for parents in unknown_groups.values()))):
        flatten = False
    plans = {}
    removed = []
    repaired = []
    unknown = []
    media = 0
    for path in files:
        target = extension_target(path) if extensions else path
        sidecar = path in playlists or (path.suffix.casefold() not in {".m3u", ".m3u8"} and disposable(path))
        if (cleanup and path not in protected and not (require_completeness and path in playlists)
                and (sidecar or detected_suffix(path) in CLEANUP_SIGNATURE_SUFFIXES)):
            # Only recognized images/documents without an established media suffix are
            # disposable. Do not delete a named audio/video file on a sniff alone.
            if path.suffix.casefold() not in KNOWN_MEDIA_SUFFIXES or disposable(path):
                removed.append(path)
                continue
        if target != path:
            repaired.append(path)
        if target.suffix.casefold() in KNOWN_MEDIA_SUFFIXES - {".jpeg"}:
            media += 1
        elif path not in cues and detected_suffix(path) is None and path.suffix.casefold() not in KNOWN_MEDIA_SUFFIXES:
            unknown.append(path)
        plans[path] = flattened_target(target, root, root) if flatten else target
        if plans[path].relative_to(root).parts[0].startswith(".unpack-music-"):
            raise ValueError("output filename conflicts with the private recovery workspace prefix")
    check_targets(list(plans.values()), root)
    rewritten = {}
    for playlist, refs in playlist_refs.items():
        if playlist not in plans:
            continue
        raw = playlist.read_bytes()
        bom = raw[:2] if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else b""
        encoding = ("utf-16-le" if bom == b"\xff\xfe" else "utf-16-be") if bom else (
            "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8")
        lines = []
        for line in raw[len(bom):].decode(encoding).splitlines(keepends=True):
            entry = playlist_reference(line)
            if entry in refs:
                relative = os.path.relpath(plans[refs[entry]], plans[playlist].parent).replace(os.sep, "/")
                rendered = "./" + relative if relative.startswith("#") or relative != relative.strip() else relative
                reference = playlist_reference(rendered)
                if reference is None or reference.as_posix() != relative:
                    raise ValueError(f"filename cannot be represented in a playlist: {playlist.name}")
                ending = line[len(line.rstrip("\r\n")):]
                line = rendered + ending
            lines.append(line)
        content = bom + "".join(lines).encode(encoding)
        if content != raw:
            rewritten[playlist] = content
    for cue, (encoding, text, refs) in cues.items():
        def replace(match: re.Match[str]) -> str:
            name = match.group("quoted") or match.group("plain")
            relative = os.path.relpath(plans[refs[name]], plans[cue].parent).replace(os.sep, "/")
            if any(char in relative for char in '"\r\n'):
                raise ValueError(f"filename cannot be represented in a cue sheet: {cue.name}")
            return match.group("prefix") + '"' + relative + '"' + match.group("tail")
        lines = []
        for line in text.splitlines(keepends=True):
            content = line.rstrip("\r\n")
            match = CUE_FILE.fullmatch(content)
            lines.append(replace(match) + line[len(content):] if match else line)
        content = "".join(lines).encode(encoding)
        if content != cue.read_bytes():
            rewritten[cue] = content
    return ProcessingPlan(plans, rewritten, removed, repaired, unknown, media)


def normalize_tree(root: Path, scratch: Path, *, flatten: bool = True,
                   extensions: bool = True, cleanup: bool = True,
                   plan: ProcessingPlan | None = None) -> None:
    plan = plan or plan_tree(root, flatten=flatten, extensions=extensions, cleanup=cleanup)
    plans, rewritten = plan.targets, plan.cues
    holding = scratch / "normalized"
    holding.mkdir()
    for index, source in enumerate(plans):
        item = holding / str(index)
        mode = source.stat().st_mode
        source.rename(item)
        if source in rewritten and item.read_bytes() != rewritten[source]:
            # Break the hard link before writing so the original remains intact.
            item.unlink()
            item.write_bytes(rewritten[source])
            item.chmod(stat.S_IMODE(mode))
    shutil.rmtree(root)
    root.mkdir()
    for index, target in enumerate(plans.values()):
        target.parent.mkdir(parents=True, exist_ok=True)
        (holding / str(index)).rename(target)


def extract_archives(stage: Path, scratch: Path) -> tuple[list[str], int]:
    count = 0
    names = []
    expanded = 0
    duplicates = []
    duplicate_storage = scratch / "duplicate-sidecars"
    duplicate_storage.mkdir()
    while archives := [path for path in tree_files(stage) if is_archive(path)]:
        for path in archives:
            count += 1
            names.append(path.relative_to(stage).as_posix())
            if count > MAX_ARCHIVES:
                raise ValueError("too many nested or separate music archives")
            extraction = scratch / "extracted"
            extraction.mkdir()
            if path.name.lower().endswith(".zip"):
                with zipfile.ZipFile(path) as archive:
                    size = validate_zip_members(archive, extraction)
                    expanded += size
                    if expanded > MAX_EXPANDED_BYTES:
                        raise ValueError("release exceeds the extraction size limit")
                    archive.extractall(extraction)
            else:
                with tarfile.open(path, mode="r:*") as archive:
                    size = validate_members(archive, extraction)
                    expanded += size
                    if expanded > MAX_EXPANDED_BYTES:
                        raise ValueError("release exceeds the extraction size limit")
                    archive.extractall(extraction, filter="data")
            for item in tree_files(extraction):
                target = path.parent / item.relative_to(extraction)
                if target.exists():
                    if target.is_file() and disposable(target) and disposable(item):
                        item.rename(duplicate_storage / str(len(duplicates)))
                        duplicates.append(target)
                        continue
                    raise FileExistsError(f"refusing to overwrite existing path: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                item.rename(target)
            shutil.rmtree(extraction)
            path.unlink()
    protected = {target for _, _, refs in read_cues(tree_files(stage), stage).values() for target in refs.values()}
    if any(target in protected for target in duplicates):
        raise FileExistsError("duplicate archive files are referenced by a cue sheet")
    return names, len(duplicates)


def publish(stage: Path, root: Path, originals: list[Path], scratch: Path,
            expected_states: dict[Path, tuple[int, ...]] | None = None) -> None:
    """Publish with rollback on ordinary I/O failures; retain recovery on failure."""
    files = tree_files(stage)
    targets = [root / path.relative_to(stage) for path in files]
    check_targets(targets, root)
    if any(target.is_dir() for target in targets):
        raise FileExistsError("a destination file conflicts with an existing directory")
    backup = scratch / "originals"
    backup.mkdir()
    with (scratch / "recovery.json").open("w", encoding="utf-8") as journal:
        json.dump({"version": 2,
                   "originals": [path.relative_to(root).as_posix() for path in originals],
                   "original_hashes": [file_hash(path) for path in originals],
                   "targets": [path.relative_to(root).as_posix() for path in targets],
                   "target_hashes": [file_hash(path) for path in files]}, journal)
        journal.flush()
        os.fsync(journal.fileno())
    saved = []
    installed = []
    try:
        for index, original in enumerate(originals):
            if expected_states and file_state(original) != expected_states[original]:
                raise ValueError("input changed before publication")
            target = backup / str(index)
            original.rename(target)
            saved.append((target, original))
        for source, target in zip(files, targets):
            check_targets([target], root)
            if target.exists() or target.is_symlink():
                raise FileExistsError(f"destination changed during processing: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            expected_state = file_state(source)
            source.rename(target)
            installed.append((target, expected_state))
    except (OSError, ValueError):
        for target, expected_state in reversed(installed):
            if target.is_symlink() or not target.exists() or file_state(target) != expected_state:
                raise FileExistsError(f"output changed during publication; retaining recovery files: {target}")
            target.unlink()
        for saved_path, original in reversed(saved):
            check_targets([original], root)
            if original.exists() or original.is_symlink():
                raise FileExistsError(f"refusing to overwrite a changed input during rollback: {original}")
            original.parent.mkdir(parents=True, exist_ok=True)
            saved_path.rename(original)
        raise

    mark_completed(scratch, "published")


def mark_completed(workspace: Path, state: str) -> None:
    """Persist verified completion before deleting any recovery data."""
    record = workspace / "recovery.json"
    journal = json.loads(record.read_text(encoding="utf-8"))
    paths, hashes = (("targets", "target_hashes") if state == "published"
                    else ("originals", "original_hashes"))
    completed = journal_paths(journal[paths], journal[hashes], workspace.parent)
    if any(not target.is_file() or file_hash(target) != digest for target, digest in completed.items()):
        raise ValueError("completed file checksum mismatch; retaining recovery files")
    journal["state"] = state
    pending = workspace / "recovery.json.new"
    with pending.open("w", encoding="utf-8") as stream:
        json.dump(journal, stream)
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(record)
    descriptor = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def cleanup_workspace(workspace: Path) -> None:
    """Keep the recovery journal until every other workspace entry is removed."""
    record = workspace / "recovery.json"
    for path in workspace.iterdir():
        if path == record:
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    record.unlink(missing_ok=True)
    workspace.rmdir()


def process_release(directory: Path, *, extract: bool = True, flatten: bool = True,
                    extensions: bool = True, cleanup: bool = True, verify_audio: bool = False,
                    require_completeness: bool = False) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("download directory must be an existing directory without a symlink")
    root = directory.resolve()
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        process_locked(root, extract=extract, flatten=flatten, extensions=extensions, cleanup=cleanup, verify_audio=verify_audio,
                       require_completeness=require_completeness)
    finally:
        os.close(descriptor)


def process_locked(root: Path, *, extract: bool, flatten: bool, extensions: bool, cleanup: bool,
                   verify_audio: bool = False, require_completeness: bool = False) -> None:
    if any(path.name.startswith(".unpack-music-") for path in root.iterdir()):
        raise ValueError("unfinished music processing workspace found; recover it before retrying")
    originals = tree_files(root)
    baseline = {path: file_state(path) for path in originals}
    audio_verified = False
    if not extract or not any(is_archive(path) for path in originals):
        initial_plan = plan_tree(root, flatten=flatten, extensions=extensions, cleanup=cleanup,
                                 require_completeness=require_completeness)
        if cleanup and not initial_plan.targets:
            raise ValueError("no files would remain after music cleanup; retaining the original release")
        if verify_audio:
            verify_audio_files(initial_plan)
            audio_verified = True
        if not initial_plan.changed:
            if tree_files(root) != originals or any(file_state(path) != baseline[path] for path in originals):
                raise ValueError("download files changed during inspection")
            print_summary(initial_plan, unchanged=True)
            return
    scratch = Path(tempfile.mkdtemp(prefix=".unpack-music-", dir=root))
    published = False
    try:
        stage = scratch / "release"
        stage.mkdir()
        for original in originals:
            target = stage / original.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(original, target)
            except OSError as error:
                if error.errno not in (errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP, errno.ENOSYS, errno.EMLINK):
                    raise
                if original.stat().st_size > shutil.disk_usage(scratch).free:
                    raise ValueError("insufficient disk space to stage files without hard-link support") from error
                shutil.copy2(original, target)
        archives, duplicates = extract_archives(stage, scratch) if extract else ([], 0)
        plan = plan_tree(stage, flatten=flatten, extensions=extensions, cleanup=cleanup,
                         require_completeness=require_completeness)
        if verify_audio and not audio_verified:
            verify_audio_files(plan)
        normalize_tree(stage, scratch, flatten=flatten, extensions=extensions, cleanup=cleanup, plan=plan)
        retained = len(tree_files(stage))
        if cleanup and not retained:
            raise ValueError("no files would remain after music cleanup; retaining the original release")
        current = tree_files(root, exclude=scratch)
        if current != originals or any(file_state(path) != baseline[path] for path in current):
            raise ValueError("download files changed during processing; retry after other writers finish")
        publish(stage, root, originals, scratch, expected_states=baseline)
        published = True
    finally:
        # A failed rollback retains private original files for manual recovery.
        backup = scratch / "originals"
        if published or not backup.exists() or not any(backup.iterdir()):
            cleanup_workspace(scratch)
        else:
            print(f"[ERROR] Recovery files retained at {scratch}", file=sys.stderr)
    for parent in sorted((path for path in root.rglob("*") if path.is_dir()),
                         key=lambda path: len(path.parts), reverse=True):
        try:
            parent.rmdir()
        except OSError:
            pass
    print_summary(plan, archives=len(archives), duplicates=duplicates)


def file_state(path: Path) -> tuple[int, ...]:
    state = path.stat()
    return (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns,
            state.st_mode, state.st_uid, state.st_gid)


def add_missing_extensions(directory: Path) -> None:
    process_release(directory, extract=False, flatten=False, cleanup=False)


def remove_unwanted_files(directory: Path) -> None:
    process_release(directory, extract=False, flatten=False, extensions=False)


def flatten_existing_tree(directory: Path) -> None:
    process_release(directory, extract=False, extensions=False, cleanup=False)


def unpack(path: Path) -> None:
    process_release(path.parent)


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def print_summary(plan: ProcessingPlan, *, archives: int = 0, duplicates: int = 0,
                  unchanged: bool = False) -> None:
    label = "Release unchanged" if unchanged else "Music processing complete"
    print(f"[INFO] {label}: {plan.media} media files retained; "
          f"{len(plan.removed) + duplicates} sidecars removed; {len(plan.repaired)} extensions repaired; "
          f"{len(plan.cues)} cue/playlist files updated; {len(plan.unknown)} unidentified files retained; "
          f"{archives} archives extracted; {len(plan.targets)} total files retained")
    for path in plan.unknown:
        print(f"[WARNING] Unidentified file retained: {json.dumps(plan.targets[path].name, ensure_ascii=False)}")


def preview(directory: Path, *, verify_audio: bool = False, require_completeness: bool = False) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("preview requires an existing release directory without a symlink")
    root = directory.resolve()
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if any(path.name.startswith(".unpack-music-") for path in root.iterdir()):
            raise ValueError("recover the unfinished workspace before previewing")
        files = tree_files(root)
        states = {path: file_state(path) for path in files}
        with tempfile.TemporaryDirectory(prefix="music-preview-") as temp:
            scratch = Path(temp)
            stage = scratch / "release"
            stage.mkdir()
            for path in files:
                if path.stat().st_size > shutil.disk_usage(scratch).free:
                    raise ValueError("insufficient temporary space for preview")
                target = stage / path.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            archives, duplicates = extract_archives(stage, scratch)
            plan = plan_tree(stage, require_completeness=require_completeness)
            if verify_audio:
                verify_audio_files(plan)
            targets = [root / path.relative_to(stage) for path in plan.targets.values()]
            check_targets(targets, root)
            if any(target.is_dir() for target in targets):
                raise FileExistsError("a destination file conflicts with an existing directory")
            if tree_files(root) != files or any(file_state(path) != states[path] for path in files):
                raise ValueError("download files changed during preview")
            print("[INFO] Preview only; the release was not modified")
            for name in archives:
                print(f"[PREVIEW] Extract archive: {json.dumps(name, ensure_ascii=False)}")
            for source in plan.removed:
                print(f"[PREVIEW] Remove sidecar: {json.dumps(source.relative_to(stage).as_posix(), ensure_ascii=False)}")
            if duplicates:
                print(f"[PREVIEW] Remove {duplicates} duplicate disposable sidecars")
            for source, target in plan.targets.items():
                if source != target:
                    print(f"[PREVIEW] Move: {json.dumps(source.relative_to(stage).as_posix(), ensure_ascii=False)}"
                          f" -> {json.dumps(target.relative_to(stage).as_posix(), ensure_ascii=False)}")
            for cue in plan.cues:
                kind = "cue FILE" if cue.suffix.casefold() == ".cue" else "playlist"
                print(f"[PREVIEW] Update {kind} references: {json.dumps(cue.relative_to(stage).as_posix(), ensure_ascii=False)}")
            print_summary(plan, archives=len(archives), duplicates=duplicates, unchanged=not plan.changed and not archives)
            if not plan.targets:
                print("[WARNING] Processing would refuse this plan because zero files would remain")
    finally:
        os.close(descriptor)


def journal_paths(values: object, hashes: object, root: Path) -> dict[Path, str]:
    if not isinstance(values, list) or not isinstance(hashes, list) or len(values) != len(hashes):
        raise ValueError("invalid recovery path/checksum lists")
    result = {}
    for value, digest in zip(values, hashes):
        if not isinstance(value, str) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid recovery path or checksum")
        relative = PurePosixPath(value)
        if (not relative.parts or relative.is_absolute() or PureWindowsPath(value).drive
                or ".." in relative.parts or "\\" in value or relative.parts[0].startswith(".unpack-music-")):
            raise ValueError("unsafe path in recovery journal")
        target = root / relative
        if target in result:
            raise ValueError("duplicate path in recovery journal")
        result[target] = digest
    check_targets(list(result), root)
    return result


def recover(workspace: Path) -> None:
    if workspace.is_symlink() or not workspace.is_dir() or not workspace.name.startswith(".unpack-music-"):
        raise ValueError("recovery requires an exact private .unpack-music-* workspace directory")
    root = workspace.parent.resolve()
    workspace = root / workspace.name
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        tree_files(workspace)
        if not any(workspace.iterdir()):
            workspace.rmdir()
            print("[INFO] Empty recovery workspace removed")
            return
        record = workspace / "recovery.json"
        if record.stat().st_size > 16 * 1024**2:
            raise ValueError("recovery journal is too large")
        journal = json.loads(record.read_text(encoding="utf-8"))
        if not isinstance(journal, dict) or journal.get("version") != 2:
            raise ValueError("legacy or incomplete recovery journal; manual recovery is required")
        originals = journal_paths(journal.get("originals"), journal.get("original_hashes"), root)
        outputs = journal_paths(journal.get("targets"), journal.get("target_hashes"), root)
        state = journal.get("state", "pending")
        if state not in ("pending", "published", "restored"):
            raise ValueError("invalid recovery publication state")
        if state in ("published", "restored"):
            completed = outputs if state == "published" else originals
            if any(not target.is_file() or file_hash(target) != digest for target, digest in completed.items()):
                raise ValueError("completed file checksum mismatch; retaining recovery workspace")
            cleanup_workspace(workspace)
            print(f"[INFO] {state.capitalize()} cleanup complete: {len(completed)} files verified")
            return
        backup = workspace / "originals"
        slots = {str(index) for index in range(len(originals))}
        if not backup.is_dir() or any(path.name not in slots
                                     or not path.is_file() for path in backup.iterdir()):
            raise ValueError("invalid original backup directory")
        restores = []
        already_restored = set()
        displace = {}
        for index, (target, digest) in enumerate(originals.items()):
            saved = backup / str(index)
            if saved.exists():
                if file_hash(saved) != digest:
                    raise ValueError("original backup checksum mismatch; manual recovery is required")
                restores.append((saved, target, digest))
                if target.exists():
                    if not target.is_file() or file_hash(target) not in (digest, outputs.get(target)):
                        raise FileExistsError(f"changed file conflicts with recovery: {target}")
                    displace[target] = file_hash(target)
            elif target.is_file() and file_hash(target) == digest:
                already_restored.add(target)
            else:
                raise ValueError(f"an original file is missing or changed: {target}")
        for target, digest in outputs.items():
            if target in already_restored or target in displace or not target.exists():
                continue
            if not target.is_file() or file_hash(target) != digest:
                raise FileExistsError(f"changed output conflicts with recovery: {target}")
            displace[target] = digest
        for _, target, _ in restores:
            for parent in target.parents:
                if parent == root:
                    break
                if parent.exists() and not parent.is_dir():
                    raise FileExistsError(f"file blocks an original directory: {parent}")
        quarantine = workspace / "recovery-displaced"
        quarantine.mkdir(exist_ok=True)
        moved_outputs = []
        moved_originals = []
        try:
            for target, digest in displace.items():
                if file_hash(target) != digest:
                    raise ValueError("output changed during recovery")
                saved = quarantine / str(len(list(quarantine.iterdir())))
                if saved.exists():
                    raise FileExistsError("conflicting recovery quarantine slot")
                target.rename(saved)
                moved_outputs.append((saved, target, digest))
            for saved, target, digest in restores:
                check_targets([target], root)
                if target.exists() or file_hash(saved) != digest:
                    raise ValueError("original or destination changed during recovery")
                target.parent.mkdir(parents=True, exist_ok=True)
                saved.rename(target)
                moved_originals.append((target, saved, digest))
            if any(not target.is_file() or file_hash(target) != digest for target, digest in originals.items()):
                raise ValueError("restored original checksum verification failed")
        except (OSError, ValueError):
            for target, saved, digest in reversed(moved_originals):
                if target.is_symlink() or file_hash(target) != digest:
                    raise ValueError("original changed during recovery rollback; retaining workspace")
                target.rename(saved)
            for saved, target, digest in reversed(moved_outputs):
                if target.exists() or target.is_symlink() or file_hash(saved) != digest:
                    raise ValueError("output changed during recovery rollback; retaining workspace")
                saved.rename(target)
            raise
        mark_completed(workspace, "restored")
        cleanup_workspace(workspace)
        print(f"[INFO] Recovery complete: {len(originals)} original files verified and restored")
    finally:
        os.close(descriptor)


def cli(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        return main()
    parser = argparse.ArgumentParser(description="Preview music processing or recover a retained workspace.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preview", type=Path, metavar="RELEASE_DIRECTORY")
    action.add_argument("--recover", type=Path, metavar="WORKSPACE_DIRECTORY")
    parser.add_argument("--verify-audio", action="store_true", help="Decode audio with ffmpeg during preview")
    parser.add_argument("--require-completeness", action="store_true",
                        help="Require track totals, covering local playlists or cue images during preview")
    options = parser.parse_args(arguments)
    if (options.verify_audio or options.require_completeness) and options.preview is None:
        parser.error("--verify-audio and --require-completeness require --preview")
    try:
        if options.preview is not None:
            preview(options.preview, verify_audio=options.verify_audio,
                    require_completeness=options.require_completeness)
        else:
            recover(options.recover)
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile, RuntimeError,
            NotImplementedError, EOFError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    category = os.environ.get("NZBPP_CATEGORY", "")
    if category.casefold() != "music":
        print(f"[INFO] Skipping category {category or '(none)'}")
        return SUCCESS
    status = os.environ.get("NZBPP_TOTALSTATUS", "").upper()
    detail = os.environ.get("NZBPP_STATUS", "").upper().split("/", 1)[0]
    legacy_bad = (os.environ.get("NZBPP_PARSTATUS") in {"1", "3", "4"}
                  or os.environ.get("NZBPP_UNPACKSTATUS") in {"1", "3", "4"})
    if (status and status != "SUCCESS") or (detail and detail != "SUCCESS") or legacy_bad:
        print("[WARNING] Download failed or requires intervention; skipping music processing and retaining all files")
        return SKIPPED
    directory_value = os.environ.get("NZBPP_FINALDIR") or os.environ.get("NZBPP_DIRECTORY")
    if not directory_value:
        print("[ERROR] NZBGet did not provide a download directory", file=sys.stderr)
        return FAILURE
    try:
        option = os.environ.get("NZBPO_VERIFYAUDIO", "no").casefold()
        if option not in {"yes", "no"}:
            raise ValueError("VerifyAudio must be yes or no")
        strict = os.environ.get("NZBPO_REQUIRECOMPLETENESS", "no").casefold()
        if strict not in {"yes", "no"}:
            raise ValueError("RequireCompleteness must be yes or no")
        process_release(Path(directory_value), verify_audio=option == "yes", require_completeness=strict == "yes")
    except (OSError, tarfile.TarError, zipfile.BadZipFile, ValueError, RuntimeError,
            NotImplementedError, EOFError) as error:
        print(f"[ERROR] Music post-processing failed: {error}", file=sys.stderr)
        return FAILURE
    return SUCCESS


if __name__ == "__main__":
    raise SystemExit(cli())
