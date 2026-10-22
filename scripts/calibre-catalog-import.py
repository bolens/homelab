#!/usr/bin/env python3
"""Read-only Calibre EPUB import planning; stdout contains aggregate counts only."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

FORMATS = {".epub", ".azw3", ".mobi", ".pdf"}
DC = "{http://purl.org/dc/elements/1.1/}"


class PlanError(Exception):
    """A bounded error whose message never contains private input."""


def normalize(value):
    value = unicodedata.normalize("NFKD", value).casefold()
    return "".join(char for char in value if char.isalnum() and not unicodedata.combining(char))


def author_key(value):
    words = re.findall(r"[^\W_]+", unicodedata.normalize("NFKD", value).casefold())
    return " ".join(sorted(normalize(word) for word in words if normalize(word)))


def isbn(value):
    value = value.strip()
    value = re.sub(r"^(?:urn:)?isbn(?:-1[03])?:\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"\d{9}[\dX]", value):
        digits = [int(char) if char != "X" else 10 for char in value]
        if sum((10 - index) * digit for index, digit in enumerate(digits)) % 11:
            return None
        base = "978" + value[:9]
        return base + str((-sum(int(char) * (1 if index % 2 == 0 else 3)
                                for index, char in enumerate(base))) % 10)
    if re.fullmatch(r"97[89]\d{10}", value):
        if sum(int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(value)) % 10 == 0:
            return value
    return None


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def epub_metadata(path):
    """Read bounded OPF metadata without extraction or network access."""
    try:
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist()) > 10000:
                raise PlanError("epub_metadata_limits")

            def read(name, limit):
                if archive.namelist().count(name) != 1 or archive.getinfo(name).file_size > limit:
                    raise PlanError("epub_metadata_limits")
                return archive.read(name)

            container = ET.fromstring(read("META-INF/container.xml", 262144))
            roots = [item.attrib.get("full-path", "") for item in container.iter()
                     if item.tag == "{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"]
            if len(roots) != 1:
                raise PlanError("ambiguous_epub_package")
            name = PurePosixPath(roots[0])
            if name.is_absolute() or ".." in name.parts or not str(name):
                raise PlanError("invalid_epub_package")
            package = ET.fromstring(read(str(name), 2097152))
            metadata_nodes = [node for node in package if node.tag.rsplit("}", 1)[-1] == "metadata"]
            if len(metadata_nodes) != 1:
                raise PlanError("missing_epub_metadata")
            metadata = metadata_nodes[0]
            titles = list(dict.fromkeys("".join(node.itertext()).strip() for node in metadata if node.tag == DC + "title"))
            if len(titles) != 1 or not normalize(titles[0]):
                raise PlanError("missing_or_ambiguous_title")
            roles = defaultdict(set)
            for node in metadata:
                if node.tag.rsplit("}", 1)[-1] == "meta" and node.attrib.get("property") == "role":
                    roles[node.attrib.get("refines", "").lstrip("#")].add((node.text or "").strip())
            authors = []
            for node in metadata:
                if node.tag != DC + "creator":
                    continue
                role = next((value for key, value in node.attrib.items() if key.rsplit("}", 1)[-1] == "role"), None)
                refined = roles.get(node.attrib.get("id", ""), set())
                if (role and role != "aut") or (refined and "aut" not in refined):
                    continue
                text = "".join(node.itertext()).strip()
                if author_key(text):
                    authors.append(text)
            authors = list(dict.fromkeys(authors))
            if not authors:
                raise PlanError("missing_author")
            identifiers = set()
            for node in metadata:
                if node.tag != DC + "identifier":
                    continue
                text = "".join(node.itertext()).strip()
                scheme = next((value for key, value in node.attrib.items() if key.rsplit("}", 1)[-1] == "scheme"), "")
                if scheme.lower() == "isbn" or text.lower().startswith("urn:isbn:") or re.fullmatch(r"[\dXx\s-]+", text):
                    canonical = isbn(text)
                    if canonical:
                        identifiers.add(canonical)
            if len(identifiers) > 1:
                raise PlanError("conflicting_edition_isbns")
            return {"title": titles[0], "authors": authors, "isbns": sorted(identifiers)}
    except PlanError:
        raise
    except (OSError, KeyError, ValueError, ET.ParseError, zipfile.BadZipFile, RuntimeError):
        raise PlanError("invalid_epub_metadata") from None


def safe_catalog_path(root, relative, name, format_name):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not name or Path(name).name != name:
        raise PlanError("unsafe_catalog_path")
    if not re.fullmatch(r"[A-Za-z0-9]+", format_name):
        raise PlanError("unsafe_catalog_format")
    result = root / path / (name + "." + format_name.lower())
    current = root
    for part in result.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise PlanError("catalog_symlink_requires_review")
    return result


def database_snapshot(root):
    database = root / "metadata.db"
    if any((root / name).is_symlink() for name in ("metadata.db", "metadata.db-wal", "metadata.db-shm", "metadata.db-journal")) or not database.is_file():
        raise PlanError("calibre_database_unavailable")
    try:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise PlanError("calibre_database_integrity_failed")
            books = list(connection.execute("SELECT id,title,path FROM books ORDER BY id"))
            formats = list(connection.execute("SELECT book,name,format FROM data ORDER BY id"))
            identifiers = list(connection.execute("SELECT book,type,val FROM identifiers ORDER BY id"))
            authors = list(connection.execute("SELECT ba.book,a.name FROM books_authors_link ba JOIN authors a ON a.id=ba.author ORDER BY ba.book,a.id"))
            digest = hashlib.sha256()
            for statement in connection.iterdump():
                digest.update(statement.encode("utf-8"))
                digest.update(b"\n")
            baseline = {"logicalSha256": digest.hexdigest(), "bookCount": len(books), "formatCount": len(formats),
                        "databasePath": str(database), "quickCheck": "ok",
                        "snapshotMethod": "read-only transaction logical SQL dump", "physicalFilesCapturedAfterSnapshot": True}
        finally:
            connection.close()
    except sqlite3.Error:
        raise PlanError("calibre_database_read_failed") from None
    baseline["physicalFiles"] = [{"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
                                 for path in (database, root / "metadata.db-wal") if path.is_file()]
    return books, formats, identifiers, authors, baseline


def plan(library):
    root = Path(library).resolve(strict=True)
    if not root.is_dir():
        raise PlanError("library_unavailable")
    books, formats, identifiers, authors, baseline = database_snapshot(root)
    book_paths = {book: path for book, _, path in books}
    title_index = defaultdict(list)
    author_index = defaultdict(list)
    for book, title, _ in books:
        title_index[normalize(title)].append(book)
    for book, author in authors:
        author_index[book].append(author_key(author))
    registered_isbns = {canonical for _, kind, value in identifiers if kind.lower() == "isbn" and (canonical := isbn(value))}
    registered = {safe_catalog_path(root, book_paths[book], name, format_name) for book, name, format_name in formats}
    existing = {path for path in registered if path.is_file()}
    known_hashes = {sha256(path) for path in existing}
    files = []
    ignored_symlinks = 0
    def scan_error(error):
        raise PlanError("source_scan_unreadable")

    for directory, dirs, names in os.walk(root, followlinks=False, onerror=scan_error):
        ignored_symlinks += sum((Path(directory) / name).is_symlink() for name in dirs)
        dirs[:] = sorted(name for name in dirs if name not in {".caltrash", ".calnotes"}
                         and not (Path(directory) / name).is_symlink())
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix.lower() not in FORMATS:
                continue
            if path.is_symlink():
                ignored_symlinks += 1
            elif path.is_file():
                files.append(path)
    counts = Counter({"sourceFiles": len(files), "registeredBooks": len(books), "registeredFormats": len(registered),
                      "registeredFilesPresent": len(existing), "registeredFilesMissing": len(registered - existing),
                      "unregisteredFiles": sum(path not in registered for path in files), "ignoredSymlinks": ignored_symlinks})
    exclusions = []
    candidates = []
    hashes = set()

    def exclude(record, reason):
        exclusions.append({**record, "reason": reason})
        counts[reason] += 1

    for path in sorted(files):
        if path in registered:
            continue
        digest = sha256(path)
        record = {"path": str(path), "sha256": digest, "format": path.suffix[1:].upper(), "bytes": path.stat().st_size}
        if digest in known_hashes:
            exclude(record, "duplicate_registered_content")
            continue
        if path.suffix.lower() != ".epub":
            exclude(record, "unsupported_orphan_format")
            continue
        if digest in hashes:
            exclude(record, "duplicate_candidate_content")
            continue
        hashes.add(digest)
        try:
            record.update(epub_metadata(path))
        except PlanError as error:
            exclude(record, str(error))
            continue
        if set(record["isbns"]) & registered_isbns:
            exclude(record, "existing_isbn")
        elif normalize(record["title"]) in title_index:
            matches = title_index[normalize(record["title"])]
            same_authors = any(sorted(author_index[book]) == sorted(author_key(author) for author in record["authors"]) for book in matches)
            exclude(record, "existing_title" if same_authors and len(matches) == 1 else "ambiguous_existing_title")
        else:
            candidates.append(record)
    by_isbn = defaultdict(list)
    for record in candidates:
        for identifier in record["isbns"]:
            by_isbn[identifier].append(record)
    conflicting = {id(record) for group in by_isbn.values()
                   if len({(normalize(item["title"]), tuple(sorted(author_key(author) for author in item["authors"]))) for item in group}) > 1
                   for record in group}
    groups = defaultdict(list)
    for record in candidates:
        if id(record) in conflicting:
            exclude(record, "isbn_conflicting_metadata")
        else:
            groups[normalize(record["title"])].append(record)
    selected = []
    for group in groups.values():
        if len(group) == 1:
            selected.extend(group)
            continue
        editions = {(tuple(record["isbns"]), tuple(sorted(author_key(author) for author in record["authors"]))) for record in group}
        if len(editions) == 1 and group[0]["isbns"]:
            selected.append(group[0])
            for record in group[1:]:
                exclude(record, "duplicate_isbn_edition")
        else:
            for record in group:
                exclude(record, "ambiguous_new_title_editions")
    counts["candidateBooks"] = len(selected)
    counts["excludedFiles"] = len(exclusions)
    return {"kind": "calibre-catalog-import-plan", "version": 1, "operation": "review-only", "reviewRequired": True,
            "libraryPath": str(root), "baseline": baseline, "counts": dict(sorted(counts.items())),
            "candidates": selected, "exclusions": exclusions}


def write_manifest(target, document):
    target = Path(target)
    if not target.is_absolute() or target.name in ("", ".", ".."):
        raise PlanError("manifest_requires_absolute_path")
    parent = target.parent
    try:
        if parent.resolve(strict=True) != parent:
            raise PlanError("manifest_symlink_or_noncanonical_parent")
        for ancestor in (parent, *parent.parents):
            if ((ancestor / ".git").is_file() or (ancestor / ".git" / "HEAD").is_file()
                    or ((ancestor / "HEAD").is_file() and (ancestor / "objects").is_dir())):
                raise PlanError("manifest_must_be_outside_git")
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(directory)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise PlanError("manifest_parent_requires_owned_0700")
            descriptor = os.open(target.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    descriptor = -1
                    json.dump(document, stream, ensure_ascii=False, sort_keys=True, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                if descriptor >= 0:
                    os.close(descriptor)
                os.unlink(target.name, dir_fd=directory)
                raise
        finally:
            os.close(directory)
    except PlanError:
        raise
    except OSError:
        raise PlanError("manifest_private_exclusive_write_failed") from None


class PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        raise PlanError("invalid_planner_arguments")


def main(argv=None):
    parser = PrivateParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--manifest", type=Path)
    try:
        args = parser.parse_args(argv)
        document = plan(args.library)
        if args.manifest is not None:
            write_manifest(args.manifest, document)
        print(json.dumps({"counts": document["counts"], "manifestWritten": args.manifest is not None}, sort_keys=True))
        return 0
    except PlanError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    except (OSError, ValueError, KeyError, RuntimeError, TypeError, UnicodeError):
        print(json.dumps({"error": "planner_read_failed"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
