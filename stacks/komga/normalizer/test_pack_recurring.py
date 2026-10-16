"""Restricted scheduler controls; API replies are fixtures, never live acceptance."""

import ast
import json
from pathlib import Path
import tempfile
import os
import signal
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pack_only
from media_writer import Busy
from publication_guard import NativeBatch, Unavailable
from test_publication_guard import AuthorityFixture


class Prepare(unittest.TestCase):
    def test_discovery_queries_only_health_and_packs_not_commands(self):
        from test_selected_prepare import SelectedPrepare

        fixture = SelectedPrepare()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.m.prepare(packs_only=True)
        self.assertEqual(fixture.calls, [("getHealth", {}), ("packWork", {})])
        fixture.worker.reader.books.assert_called_once_with()


class Discovery(AuthorityFixture, unittest.TestCase):
    def fixture(self, records):
        from test_pack_only import OwnedPassTests

        helper = OwnedPassTests()
        # Use this case's real SQLite/files/Writer and fixture backend, retaining
        # the existing exact Authority constructor projection for tool location.
        helper.__dict__.update(self.__dict__)
        module, worker, m, init = helper.setup_pass()
        worker.config["maintenance"].update(auto_import=True)
        m.prepare = Mock(
            return_value=NativeBatch(
                worker, {"packWork": {"enabled": True, "packs": records}}
            )
        )
        return module, worker, m, init

    def test_real_writer_scope_discovers_future_capture_without_pending_birth(self):
        row = {"id": "a" * 64, "ddl_id": "1", "phase": "discovered"}
        module, worker, m, init = self.fixture([row])
        with (
            patch("publication_guard.Authority.__init__", init),
            patch.object(module, "Maintenance", return_value=m),
        ):
            self.assertEqual(module.discover(worker), [("a" * 64, "1")])
        m.prepare.assert_called_once_with(packs_only=True)
        self.assertFalse(self.writer.fenced())

    def test_unknown_duplicate_or_oversized_work_never_selects(self):
        row = {"id": "a" * 64, "ddl_id": "1", "phase": "discovered"}
        variants = [
            [dict(row, phase="unknown")],
            [row, row],
            [row] * 51,
            [dict(row, ddl_id=True)],
        ]
        module, worker, m, init = self.fixture([])
        for records in variants:
            with self.subTest(records=len(records)):
                m.prepare.return_value = NativeBatch(
                    worker, {"packWork": {"enabled": True, "packs": records}}
                )
                with (
                    patch("publication_guard.Authority.__init__", init),
                    patch.object(module, "Maintenance", return_value=m),
                    self.assertRaises(Unavailable),
                ):
                    module.discover(worker)
        self.assertFalse(self.writer.fenced())

    def test_real_pending_refuses_before_any_api_and_is_preserved(self):
        module, worker, m, init = self.fixture([])
        with self.writer.hold(allow_pending=True):
            self.writer.mark_pending()
        original = self.writer.pending.read_bytes()
        with (
            patch.object(module, "Maintenance", return_value=m),
            self.assertRaises(Busy),
        ):
            module.discover(worker)
        m.prepare.assert_not_called()
        self.assertEqual(self.writer.pending.read_bytes(), original)

    def test_once_real_contender_reports_wait_without_api_or_success(self):
        import fcntl

        module, worker, m, init = self.fixture([])
        worker.config["poll_seconds"] = 30
        fd = os.open(self.writer.lock, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (
                patch.object(module, "Maintenance", return_value=m),
                self.assertRaises(Unavailable),
            ):
                module.serve(worker, once=True)
        finally:
            os.close(fd)
        m.prepare.assert_not_called()
        status = json.loads((worker.state / "status.json").read_text())
        self.assertEqual(status["state"], "stopped")
        self.assertFalse(self.writer.fenced())


class Scheduler(unittest.TestCase):
    def test_later_ticks_consume_future_ids_only_through_selected_run(self):
        worker = SimpleNamespace(
            cycle=Mock(side_effect=AssertionError("bulk")), config={}
        )
        with (
            patch.object(
                pack_only,
                "discover",
                side_effect=[[("a" * 64, "1")], [("b" * 64, "2")]],
            ),
            patch.object(
                pack_only,
                "run",
                return_value={
                    "import_requests": 1,
                    "maintenance_requests": 0,
                    "complete": False,
                },
            ) as selected,
        ):
            first = pack_only.tick(worker)
            second = pack_only.tick(worker)
        self.assertEqual(
            selected.call_args_list,
            [
                unittest.mock.call(worker, "a" * 64, "1"),
                unittest.mock.call(worker, "b" * 64, "2"),
            ],
        )
        self.assertEqual((first["captures"], second["captures"]), (1, 1))
        self.assertFalse(first["complete"])
        worker.cycle.assert_not_called()

    def test_tick_visits_review_before_other_work_but_stops_after_one_import(self):
        worker = object()
        with (
            patch.object(
                pack_only,
                "discover",
                return_value=[("a" * 64, "1"), ("b" * 64, "2"), ("c" * 64, "3")],
            ),
            patch.object(
                pack_only,
                "run",
                side_effect=[
                    {
                        "import_requests": 0,
                        "maintenance_requests": 0,
                        "complete": False,
                    },
                    {
                        "import_requests": 1,
                        "maintenance_requests": 1,
                        "complete": False,
                    },
                ],
            ) as selected,
        ):
            result = pack_only.tick(worker)
        self.assertEqual(selected.call_count, 2)
        self.assertEqual(result["captures"], 2)

    def test_uncertain_selected_exception_stops_tick_without_second_dispatch(self):
        with (
            patch.object(
                pack_only, "discover", return_value=[("a" * 64, "1"), ("b" * 64, "2")]
            ),
            patch.object(
                pack_only, "run", side_effect=Unavailable("uncertain")
            ) as selected,
            self.assertRaises(Unavailable),
        ):
            pack_only.tick(object())
        self.assertEqual(selected.call_count, 1)

    def test_loop_source_never_calls_broad_producers(self):
        tree = ast.parse(Path(pack_only.__file__).read_text())
        for name in ("discover", "tick", "serve"):
            fn = next(
                n
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == name
            )
            text = ast.unparse(fn)
            for bad in (
                "normalizer.cycle",
                "maintenance.cycle",
                "render_pending",
                "naming.tick",
                "workflowCommands",
                "packCatalog",
            ):
                self.assertNotIn(bad, text)

    def test_cli_holds_real_worker_lock_through_restricted_service(self):
        import fcntl
        import normalize

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(json.dumps({"state": str(root)}))
            worker = SimpleNamespace(
                state=root, cycle=Mock(side_effect=AssertionError("bulk"))
            )

            def service(value, *, once):
                self.assertIs(value, worker)
                self.assertTrue(once)
                with (
                    (root / "worker.lock").open("a") as contender,
                    self.assertRaises(BlockingIOError),
                ):
                    fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)

            with (
                patch(
                    "sys.argv",
                    ["normalize.py", "--config", str(config), "--packs-only", "--once"],
                ),
                patch.object(normalize, "Normalizer", return_value=worker),
                patch.object(pack_only, "serve", side_effect=service) as selected,
            ):
                normalize.main()
            selected.assert_called_once_with(worker, once=True)
            worker.cycle.assert_not_called()
            with (root / "worker.lock").open("a") as after:
                fcntl.flock(after, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_cli_selected_and_recurring_conflicts_refuse_before_config(self):
        import normalize

        cases = [
            ["--packs-only", "--pack-capture", "a" * 64, "--pack-ddl", "1"],
            ["--packs-only", "--naming-plan", "x"],
            ["--packs-only", "--naming-apply", "x"],
        ]
        for flags in cases:
            with (
                self.subTest(flags=flags),
                patch("sys.argv", ["normalize.py", "--config", "/absent", *flags]),
                self.assertRaises(SystemExit) as e,
            ):
                normalize.main()
            self.assertEqual(e.exception.code, 2)


class Loop(unittest.TestCase):
    def test_real_process_shutdown_finishes_pass_without_second_tick(self):
        with tempfile.TemporaryDirectory() as directory:
            program = """
import os, signal, sys
from pathlib import Path
from types import SimpleNamespace
import pack_only
root=Path(sys.argv[1])
def tick(worker, stopping):
    with (root/'ticks').open('a') as f: f.write('tick\\n')
    os.kill(os.getpid(),signal.SIGTERM)
    return dict(captures=1,import_requests=0,maintenance_requests=0,complete=False)
pack_only.tick=tick
worker=SimpleNamespace(state=root,config={'poll_seconds':30,'maintenance':{'pack_import':True,'auto_import':True}})
pack_only.serve(worker)
"""
            result = subprocess.run(
                [sys.executable, "-B", "-c", program, directory],
                cwd=Path(pack_only.__file__).parent,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            root = Path(directory)
            self.assertEqual((root / "ticks").read_text().splitlines(), ["tick"])
            status = json.loads((root / "status.json").read_text())
            self.assertEqual(status["state"], "stopped")
            self.assertFalse(status["complete"])

    def test_once_uncertain_result_is_held_and_never_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = SimpleNamespace(
                state=Path(directory),
                config={
                    "poll_seconds": 30,
                    "maintenance": {"pack_import": True, "auto_import": True},
                },
            )
            with (
                patch.object(
                    pack_only, "tick", side_effect=Unavailable("lost response")
                ) as selected,
                self.assertRaises(Unavailable),
            ):
                pack_only.serve(worker, once=True)
            self.assertEqual(selected.call_count, 1)
            self.assertEqual(
                json.loads((worker.state / "status.json").read_text())["errors"],
                ["Guarded pack pass requires review"],
            )

    def test_health_has_separate_mode_freshness_and_held_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "heartbeat").touch()
            good = dict(
                mode="packs-only",
                state="checked",
                checked_at=time.time(),
                errors=[],
                complete=False,
            )
            for status in (
                good,
                dict(good, mode="full"),
                dict(good, state="held"),
                dict(good, checked_at=time.time() - 181),
                dict(good, errors=["review"]),
            ):
                (root / "status.json").write_text(json.dumps(status))
                if status == good:
                    pack_only.check_health({"poll_seconds": 30}, root)
                else:
                    with self.assertRaises(Unavailable):
                        pack_only.check_health({"poll_seconds": 30}, root)
            os.utime(root / "heartbeat", (time.time() - 91, time.time() - 91))
            (root / "status.json").write_text(json.dumps(good))
            with self.assertRaises(Unavailable):
                pack_only.check_health({"poll_seconds": 30}, root)

    def test_repeated_wait_does_not_refresh_last_completed_check(self):
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as directory:
            worker = SimpleNamespace(
                state=Path(directory),
                config={
                    "poll_seconds": 30,
                    "maintenance": {"pack_import": True, "auto_import": True},
                },
            )
            clock = [1000]

            def waiting(worker, stopping):
                clock[0] += 200
                os.kill(os.getpid(), signal.SIGTERM)
                return None

            output = io.StringIO()
            with (
                patch.object(time, "time", side_effect=lambda: clock[0]),
                patch.object(pack_only, "tick", side_effect=waiting),
                contextlib.redirect_stdout(output),
            ):
                pack_only.serve(worker)
            status = json.loads(output.getvalue())
            self.assertEqual(status["checked_at"], 0)
            self.assertEqual(status["observed_at"], 1200)
            self.assertEqual(status["state"], "waiting")

    def test_invalid_poll_never_calls_api_or_arms_signal_handlers(self):
        for value in (True, 0, 29, 3601, "60"):
            worker = SimpleNamespace(config={"poll_seconds": value})
            with (
                self.subTest(value=value),
                patch.object(pack_only, "tick") as selected,
                patch.object(signal, "signal") as handlers,
                self.assertRaises(ValueError),
            ):
                pack_only.serve(worker)
            selected.assert_not_called()
            handlers.assert_not_called()


class DurableDispatchStatus(unittest.TestCase):
    def fixture(self):
        from test_import_recovery import CoordinatedRecoveryTest

        fixture = CoordinatedRecoveryTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        source, receipt = fixture.prepared()
        fixture.m.worker.config.update(
            poll_seconds=30,
            maintenance={"pack_import": True, "auto_import": True},
        )
        return fixture, source, receipt

    def actual_dispatch_tick(self, fixture):
        def tick(worker, stopping):
            self.assertIs(worker, fixture.m.worker)
            result = fixture.dispatch()
            return dict(captures=1, import_requests=result,
                        maintenance_requests=0, complete=False)
        return tick

    def test_real_lost_response_holds_once_and_restart_without_replay(self):
        fixture, source, receipt = self.fixture()
        original_source = source.read_bytes()

        def lost_response(command, **kwargs):
            result = fixture.native_api(command, **kwargs)
            if command == "forceProcess":
                raise TimeoutError("fixture lost response")
            return result

        fixture.m.mylar.side_effect = lost_response
        worker = fixture.m.worker
        with (patch.object(pack_only, "tick", side_effect=self.actual_dispatch_tick(fixture)),
              self.assertRaises(Unavailable)):
            pack_only.serve(worker, once=True)
        self.assertFalse(hasattr(worker, "_pack_recurring_status"))
        retained = receipt.read_bytes()
        self.assertEqual(json.loads(retained)["phase"], "dispatching")
        self.assertTrue(json.loads((worker.state / "status.json").read_text())["errors"])
        with self.assertRaises(Unavailable):
            pack_only.check_health(worker.config, worker.state)
        # The original manual/default dispatch preserves its returned-zero contract.
        self.assertEqual(fixture.dispatch(), 0)
        self.assertEqual(receipt.read_bytes(), retained)
        # A fresh worker object simulates a restarted restricted process. It owns
        # exactly the same durable files, and cannot replay the uncertain request.
        restarted = SimpleNamespace(config=worker.config, state=worker.state, jobs=worker.jobs)
        fixture.m.worker = restarted
        with (patch.object(pack_only, "tick", side_effect=self.actual_dispatch_tick(fixture)),
              self.assertRaises(Unavailable)):
            pack_only.serve(restarted, once=True)
        self.assertFalse(hasattr(restarted, "_pack_recurring_status"))
        self.assertEqual(receipt.read_bytes(), retained)
        self.assertEqual(source.read_bytes(), original_source)
        self.assertEqual(sum(call.args[0] == "forceProcess"
                             for call in fixture.m.mylar.call_args_list), 1)
        status = json.loads((restarted.state / "status.json").read_text())
        self.assertEqual(status["state"], "stopped")
        self.assertEqual(status["errors"], ["Guarded pack pass requires review"])

    def test_fresh_real_submitted_receipt_waits_without_replay_or_false_review(self):
        fixture, source, receipt = self.fixture()
        fixture.m.mylar.side_effect = fixture.native_api
        self.assertEqual(fixture.dispatch(), 1)
        retained = receipt.read_bytes()
        worker = fixture.m.worker
        # A prior process-local value is restored rather than silently overwritten.
        worker._pack_recurring_status = "prior status context"
        with patch.object(pack_only, "tick", side_effect=self.actual_dispatch_tick(fixture)):
            result = pack_only.serve(worker, once=True)
        self.assertEqual(result["state"], "checked")
        self.assertEqual(result["errors"], [])
        self.assertEqual(worker._pack_recurring_status, "prior status context")
        self.assertEqual(receipt.read_bytes(), retained)
        self.assertEqual(sum(call.args[0] == "forceProcess"
                             for call in fixture.m.mylar.call_args_list), 1)

    def test_stale_real_submitted_receipt_holds_without_replaying(self):
        fixture, source, receipt = self.fixture()
        fixture.m.mylar.side_effect = fixture.native_api
        self.assertEqual(fixture.dispatch(), 1)
        original = receipt.read_bytes()
        submitted = json.loads(original)["submitted_at"]
        worker = fixture.m.worker
        with (patch.object(pack_only, "tick", side_effect=self.actual_dispatch_tick(fixture)),
              patch.object(time, "time", return_value=submitted + 1801),
              self.assertRaises(Unavailable)):
            pack_only.serve(worker, once=True)
        self.assertEqual(receipt.read_bytes(), original)
        self.assertEqual(sum(call.args[0] == "forceProcess"
                             for call in fixture.m.mylar.call_args_list), 1)


if __name__ == "__main__":
    unittest.main()
