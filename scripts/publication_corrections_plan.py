"""Read-only correction plans; no registration, media or catalog mutation."""

from contextlib import closing
import importlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

NATIVE = Path(__file__).resolve().parents[1] / "stacks/mylar3/config"
sys.path.insert(0, str(NATIVE))
guard = importlib.import_module("publication_guard")
media_writer = importlib.import_module("media_writer")
Writer = media_writer.Writer

LIMIT = 4 * 1024 * 1024


def compatible(records, left, right):
    if left == right:
        return True
    if not any(record['version'] == 2 for record in records.values()):
        return False
    from publication_derivative import families
    index, _ = families(records)
    return left in index and right in index and index[left] == index[right]


def observe_correct(database, writer, owners, roots, tool, records):
    observations = []
    inventory = None
    for owner in owners:
        current = guard.observe_owners(database, writer, [owner], roots, tool_root=tool)
        if inventory is None:
            inventory = current['inventory']
        elif not compatible(records, inventory['payload'], current['inventory']['payload']):
            raise guard.Unavailable('Correct publications are not one exact reviewed family')
        observations.extend(current['observed'])
    if inventory is None:
        raise guard.Unavailable('Reviewed correct publication required')
    return dict(inventory=inventory, observed=observations)


def exact(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise guard.Unavailable("Plan schema requires review")


def path(value):
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise guard.Unavailable("Plan path requires review")
    result = Path(value)
    if (
        not result.is_absolute()
        or result == Path("/")
        or ".." in result.parts
        or any(item.is_symlink() for item in (result, *result.parents))
    ):
        raise guard.Unavailable("Plan path requires review")
    return result


def private(value, *, limit=LIMIT):
    value = path(value)
    facts = value.lstat()
    folder = value.parent.lstat()
    if (
        not stat.S_ISREG(facts.st_mode)
        or facts.st_uid != os.geteuid()
        or facts.st_nlink != 1
        or stat.S_IMODE(facts.st_mode) != 0o600
        or not 0 < facts.st_size <= limit
        or not stat.S_ISDIR(folder.st_mode)
        or folder.st_uid != os.geteuid()
        or stat.S_IMODE(folder.st_mode) != 0o700
    ):
        raise guard.Unavailable("Private owned plan evidence required")
    return value


def read(value):
    value = private(value)
    before, checksum = guard.file_hash(value)
    with guard.regular(value) as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT or guard.file_hash(value) != (before, checksum):
        raise guard.Unavailable("Plan evidence changed")
    return guard.decode_json(raw), checksum


def checked_hash(value, expected, *, owned=False):
    if not guard.digest_value(expected):
        raise guard.Unavailable("Exact plan checksum required")
    value = private(value, limit=guard.MAX_BYTES) if owned else path(value)
    signature, checksum = guard.file_hash(value)
    if checksum != expected:
        raise guard.Unavailable("Reviewed plan file changed")
    return signature


def database(value):
    value = path(value)
    if any(
        os.path.lexists(str(value) + suffix) for suffix in ("-journal", "-wal", "-shm")
    ):
        raise guard.Unavailable("Database backup has pending state")
    before = guard.signature(value.lstat())
    with closing(
        sqlite3.connect(value.as_uri() + "?mode=ro&immutable=1", uri=True)
    ) as connection:
        if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise guard.Unavailable("Database backup is unreadable")
    if guard.signature(value.lstat()) != before:
        raise guard.Unavailable("Database backup changed")


def backup(review, required, roots):
    exact(
        review,
        (
            "manifest_path",
            "manifest_sha256",
            "restore_receipt_path",
            "restore_receipt_sha256",
        ),
    )
    manifest, checksum = read(review["manifest_path"])
    receipt, restored = read(review["restore_receipt_path"])
    if (
        checksum != review["manifest_sha256"]
        or restored != review["restore_receipt_sha256"]
    ):
        raise guard.Unavailable("Reviewed backup evidence changed")
    exact(manifest, ("version", "files"))
    exact(receipt, ("version", "manifest_sha256", "files"))
    if (
        type(manifest["version"]) is not int
        or manifest["version"] != 1
        or type(receipt["version"]) is not int
        or receipt["version"] != 1
        or receipt["manifest_sha256"] != checksum
        or not isinstance(manifest["files"], list)
        or len(manifest["files"]) != len(required)
        or not isinstance(receipt["files"], list)
        or len(receipt["files"]) != len(required)
    ):
        raise guard.Unavailable("Incomplete independently restored backup")
    restored_rows = {}
    for row in receipt["files"]:
        exact(row, ("role", "sha256"))
        if row["role"] in restored_rows:
            raise guard.Unavailable("Duplicate restore role")
        restored_rows[row["role"]] = row["sha256"]
    facts = {}
    seen = set()
    for row in manifest["files"]:
        exact(row, ("role", "source", "backup", "restore", "sha256"))
        role = row["role"]
        if role not in required or role in seen or row["source"] != str(required[role]):
            raise guard.Unavailable("Backup scope differs from correction operation")
        seen.add(role)
        if restored_rows.get(role) != row["sha256"]:
            raise guard.Unavailable("Restore receipt differs from backup")
        if any(
            path(row[key]).is_relative_to(root)
            for key in ("backup", "restore")
            for root in roots
        ):
            raise guard.Unavailable(
                "Backup and restore copies must remain outside libraries"
            )
        signatures = [
            checked_hash(row[key], row["sha256"], owned=key != "source")
            for key in ("source", "backup", "restore")
        ]
        if len({tuple(value[:2]) for value in signatures}) != 3:
            raise guard.Unavailable("Independent backup and restore copies required")
        if Path(row["backup"]).parent == Path(row["restore"]).parent:
            raise guard.Unavailable("Independent restore directory required")
        if role in ("catalog", "workflow"):
            for key in ("source", "backup", "restore"):
                database(row[key])
        facts[role] = dict(row, signatures=signatures)
    if seen != set(required) or set(restored_rows) != seen:
        raise guard.Unavailable("Missing backup state")
    return dict(manifest_sha256=checksum, restore_sha256=restored, files=facts)


@guard.state_errors
def prepare(scope, review):
    raw = guard.compact(dict(scope=scope, review=review))
    if len(raw) > LIMIT:
        raise guard.Unavailable("Correction review exceeds bound")
    captured = guard.decode_json(raw)
    scope, review = captured["scope"], captured["review"]
    exact(scope, ("version", "config_dir", "library_roots", "tool_root"))
    exact(
        review,
        (
            "version",
            "census",
            "allowed",
            "rejected",
            "correct",
            "repeat",
            "evidence",
            "backup",
            "created",
        ),
    )
    if (
        type(scope["version"]) is not int
        or scope["version"] != 1
        or type(review["version"]) is not int
        or review["version"] != 1
        or type(review["created"]) is not int
        or review["created"] < 0
        or not isinstance(scope["library_roots"], list)
        or not 1 <= len(scope["library_roots"]) <= 8
    ):
        raise guard.Unavailable("Unsupported correction plan")
    config = path(scope["config_dir"])
    roots = [path(item) for item in scope["library_roots"]]
    tool = path(scope["tool_root"])
    if (
        any(not root.is_dir() for root in roots)
        or not config.is_dir()
        or not tool.is_dir()
    ):
        raise guard.Unavailable("Missing trusted correction scope")
    guard.census_value(review["census"])
    owners = []
    for key in ("allowed", "rejected"):
        if not isinstance(review[key], list) or not 1 <= len(review[key]) <= 8:
            raise guard.Unavailable("Explicit reviewed publication owners required")
        owners.extend(
            guard.canonical_digest(guard.exact_owner(owner)) for owner in review[key]
        )
    if len(owners) > 8 or len(set(owners)) != len(owners):
        raise guard.Unavailable("Conflicting correction plan owners")
    if not isinstance(review["correct"], list) or len(review["correct"]) != len(
        review["allowed"]
    ):
        raise guard.Unavailable("Complete correct publication witnesses required")
    exact(review["evidence"], ("path", "sha256", "description"))
    description = review["evidence"]["description"]
    if (
        not isinstance(description, str)
        or not 1 <= len(description.encode()) <= 2048
        or "://" in description
        or any(ord(char) < 32 for char in description)
    ):
        raise guard.Unavailable("Reviewed publication evidence required")
    evidence_signature = checked_hash(review["evidence"]["path"], review["evidence"]["sha256"], owned=True)
    writer = Writer(config / "media-writer", create=False)
    with writer.hold(timeout=0):
        census, records = guard.registry_snapshot(
            config / "workflow.sqlite", writer.root / "publication-v1.json"
        )
        if not guard.same_json(census, review["census"]):
            raise guard.Unavailable("Reviewed correction census changed")
        observed = observe_correct(
            config / "mylar.db", writer, review["allowed"], roots, tool, records
        )
        required = dict(
            catalog=config / "mylar.db",
            workflow=config / "workflow.sqlite",
            marker=writer.root / "publication-v1.json",
        )
        source_ids = set()
        for index, (row, actual, owner) in enumerate(
            zip(review["correct"], observed["observed"], review["allowed"])
        ):
            exact(row, ("owner", "path", "sha256"))
            if (
                not guard.same_json(row["owner"], owner)
                or row["path"] != actual["catalog"]["path"]
                or row["sha256"] != actual["source_sha256"]
            ):
                raise guard.Unavailable("Reviewed correct publication changed")
            checked_hash(row["path"], row["sha256"])
            source_ids.add(tuple(actual["signature"][:2]))
            required["correct_" + str(index)] = path(row["path"])
        repeat = None
        if review["repeat"] is not None:
            row = review["repeat"]
            exact(row, ("owner", "path", "sha256"))
            if not any(
                guard.same_json(row["owner"], owner) for owner in review["rejected"]
            ):
                raise guard.Unavailable("Repeat has no explicit rejected owner")
            actual = guard.observe_owners(
                config / "mylar.db", writer, [row["owner"]], roots, tool_root=tool
            )
            claim = actual["observed"][0]
            if (
                row["path"] != claim["catalog"]["path"]
                or row["sha256"] != claim["source_sha256"]
                or not compatible(records, actual["inventory"]["payload"], observed["inventory"]["payload"])
                or tuple(claim["signature"][:2]) in source_ids
            ):
                raise guard.Unavailable(
                    "Repeat is different, changed or a protected physical original"
                )
            if any(record['version'] == 2 for record in records.values()):
                from publication_derivative import matches
                members = matches(records, actual['inventory']['payload'])
                if members:
                    for field in ('allowed', 'rejected'):
                        inherited = {guard.canonical_digest(owner) for record in members.values() for owner in record[field]}
                        if inherited != {guard.canonical_digest(owner) for owner in review[field]}:
                            raise guard.Unavailable('Reviewed family owners must inherit the complete exact census')
            required["repeat"] = path(row["path"])
            repeat = dict(
                executable=False,
                readiness="fresh-native-retention-review-required",
                source=claim,
                inventory=actual["inventory"],
                correct=observed["observed"],
                acquisition_provenance=None,
                failed_release_binding=None,
                retention="verified-outside-library-copy-required-before-any-unlink",
            )
        restored = backup(review["backup"], required, roots)
        private_documents = [(review['evidence']['path'], evidence_signature)]
        for field, digest_field in (('manifest_path','manifest_sha256'),('restore_receipt_path','restore_receipt_sha256')):
            private_documents.append((review['backup'][field], checked_hash(review['backup'][field], review['backup'][digest_field], owned=True)))
        if not guard.same_json(
            observed,
            observe_correct(
                config / "mylar.db", writer, review["allowed"], roots, tool, records
            ),
        ) or not guard.same_json(
            census,
            guard.registry_snapshot(
                config / "workflow.sqlite", writer.root / "publication-v1.json"
            )[0],
        ):
            raise guard.Unavailable(
                "Correction plan authority changed during preparation"
            )
        if repeat is not None:
            if not guard.same_json(
                actual,
                guard.observe_owners(
                    config / "mylar.db",
                    writer,
                    [review["repeat"]["owner"]],
                    roots,
                    tool_root=tool,
                ),
            ):
                raise guard.Unavailable("Repeat changed during preparation")
        checked_hash(
            review["evidence"]["path"], review["evidence"]["sha256"], owned=True
        )
        if not guard.same_json(restored, backup(review["backup"], required, roots)):
            raise guard.Unavailable("Backup or restore changed during preparation")
        final_census, final_records = guard.registry_snapshot(config / 'workflow.sqlite', writer.root / 'publication-v1.json')
        if not guard.same_json(final_census, census) or not guard.same_json(
                observe_correct(config / 'mylar.db', writer, review['allowed'], roots, tool, final_records), observed):
            raise guard.Unavailable('Reviewed census or publication changed during final backup proof')
        if repeat and not guard.same_json(guard.observe_owners(config / 'mylar.db', writer, [review['repeat']['owner']], roots, tool_root=tool), actual):
            raise guard.Unavailable('Reviewed repeat changed during final backup proof')
        # Expensive private/census/archive reads precede this last incarnation
        # pass. A passive plan must not describe stale current source rights.
        for row in restored['files'].values():
            for field, expected in zip(('source','backup','restore'), row['signatures']):
                candidate = path(row[field]) if field == 'source' else private(row[field], limit=guard.MAX_BYTES)
                with guard.regular(candidate) as stream:
                    if guard.signature(os.fstat(stream.fileno())) != expected:
                        raise guard.Unavailable('Backup or current source changed during final proof')
        for candidate, expected in private_documents:
            if guard.signature(private(candidate, limit=guard.MAX_BYTES).lstat()) != expected:
                raise guard.Unavailable('Private review document changed during final proof')
        for claim in observed['observed'] + ([repeat['source']] if repeat else []):
            with guard.regular(path(claim['catalog']['path'])) as stream:
                if guard.signature(os.fstat(stream.fileno())) != claim['signature']:
                    raise guard.Unavailable('Reviewed publication changed during final private proof')
        request = dict(
            version=1,
            action="prepare-registration",
            census=census,
            inventory={
                key: observed["inventory"][key]
                for key in ("version", "members", "pages", "payload")
            },
            allowed=review["allowed"],
            rejected=review["rejected"],
            evidence={
                key: review["evidence"][key] for key in ("sha256", "description")
            },
            created=review["created"],
        )
        # Validate the exact existing public protocol; do not invent repair actions.
        from publication_api import request as validate_request

        validate_request(json.dumps(request))
        body = dict(
            version=1,
            kind="publication-correction-plan",
            executable=False,
            readiness="registration-preparation-only",
            scope=scope,
            registration_request=request,
            registration_commit={
                "action": "register",
                "requires": "exact-token-returned-by-native-prepare",
            },
            observations=observed,
            writer_identity=guard.writer_identity(writer),
            backup=restored,
            evidence=review["evidence"],
            repeat=repeat,
        )
        return dict(body, token=guard.canonical_digest(body))


def write(value, output):
    output = path(output)
    if any(
        output.is_relative_to(path(root)) for root in value["scope"]["library_roots"]
    ):
        raise guard.Unavailable("Private plans must remain outside scanned libraries")
    if value.get("token") != guard.canonical_digest(
        {key: item for key, item in value.items() if key != "token"}
    ):
        raise guard.Unavailable("Correction plan binding changed")
    folder = output.parent.lstat()
    if (
        not stat.S_ISDIR(folder.st_mode)
        or folder.st_uid != os.geteuid()
        or stat.S_IMODE(folder.st_mode) != 0o700
    ):
        raise guard.Unavailable("Private owned output directory required")
    raw = guard.compact(value)
    if len(raw) > LIMIT:
        raise guard.Unavailable("Correction plan exceeds bound")
    directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        bound = os.fstat(directory)
        if (bound.st_dev, bound.st_ino, bound.st_uid, stat.S_IMODE(bound.st_mode)) != (
            folder.st_dev,
            folder.st_ino,
            os.geteuid(),
            0o700,
        ):
            raise guard.Unavailable("Private output directory changed")
        fd = os.open(
            output.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        # Partial files remain in this bound private directory for explicit review.
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(directory)
        current = output.parent.lstat()
        if (
            current.st_dev,
            current.st_ino,
            current.st_uid,
            stat.S_IMODE(current.st_mode),
        ) != (bound.st_dev, bound.st_ino, os.geteuid(), 0o700) or any(
            item.is_symlink() for item in (output.parent, *output.parents)
        ):
            raise guard.Unavailable("Private output directory changed")
    finally:
        os.close(directory)
