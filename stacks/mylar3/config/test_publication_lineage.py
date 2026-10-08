"""Actual native owner, archive migration, retained-copy and restore controls."""

import copy
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import zipfile

import metadata_repair
import publication_guard as guard
import publication_lineage as lineage
import publication_native as native
import test_publication_rename as fixtures
from test_publication_guard import TOOL_ROOT


@unittest.skipUnless((Path(TOOL_ROOT) / 'lib/archive_backend.py').is_file(),
                     'offline native archive verifier required')
class LineageTests(unittest.TestCase):
    connection = fixtures.RenameTests.connection
    call = fixtures.RenameTests.call
    bootstrap = fixtures.RenameTests.bootstrap
    prepare = fixtures.RenameTests.prepare
    registered = fixtures.RenameTests.registered

    def setUp(self):
        fixtures.RenameTests.setUp(self)
        with zipfile.ZipFile(self.source, "w") as archive:
            archive.comment = b"preserved release comment"
            archive.writestr("pages/", b"")
            archive.writestr("pages/01.jpg", b"one")
            archive.writestr("pages/02.jpg", b"two")
            archive.writestr("extras/provenance.txt", b"release evidence")
            archive.writestr(
                "ComicInfo.xml",
                "<ComicInfo><Series>Publication</Series><Number>1</Number><Notes>original note</Notes></ComicInfo>",
            )
            archive.writestr(
                "metadata/ComicInfo.xml",
                "<ComicInfo><Series>Publication</Series><Number>1</Number><Writer>Writer</Writer></ComicInfo>",
            )
        self.private = self.root / "lineage-private"
        self.private.mkdir(mode=0o700)
        self.derivative = self.private / "prepared.cbz"
        metadata_repair.prepare(self.source, self.derivative)
        self.derivative.chmod(0o600)
        pair = {}
        for name in ("original", "restore"):
            target = self.private / (name + ".cbz")
            shutil.copyfile(self.source, target)
            target.chmod(0o600)
            pair[name] = dict(path=str(target), signature=guard.file_hash(target)[0])
        with self.writer.hold():
            census = self.runtime.admission(self.writer)
        self.request = dict(
            version=1,
            source=str(self.source),
            prepared=str(self.derivative),
            source_sha256=guard.file_hash(self.source)[1],
            prepared_sha256=guard.file_hash(self.derivative)[1],
            owner=self.owner,
            census=census,
            mapping=[
                {"from": "metadata/ComicInfo.xml", "to": "metadata/SourceMetadata.xml"}
            ],
            preservation=pair,
            review={},
            backup={},
        )
        self.review = self.private / "review.json"
        self.refresh_review()
        self.capture_backup()

    def document(self, path, value):
        path.write_bytes(guard.compact(value))
        path.chmod(0o600)
        return guard.file_hash(path)[1]

    def refresh_review(self):
        body = {
            key: value
            for key, value in self.request.items()
            if key not in ("review", "backup")
        }
        sha = self.document(
            self.review, dict(version=1, kind="reviewed-nested-lineage", request=body)
        )
        self.request["review"] = dict(path=str(self.review), sha256=sha)

    def capture_backup(self):
        self.backupdir = self.root / "backup"
        self.backupdir.mkdir(mode=0o700)
        self.restoredir = self.root / "restored"
        self.restoredir.mkdir(mode=0o700)
        rows = []
        for role, source in dict(
            source=self.source,
            catalog=self.root / "mylar.db",
            workflow=self.store.path,
            marker=self.writer.root / "publication-v1.json",
        ).items():
            backup = self.backupdir / role
            restore = self.restoredir / role
            shutil.copyfile(source, backup)
            shutil.copyfile(backup, restore)
            backup.chmod(0o600)
            restore.chmod(0o600)
            rows.append(
                dict(
                    role=role,
                    source=str(source),
                    backup=str(backup),
                    restore=str(restore),
                    sha256=guard.file_hash(source)[1],
                )
            )
        self.manifest = self.private / "backup.json"
        sha = self.document(self.manifest, dict(version=1, files=rows))
        self.restore = self.private / "restore.json"
        restored_sha = self.document(
            self.restore,
            dict(
                version=1,
                manifest_sha256=sha,
                files=[dict(role=row["role"], sha256=row["sha256"]) for row in rows],
            ),
        )
        self.request["backup"] = dict(
            manifest=str(self.manifest),
            manifest_sha256=sha,
            restore=str(self.restore),
            restore_sha256=restored_sha,
        )

    def plan(self):
        with self.writer.hold():
            return lineage.prepare(self.writer, self.request)

    def refused(self):
        with (
            self.writer.hold(),
            self.assertRaises((guard.Unavailable, native.Review, ValueError)),
        ):
            lineage.prepare(self.writer, self.request)

    def test_actual_nested_provenance_bijection_is_read_only_and_gives_no_alias_rights(
        self,
    ):
        before = {
            path: path.read_bytes()
            for path in (
                self.source,
                self.derivative,
                self.root / "mylar.db",
                self.store.path,
            )
        }
        plan = self.plan()
        self.assertIs(plan["executable"], False)
        self.assertEqual(plan["readiness"], "explicit-adoption-required")
        self.assertNotEqual(
            plan["facts"]["source"]["inventory"]["payload"],
            plan["facts"]["derivative"]["payload"],
        )
        with self.writer.hold():
            self.assertEqual(lineage.verify(self.writer, plan), plan["facts"])
        for path, value in before.items():
            self.assertEqual(path.read_bytes(), value)
        self.assertFalse(self.writer.fenced(release=True))
        self.assertFalse(self.writer.fenced(tagger=True))

    def test_wrong_owner_mapping_or_review_cannot_prepare(self):
        initial = copy.deepcopy(self.request)
        for mutate in (
            lambda: self.request["owner"].update(issueid="999"),
            lambda: self.request["mapping"][0].update(to="metadata/Other.xml"),
            lambda: self.request["review"].update(sha256="a" * 64),
        ):
            self.request = copy.deepcopy(initial)
            mutate()
            self.refused()

    def test_changed_source_or_catalog_stales_existing_proof(self):
        plan = self.plan()
        with self.connection() as db:
            db.execute(
                "UPDATE issues SET Status='Wanted' WHERE IssueID=?",
                (self.owner["issueid"],),
            )
        with self.writer.hold(), self.assertRaises((guard.Unavailable, native.Review)):
            lineage.verify(self.writer, plan)

    def test_same_payload_changed_root_metadata_is_not_the_reviewed_source(self):
        plan = self.plan()
        with zipfile.ZipFile(self.source) as old:
            rows = [(info, old.read(info)) for info in old.infolist()]
        with zipfile.ZipFile(self.source, "w") as new:
            for info, data in rows:
                new.writestr(
                    info,
                    data
                    if info.filename != "ComicInfo.xml"
                    else b"<ComicInfo><Series>Publication</Series><Number>1</Number></ComicInfo>",
                )
        with self.writer.hold(), self.assertRaises((guard.Unavailable, native.Review)):
            lineage.verify(self.writer, plan)

    def test_changed_pages_extras_and_metadata_merge_are_refused(self):
        expected = self.derivative.read_bytes()
        for member in ("pages/01.jpg", "extras/provenance.txt", "ComicInfo.xml"):
            self.derivative.write_bytes(expected)
            with zipfile.ZipFile(self.derivative) as old:
                rows = [(info, old.read(info)) for info in old.infolist()]
            with zipfile.ZipFile(self.derivative, "w") as new:
                for info, data in rows:
                    new.writestr(
                        info,
                        b"<ComicInfo><Series>Publication</Series><Number>1</Number></ComicInfo>"
                        if info.filename == member == "ComicInfo.xml"
                        else b"changed"
                        if info.filename == member
                        else data,
                    )
            self.request["prepared_sha256"] = guard.file_hash(self.derivative)[1]
            self.refresh_review()
            self.refused()

    def test_member_order_and_comment_changes_are_not_lossless_derivatives(self):
        with zipfile.ZipFile(self.derivative) as old:
            rows = [(info, old.read(info)) for info in old.infolist()]
        with zipfile.ZipFile(self.derivative, "w") as new:
            for info, data in reversed(rows):
                new.writestr(info, data)
        self.request["prepared_sha256"] = guard.file_hash(self.derivative)[1]
        self.refresh_review()
        self.refused()

    def test_missing_backup_role_and_mismatched_restored_copy_hold(self):
        (self.restoredir / "source").write_bytes(b"unverified restore")
        self.refused()
        shutil.copyfile(self.backupdir / "source", self.restoredir / "source")
        value = json.loads(self.manifest.read_bytes())
        value["files"].pop()
        self.request["backup"]["manifest_sha256"] = self.document(self.manifest, value)
        self.refused()

    def test_shared_original_and_changed_retained_copy_are_refused(self):
        row = self.request["preservation"]["restore"]
        target = Path(row["path"])
        target.unlink()
        target.hardlink_to(Path(self.request["preservation"]["original"]["path"]))
        self.refused()

    def test_private_evidence_permissions_links_and_library_prepared_path_hold(self):
        self.review.chmod(0o644)
        self.refused()
        self.review.chmod(0o600)
        self.request["prepared"] = str(self.source)
        self.refused()

    def test_final_native_proof_cannot_hide_retained_copy_or_review_replacement(self):
        actual = native.require
        calls = 0

        def change(*args, **kwargs):
            nonlocal calls
            result = actual(*args, **kwargs)
            calls += 1
            if calls == 2:
                Path(self.request["preservation"]["original"]["path"]).write_bytes(
                    b"foreign retained original"
                )
            return result

        with patch.object(native, "require", side_effect=change):
            self.refused()

    def test_forged_plan_digest_wrong_writer_or_missing_fence_is_not_an_admission(self):
        plan = self.plan()
        plan["facts"]["migration"]["root_sha256"] = "f" * 64
        with self.writer.hold(), self.assertRaises(guard.Unavailable):
            lineage.verify(self.writer, plan)
        with self.assertRaises(guard.Unavailable):
            lineage.prepare(self.writer, self.request)

    def test_malformed_request_is_bounded_and_strict(self):
        for value in (
            dict(self.request, version=True),
            dict(self.request, unknown=True),
            dict(self.request, mapping=[]),
        ):
            with self.writer.hold(), self.assertRaises(guard.Unavailable):
                lineage.prepare(self.writer, value)

    def test_final_backup_read_changed_source_cannot_create_stale_certificate(self):
        real = lineage.backup
        count = 0

        def change(*args, **kwargs):
            nonlocal count
            result = real(*args, **kwargs)
            count += 1
            if count == 2:
                self.source.write_bytes(b"changed during final backup read")
            return result

        with (
            self.writer.hold(),
            patch.object(lineage, "backup", side_effect=change),
            self.assertRaisesRegex(guard.Unavailable, "after final reads"),
        ):
            lineage.prepare(self.writer, self.request)
        self.assertEqual(count, 2)
        self.assertEqual(self.source.read_bytes(), b"changed during final backup read")


if __name__ == "__main__":
    unittest.main()
