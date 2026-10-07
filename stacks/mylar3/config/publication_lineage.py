"""Read-only, reviewed nested-metadata lineage. No alias or publication rights."""

from contextlib import closing
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import zipfile

if __package__:
    from . import publication_guard as guard, publication_native as native
    from . import (
        publication_transaction as transaction,
        metadata_repair,
        tagger_archive,
    )
else:
    import publication_guard as guard
    import publication_native as native
    import publication_transaction as transaction
    import metadata_repair
    import tagger_archive

FIELDS = {
    "version",
    "source",
    "prepared",
    "source_sha256",
    "prepared_sha256",
    "owner",
    "census",
    "mapping",
    "preservation",
    "review",
    "backup",
}


def checksum(value):
    return isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value) is not None


def path(value):
    if not isinstance(value, str):
        raise guard.Unavailable("Exact lineage path required")
    result = Path(value)
    if (
        not result.is_absolute()
        or ".." in result.parts
        or any(p.is_symlink() for p in (result, *result.parents))
    ):
        raise guard.Unavailable("Linked or ambiguous lineage path")
    return result


def private(value):
    result = path(value)
    parent = result.parent.lstat()
    if (
        not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != os.geteuid()
        or stat.S_IMODE(parent.st_mode) != 0o700
    ):
        raise guard.Unavailable("Private lineage evidence directory required")
    with guard.regular(result) as stream:
        info = guard.signature(os.fstat(stream.fileno()))
    if info[6] != os.geteuid() or info[8] != 1 or stat.S_IMODE(info[5]) != 0o600:
        raise guard.Unavailable("Private exclusive lineage evidence required")
    signature, sha = guard.file_hash(result)
    if signature != info:
        raise guard.Unavailable("Lineage evidence changed during reading")
    return dict(path=str(result), signature=signature, sha256=sha)


def private_json(value, expected):
    before = private(value)
    if before["sha256"] != expected:
        raise guard.Unavailable("Reviewed lineage evidence changed")
    result = guard.private_json(path(value))
    if not guard.same_json(before, private(value)):
        raise guard.Unavailable("Lineage document changed during reading")
    return result, before


def database(value):
    value = path(str(value))
    if any(
        os.path.lexists(str(value) + suffix) for suffix in ("-journal", "-wal", "-shm")
    ):
        raise guard.Unavailable("Lineage database requires recovery")
    with closing(
        sqlite3.connect(value.as_uri() + "?mode=ro&immutable=1", uri=True)
    ) as db:
        deadline = time.monotonic() + guard.TIMEOUT
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        if db.execute("PRAGMA quick_check").fetchmany(2) != [("ok",)]:
            raise guard.Unavailable("Lineage restore database is unreadable")


def backup(writer, request):
    import mylar

    value = request["backup"]
    if not isinstance(value, dict) or set(value) != {
        "manifest",
        "manifest_sha256",
        "restore",
        "restore_sha256",
    }:
        raise guard.Unavailable("Exact verified lineage backup required")
    if not checksum(value["manifest_sha256"]) or not checksum(value["restore_sha256"]):
        raise guard.Unavailable("Exact backup evidence hashes required")
    manifest, manifest_proof = private_json(value["manifest"], value["manifest_sha256"])
    restored, restore_proof = private_json(value["restore"], value["restore_sha256"])
    sources = dict(
        source=request["source"],
        catalog=str(Path(mylar.DATA_DIR) / "mylar.db"),
        workflow=str(Path(mylar.DATA_DIR) / "workflow.sqlite"),
        marker=str(writer.root / "publication-v1.json"),
    )
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"version", "files"}
        or type(manifest["version"]) is not int
        or manifest["version"] != 1
        or not isinstance(manifest["files"], list)
        or len(manifest["files"]) != len(sources)
    ):
        raise guard.Unavailable("Complete lineage backup manifest required")
    facts, roles, identities = [], set(), set()
    for row in manifest["files"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"role", "source", "backup", "restore", "sha256"}
            or row["role"] not in sources
            or row["role"] in roles
            or row["source"] != sources[row["role"]]
            or not checksum(row["sha256"])
        ):
            raise guard.Unavailable("Wrong lineage backup scope")
        roles.add(row["role"])
        source = path(row["source"])
        sig, sha = guard.file_hash(source)
        if sha != row["sha256"] or sig[8] != 1:
            raise guard.Unavailable("Current lineage backup baseline changed")
        copies = [private(row[key]) for key in ("backup", "restore")]
        if (
            any(copy["sha256"] != sha for copy in copies)
            or path(row["backup"]).parent == path(row["restore"]).parent
        ):
            raise guard.Unavailable("Independent lineage restore mismatch")
        for copy_path, signature in [
            (source, sig),
            *[(path(copy["path"]), copy["signature"]) for copy in copies],
        ]:
            if tuple(signature[:2]) in identities:
                raise guard.Unavailable("Aliased lineage backup or restore")
            identities.add(tuple(signature[:2]))
            if row["role"] in ("catalog", "workflow"):
                database(copy_path)
        facts.append(
            dict(
                role=row["role"],
                source=dict(path=str(source), signature=sig, sha256=sha),
                copies=copies,
            )
        )
    expected = dict(
        version=1,
        manifest_sha256=value["manifest_sha256"],
        files=[
            dict(role=row["role"], sha256=row["sha256"]) for row in manifest["files"]
        ],
    )
    if not guard.same_json(restored, expected):
        raise guard.Unavailable(
            "Verified restore receipt does not match lineage backup"
        )
    return dict(manifest=manifest_proof, restore=restore_proof, files=facts)


def validate(request):
    if (
        not isinstance(request, dict)
        or set(request) != FIELDS
        or type(request["version"]) is not int
        or request["version"] != 1
        or not checksum(request["source_sha256"])
        or not checksum(request["prepared_sha256"])
        or not isinstance(request["review"], dict)
        or set(request["review"]) != {"path", "sha256"}
        or not checksum(request["review"]["sha256"])
        or not isinstance(request["mapping"], list)
        or len(request["mapping"]) != 1
        or not isinstance(request["mapping"][0], dict)
        or set(request["mapping"][0]) != {"from", "to"}
    ):
        raise guard.Unavailable(
            "Exact reviewed nested-metadata lineage request required"
        )
    # Serialization makes a private immutable request; arbitrary Python values
    # and an unbounded caller object cannot become evidence.
    guard.exact_owner(request["owner"])
    guard.census_value(request["census"])
    for key in ("source", "prepared"):
        value = request[key]
        if (
            not isinstance(value, str)
            or not Path(value).is_absolute()
            or ".." in Path(value).parts
        ):
            raise guard.Unavailable("Exact lineage request path required")
    if any(
        not isinstance(value, str) or not value
        for value in request["mapping"][0].values()
    ):
        raise guard.Unavailable("Exact lineage member mapping required")
    pair = request["preservation"]
    if not isinstance(pair, dict) or set(pair) != {"original", "restore"}:
        raise guard.Unavailable("Exact lineage retained pair required")
    for item in pair.values():
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "signature"}
            or not isinstance(item["path"], str)
            or not Path(item["path"]).is_absolute()
            or ".." in Path(item["path"]).parts
            or not isinstance(item["signature"], (list, tuple))
            or len(item["signature"]) != 9
            or any(
                type(number) is not int or number < 0 for number in item["signature"]
            )
        ):
            raise guard.Unavailable("Exact lineage retained file facts required")
        signature = item["signature"]
        if (
            not stat.S_ISREG(signature[5])
            or stat.S_IMODE(signature[5]) != 0o600
            or signature[8] != 1
        ):
            raise guard.Unavailable(
                "Private exclusive lineage retained signature required"
            )
    if (
        pair["original"]["path"] == pair["restore"]["path"]
        or pair["original"]["signature"][:2] == pair["restore"]["signature"][:2]
    ):
        raise guard.Unavailable("Independent lineage retained pair required")
    backup = request["backup"]
    if not isinstance(backup, dict) or set(backup) != {
        "manifest",
        "manifest_sha256",
        "restore",
        "restore_sha256",
    }:
        raise guard.Unavailable("Exact lineage backup request required")
    for key in ("manifest", "restore"):
        if (
            not checksum(backup[key + "_sha256"])
            or not isinstance(backup[key], str)
            or not Path(backup[key]).is_absolute()
            or ".." in Path(backup[key]).parts
        ):
            raise guard.Unavailable("Exact lineage backup document required")
    if (
        not isinstance(request["review"]["path"], str)
        or not Path(request["review"]["path"]).is_absolute()
        or ".." in Path(request["review"]["path"]).parts
    ):
        raise guard.Unavailable("Exact lineage review document required")
    return guard.decode_json(guard.compact(request))


def migration(source, prepared, mapping):
    old = tagger_archive.snapshot(source, allow_nested_metadata=True)
    new = tagger_archive.snapshot(prepared)
    with tagger_archive.regular(source) as stream, zipfile.ZipFile(stream) as archive:
        nested, target, merged = metadata_repair.layout(archive)
    if mapping != [dict(**{"from": nested}, to=target)]:
        raise guard.Unavailable(
            "Only the exact reviewed nested provenance mapping is supported"
        )
    members = tuple(
        (target if name == nested else name, size, sha)
        for name, size, sha in old.members
    )
    attributes = tuple(
        (target if row[0] == nested else row[0], *row[1:]) for row in old.attributes
    )
    if old.xml is None:
        nested_attributes = next(row for row in old.attributes if row[0] == nested)
        attributes = (*attributes, ("ComicInfo.xml", *nested_attributes[1:]))
    if (
        new.members != members
        or new.attributes != attributes
        or new.comment != old.comment
        or new.xml != merged
    ):
        raise guard.Unavailable(
            "Derivative lost members, reader order, attributes or exact metadata migration"
        )
    if (
        tagger_archive.identity(source.lstat()) != old.identity
        or tagger_archive.identity(prepared.lstat()) != new.identity
    ):
        raise guard.Unavailable("Derivative changed during metadata proof")
    return dict(
        mapping=mapping,
        root_sha256=hashlib.sha256(merged).hexdigest(),
        member_order=[row[0] for row in old.attributes],
        derivative_order=[row[0] for row in new.attributes],
    )


def observe(writer, raw):
    import mylar
    from mylar import native_writers

    request = validate(raw)
    if not writer.local[1].depth:
        raise guard.Unavailable("Active shared writer required for lineage observation")
    census = native_writers.admission(writer)
    if not guard.same_json(census, request["census"]):
        raise guard.Unavailable("Lineage census changed")
    source, prepared = path(request["source"]), path(request["prepared"])
    if source.suffix != ".cbz" or prepared.suffix != ".cbz" or source == prepared:
        raise guard.Unavailable(
            "Nested lineage requires separate exact CBZ source and derivative"
        )
    roots = [Path(mylar.CONFIG.DESTINATION_DIR)]
    if any(prepared.is_relative_to(root) for root in roots):
        raise guard.Unavailable(
            "Prepared derivative must remain outside scanned library"
        )
    prepared_proof = private(str(prepared))
    original = native.require(
        source,
        issueid=request["owner"]["issueid"],
        comicid=request["owner"]["parentcomicid"],
    )
    if (
        original is None
        or not guard.same_json(original["owner"], request["owner"])
        or original["inventory"]["source_sha256"] != request["source_sha256"]
        or prepared_proof["sha256"] != request["prepared_sha256"]
    ):
        raise guard.Unavailable("Current exact lineage source or owner changed")
    selected = guard.observe_owners(
        Path(mylar.DATA_DIR) / "mylar.db", writer, [request["owner"]], roots
    )["observed"]
    if selected[0]["catalog"]["path"] != str(source):
        raise guard.Unavailable("Lineage source is not the current correct publication")
    transaction.preserved_pair(request["preservation"], request["source_sha256"])
    for row in request["preservation"].values():
        if any(path(row["path"]).is_relative_to(root) for root in roots):
            raise guard.Unavailable(
                "Retained lineage originals must remain outside scanned library"
            )
    review, review_proof = private_json(
        request["review"]["path"], request["review"]["sha256"]
    )
    reviewed = {
        key: value for key, value in request.items() if key not in ("review", "backup")
    }
    if not guard.same_json(
        review, dict(version=1, kind="reviewed-nested-lineage", request=reviewed)
    ):
        raise guard.Unavailable("Explicit review does not bind this exact derivative")
    restored = backup(writer, request)
    change = migration(source, prepared, request["mapping"])
    derivative = guard.inventory(prepared)
    original_pages = original["inventory"]["pages"]
    if (
        derivative["pages"] != original_pages
        or derivative["payload"] == original["inventory"]["payload"]
    ):
        raise guard.Unavailable(
            "Derivative page order changed or provenance migration is absent"
        )
    # Fresh proof follows every archive/copy/document read. Nothing below this
    # line invokes a caller or a source mutation routine.
    final = native.require(
        source,
        issueid=request["owner"]["issueid"],
        comicid=request["owner"]["parentcomicid"],
    )
    final_selected = guard.observe_owners(
        Path(mylar.DATA_DIR) / "mylar.db", writer, [request["owner"]], roots
    )["observed"]
    if not guard.same_json(final, original) or not guard.same_json(
        final_selected, selected
    ):
        raise guard.Unavailable(
            "Lineage source or current catalog changed during verification"
        )
    transaction.preserved_pair(request["preservation"], request["source_sha256"])
    if (
        not guard.same_json(private(str(prepared)), prepared_proof)
        or not guard.same_json(private(request["review"]["path"]), review_proof)
        or not guard.same_json(backup(writer, request), restored)
        or not guard.same_json(native_writers.admission(writer), census)
    ):
        raise guard.Unavailable(
            "Retained lineage evidence changed during final source proof"
        )
    transaction.preserved_pair(request["preservation"], request["source_sha256"])
    if not guard.same_json(
        private(str(prepared)), prepared_proof
    ) or not guard.same_json(private(request["review"]["path"]), review_proof):
        raise guard.Unavailable(
            "Lineage private evidence changed during final admission"
        )
    for role in ("catalog", "source"):
        item = next(row["source"] for row in restored["files"] if row["role"] == role)
        signature, sha = guard.file_hash(item["path"])
        if not guard.same_json(signature, item["signature"]) or sha != item["sha256"]:
            raise guard.Unavailable(
                "Lineage current source baseline changed after final reads"
            )
    return dict(
        writer=guard.writer_identity(writer),
        source=original,
        observed=selected,
        derivative=derivative,
        migration=change,
        prepared=prepared_proof,
        review=review_proof,
        backup=restored,
    )


def prepare(writer, request):
    request = validate(request)
    facts = observe(writer, request)
    body = dict(
        version=1,
        kind="reviewed-nested-lineage",
        executable=False,
        readiness="explicit-adoption-required",
        request=request,
        facts=facts,
    )
    return dict(body, token=guard.canonical_digest(body))


def verify(writer, plan):
    if (
        not isinstance(plan, dict)
        or set(plan)
        != {"version", "kind", "executable", "readiness", "request", "facts", "token"}
        or type(plan["version"]) is not int
        or plan["version"] != 1
        or plan["kind"] != "reviewed-nested-lineage"
        or plan["executable"] is not False
        or plan["readiness"] != "explicit-adoption-required"
        or plan["token"]
        != guard.canonical_digest({k: v for k, v in plan.items() if k != "token"})
    ):
        raise guard.Unavailable("Immutable reviewed lineage proof required")
    if not guard.same_json(observe(writer, plan["request"]), plan["facts"]):
        raise guard.Unavailable("Reviewed lineage proof is stale")
    return plan["facts"]
