#!/usr/bin/env python3
"""Safely unpack music archives that NZBGet's built-in unpacker missed."""

from __future__ import annotations

import os
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

SUCCESS = 93
FAILURE = 94
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
DISC_DIRECTORY = re.compile(r"^(?:cd|disc|disk)[ _.-]*\d{1,2}$", re.IGNORECASE)
UNWANTED_SUFFIXES = {
    ".accurip",
    ".cue",
    ".jpg",
    ".log",
    ".m3u",
    ".m3u8",
    ".md5",
    ".nfo",
    ".nzb",
    ".pls",
    ".png",
    ".sfv",
    ".srr",
    ".toc",
    ".txt",
    ".url",
}


def is_archive(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in ARCHIVE_SUFFIXES)


def validate_members(archive: tarfile.TarFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if os.path.commonpath((root, target)) != str(root):
            raise ValueError(f"unsafe path in archive: {member.name}")
        if member.issym() or member.islnk():
            raise ValueError(f"links are not allowed in archive: {member.name}")
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"special files are not allowed in archive: {member.name}")


def validate_zip_members(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (root / member.filename).resolve()
        if os.path.commonpath((root, target)) != str(root):
            raise ValueError(f"unsafe path in archive: {member.filename}")
        # The high 16 bits contain the Unix file mode when the archive has one.
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError(f"links are not allowed in archive: {member.filename}")


def flattened_target(path: Path, source: Path, destination: Path) -> Path:
    relative = path.relative_to(source)
    disc = next((part for part in relative.parts[:-1] if DISC_DIRECTORY.fullmatch(part)), None)
    if disc:
        return destination / disc / path.name
    return destination / path.name


def merge_flattened(source: Path, destination: Path) -> None:
    moves = [
        (path, flattened_target(path, source, destination))
        for path in source.rglob("*")
        if path.is_file()
    ]
    targets: set[Path] = set()
    for _, target in moves:
        if target in targets or target.exists():
            raise FileExistsError(f"refusing to overwrite existing path: {target}")
        targets.add(target)
    for item, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(item), str(target))


def flatten_existing_tree(directory: Path) -> None:
    moves = []
    for path in directory.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        target = flattened_target(path, directory, directory)
        if path != target:
            moves.append((path, target))

    targets: set[Path] = set()
    for _, target in moves:
        if target in targets or target.exists():
            raise FileExistsError(f"refusing to overwrite existing path: {target}")
        targets.add(target)
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))

    directories = sorted(
        (path for path in directory.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for path in directories:
        try:
            path.rmdir()
        except OSError:
            pass


def remove_unwanted_files(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix.casefold() in UNWANTED_SUFFIXES:
            path.unlink()
            print(f"[INFO] Removed unwanted file {path.relative_to(directory)}")


def unpack(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix=".unpack-music-", dir=path.parent) as temp:
        staging = Path(temp)
        if path.name.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as archive:
                validate_zip_members(archive, staging)
                archive.extractall(staging)
        else:
            with tarfile.open(path, mode="r:*") as archive:
                validate_members(archive, staging)
                archive.extractall(staging, filter="data")
        merge_flattened(staging, path.parent)
    remove_unwanted_files(path.parent)
    path.unlink()
    print(f"[INFO] Unpacked and removed {path.name}")


def main() -> int:
    category = os.environ.get("NZBPP_CATEGORY", "")
    if category.casefold() != "music":
        print(f"[INFO] Skipping category {category or '(none)'}")
        return SUCCESS

    directory_value = os.environ.get("NZBPP_FINALDIR") or os.environ.get("NZBPP_DIRECTORY")
    if not directory_value:
        print("[ERROR] NZBGet did not provide a download directory", file=sys.stderr)
        return FAILURE

    directory = Path(directory_value)
    archives = sorted(path for path in directory.rglob("*") if path.is_file() and is_archive(path))
    try:
        if not archives:
            print("[INFO] No supported music archives found")
            remove_unwanted_files(directory)
            flatten_existing_tree(directory)
            return SUCCESS

        for archive in archives:
            unpack(archive)
        # Also clean sidecars left behind by NZBGet's built-in unpacker or found
        # elsewhere under the completed release directory.
        remove_unwanted_files(directory)
        flatten_existing_tree(directory)
    except (OSError, tarfile.TarError, zipfile.BadZipFile, ValueError) as error:
        print(f"[ERROR] Music post-processing failed: {error}", file=sys.stderr)
        return FAILURE
    return SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
