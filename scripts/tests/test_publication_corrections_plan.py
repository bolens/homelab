"""Offline plan evidence uses real native catalogs, authority and archive inventories."""

from contextlib import closing, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
plans = importlib.import_module("publication_corrections_plan")
Store = importlib.import_module("workflow_store").Store

SPEC = importlib.util.spec_from_file_location(
    "prepare_corrections", ROOT / "scripts/prepare-publication-corrections.py"
)
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


class CorrectionPlanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / "config"
        self.config.mkdir()
        self.library = self.root / "library"
        self.library.mkdir()
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.tool = self.root / "page-protocol"
        (self.tool / "lib").mkdir(parents=True)
        (self.tool / "lib/comics.py").write_text(
            "PAGE_EXTENSIONS=" + repr(plans.guard.PAGE_EXTENSIONS)
        )
        self.correct = self.archive("correct.cbz", b"actual page")
        self.repeat = self.archive("wrong-label.cbz", b"actual page")
        self.catalog = self.config / "mylar.db"
        with closing(sqlite3.connect(self.catalog)) as db:
            db.executescript(
                "CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT);"
                "CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Location TEXT,Status TEXT);"
                "CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,ReleaseComicID TEXT,Location TEXT,Status TEXT,Deleted INT);"
            )
            for comic in ("456", "888"):
                db.execute(
                    "INSERT INTO comics VALUES (?,?)", (comic, str(self.library))
                )
            db.execute(
                "INSERT INTO issues VALUES (?,?,?,?)",
                ("123", "456", self.correct.name, "Downloaded"),
            )
            db.execute(
                "INSERT INTO issues VALUES (?,?,?,?)",
                ("999", "888", self.repeat.name, "Downloaded"),
            )
            db.commit()
        self.store = Store(self.config)
        self.writer = plans.Writer(self.config / "media-writer", create=True)
        state = plans.guard.RegistryState(self.store.path, self.writer)
        token = state.prepare_bootstrap(
            dict(
                manifest_sha256="a" * 64,
                restore_sha256="b" * 64,
                description="Isolated test restore",
            ),
            epoch="e" * 64,
        )
        state.initialize(token, accepted_token=token)
        self.scope = dict(
            version=1,
            config_dir=str(self.config),
            library_roots=[str(self.library)],
            tool_root=str(self.tool),
        )
        self.allowed = dict(
            table="issues", issueid="123", parentcomicid="456", releasecomicid="456"
        )
        self.rejected = dict(
            table="issues", issueid="999", parentcomicid="888", releasecomicid="888"
        )
        evidence = self.private / "reviewed-evidence"
        evidence.write_bytes(b"Explicit operator-reviewed actual publication evidence")
        evidence.chmod(0o600)
        census = state.snapshot()[0]
        self.review = dict(
            version=1,
            census=census,
            allowed=[self.allowed],
            rejected=[self.rejected],
            correct=[
                dict(
                    owner=self.allowed,
                    path=str(self.correct),
                    sha256=self.sha(self.correct),
                )
            ],
            repeat=dict(
                owner=self.rejected, path=str(self.repeat), sha256=self.sha(self.repeat)
            ),
            evidence=dict(
                path=str(evidence),
                sha256=self.sha(evidence),
                description="Reviewed actual fixture pages",
            ),
            backup=None,
            created=1,
        )
        self.backups()

    def archive(self, name, page):
        target = self.library / name
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("01.jpg", page)
            archive.writestr("ComicInfo.xml", "<ComicInfo/>")
        return target

    def sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def private_json(self, path, value):
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return path

    def backups(self):
        backup = self.private / "backup"
        backup.mkdir(mode=0o700, exist_ok=True)
        restore = self.private / "restore"
        restore.mkdir(mode=0o700, exist_ok=True)
        files = []
        sources = dict(
            catalog=self.catalog,
            workflow=self.store.path,
            marker=self.writer.root / "publication-v1.json",
            correct_0=self.correct,
            repeat=self.repeat,
        )
        for role, source in sources.items():
            for folder in (backup, restore):
                shutil.copyfile(source, folder / role)
                (folder / role).chmod(0o600)
            files.append(
                dict(
                    role=role,
                    source=str(source),
                    backup=str(backup / role),
                    restore=str(restore / role),
                    sha256=self.sha(source),
                )
            )
        self.manifest = self.private_json(
            self.private / "manifest.json", dict(version=1, files=files)
        )
        self.restore_receipt = self.private_json(
            self.private / "restore.json",
            dict(
                version=1,
                manifest_sha256=self.sha(self.manifest),
                files=[dict(role=row["role"], sha256=row["sha256"]) for row in files],
            ),
        )
        self.review["backup"] = dict(
            manifest_path=str(self.manifest),
            manifest_sha256=self.sha(self.manifest),
            restore_receipt_path=str(self.restore_receipt),
            restore_receipt_sha256=self.sha(self.restore_receipt),
        )

    def prepare(self):
        return plans.prepare(self.scope, self.review)

    def test_complete_plan_binds_exact_existing_api_and_refuses_repeat_execution(self):
        before = (
            self.catalog.read_bytes(),
            self.store.path.read_bytes(),
            self.correct.read_bytes(),
            self.repeat.read_bytes(),
        )
        result = self.prepare()
        self.assertFalse(result["executable"])
        self.assertFalse(result["repeat"]["executable"])
        self.assertEqual(
            result["registration_request"]["action"], "prepare-registration"
        )
        self.assertEqual(
            result["repeat"]["readiness"],
            "fresh-native-retention-review-required",
        )
        self.assertIsNone(result["repeat"]["failed_release_binding"])
        self.assertEqual(
            before,
            (
                self.catalog.read_bytes(),
                self.store.path.read_bytes(),
                self.correct.read_bytes(),
                self.repeat.read_bytes(),
            ),
        )
        output = self.private / "plan.json"
        plans.write(result, str(output))
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(plans.read(str(output))[0]["token"], result["token"])
        with self.assertRaises(FileExistsError):
            plans.write(result, str(output))

    def test_comic_backups_larger_than_json_limit_remain_bounded_and_eligible(self):
        for value in (self.correct, self.repeat):
            self.archive(value.name, b"p" * (5 * 1024 * 1024))
        self.review["correct"][0]["sha256"] = self.sha(self.correct)
        self.review["repeat"]["sha256"] = self.sha(self.repeat)
        self.backups()
        self.assertFalse(self.prepare()["executable"])

    def test_changed_missing_or_wrong_correct_owner_is_held(self):
        self.review["correct"][0]["owner"] = self.rejected
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()
        self.review["correct"][0]["owner"] = self.allowed
        self.correct.unlink()
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()

    def test_same_payload_correct_metadata_sha_drift_requires_new_review(self):
        with zipfile.ZipFile(self.correct, "a") as archive:
            archive.comment = b"changed archive generation"
        before = self.correct.read_bytes()
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()
        self.assertEqual(self.correct.read_bytes(), before)

    def test_required_backup_role_cannot_be_omitted_or_substituted(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["files"] = [
            row for row in manifest["files"] if row["role"] != "workflow"
        ]
        self.private_json(self.manifest, manifest)
        self.review["backup"]["manifest_sha256"] = self.sha(self.manifest)
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()

    def test_wrong_current_owner_and_annual_shadow_are_held(self):
        for sql, args in [
            ("UPDATE issues SET ComicID=? WHERE IssueID=?", ("888", "123")),
            (
                "INSERT INTO annuals VALUES (?,?,?,?,?,?)",
                ("123", "456", "456", None, "Wanted", 1),
            ),
        ]:
            with closing(sqlite3.connect(self.catalog)) as db:
                db.execute(sql, args)
                db.commit()
            with self.assertRaises(plans.guard.Unavailable):
                self.prepare()

    def test_changed_source_and_legitimate_different_payload_remain_untouched(self):
        self.archive(self.repeat.name, b"legitimate different release")
        before = self.repeat.read_bytes()
        self.review["repeat"]["sha256"] = self.sha(self.repeat)
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()
        self.assertEqual(self.repeat.read_bytes(), before)
        self.assertTrue(self.correct.exists())

    def test_shared_inode_repeat_cannot_relocate_protected_original(self):
        self.repeat.unlink()
        os.link(self.correct, self.repeat)
        self.review["repeat"]["sha256"] = self.sha(self.repeat)
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()
        self.assertTrue(self.correct.exists())
        self.assertTrue(self.repeat.exists())

    def test_changed_census_or_missing_authority_never_bootstraps(self):
        self.review["census"]["revision"] += 1
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()
        self.review["census"]["revision"] -= 1
        marker = self.writer.root / "publication-v1.json"
        marker.unlink()
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()
        self.assertFalse(marker.exists())

    def test_missing_backup_and_different_restored_copy_are_held(self):
        saved = json.loads(self.manifest.read_text())
        path = Path(saved["files"][0]["restore"])
        path.write_bytes(b"wrong isolated restore")
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()
        path.unlink()
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()

    def test_malformed_evidence_private_links_and_output_permissions_are_held(self):
        evidence = Path(self.review["evidence"]["path"])
        evidence.chmod(0o644)
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()
        evidence.chmod(0o600)
        self.review["evidence"]["unexpected"] = "guessed release provenance"
        with self.assertRaises(plans.guard.Unavailable):
            self.prepare()
        self.review["evidence"].pop("unexpected")
        result = self.prepare()
        public = self.root / "public"
        public.mkdir(mode=0o755)
        with self.assertRaises(plans.guard.Unavailable):
            plans.write(result, str(public / "public.json"))
        target = self.private / "linked.json"
        target.symlink_to(self.private / "absent")
        with self.assertRaises(plans.guard.Unavailable):
            plans.write(result, str(target))

    def test_output_directory_replacement_cannot_disclose_plan_into_foreign_folder(
        self,
    ):
        result = self.prepare()
        actual = plans.os.open
        saved = self.root / "retained-private"
        foreign = self.root / "foreign"
        foreign.mkdir(mode=0o755)

        def moved(name, flags, *args, **kwargs):
            fd = actual(name, flags, *args, **kwargs)
            if Path(name) == self.private and flags & os.O_DIRECTORY:
                self.private.rename(saved)
                self.private.symlink_to(foreign, target_is_directory=True)
            return fd

        with (
            patch.object(plans.os, "open", side_effect=moved),
            self.assertRaises(plans.guard.Unavailable),
        ):
            plans.write(result, str(self.private / "plan.json"))
        self.assertFalse((foreign / "plan.json").exists())
        self.assertEqual((saved / "plan.json").stat().st_mode & 0o777, 0o600)

    def test_copy_mutation_during_final_owner_observation_holds(self):
        actual = plans.guard.observe_owners
        calls = [0]

        def drift(*args, **kwargs):
            result = actual(*args, **kwargs)
            calls[0] += 1
            if calls[0] == 3:
                (self.private / "restore/correct_0").write_bytes(b"changed restore")
            return result

        with (
            patch.object(plans.guard, "observe_owners", side_effect=drift),
            self.assertRaises(plans.guard.Unavailable),
        ):
            self.prepare()

    def test_cli_is_plan_only_and_diagnostics_never_disclose_private_paths(self):
        scope = self.private_json(self.private / "scope.json", self.scope)
        review = self.private_json(self.private / "review.json", self.review)
        output = self.private / "plan.json"
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(
                CLI.main(
                    [
                        "--scope-file",
                        str(scope),
                        "--review-file",
                        str(review),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
        self.assertNotIn(str(self.root), stream.getvalue())
        self.assertFalse(json.loads(stream.getvalue())["executable"])
        stream = io.StringIO()
        review.write_text("{broken")
        with redirect_stdout(stream):
            self.assertEqual(
                CLI.main(
                    [
                        "--scope-file",
                        str(scope),
                        "--review-file",
                        str(review),
                        "--output",
                        str(output),
                    ]
                ),
                1,
            )
        self.assertEqual(
            json.loads(stream.getvalue()),
            {"state": "review-required", "executable": False},
        )


@unittest.skipUnless((Path(os.environ.get('ARCHIVING_UTILS_ROOT','/opt/archiving-utils'))/'lib/archive_backend.py').is_file(), 'pinned native verifier required')
class AdoptedFamilyPlanTests(unittest.TestCase):
    def setUp(self):
        import test_publication_reconcile
        fixture=test_publication_reconcile.FamilyReconcileTests()
        self.addCleanup(fixture.doCleanups);fixture.setUp();self.fixture=fixture
        retained=plans.guard.private_json(fixture.plan)
        self.scope=dict(retained['scope'],tool_root=os.environ.get('ARCHIVING_UTILS_ROOT','/opt/archiving-utils'))
        self.review=dict(version=1,census=fixture.request['census'],allowed=retained['registration_request']['allowed'],
            rejected=retained['registration_request']['rejected'],
            correct=[dict(owner=item['owner'],path=item['catalog']['path'],sha256=item['source_sha256']) for item in retained['observations']['observed']],
            repeat=dict(owner=fixture.wrong,path=str(fixture.repeat),sha256=plans.guard.file_hash(fixture.repeat)[1]),
            evidence=retained['evidence'],backup=fixture.request['backup'],created=1)

    def test_old_rejected_new_regular_and_old_archived_annual_plan_is_read_only(self):
        fixture=self.fixture;before=(fixture.source.read_bytes(),fixture.annual.read_bytes(),fixture.repeat.read_bytes(),fixture.database.read_bytes(),fixture.store.path.read_bytes())
        result=plans.prepare(self.scope,self.review)
        self.assertFalse(result['executable']);self.assertFalse(result['repeat']['executable'])
        self.assertEqual(result['repeat']['readiness'],'fresh-native-retention-review-required')
        self.assertNotEqual(result['observations']['inventory']['payload'],result['repeat']['inventory']['payload'])
        self.assertEqual(len(result['observations']['observed']),2)
        self.assertEqual(before,(fixture.source.read_bytes(),fixture.annual.read_bytes(),fixture.repeat.read_bytes(),fixture.database.read_bytes(),fixture.store.path.read_bytes()))

    def test_incomplete_inherited_allowed_family_is_held(self):
        self.review['allowed']=self.review['allowed'][:1];self.review['correct']=self.review['correct'][:1]
        with self.assertRaises(plans.guard.Unavailable):plans.prepare(self.scope,self.review)

    def test_unrelated_correct_archive_cannot_create_family_plan(self):
        with zipfile.ZipFile(self.fixture.source,'w') as archive:archive.writestr('01.jpg',b'unrelated payload')
        self.review['correct'][0]['sha256']=plans.guard.file_hash(self.fixture.source)[1]
        with self.assertRaises(plans.guard.Unavailable):plans.prepare(self.scope,self.review)

    def test_changed_correct_after_last_private_backup_read_is_held(self):
        original=plans.backup;calls=[]
        def changed(*args,**kwargs):
            value=original(*args,**kwargs);calls.append(None)
            if len(calls)==2:
                with self.fixture.source.open('ab') as stream:stream.write(b'foreign trailing bytes')
            return value
        with patch.object(plans,'backup',side_effect=changed),self.assertRaises(plans.guard.Unavailable):plans.prepare(self.scope,self.review)

    def test_changed_census_after_last_private_backup_read_is_held(self):
        original=plans.backup;calls=[]
        def changed(*args,**kwargs):
            value=original(*args,**kwargs);calls.append(None)
            if len(calls)==2:
                (self.fixture.writer.root/'publication-v1.json').write_text('{}')
            return value
        with patch.object(plans,'backup',side_effect=changed),self.assertRaises(plans.guard.Unavailable):plans.prepare(self.scope,self.review)

    def test_changed_private_copy_during_final_owner_read_is_held(self):
        original=plans.observe_correct;calls=[]
        manifest=plans.guard.private_json(self.review['backup']['manifest_path'])
        target=Path(manifest['files'][0]['restore'])
        def changed(*args,**kwargs):
            value=original(*args,**kwargs);calls.append(None)
            if len(calls)==3:
                with target.open('ab') as stream:stream.write(b'foreign restore mutation')
            return value
        with patch.object(plans,'observe_correct',side_effect=changed),self.assertRaises(plans.guard.Unavailable):plans.prepare(self.scope,self.review)


if __name__ == "__main__":
    unittest.main()
