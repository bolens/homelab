"""Synthetic fixtures: no Docker, live configuration or network access."""

import json
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from policy import decide, source_unhealthy
from runner import Maintenance, atomic_json, require_mount


CHANNEL = {"id": 1, "uuid": "test-uuid", "name": "Test channel", "group_id": 7,
           "stream_ids": [10, 11], "protected": False}
DEAD = [{"channel_id": 1, "stream_id": number, "status": "Dead"} for number in [10, 11]]


class QuarantineTests(unittest.TestCase):
    def test_retries_and_duplicate_same_day_do_not_admit_deletion(self):
        history = {}
        for _ in range(4):
            history, actions = decide([CHANNEL], DEAD, history, 1800000000)
        self.assertEqual(len(history["test-uuid"]["failed_dates"]), 1)
        self.assertEqual(actions[0]["kind"], "quarantine")

    def test_three_checks_and_fourteen_elapsed_days_are_both_required(self):
        history = {}
        for day in [0, 1, 13]:
            history, actions = decide([CHANNEL], DEAD, history, 1800000000 + day * 86400)
            self.assertEqual(actions[0]["kind"], "quarantine")
        _, actions = decide([CHANNEL], DEAD, history, 1800000000 + 14 * 86400)
        self.assertEqual(actions[0]["kind"], "delete")

    def test_partial_check_skipped_or_healthy_alternate_prevents_dead_verdict(self):
        for rows in [DEAD[:1], DEAD[:1] + [{**DEAD[1], "status": "Skipped"}],
                     DEAD[:1] + [{**DEAD[1], "status": "Alive"}],
                     DEAD[:1] + [{**DEAD[1], "error_type": "Cancelled"}]]:
            history, actions = decide([CHANNEL], rows, {}, 1800000000)
            self.assertEqual(history, {})
            self.assertEqual(actions, [])

    def test_recovery_restores_original_group_and_clears_failure_history(self):
        history, _ = decide([CHANNEL], DEAD, {}, 1800000000)
        history, actions = decide([CHANNEL], [{**DEAD[0], "status": "Alive"}], history,
                                  1800000000 + 86400)
        self.assertEqual(history, {})
        self.assertEqual(actions[0]["kind"], "restore")
        self.assertEqual(actions[0]["original_group_id"], 7)

    def test_protection_rescues_existing_quarantine(self):
        history, _ = decide([CHANNEL], DEAD, {}, 1800000000)
        history, actions = decide([{**CHANNEL, "protected": True}], DEAD, history,
                                  1800000000 + 15 * 86400)
        self.assertEqual(history, {})
        self.assertEqual(actions[0]["kind"], "restore")


class MaintenanceTests(unittest.TestCase):
    def test_first_check_baselines_existing_retention_without_put(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = object.__new__(Maintenance)
            runner.state = Path(directory)
            runner.config = {"dvr_library_ids": [8]}
            sample = ET.fromstring('<MediaContainer>'
                '<MediaSubscription key="existing" type="2" targetLibrarySectionID="8"/>'
                '</MediaContainer>')
            with patch.object(runner, "plex_call", return_value=sample) as api:
                runner.recording_defaults()
            api.assert_called_once_with("/media/subscriptions")
            self.assertEqual(json.loads((runner.state / 'recording-defaults.json').read_text()),
                             {'processed': ['existing']})

    def test_successful_empty_plex_mutation_response_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = object.__new__(Maintenance)
            runner.config = {"plex_root": directory}
            (Path(directory) / "Preferences.xml").write_text(
                '<Preferences PlexOnlineToken="fixture-token"/>')
            with patch("runner.urllib.request.urlopen") as api:
                api.return_value.__enter__.return_value.read.return_value = b""
                self.assertEqual(runner.plex_call("/livetv/dvrs/2/reloadGuide", "POST").tag,
                                 "MediaContainer")
                with self.assertRaises(ET.ParseError):
                    runner.plex_call("/livetv/dvrs")

    def test_private_job_umask_keeps_public_metric_path_traversable(self):
        import time
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as directory:
            runner = object.__new__(Maintenance)
            runner.state = Path(directory)
            output = runner.state / "node" / "collector" / "iptv.prom"
            runner.config = {"recordings_directory": directory, "recordings_mount": {},
                             "metrics_file": str(output), "minimum_recording_free_bytes": 0}
            snapshot = {"guides": [{"status": "success", "updated_at": time.time(),
                                    "interval": 6}], "current_programs": 1,
                        "failed_recordings": 0}
            old = os.umask(0o077)
            try:
                with patch("runner.require_mount"), patch.object(
                    runner, "plex_call", return_value=ET.fromstring('<MediaContainer/>')
                ):
                    runner.health(snapshot)
            finally:
                os.umask(old)
            self.assertEqual(output.parent.stat().st_mode & 0o777, 0o755)
            self.assertEqual(output.parent.parent.stat().st_mode & 0o777, 0o755)
            self.assertEqual(output.stat().st_mode & 0o777, 0o644)

    def test_failed_backup_does_not_remove_existing_verified_generations(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = object.__new__(Maintenance)
            runner.state = Path(directory)
            runner.config = {"state_mount": {"fstype": "test", "source": "test"}}
            generation = runner.state / "backups" / "20260101T000000Z"
            generation.mkdir(parents=True)
            (generation / "verified.json").write_text('{"verified":true}')
            with patch("runner.require_mount"), patch.object(
                runner, "django", side_effect=RuntimeError("fixture backup failure")
            ):
                with self.assertRaises(RuntimeError):
                    runner.backup()
            self.assertTrue((generation / "verified.json").is_file())

    def test_mount_refuses_local_fallback(self):
        with patch("runner.command", return_value=b"btrfs /dev/root\n"):
            with self.assertRaises(RuntimeError):
                require_mount(Path("/fixture/media"), {"fstype": "nfs4", "source": "nas:/media"})

    def test_unknown_failed_or_stale_guide_is_unhealthy(self):
        self.assertTrue(source_unhealthy("error", 1000, 1001, 6))
        self.assertTrue(source_unhealthy("success", None, 1001, 6))
        self.assertTrue(source_unhealthy("success", 1000, 1000 + 19 * 3600, 6))
        self.assertFalse(source_unhealthy("success", 1000, 1000 + 2 * 3600, 6))

    def test_write_ahead_replays_recovery_after_database_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = object.__new__(Maintenance)
            runner.state = Path(directory)
            runner.config = {}
            history, _ = decide([CHANNEL], DEAD, {}, 1800000000)
            atomic_json(runner.state / "quarantine.json", {"history": history})
            snapshot = {"channels": [CHANNEL], "results": [{**DEAD[0], "status": "Alive"}],
                        "progress": {"status": "idle", "end_time": 1800000000 + 86400}}
            with patch.object(runner, "django", side_effect=RuntimeError("fixture")):
                with self.assertRaises(RuntimeError):
                    runner.quarantine(snapshot)
            with patch.object(runner, "django", return_value={"restore": 1}) as adapter:
                runner.quarantine(snapshot)
                self.assertEqual(adapter.call_args.args[1]["actions"][0]["kind"], "restore")
            state = json.loads((runner.state / "quarantine.json").read_text())
            self.assertEqual(state["history"], {})
            self.assertNotIn("pending_actions", state)

    def test_retention_only_touches_new_dedicated_dvr_series(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as directory:
            runner = object.__new__(Maintenance)
            runner.state = Path(directory)
            runner.config = {"dvr_library_ids": [8]}
            atomic_json(runner.state / "recording-defaults.json", {"processed": ["old"]})
            sample = ET.fromstring('<MediaContainer>'
                '<MediaSubscription key="old" type="2" targetLibrarySectionID="8"/>'
                '<MediaSubscription key="shared" type="2" targetLibrarySectionID="2"/>'
                '<MediaSubscription key="new" type="2" targetLibrarySectionID="8"/>'
                '</MediaContainer>')
            with patch.object(runner, "plex_call", return_value=sample) as api:
                runner.recording_defaults()
            self.assertEqual(api.call_count, 2)
            self.assertEqual(api.call_args.args[0], "/media/subscriptions/new")


if __name__ == "__main__":
    unittest.main()
