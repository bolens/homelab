"""Exercise local retention without accessing a real backup repository."""

from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "stacks/restic/local-retention.sh"


class LocalRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "calls"
        self.stamp = self.root / "stamp"
        self.script = self.root / "retention.sh"
        self.script.write_text(SCRIPT.read_text().replace(
            "stamp=/cache/local-retention-last-prune", f"stamp={self.stamp}"
        ))
        restic = self.root / "restic"
        restic.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n'
            'case " $* " in *" $FAIL_COMMAND "*) exit 1 ;; esac\nexit 0\n'
        )
        restic.chmod(0o755)
        df = self.root / "df"
        df.write_text(
            '#!/bin/sh\necho "Filesystem 1024-blocks Used Available Capacity Mounted"\n'
            'echo "test 1000 100 ${TEST_FREE:-900} 10% /repository"\n'
        )
        df.chmod(0o755)
        self.env = {
            "PATH": f"{self.root}:/usr/bin:/bin",
            "CALL_LOG": str(self.log),
            "FAIL_COMMAND": "never-match",
            "RESTIC_REPOSITORY": "s3:must-never-be-used",
        }

    def run_hook(self):
        return subprocess.run(
            ["sh", str(self.script)], env=self.env,
            capture_output=True, text=True, check=False,
        )

    def test_local_target_policy_and_weekly_prune(self):
        self.assertEqual(self.run_hook().returncode, 0)
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), 2)
        self.assertIn("--repo /repository forget --group-by paths", calls[0])
        self.assertIn("--keep-last 3 --keep-daily 7 --keep-weekly 4 --keep-monthly 3", calls[0])
        self.assertIn("--repo /repository prune --max-repack-size 1G", calls[1])
        self.assertTrue(self.stamp.exists())
        self.assertEqual(self.run_hook().returncode, 0)
        self.assertEqual(len(self.log.read_text().splitlines()), 3)

    def test_failed_forget_does_not_prune(self):
        self.env["FAIL_COMMAND"] = "forget"
        self.assertNotEqual(self.run_hook().returncode, 0)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)
        self.assertFalse(self.stamp.exists())

    def test_failed_prune_is_retried(self):
        self.env["FAIL_COMMAND"] = "prune"
        self.assertNotEqual(self.run_hook().returncode, 0)
        self.assertFalse(self.stamp.exists())
        self.env["FAIL_COMMAND"] = "never-match"
        self.assertEqual(self.run_hook().returncode, 0)
        self.assertTrue(self.stamp.exists())

    def test_invalid_policy_does_not_touch_repository(self):
        for value in ("0", "-1", "invalid"):
            with self.subTest(value=value):
                self.env["LOCAL_KEEP_LAST"] = value
                self.assertNotEqual(self.run_hook().returncode, 0)
                self.assertFalse(self.log.exists())

    def test_low_space_reports_failure_after_cleanup(self):
        self.env["TEST_FREE"] = "150"
        result = self.run_hook()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("below 20%", result.stderr)
        self.assertEqual(len(self.log.read_text().splitlines()), 2)
        self.assertTrue(self.stamp.exists())


if __name__ == "__main__":
    unittest.main()
