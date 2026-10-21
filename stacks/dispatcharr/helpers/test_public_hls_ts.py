"""Isolated process-lifecycle checks for the optional public HLS bridge."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest


BRIDGE = Path(__file__).with_name("public-hls-ts.py")


class BridgeTests(unittest.TestCase):
    def test_reaps_source_when_downstream_exits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pid_file = root / "source.pid"
            source = root / "streamlink"
            source.write_text(
                f"#!{sys.executable}\n"
                "import os, pathlib, sys, time\n"
                f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\n"
                "sys.stdout.buffer.write(b'test'); sys.stdout.buffer.flush()\n"
                "time.sleep(120)\n"
            )
            muxer = root / "ffmpeg"
            muxer.write_text(
                f"#!{sys.executable}\n"
                "import sys\n"
                "sys.stdin.buffer.read(4)\n"
            )
            source.chmod(0o700)
            muxer.chmod(0o700)
            environment = dict(os.environ, PATH=str(root))
            try:
                result = subprocess.run(
                    [sys.executable, str(BRIDGE), "https://example.invalid/live.m3u8"],
                    env=environment, capture_output=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(pid_file.read_text()), 0)
            finally:
                if pid_file.exists():
                    try:
                        os.kill(int(pid_file.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_rejects_non_http_input_before_starting_tools(self):
        result = subprocess.run(
            [sys.executable, str(BRIDGE), "file:///etc/passwd"],
            capture_output=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"HTTP or HTTPS", result.stderr)


if __name__ == "__main__":
    unittest.main()
