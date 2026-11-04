#!/usr/bin/env python3
"""Safely unpack music archives that NZBGet's built-in unpacker missed."""

from __future__ import annotations

import errno
import argparse
import datetime
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
from typing import BinaryIO

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
    r"^(?:cdm|cd|disc|disk)[ _.-]*\d+(?:[ _.-]+.*|[\[(].*)?$", re.IGNORECASE
)
UNWANTED_SUFFIXES = {
    ".accurip",
    ".htm",
    ".html",
    ".jpg",
    ".jpeg",
    ".log",
    ".lrc",
    ".m3u",
    ".m3u8",
    ".ffp",
    ".md5",
    ".nfo",
    ".nzb",
    ".pdf",
    ".pls",
    ".png",
    ".sfv",
    ".srr",
    ".toc",
    ".tif",
    ".tiff",
    ".txt",
    ".url",
    ".website",
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
    ".aac", ".aif", ".aiff", ".alac", ".ape", ".avi", ".flac", ".m4a",
    ".m4v", ".mka", ".mkv", ".mov", ".mp3", ".mp4", ".ogg", ".opus",
    ".wav", ".webm", ".wma", ".wmv",
}
IMAGE_SUFFIXES = {".jpg", ".png", ".tif"}
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


def flac_stream_offset(stream: BinaryIO) -> int | None:
    """Locate native FLAC or a bounded ID3v2-prefixed FLAC without changing bytes."""
    stream.seek(0)
    header = stream.read(10)
    if header.startswith(b"fLaC"):
        return 0
    if len(header) != 10 or header[:3] != b"ID3" or header[3] not in (2, 3, 4) or header[4] == 255:
        return None
    allowed_flags = {2: 0xc0, 3: 0xe0, 4: 0xf0}[header[3]]
    if header[5] & ~allowed_flags or any(value & 128 for value in header[6:10]):
        return None
    size = sum(value << shift for value, shift in zip(header[6:10], (21, 14, 7, 0)))
    if size > 16 * 1024**2:
        return None
    offset = 10 + size
    if header[3] == 4 and header[5] & 16:
        stream.seek(offset)
        if stream.read(10) != b"3DI" + header[3:]:
            return None
        offset += 10
    stream.seek(offset)
    prefix = stream.read(42)
    if len(prefix) != 42 or prefix[:4] != b"fLaC" or prefix[4] & 127 or prefix[5:8] != b"\x00\x00\x22":
        return None
    info = prefix[8:]
    minimum, maximum = int.from_bytes(info[:2], "big"), int.from_bytes(info[2:4], "big")
    audio = int.from_bytes(info[10:18], "big")
    if not (16 <= minimum <= maximum and audio >> 44 and 4 <= ((audio >> 36) & 31) + 1 <= 32):
        return None
    return offset


def detected_suffix(path: Path) -> str | None:
    with path.open("rb") as stream:
        header = stream.read(4096)
        if header.startswith(b"ID3") and flac_stream_offset(stream) is not None:
            return ".flac"
    if header[:4] in (b"II\x2a\x00", b"MM\x00\x2a") and is_tiff_image(path):
        return ".tif"
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


def is_tiff_image(path: Path) -> bool:
    """Recognise single-IFD classic TIFF rasters with in-bounds strip/tile payloads."""
    size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(8)
        if len(header) != 8 or header[:4] not in (b'II\x2a\x00', b'MM\x00\x2a'):
            return False
        order = 'little' if header[:2] == b'II' else 'big'
        offset = int.from_bytes(header[4:], order)
        if not 8 <= offset <= size - 6:
            return False
        stream.seek(offset)
        count = int.from_bytes(stream.read(2), order)
        if not 1 <= count <= 4096 or offset + 6 + count * 12 > size:
            return False
        entries = stream.read(count * 12)
        if stream.read(4) != bytes(4):
            return False
        fields = {}
        for index in range(count):
            entry = entries[index * 12:(index + 1) * 12]
            tag = int.from_bytes(entry[:2], order)
            if tag not in {256, 257, 273, 279, 324, 325}:
                continue
            kind = int.from_bytes(entry[2:4], order)
            length = int.from_bytes(entry[4:8], order)
            if tag in fields or kind not in (3, 4) or not 1 <= length <= 4096:
                return False
            width = 2 if kind == 3 else 4
            raw = entry[8:12]
            if width * length > 4:
                address = int.from_bytes(raw, order)
                if not 8 <= address <= size - width * length:
                    return False
                stream.seek(address)
                raw = stream.read(width * length)
            fields[tag] = [int.from_bytes(raw[i:i + width], order) for i in range(0, width * length, width)]
        if any(len(fields.get(tag, [])) != 1 or fields[tag][0] == 0 for tag in (256, 257)):
            return False
        offsets, lengths = (fields.get(273), fields.get(279)) if 273 in fields else (fields.get(324), fields.get(325))
        return bool(offsets and lengths and len(offsets) == len(lengths)
                    and all(length > 0 and 8 <= address <= size - length for address, length in zip(offsets, lengths)))


def is_windows_thumbnail_cache(path: Path) -> bool:
    """Recognise bounded v3 Thumbs.db files containing only hashed JPEG thumbnails."""
    if path.name.casefold() != 'thumbs.db' or not 1536 <= path.stat().st_size <= 8 * 1024**2:
        return False
    with path.open('rb') as stream:
        raw = stream.read(8 * 1024**2 + 1)
    if (len(raw) > 8 * 1024**2 or len(raw) % 512
            or raw[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
            or raw[8:24] != bytes(16) or raw[26:34] != b'\x03\x00\xfe\xff\x09\x00\x06\x00'
            or raw[34:44] != bytes(10) or int.from_bytes(raw[56:60], 'little') != 4096
            or raw[68:76] != b'\xfe\xff\xff\xff\x00\x00\x00\x00'):
        return False
    def number(data: bytes) -> int:
        return int.from_bytes(data, 'little')
    sectors = len(raw) // 512 - 1
    fat_count = number(raw[44:48])
    fat_ids = [number(raw[i:i + 4]) for i in range(76, 512, 4)]
    if (not 1 <= fat_count <= 109 or len(set(fat_ids[:fat_count])) != fat_count
            or any(sid >= sectors for sid in fat_ids[:fat_count])
            or any(sid != 0xffffffff for sid in fat_ids[fat_count:])):
        return False
    fat_data = b''.join(raw[(sid + 1) * 512:(sid + 2) * 512] for sid in fat_ids[:fat_count])
    fat = [number(fat_data[i:i + 4]) for i in range(0, len(fat_data), 4)]
    if (len(fat) < sectors or any(fat[sid] != 0xfffffffd for sid in fat_ids[:fat_count])
            or any(value != 0xffffffff for value in fat[sectors:])):
        return False
    used = set(fat_ids[:fat_count])
    def chain(sid: int, limit: int) -> bytes:
        chunks = []
        while sid != 0xfffffffe:
            if sid >= sectors or sid in used or len(chunks) >= limit:
                raise ValueError('invalid thumbnail sector chain')
            used.add(sid)
            chunks.append(raw[(sid + 1) * 512:(sid + 2) * 512])
            sid = fat[sid]
        return b''.join(chunks)
    try:
        directory = chain(number(raw[48:52]), 256)
        mini_count = number(raw[64:68])
        mini = chain(number(raw[60:64]), sectors)
        if len(mini) != mini_count * 512 or any(value != 255 for value in mini):
            return False
        thumbnails = 0
        names = set()
        nodes = {}
        for index in range(0, len(directory), 128):
            entry = directory[index:index + 128]
            kind = entry[66]
            if kind == 0:
                if entry[68:80] != b'\xff' * 12:
                    return False
                continue
            length = number(entry[64:66])
            if not 2 <= length <= 64 or length % 2 or entry[length - 2:length] != b'\0\0':
                return False
            name = entry[:length - 2].decode('utf-16-le')
            left, right, child = (number(entry[p:p + 4]) for p in (68, 72, 76))
            nodes[index // 128] = (left, right, child)
            if entry[67] not in (0, 1):
                return False
            start, size = number(entry[116:120]), number(entry[120:128])
            if index == 0:
                if (kind != 5 or name != 'Root Entry' or size or start != 0xfffffffe
                        or left != 0xffffffff or right != 0xffffffff):
                    return False
                continue
            if (kind != 2 or child != 0xffffffff or not re.fullmatch(r'256_[0-9a-f]{1,16}', name)
                    or name in names or not 4096 <= size <= len(raw)):
                return False
            names.add(name)
            payload = chain(start, (size + 511) // 512)
            if len(payload) != (size + 511) // 512 * 512:
                return False
            payload = payload[:size]
            if (payload[:8] != b'\x18\x00\x00\x00\x03\x00\x00\x00'
                    or number(payload[8:12]) != size - 24 or payload[24:27] != b'\xff\xd8\xff'
                    or payload[-2:] != b'\xff\xd9'):
                return False
            thumbnails += 1
        if 0 not in nodes:
            return False
        visited = {0}
        pending = [nodes[0][2]]
        while pending:
            sid = pending.pop()
            if sid == 0xffffffff:
                continue
            if sid not in nodes or sid in visited:
                return False
            visited.add(sid)
            pending.extend(nodes[sid][:2])
        if visited != set(nodes):
            return False
        return bool(directory and directory[66] == 5 and thumbnails
                    and all(sid in used or fat[sid] == 0xffffffff for sid in range(sectors)))
    except (ValueError, UnicodeDecodeError):
        return False


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


def scene_nfo_controls(path: Path) -> str:
    """Allow only observed control-byte display forms in bounded scene NFOs."""
    if path.suffix.casefold() != ".nfo":
        return ""
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536 or not any(char in raw for char in (7, 8, 14, 16, 20, 22)):
        return ""
    text = raw.decode("cp437")
    fields = set()
    frame_chars = " \t\u00a0\u25a0" + "".join(chr(code) for code in range(0x2500, 0x25a0))

    def unpad(match: re.Match[str]) -> str:
        if match[3].strip(frame_chars):
            fields.add(match[2].strip().casefold())
        return match[1] + match[2] + ":" + match[3]

    frame = "\u2500-\u259f\u25a0 \t\u00a0"
    unpadded = re.sub(r"(?m)^([" + frame + r"]*)([A-Za-z][A-Za-z. ]{0,23})\x07+:([^\r\n]*)", unpad, text)
    allowed = "\x07" if "\x07" not in unpadded and {"artist", "title", "tracks"} <= fields else ""
    headers = {match[1].casefold() for line in unpadded.splitlines()
               if (match := re.fullmatch(r"(Artist|Title|Tracks)[ .]*:[ \t\u00a0]*\S.*",
                                        line.strip(frame_chars), re.IGNORECASE))}
    art_lines = [line for line in text.splitlines() if "\x16" in line]
    if ({"artist", "title", "tracks"} <= headers and art_lines
            and all(re.fullmatch(r"[" + frame + r"\x16]+", line) for line in art_lines)):
        allowed += "\x16"
    display = text.replace("\x08", "")
    display_fields = {match[1].casefold() for line in display.splitlines()
                      if (match := re.fullmatch(r"(Artist|Album|Title|Genre|Tracks)(?:[ .]*[:|][ \t]*|\.{2,}[ \t]+)(\S.*)",
                                                line.strip(frame_chars), re.IGNORECASE))
                      and match[2].strip(frame_chars + " .:|")}
    identity = "artist" in display_fields and bool({"album", "title"} & display_fields)
    structured = identity and bool({"tracks", "genre"} & display_fields)
    if structured:
        for control in ("\x10", "\x14"):
            rows = [line for line in text.splitlines() if control in line]
            if rows and all(not line.strip(frame_chars + control) for line in rows):
                allowed += control
        backspaces = list(re.finditer(r"\x08+", text))
        credit = "\x0e\x07nfoLayoutBy"
        def beside_border(match: re.Match[str]) -> bool:
            left = text[:match.start()].rstrip(" \t\u00a0")
            right = text[match.end():].lstrip(" \t\u00a0")
            return bool(left) and left[-1] in frame_chars.strip() or bool(right) and right[0] in frame_chars.strip()
        if (backspaces and text.count(credit) == text.count("\x0e") == text.count("\x07") == 1
                and {"artist", "title", "tracks"} <= display_fields
                and all(beside_border(match) for match in backspaces)):
            allowed += "\x08\x0e\x07"
    return allowed


def is_text_sidecar(path: Path, *, suffix: str | None = None) -> bool:
    """Check the entire file before treating an explicit sidecar suffix as text."""
    effective_suffix = (suffix or path.suffix).casefold()
    with path.open("rb") as stream:
        bom = stream.read(2)
    encoding = "utf-16" if bom in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        with path.open(encoding=encoding) as stream:
            while chunk := stream.read(65536):
                if any(not char.isprintable() and char not in "\t\r\n\f"
                       and not (char == "\u00a0" and effective_suffix == ".nfo")
                       and not (char == "\u200e" and effective_suffix == ".txt") for char in chunk):
                    return False
    except UnicodeDecodeError:
        if encoding == "utf-16" or effective_suffix not in {".nfo", ".txt", ".log", ".cue"}:
            return False
        if effective_suffix == ".log":
            with path.open("rb") as stream:
                if not stream.read(128).startswith((b"Exact Audio Copy ", b"AUDIOCHECKER v")):
                    return False
        # Scene NFOs mix drawing glyphs with accented release text. Keep the
        # drawing alphabet separate from Windows text. Only bounded, framed NFO
        # header padding may contain BEL and art-only rows may contain SYN;
        # other binary controls remain rejected.
        controls = scene_nfo_controls(path)
        drawing = False
        valid_cp437 = True
        drawing_run = False
        previous_drawing = False
        with path.open("rb") as stream:
            while chunk := stream.read(65536):
                for char in chunk.decode("cp437"):
                    glyph = "\u2500" <= char <= "\u259f" or char == "\u25a0"
                    drawing |= glyph
                    drawing_run |= glyph and previous_drawing
                    previous_drawing = glyph
                    if not (char.isascii() and (char.isprintable() or char in "\t\r\n\f")
                            or glyph or char.isalpha() or char in "·∙¼«»⌐÷≤\u00a0"
                            or char in controls):
                        valid_cp437 = False
        if drawing and valid_cp437 and (not controls or drawing_run) and effective_suffix == ".nfo":
            return True
        # A lone accented Windows character can resemble a drawing glyph.
        # Keep malformed box art protected rather than retrying it as Windows text.
        if drawing_run:
            return False
        try:
            with path.open(encoding="cp1252") as stream:
                while chunk := stream.read(65536):
                    if any(not char.isprintable() and char not in "\t\r\n\f" for char in chunk):
                        return False
        except UnicodeDecodeError:
            return False
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


def is_synology_metadata(path: Path) -> bool:
    """Recognise a bounded AppleDouble v2 header with no data or resource fork."""
    if not path.name.casefold().endswith("@synoeastream"):
        return False
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if (not 82 <= len(raw) <= 65536
            or raw[:8] != b"\x00\x05\x16\x07\x00\x02\x00\x00"
            or raw[24:26] != b"\x00\x02"):
        return False
    entries = {}
    for offset in (26, 38):
        kind, start, size = (int.from_bytes(raw[p:p + 4], "big") for p in range(offset, offset + 12, 4))
        if kind in entries:
            return False
        entries[kind] = (start, size)
    # Exactly FinderInfo/attributes from the end of the table to EOF, followed
    # by an empty resource fork. Unknown entries, payload forks and gaps stay.
    if entries != {9: (50, len(raw) - 50), 2: (len(raw), 0)}:
        return False
    if len(raw) == 82:
        return True
    # XNU aligns its ATTR header after two padding bytes. Accept the observed
    # single provenance attribute, with complete record/data coverage only.
    if len(raw) < 153 or raw[82:84] != bytes(2) or raw[84:88] != b"ATTR":
        return False
    total, start, size = (int.from_bytes(raw[p:p + 4], "big") for p in (92, 96, 100))
    if (total != len(raw) or not 1 <= size <= 64 or start + size != len(raw)
            or raw[104:118] != bytes(14) or raw[118:120] != b"\x00\x01"):
        return False
    offset = int.from_bytes(raw[120:124], "big")
    length = int.from_bytes(raw[124:128], "big")
    name_length = raw[130]
    name_end = 131 + name_length
    aligned_end = (name_end + 3) & ~3
    return (raw[128:130] == bytes(2) and raw[131:name_end] == b"com.apple.provenance\x00"
            and start == aligned_end and offset == start and length == size
            and raw[name_end:start] == bytes(start - name_end))


def is_album_info_sidecar(path: Path) -> bool:
    """Recognise bounded posting metadata, never arbitrary extensionless text."""
    if not re.fullmatch(r"(?:(?:[a-z0-9]{1,32}_)?album_info|about_album)", path.name, re.IGNORECASE):
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


def is_obfuscated_posting_sidecar(path: Path) -> bool:
    """Require both a posting filename and structured release metadata/checksums."""
    legacy = re.fullmatch(
        r"\[\d{1,8}\]-\[FULL\]-\[\#a\.b\.flac@EFNet\]-\[ [^\[\]\r\n]{1,256} \]-"
        r"\[\d{1,5}_\d{1,5}\] - _[^/\\\r\n]{1,256}\.(?:nfo|sfv)_ yEnc \(\d{1,5}_\d{1,5}\)(?: \(\d{1,5}_\d{1,5}\))?",
        path.name, re.IGNORECASE)
    modern = re.search(r"\.[0-9a-f]{8}(?:___|-_-_--_)[0-9a-f]{12}_ \[(?:newzNZB|WtFnZb)\] \[\d+_\d+\] - yEnc +\d+ \(\d+_\d+\)$",
                       path.name, re.IGNORECASE)
    if not legacy and not modern:
        return False
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if not raw or len(raw) > 65536:
        return False
    def structured_nfo(text: str) -> bool:
        frame = " \t|" + "".join(chr(code) for code in range(0x2500, 0x25a0)) + "\u25a0"
        lines = [line.strip(frame) for line in text.splitlines()]
        fields = {match[1].casefold().removesuffix(" name") for line in lines
                  if (match := re.fullmatch(r"(Artist(?: Name)?|Album(?: Name)?|Title|Genre|Source|Encoder|Quality|Tracks|Label)"
                                            r"(?:[ .]*:[ \t]*|\.{2,}[ \t]+|_+>[ \t]*)\S[^\r\n]*",
                                            line, re.IGNORECASE))}
        return (({"artist", "album"} <= fields or {"artist", "title"} <= fields)
                and len(fields - {"artist", "album", "title"}) >= 2
                and any(re.fullmatch(r"\d{1,3}[ .)-]+\S[^\r\n]*", line) for line in lines))

    def tool_log(text: str) -> bool:
        if modern is None:
            return False
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return False
        if (re.fullmatch(r"foobar2000 .+ / Dynamic Range Meter .+", lines[0])
                and any(re.fullmatch(r"log date: [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:]{8}", line) for line in lines)
                and any(re.fullmatch(r"Analyzed: .+", line) for line in lines)
                and "DR         Peak         RMS     Duration Track" in lines
                and any(re.fullmatch(r"DR[0-9]+ +[-+0-9.]+ dB +[-+0-9.]+ dB +[0-9]+:[0-9]{2} +[0-9]+-.+", line) for line in lines)
                and any(re.fullmatch(r"Number of tracks: +[1-9][0-9]*", line) for line in lines)
                and any(re.fullmatch(r"Official DR value: DR[0-9]+", line) for line in lines)):
            return True
        if (re.fullmatch(r"AUDIOCHECKER v[0-9].+", lines[0])
                and "-=== DO NOT EDIT THIS FILE! ===-" in lines
                and any(re.fullmatch(r"Summary [0-9]+[,.][0-9]+% CDDA", line) for line in lines)):
            rows = [line for line in lines if re.match(r"[0-9]{3} -=- ", line)]
            return bool(rows) and all((match := re.fullmatch(r"[0-9]{3} -=- (.+) -=- (?:CDDA|MPEG) \([0-9]{1,3}%\)", line))
                                      and playlist_reference(match[1]) is not None for line in rows)
        if ("PERFORMER: auCDtect Task Manager," in text and "ANALYZER: auCDtect:" in text
                and "DON'T MODIFY THIS FILE" in lines):
            records = re.findall(r"(?m)^FILE: (.+)\r?\n +Size: [0-9]+ Hash: [0-9A-Fa-f]{32} Accuracy: -m[0-9]+\r?\n"
                                 r" +Conclusion: (?:CDDA|MPEG) [0-9]{1,3}%\r?\n +Signature: [0-9A-Fa-f]{40}\r?$", text)
            return bool(records) and len(records) == sum(line.startswith("FILE:") for line in lines) and all(playlist_reference(name) is not None for name in records)
        return re.fullmatch(r"Torrent downloaded from Demonoid - https://(?:www\.)?demonoid\.is", text.strip()) is not None

    def posting_info(text: str) -> bool:
        if modern is None:
            return False
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        releases = [match[1] for line in lines
                    if (match := re.fullmatch(r"RELEASE[ \t]*:[ \t]*(.*)", line, re.IGNORECASE))]
        uploaded = [match[1] for line in lines
                    if (match := re.fullmatch(r"UPLOADED DATE[ \t]*:[ \t]*(.*)", line, re.IGNORECASE))]
        if len(releases) != 1 or len(uploaded) != 1 or not lines or lines[-1] != ".::newz[NZB]::.":
            return False
        def identity(value: str) -> str:
            value = re.sub(r"[-_. ]xpost$", "", value.strip(), flags=re.IGNORECASE)
            return "".join(char for char in value.casefold() if char.isalnum())
        expected = identity(path.name[:modern.start()])
        if not expected or identity(releases[0]) != expected:
            return False
        match = re.fullmatch(r"([0-9]{4})-([A-Za-z]+)-([0-9]{2})", uploaded[0].strip())
        months = ("january", "february", "march", "april", "may", "june", "july", "august",
                  "september", "october", "november", "december")
        if not match or match[2].casefold() not in months:
            return False
        try:
            datetime.date(int(match[1]), months.index(match[2].casefold()) + 1, int(match[3]))
        except ValueError:
            return False
        return True

    try:
        text = raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")
    except UnicodeDecodeError:
        text = None
    unicode_text = text is not None
    if text is None:
        try:
            text = raw.decode("cp1252")
        except UnicodeDecodeError:
            pass
    if text is not None and all(char.isprintable() or char in "\t\r\n\f" for char in text):
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith(";")]
        if lines and all((match := re.fullmatch(r"(.+) +[0-9a-fA-F]{8}", line))
                         and playlist_reference(match[1]) is not None for line in lines):
            return True
        if structured_nfo(text) or posting_info(text) or tool_log(text):
            return True
    if unicode_text:
        return False
    text = raw.decode("cp437")
    def drawing(char: str) -> bool:
        return "\u2500" <= char <= "\u259f" or char == "\u25a0"
    return (any(drawing(left) and drawing(right) for left, right in zip(text, text[1:]))
            and all((" " <= char <= "~") or char in "\t\r\n\f·∙¼«»⌐" or char.isalpha() or drawing(char) for char in text)
            and (structured_nfo(text) or posting_info(text) or tool_log(text)))


def is_windows_folder_metadata(path: Path) -> bool:
    """Recognise bounded Windows music-folder metadata, never arbitrary INI files."""
    if path.name.casefold() != "desktop.ini":
        return False
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if not raw or len(raw) > 65536:
        return False
    try:
        text = raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")
    except UnicodeDecodeError:
        return False
    # Explorer may append one string terminator. Embedded or repeated NULs fail.
    text = text.removesuffix("\x00")
    if any(not (char.isprintable() or char in "\t\r\n") for char in text):
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0].casefold() != "[.shellclassinfo]":
        return False
    fields = {}
    for line in lines[1:]:
        key, separator, value = line.partition("=")
        key, value = key.strip().casefold(), value.strip()
        if not separator or key not in {"foldertype", "musicbuyurl"} or key in fields or not value:
            return False
        fields[key] = value
    return (fields.get("foldertype", "").casefold() in {"musicalbum", "musicartist"}
            and bool(fields.get("musicbuyurl")))



def wrapped_posting_name(path: Path) -> tuple[str, bool] | None:
    match = re.fullmatch(
        r'(?:\[N3wZ\] _[A-Za-z0-9]+___)?\[PRiVATE\]-\[(?:WtFnZb|EnCrYpTnZb)\]-\[([^/\\\r\n]{1,256})\]'
        r'-\[[0-9]+_[0-9]+\] - __ yEnc +[0-9]+ \([0-9]+_[0-9]+\)(\.flac)?', path.name, re.IGNORECASE)
    if not match or match[1].startswith('.') or not all(c.isprintable() for c in match[1]):
        return None
    return match[1], bool(match[2])


def is_wrapped_text_sidecar(path: Path) -> bool:
    posting = wrapped_posting_name(path)
    if posting is None or posting[1] or path.stat().st_size > 65536 or detected_suffix(path) is not None:
        return False
    suffix = PurePosixPath(posting[0]).suffix.casefold()
    return suffix in {'.accurip', '.log', '.txt'} and is_text_sidecar(path, suffix=suffix)


def wrapped_posting_target(path: Path) -> Path | None:
    """Restore only the observed disc-scoped WtFnZb wrapper and verified content."""
    match = re.fullmatch(
        r"(?:\[N3wZ\] _[A-Za-z0-9]+___)?\[PRiVATE\]-\[WtFnZb\]-\[_[^/\\\r\n]{1,256}_CD([1-9][0-9]?)_"
        r"([^/\\\r\n]{1,180}\.(flac|cue|log|txt))\]-\[[0-9]+_[0-9]+\] - __ yEnc +[0-9]+ \([0-9]+_[0-9]+\)(\.flac)?",
        path.name, re.IGNORECASE)
    if match:
        disc, name, suffix, appended = match[1], match[2], "." + match[3].casefold(), bool(match[4])
    else:
        posting = wrapped_posting_name(path)
        image = re.fullmatch(r"(.+\.\(CD([1-9][0-9]?)\))\.(flac|cue|log|txt|accurip)",
                             posting[0], re.IGNORECASE) if posting else None
        if image is None:
            return None
        disc, name, suffix, appended = image[2], posting[0], "." + image[3].casefold(), posting[1]
    if len(re.findall(r"(?=_CD[1-9][0-9]?_)|\(CD[1-9][0-9]?\)", path.name, re.IGNORECASE)) != 1:
        return None
    if (name.startswith(".") or not all(char.isprintable() for char in name)
            or PureWindowsPath(name).drive or any(char in name for char in ':"<>|?*')):
        return None
    detected = detected_suffix(path)
    if suffix == ".flac":
        if detected != ".flac":
            return None
    else:
        if appended or detected is not None or path.stat().st_size > 65536 or not is_text_sidecar(path, suffix=suffix):
            return None
        if suffix == ".cue":
            raw = path.read_bytes()
            encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
            try:
                text = raw.decode(encoding)
            except UnicodeDecodeError:
                text = raw.decode("cp1252")
            if not any(CUE_FILE.fullmatch(line) for line in text.splitlines()):
                return None
    return path.parent / ("CD" + disc) / name


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
        if suffix in KNOWN_MEDIA_SUFFIXES | {".cue"} or detected_suffix(path) is not None:
            return False
        if playlist_entries(path) is not None:
            return False
        wrapped = wrapped_posting_target(path)
        if wrapped is not None and wrapped.suffix.casefold() in {".log", ".txt"}:
            return True
        return (is_wrapped_text_sidecar(path) or is_windows_thumbnail_cache(path) or is_windows_folder_metadata(path) or is_synology_metadata(path)
                or is_srr_sidecar(path) or is_obfuscated_posting_sidecar(path))
    # Playlist disposal needs the whole release, including files from later
    # archives. Never discard a duplicate before completeness is established.
    if path.suffix.casefold() in {".m3u", ".m3u8"} or playlist_entries(path) is not None:
        return False
    suffix = detected_suffix(path)
    if suffix is None and path.suffix.casefold() == ".srr" and is_srr_sidecar(path):
        return True
    return suffix in CLEANUP_SIGNATURE_SUFFIXES or (suffix is None and is_text_sidecar(path))


def extension_target(path: Path) -> Path:
    wrapped = wrapped_posting_target(path)
    if wrapped is not None:
        return wrapped
    if path.suffix.casefold() == ".mp3" and detected_suffix(path) == ".flac":
        return path.with_suffix(".flac")
    if path.suffix.casefold() in KNOWN_MEDIA_SUFFIXES:
        return path
    suffix = detected_suffix(path)
    if not suffix or (suffix in CLEANUP_SIGNATURE_SUFFIXES and path.suffix.casefold() in UNWANTED_SUFFIXES):
        return path
    return path.with_name(path.name + suffix)


def cue_flac_reference(name: str, cue: Path, text: str, files: list[Path]) -> Path | None:
    """Resolve local WAV/FLAC export names with strong, unambiguous FLAC evidence."""
    def identity(value: str) -> str:
        return "".join(re.findall(r"[^\W_]+", value.casefold()))

    entry = PurePosixPath(name.replace("\\", "/"))
    if len(entry.parts) != 1:
        return None
    parent = extension_target(cue).parent
    candidates = [p for p in files if extension_target(p).parent == parent and detected_suffix(p) == ".flac"]
    if wrapped_posting_target(cue) is not None:
        physical = [p for p in candidates if p.parent == cue.parent and p.name.casefold() == entry.name.casefold()]
        if physical:
            return physical[0] if len(physical) == 1 else None
    if entry.suffix.casefold() not in {".wav", ".flac"}:
        return None
    expected = entry.with_suffix(".flac").name.casefold()
    aliases = [p for p in candidates if expected in {p.name.casefold(), extension_target(p).name.casefold()}]
    if not aliases and " " in expected:
        dotted = expected.replace(" ", ".")
        aliases = [p for p in candidates if dotted in {p.name.casefold(), extension_target(p).name.casefold()}]
    if not aliases:
        cue_name = extension_target(cue).stem
        cue_disc = re.search(r"(?:^|[ ._-])(?:cd|disc|disk)[ ._-]*([1-9])$", cue_name, re.IGNORECASE)
        numbered = re.fullmatch(r"([0-9]{1,2})[ ._-]+(.+)", entry.stem)
        if cue_disc and numbered:
            header = re.split(r"(?im)^[ \t]*TRACK[ \t]", "\n".join(text.splitlines()), maxsplit=1)[0]
            identities = {}
            for field in ("PERFORMER", "TITLE"):
                lines = re.findall(r"^[\ufeff \t]*" + field + r"[ \t].*$", header, re.MULTILINE | re.IGNORECASE)
                values = re.findall(r'^[\ufeff \t]*' + field + r'[ \t]+"([^"\r\n]+)"[ \t]*\r?$', header, re.MULTILINE | re.IGNORECASE)
                if len(lines) != len(values) or len(values) > 1 or any(not identity(v) for v in values):
                    return None
                identities[field] = identity(values[0]) if values else ""
            for path in candidates:
                posting = re.fullmatch(r"([1-9])([0-9]{2})[ ._-]+(.+)", extension_target(path).stem)
                if not posting or posting[1] != cue_disc[1] or int(posting[2]) != int(numbered[1]):
                    continue
                tags, _ = flac_album_metadata(path)
                track, _ = metadata_position(tags, ("TRACKNUMBER", "TRACK"), ("TRACKTOTAL", "TOTALTRACKS"), "track")
                disc, _ = metadata_position(tags, ("DISCNUMBER", "DISC"), ("DISCTOTAL", "TOTALDISCS"), "disc")
                if (track != str(int(numbered[1])) or disc and disc != cue_disc[1]
                        or identity(tags.get("ALBUM", "")) != identity(cue_name)
                        or not tags.get("ARTIST", "").strip() or not tags.get("TITLE", "").strip()
                        or identities["PERFORMER"] and identities["PERFORMER"] != identity(tags["ARTIST"])
                        or identities["TITLE"] and identities["TITLE"] != identity(tags.get("ALBUM", ""))):
                    continue
                actual = identity(posting[3])
                requested = identity(numbered[2])
                if (actual == requested and identity(posting[3]).startswith(identity(tags["ARTIST"] + tags["TITLE"]))):
                    aliases.append(path)
    if aliases:
        return aliases[0] if len(aliases) == 1 else None

    header = re.split(r"(?im)^[ \t]*TRACK[ \t]", "\n".join(text.splitlines()), maxsplit=1)[0]
    performers = {identity(value) for value in re.findall(r'^[\ufeff \t]*PERFORMER[ \t]+"([^"\r\n]+)"[ \t]*\r?$', header, re.MULTILINE | re.IGNORECASE)}
    numbered = re.fullmatch(r"([0-9]{1,5})[ _.-]+(.+)", entry.stem)
    if not numbered or len(performers) != 1 or not next(iter(performers)):
        return None
    performer = next(iter(performers))
    def album_identity(value: str) -> str:
        return identity(re.sub(r"\s*\(single\)\s*$", "", value, flags=re.IGNORECASE))
    album_titles = re.findall(r'^[\ufeff \t]*TITLE[ \t]+"([^"\r\n]+)"[ \t]*$', header, re.MULTILINE | re.IGNORECASE)
    title_lines = re.findall(r"^[\ufeff \t]*TITLE[ \t]", header, re.MULTILINE | re.IGNORECASE)
    expected_albums = {album_identity(value) for value in album_titles}
    if len(album_titles) != len(title_lines) or len(expected_albums) > 1 or "" in expected_albums:
        return None
    cue_disc = re.search(r"(?:^|[ ._-])(?:cd|disc|disk)[ ._-]*([1-9][0-9]?)$",
                         extension_target(cue).stem, re.IGNORECASE)
    candidate_discs = set()
    if cue_disc and len(album_titles) == 1:
        candidate_discs = {metadata_position(flac_album_metadata(path)[0], ("DISCNUMBER", "DISC"),
                                             ("DISCTOTAL", "TOTALDISCS"), "disc")[0] for path in candidates}
    if cue_disc and len(album_titles) == 1 and len(candidate_discs) > 1:
        performer_lines = re.findall(r"^[\ufeff \t]*PERFORMER[ \t]", header, re.MULTILINE | re.IGNORECASE)
        if len(performer_lines) != 1:
            return None
        positions = {}
        totals = set()
        for path in candidates:
            tags, embedded = flac_album_metadata(path)
            disc, total = metadata_position(tags, ("DISCNUMBER", "DISC"), ("DISCTOTAL", "TOTALDISCS"), "disc")
            if (embedded or tags.get("CUESHEET") or not re.fullmatch(r"[1-9][0-9]?", disc)
                    or not re.fullmatch(r"[1-9][0-9]?", total) or int(disc) > int(total)):
                return None
            positions[path] = int(disc)
            totals.add(int(total))
        if len(totals) != 1 or set(positions.values()) != set(range(1, next(iter(totals)) + 1)):
            return None
        candidates = [path for path in candidates if positions[path] == int(cue_disc[1])]
    albums = set()
    matches = []
    for path in candidates:
        tags, embedded = flac_album_metadata(path)
        if embedded or tags.get("CUESHEET") or any(not tags.get(key, "").strip() for key in ("ALBUM", "ARTIST", "TITLE")):
            return None
        track, _ = metadata_position(tags, ("TRACKNUMBER", "TRACK"), ("TRACKTOTAL", "TOTALTRACKS"), "track")
        disc, _ = metadata_position(tags, ("DISCNUMBER", "DISC"), ("DISCTOTAL", "TOTALDISCS"), "disc")
        if not re.fullmatch(r"[0-9]{1,5}", track):
            return None
        if expected_albums and album_identity(tags["ALBUM"]) not in expected_albums:
            return None
        albums.add((tags["ALBUM"].strip().casefold(),
                    (tags.get("ALBUMARTIST") or tags.get("ALBUM ARTIST", "")).strip().casefold(), disc))
        album_performers = {identity(tags[key]) for key in ("ALBUMARTIST", "ALBUM ARTIST")
                            if tags.get(key, "").strip()}
        performer_matches = (identity(tags["ARTIST"]) == performer
                             or bool(expected_albums) and album_performers == {performer})
        if (int(track) == int(numbered[1]) and performer_matches
                and identity(numbered[2]) in {identity(tags["TITLE"]), identity(tags["ARTIST"] + " " + tags["TITLE"]),
                                             performer + identity(tags["TITLE"])}):
            matches.append(path)
    return matches[0] if len(albums) == 1 and len(matches) == 1 else None


def read_cues(files: list[Path], root: Path) -> dict[Path, tuple[str, str, dict[str, Path]]]:
    cues = {}
    repaired = set()
    by_relative = {path.relative_to(root).as_posix(): path for path in files}
    for cue in files:
        if extension_target(cue).suffix.casefold() != ".cue":
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
        new_references = False
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
            target = (extension_target(cue).parent / portable).resolve()
            target.relative_to(root)
            relative = target.relative_to(root).as_posix()
            if relative not in by_relative:
                candidates = [value for key, value in by_relative.items() if key.casefold() == relative.casefold()]
                if len(candidates) == 1:
                    target = candidates[0]
                else:
                    alternate = (cue_flac_reference(portable, cue, text, files)
                                 if not candidates and match["tail"].strip().casefold() == "wave" else None)
                    if alternate is None:
                        raise ValueError(f"missing or ambiguous FILE reference in cue sheet: {cue.name}: {name}")
                    target = alternate
                    repaired.add(target)
                    new_references = True
            if extension_target(target).suffix.casefold() == ".cue" or is_archive(target):
                raise ValueError(f"invalid FILE reference in cue sheet: {cue.name}")
            references[name] = target
        if new_references and len(set(references.values())) != len(references):
            raise ValueError(f"ambiguous repaired FILE references in cue sheet: {cue.name}")
        cues[cue] = (encoding, text, references)
    images = cue_image_targets(cues)
    affected = {p.parent for p in repaired - images}
    if affected:
        # A repaired track-file cue must not turn a missing album track into
        # apparent image evidence. Other folders keep their original protection.
        check_album_tracks(files, {p for p in files if p.parent not in affected} | images, root)
    return cues


def cue_image_targets(cues: dict[Path, tuple[str, str, dict[str, Path]]]) -> set[Path]:
    images = set()
    for _, text, references in cues.values():
        lines = text.splitlines()
        files = sum(CUE_FILE.fullmatch(line) is not None for line in lines)
        tracks = sum(re.fullmatch(r"[ \t]*TRACK[ \t]+[0-9]+[ \t]+AUDIO[ \t]*", line, re.IGNORECASE) is not None for line in lines)
        if files == 1 and tracks > 1:
            images.update(references.values())
    return images


def flac_album_metadata(path: Path) -> tuple[dict[str, str], bool]:
    """Read bounded FLAC comments; skip artwork without loading it (RFC 9639)."""
    tags: dict[str, str] = {}
    embedded_cue = False
    with path.open("rb") as stream:
        offset = flac_stream_offset(stream)
        if offset is None:
            return tags, embedded_cue
        stream.seek(offset + 4)
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
    path = extension_target(path)
    parent = root
    for part in path.relative_to(root).parts[:-1]:
        parent = parent / part
        if DISC_DIRECTORY.fullmatch(part):
            return parent.parent
    return path.parent


def playlist_local_targets(entries: list[PurePosixPath], audio: list[Path], parent: Path) -> list[set[Path]]:
    available: dict[str, set[Path]] = {}
    for path in audio:
        for target in (path, extension_target(path)):
            if target.is_relative_to(parent):
                available.setdefault(target.relative_to(parent).as_posix().casefold(), set()).add(path)
    resolved = []
    for entry in entries:
        key = entry.as_posix().casefold()
        # NZBGet can replace each ASCII space with a dot. Resolve only
        # same-folder names, keeping existing exact references authoritative.
        if key not in available and len(entry.parts) == 1:
            key = key.replace(" ", ".")
        resolved.append(available.get(key, set()))
    return resolved


def playlist_disc_groups(files: list[Path], protected: set[Path], root: Path,
                         required_manifests: set[Path] | None = None,
                         proven_tracks: set[Path] | None = None) -> dict[Path, str]:
    """Partition numbered tracks using covering playlists or matching CD NFOs."""
    audio = [path for path in files if detected_suffix(path) in AUDIO_SUFFIXES
             or path.suffix.casefold() in AUDIO_SUFFIXES]
    cohorts: dict[tuple, list[tuple[Path, dict[str, str]]]] = {}
    for path in files:
        if detected_suffix(path) != ".flac":
            continue
        tags, embedded = flac_album_metadata(path)
        if embedded or tags.get("CUESHEET"):
            continue
        artists = [tags.get(key, "").strip().casefold() for key in ("ALBUMARTIST", "ALBUM ARTIST")
                   if tags.get(key, "").strip()]
        key = (path.parent, tags.get("ALBUM", "").strip().casefold(),
               artists[0] if artists else "")
        cohorts.setdefault(key, []).append((path, tags))
    inferred = {}
    playlists = [path for path in files if path.suffix.casefold() in {".m3u", ".m3u8"}]
    for records in cohorts.values():
        if any(path in protected or any(DISC_DIRECTORY.fullmatch(part) for part in path.parent.relative_to(root).parts)
               for path, _ in records):
            continue
        groups: dict[int, list[int]] = {}
        positions = {}
        performers = set()
        numbering = None
        for path, tags in records:
            artists = {tags.get(key, "").strip().casefold() for key in ("ALBUMARTIST", "ALBUM ARTIST")
                       if tags.get(key, "").strip()}
            if len(artists) > 1:
                break
            disc, total = metadata_position(tags, ("DISCNUMBER", "DISC"), ("DISCTOTAL", "TOTALDISCS"), "disc")
            track, _ = metadata_position(tags, ("TRACKNUMBER", "TRACK"), ("TRACKTOTAL", "TOTALTRACKS"), "track")
            match = re.fullmatch(r"([1-9])([0-9]{2})[ _.-]+.+", path.stem)
            scheme = "disc"
            if not match:
                match = re.fullmatch(r"([A-Za-z])([0-9]{1,2})[ _.-]+.+", path.stem)
                scheme = "side"
            if (disc or total or not match or not re.fullmatch(r"[0-9]{1,2}", track)
                    or numbering not in (None, scheme)
                    or int(track) != int(match[2]) or int(track) == 0
                    or any(not tags.get(key, "").strip() for key in ("ALBUM", "ARTIST", "TITLE"))):
                break
            performers.add(next(iter(artists)) if artists else tags["ARTIST"].strip().casefold())
            numbering = scheme
            number = int(match[1]) if scheme == "disc" else ord(match[1].upper()) - ord("A") + 1
            groups.setdefault(number, []).append(int(track))
            positions[path] = str(number)
        else:
            if (len(performers) != 1 or len(groups) < 2 or set(groups) != set(range(1, len(groups) + 1))
                    or any(sorted(tracks) != list(range(1, len(tracks) + 1)) for tracks in groups.values())):
                continue
            if numbering == "disc":
                titles = {(int(positions[path]), int(metadata_position(tags, ("TRACKNUMBER", "TRACK"),
                            ("TRACKTOTAL", "TOTALTRACKS"), "track")[0])): tags["TITLE"] for path, tags in records}
                parent = records[0][0].parent
                nfos = [path for path in files if path.parent == parent and path.suffix.casefold() == ".nfo"
                        and nfo_disc_manifest(path, next(iter(performers)), records[0][1]["ALBUM"], titles)]
                if nfos:
                    inferred.update(positions)
                    if required_manifests is not None:
                        required_manifests.add(nfos[0])
                    if proven_tracks is not None:
                        proven_tracks.update(positions)
                    continue
            for playlist in playlists:
                entries = playlist_entries(playlist)
                if not entries or len(entries) != len(records):
                    continue
                resolved = playlist_local_targets(entries, audio, playlist.parent)
                if (all(len(matches) == 1 for matches in resolved)
                        and {next(iter(matches)) for matches in resolved} == {path for path, _ in records}):
                    inferred.update(positions)
                    if required_manifests is not None:
                        required_manifests.add(playlist)
                    break
    return inferred


def pipe_nfo_disc_manifest(text: str, artist: str, album: str,
                           titles: dict[tuple[int, int], str]) -> bool:
    """Validate the observed pipe-header, CD n/total NFO tracklist."""
    text = "\n".join(text.splitlines())
    markers = list(re.finditer(r"(?im)^[ \t]*─+┤[ \t]*Tracks[ \t]*├─+[ \t]*$", text))
    if len(markers) != 1:
        return False
    def identity(value: str) -> str:
        return "".join(re.findall(r"[^\W_]+", value.casefold()))
    header = text[:markers[0].start()]
    artists = re.findall(r"(?im)^[ \t]*Artist[ \t]*\|[ \t]*(.+?)[ \t]*$", header)
    albums = re.findall(r"(?im)^[ \t]*Title[ \t]*\|[ \t]*(.+?)[ \t]*$", header)
    sources = re.findall(r"(?im)^[ \t]*Source[ \t]*\|[^\r\n]*", header)
    if (len(artists) != 1 or identity(artists[0]) != identity(artist)
            or len(albums) != 1 or identity(albums[0]) != identity(album) or len(sources) != 1
            or not re.fullmatch(r"[ \t]*Source[ \t]*\|[ \t]*CD(?:[ \t]{2,}Time[ \t]*\|[ \t]*[0-9]{1,3}:[0-5][0-9])?[ \t]*", sources[0], re.IGNORECASE)):
        return False
    expected_discs = {disc for disc, _ in titles}
    disc = None
    discs = set()
    found = {}
    for line in text[markers[0].end():].splitlines():
        line = line.strip()
        if match := re.fullmatch(r"CD ([1-9][0-9]?)/([1-9][0-9]?)", line, re.IGNORECASE):
            disc = int(match[1])
            if int(match[2]) != len(expected_discs) or disc in discs:
                return False
            discs.add(disc)
        elif match := re.fullmatch(r"([0-9]{1,3})\.[ \t]+(.+?)[ \t]{2,}[0-9]{1,3}:[0-5][0-9]", line):
            key = (disc, int(match[1]))
            if disc is None or key in found:
                return False
            found[key] = identity(match[2])
        elif re.match(r"[0-9]{1,3}[ .)-]", line):
            return False
    return discs == expected_discs and found == {key: identity(value) for key, value in titles.items()}


def nfo_disc_manifest(path: Path, artist: str, album: str,
                      titles: dict[tuple[int, int], str]) -> bool:
    """Require the observed explicit CD tracklist, with matching release identity."""
    if path.stat().st_size > 65536 or detected_suffix(path) is not None or not is_text_sidecar(path):
        return False
    raw = path.read_bytes()
    def identity(value: str) -> str:
        return "".join(re.findall(r"[^\W_]+", value.casefold()))
    for encoding in ("utf-8-sig", "utf-16", "cp437", "cp1252"):
        try:
            text = raw.decode(encoding)
        except UnicodeError:
            continue
        if pipe_nfo_disc_manifest(text, artist, album, titles):
            return True
        markers = list(re.finditer(r"(?im)^[ \t]*Tracklist[ .:]*[ \t]*$", text))
        if len(markers) != 1:
            continue
        header = text[:markers[0].start()]
        artists = re.findall(r"(?im)^[ \t]*Artist[ .]*:[ \t]*(.*?)(?=[ \t]{2,}(?:Title|Album)[ .]*:|[ \t]*$)", header)
        albums = re.findall(r"(?im)(?:^[ \t]*|[ \t]{2,})(?:Title|Album)[ .]*:[ \t]*([^\r\n]+?)[ \t]*$", header)
        sources = re.findall(r"\bSource[ .]*:[ \t]*([1-9][0-9]?)CD\b", header, re.IGNORECASE)
        expected_discs = {disc for disc, _ in titles}
        if (len(artists) != 1 or identity(artists[0]) != identity(artist)
                or len(albums) != 1 or identity(albums[0]) != identity(album)
                or sources != [str(len(expected_discs))]):
            continue
        disc = None
        discs = set()
        found = {}
        for line in text[markers[0].end():].splitlines():
            line = line.strip()
            if match := re.fullmatch(r"CD[ ._-]*([1-9][0-9]?):", line, re.IGNORECASE):
                disc = int(match[1])
                if disc in discs:
                    break
                discs.add(disc)
            elif match := re.fullmatch(r"([0-9]{1,3})[ .)-]+(.+?)[ \t]{2,}\[[0-9]{1,3}:[0-5][0-9]\]", line):
                key = (disc, int(match[1]))
                if disc is None or key in found:
                    break
                found[key] = identity(match[2])
            elif re.match(r"[0-9]{1,3}[ .)-]", line):
                break
        else:
            if discs == expected_discs and found == {key: identity(value) for key, value in titles.items()}:
                return True
    return False


def release_total_evidence(groups: dict, members: dict, files: list[Path],
                           required_manifests: set[Path] | None) -> set[Path]:
    """Disambiguate whole-release totals only with an NFO and covering playlist."""
    cohorts = {}
    for key, records in groups.items():
        cohorts.setdefault((key[0], key[1], key[4]), []).append((key, records))
    audio = None
    proven = set()
    for owner, disc_groups in cohorts.items():
        paths = {p for _, records in disc_groups for p, _, _ in records}
        totals = {total for _, records in disc_groups for _, _, total in records}
        if (len(disc_groups) < 2 or paths != members.get(owner) or totals != {str(len(paths))}):
            continue
        titles = {}
        performers = set()
        discs = set()
        positions = {}
        for key, records in disc_groups:
            ancestry = [re.match(r"(?:cdm|cd|disc|disk)[ _.-]*([0-9]+)", label, re.IGNORECASE)[1] for label in key[3]]
            disc = key[2] or (ancestry[0] if len(ancestry) == 1 else "")
            if (not re.fullmatch(r"[0-9]{1,5}", disc) or not 1 <= int(disc) <= 99 or len(ancestry) > 1
                    or ancestry and int(ancestry[0]) != int(disc) or int(disc) in discs):
                break
            disc = int(disc)
            discs.add(disc)
            numbers = [int(n) for _, n, _ in records if re.fullmatch(r"[1-9][0-9]{0,4}", n)]
            if len(numbers) != len(records) or len(set(numbers)) != len(numbers):
                break
            positions[disc] = sorted(numbers)
            for path, number, _ in records:
                tags, _ = flac_album_metadata(path)
                if not tags.get("ALBUM", "").strip() or not tags.get("TITLE", "").strip():
                    break
                performers.add((tags.get("ALBUMARTIST") or tags.get("ALBUM ARTIST") or tags.get("ARTIST", "")).strip().casefold())
                titles[(disc, int(number))] = tags["TITLE"]
            else:
                continue
            break
        else:
            if discs != set(range(1, len(disc_groups) + 1)) or len(performers) != 1 or not next(iter(performers)):
                continue
            offset = 0
            local_numbering = global_numbering = True
            local_titles = {}
            for disc in sorted(discs):
                numbers = positions[disc]
                local_numbering &= numbers == list(range(1, len(numbers) + 1))
                global_numbering &= numbers == list(range(offset + 1, offset + len(numbers) + 1))
                local_titles.update({(disc, number - offset): titles[(disc, number)] for number in numbers})
                offset += len(numbers)
            if not local_numbering:
                if not global_numbering:
                    continue
                titles = local_titles
            base = Path(owner[2])
            nfos = [p for p in files if p.parent == base and p.suffix.casefold() == ".nfo"
                    and nfo_disc_manifest(p, next(iter(performers)), owner[0], titles)]
            if not nfos:
                continue
            if audio is None:
                audio = [p for p in files if detected_suffix(p) in AUDIO_SUFFIXES or p.suffix.casefold() in AUDIO_SUFFIXES]
            for playlist in files:
                if playlist.parent != base or playlist.suffix.casefold() not in {".m3u", ".m3u8"}:
                    continue
                entries = playlist_entries(playlist)
                if not entries or len(entries) != len(paths):
                    continue
                resolved = playlist_local_targets(entries, audio, playlist.parent)
                if all(len(items) == 1 for items in resolved) and {next(iter(items)) for items in resolved} == paths:
                    proven.update(paths)
                    if required_manifests is not None:
                        required_manifests.update((playlist, nfos[0]))
                    break
    return proven


def check_album_tracks(files: list[Path], protected: set[Path], root: Path,
                       required_manifests: set[Path] | None = None) -> set[Path]:
    proven = set(protected)
    filename_discs = playlist_disc_groups(files, protected, root, required_manifests, proven)
    groups: dict[tuple, list[tuple[Path, str, str]]] = {}
    discs: dict[tuple, list[tuple[str, str]]] = {}
    members: dict[tuple, set[Path]] = {}
    for path in files:
        if detected_suffix(path) != ".flac":
            continue
        tags, embedded_cue = flac_album_metadata(path)
        disc, disc_total = metadata_position(tags, ("DISCNUMBER", "DISC"),
                                             ("DISCTOTAL", "TOTALDISCS"), "disc")
        ancestry = tuple(part.casefold() for part in extension_target(path).parent.relative_to(root).parts if DISC_DIRECTORY.fullmatch(part))
        album = tags.get("ALBUM", "").strip().casefold()
        artist = (tags.get("ALBUMARTIST") or tags.get("ALBUM ARTIST", "")).strip().casefold()
        base = album_directory(path, root)
        members.setdefault((album, artist, str(base)), set()).add(path)
        # A shared album name alone must not combine independent edition folders.
        discs.setdefault((album or str(base), artist, str(base)), []).append((disc, disc_total))
        if path in protected or embedded_cue or tags.get("CUESHEET"):
            proven.add(path)
            continue
        number, total = metadata_position(tags, ("TRACKNUMBER", "TRACK"),
                                          ("TRACKTOTAL", "TOTALTRACKS"), "track")
        key = (album or str(path.parent), artist, disc or filename_discs.get(path, ""), ancestry, str(base))
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
    release_proven = release_total_evidence(groups, members, files, required_manifests)
    proven.update(release_proven)
    for records in groups.values():
        if all(path in release_proven for path, _, _ in records):
            continue
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


def playlist_encoding(raw: bytes, path: Path) -> str:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16-le" if raw[:2] == b"\xff\xfe" else "utf-16-be"
    try:
        raw.decode("utf-8-sig")
        return "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    except UnicodeDecodeError:
        if path.suffix.casefold() not in {".m3u", ".m3u8"}:
            raise
        return "cp1252"


def playlist_entries(path: Path) -> list[PurePosixPath] | None:
    """Recognise bounded local M3U text, never arbitrary text or remote paths."""
    if path.suffix.casefold() in KNOWN_MEDIA_SUFFIXES | {".cue"}:
        return None
    if path.stat().st_size > 1024**2 or detected_suffix(path) is not None:
        return None
    try:
        raw = path.read_bytes()
        text = raw.decode(playlist_encoding(raw, path)).removeprefix("\ufeff")
    except UnicodeDecodeError:
        return None
    checksum_rows = [line.strip() for line in text.splitlines() if line.strip()]
    if (path.suffix.casefold() == ".md5" and checksum_rows
            and all(re.fullmatch(r"[0-9a-fA-F]{32} [ *].+", line) for line in checksum_rows)):
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
        resolved = playlist_local_targets(entries, audio, playlist.parent)
        local = [bool(matches) for matches in resolved]
        if all(local):
            if any(len(matches) != 1 for matches in resolved) or len({next(iter(matches)) for matches in resolved}) != len(entries):
                raise ValueError(f"ambiguous playlist: {playlist.name}; entries must reference distinct audio files; retaining all files")
            if covered is not None:
                for matches in resolved:
                    covered.update(matches)
            if references is not None:
                references[playlist] = {entry: next(iter(matches)) for entry, matches in zip(entries, resolved)}
            recognised.add(playlist)
            continue
        if playlist in protected:
            continue
        # Obfuscated files can still be related through numbered artist/title
        # entries, but only for one fully tagged, cue-free FLAC album/disc.
        candidates = [path for path in audio if path.parent == playlist.parent]
        if not candidates or any(path in protected or detected_suffix(path) != ".flac" for path in candidates):
            if validate and any(local):
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
        if validate and any(local):
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
    completeness_cues = cue_image_targets(cues) if require_completeness else protected
    completeness_manifests: set[Path] = set()
    proven = check_album_tracks(files, completeness_cues, root, completeness_manifests) if cleanup or require_completeness else set()
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
        if (cleanup and path not in protected and path not in completeness_manifests
                and not (require_completeness and path in playlists)
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
        encoding = playlist_encoding(raw, playlist)
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
                kind = "cue FILE" if extension_target(cue).suffix.casefold() == ".cue" else "playlist"
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
