#!/usr/bin/env python3
"""Safely unpack tar archives downloaded in NZBGet's music category."""

from __future__ import annotations

import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

SUCCESS = 93
FAILURE = 94
ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")


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


def merge_tree(source: Path, destination: Path) -> None:
    items = list(source.iterdir())
    for item in items:
        target = destination / item.name
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing path: {target}")
    for item in items:
        target = destination / item.name
        shutil.move(str(item), str(target))


def unpack(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix=".unpack-music-", dir=path.parent) as temp:
        staging = Path(temp)
        with tarfile.open(path, mode="r:*") as archive:
            validate_members(archive, staging)
            archive.extractall(staging, filter="data")
        merge_tree(staging, path.parent)
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
    if not archives:
        print("[INFO] No music tar archives found")
        return SUCCESS

    try:
        for archive in archives:
            unpack(archive)
    except (OSError, tarfile.TarError, ValueError) as error:
        print(f"[ERROR] Music tar extraction failed: {error}", file=sys.stderr)
        return FAILURE
    return SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
