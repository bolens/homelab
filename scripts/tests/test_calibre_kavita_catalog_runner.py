import importlib.util
import unittest
import tempfile
import sqlite3
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "catalog_runner", Path(__file__).parents[1] / "calibre-kavita-catalog-runner.py"
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.lib = self.root / "books"
        self.lib.mkdir()
        self.config = self.root / "config"
        self.config.mkdir()
        self.runtime = self.root / "runtime"
        self.runtime.mkdir(mode=0o700)
        self.actions = []
        self.mode = "none"
        db = sqlite3.connect(self.lib / "metadata.db")
        db.execute("create table books(id integer primary key)")
        db.execute("insert into books values(1)")
        db.commit()
        db.close()
        (self.lib / "original.epub").write_bytes(b"original")
        self.plan = {"candidates": [{"sha256": "a" * 64}], "baseline": {"bookCount": 1}}
        self.patches = [
            patch.object(M, "require_root", lambda: None),
            patch.object(M, "RUNTIME", self.runtime),
            patch.object(M, "SYNC_LOCK", self.runtime / "publication.lock"),
            patch.dict(M.os.environ, {"CALIBRE_AUTO_REGISTER": "true"}),
            patch.object(M, "LIBRARY", self.lib),
            patch.object(M, "CONFIG", self.config),
            patch.object(M, "run", self.run_command),
            patch.object(M, "load", self.load),
            patch.object(M, "nfs_proof", lambda *a: 10),
            patch.object(M.subprocess, "run", self.process),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def load(self, *args):
        outer = self

        class Planner:
            def plan(self, path):
                return outer.plan

        return Planner()

    def run_command(self, args):
        self.actions.append(args)
        if args[0] == "findmnt":
            return (
                str(M.MEDIA_MOUNT).encode()
                if "-T" in args and args[args.index("-T") + 1] == str(self.lib)
                else str(M.STATE_MOUNT).encode()
            )
        if args[:2] == ["docker", "inspect"]:
            return json.dumps([{"State": {"Running": True}}]).encode()
        if "s6-svstat" in args:
            return b"true"
        if self.mode == "quiesce-fail" and "s6-svc" in args and "-d" in args:
            raise RuntimeError("fixture")
        return b""

    def process(self, args, **kwargs):
        self.actions.append(args)
        if args[0] == "systemctl":
            return subprocess.CompletedProcess(args, 0)
        if str(M.CORE) in args:
            if self.mode in ["partial", "success"]:
                db = sqlite3.connect(self.lib / "metadata.db")
                db.execute("insert into books values(2)")
                db.commit()
                db.close()
            return subprocess.CompletedProcess(args, 0 if self.mode == "success" else 1)
        return subprocess.CompletedProcess(args, 0)

    def resumed(self):
        return any(a[:2] == ["docker", "start"] for a in self.actions)

    def test_opt_in_is_required_for_automatic_registration(self):
        with patch.dict(M.os.environ, {"CALIBRE_AUTO_REGISTER": "false"}):
            M.main()
        self.assertFalse(any(str(M.CORE) in a for a in self.actions))
        self.assertTrue(any(a == [M.EXPORT] for a in self.actions))

    def test_success_replaces_stale_failure_status(self):
        failure = self.runtime / "last-failure.log"
        failure.write_text("previous failure")
        with patch.dict(M.os.environ, {"CALIBRE_AUTO_REGISTER": "false"}):
            M.main()
        self.assertFalse(failure.exists())
        receipt = json.loads((self.runtime / "last-sync-receipt.json").read_text())
        self.assertEqual(receipt["status"], "verified")
        self.assertTrue(receipt["exportAndScanRequested"])

    def test_wrong_mount_refuses_before_state_or_lifecycle(self):
        missing = self.root / "not-created"
        with (
            patch.object(M, "RUNTIME", missing),
            patch.object(M, "run", lambda args: b"/"),
        ):
            with self.assertRaises(AssertionError):
                M.main()
        self.assertFalse(missing.exists())
        self.assertFalse(self.actions)

    def test_overlap_refuses_without_lifecycle_or_export(self):
        import fcntl

        with (self.runtime / "publication.lock").open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            M.main()
        self.assertFalse(any(a[0] == "docker" or a == [M.EXPORT] for a in self.actions))

    def test_nfs_proof_failure_precedes_writer_stop(self):
        with patch.object(M, "nfs_proof", side_effect=RuntimeError("fixture")):
            with self.assertRaises(RuntimeError):
                M.main()
        self.assertFalse(any(a[:2] == ["docker", "stop"] for a in self.actions))

    def test_empty_plan_exports_without_quiesce(self):
        self.plan["candidates"] = []
        M.main()
        self.assertFalse(any(a[:2] == ["docker", "stop"] for a in self.actions))
        self.assertTrue(any(a == [M.EXPORT] for a in self.actions))

    def test_quiesce_failure_resumes_stopped_writer(self):
        self.mode = "quiesce-fail"
        with self.assertRaises(RuntimeError):
            M.main()
        self.assertTrue(self.resumed())
        self.assertTrue(any("s6-svc" in a and "-u" in a for a in self.actions))
        self.assertFalse(any(str(M.CORE) in a for a in self.actions))

    def test_refused_unchanged_import_resumes_and_retains_evidence(self):
        with self.assertRaises(RuntimeError):
            M.main()
        self.assertTrue(self.resumed())
        self.assertTrue(list(self.runtime.glob("run-*")))
        self.assertFalse(any(a == [M.EXPORT] for a in self.actions))

    def test_uncertain_changed_catalog_keeps_writers_quiesced(self):
        self.mode = "partial"
        with self.assertRaises(RuntimeError):
            M.main()
        self.assertFalse(self.resumed())
        self.assertTrue(list(self.runtime.glob("run-*")))

    def test_verified_import_resumes_cleans_and_exports(self):
        self.mode = "success"
        M.main()
        self.assertTrue(self.resumed())
        self.assertFalse(list(self.runtime.glob("run-*")))
        self.assertTrue(any(a == [M.EXPORT] for a in self.actions))
        self.assertEqual(
            json.loads((self.runtime / "last-catalog-receipt.json").read_text())[
                "catalogBooks"
            ],
            2,
        )


if __name__ == "__main__":
    unittest.main()
