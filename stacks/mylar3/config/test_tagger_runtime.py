"""Real-process acceptance for the inactive modern-tagger runtime boundary."""
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from tagger_runtime import MAX_OUTPUT, run


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def child(self, code, **kwargs):
        return run([sys.executable, '-c', code], cwd=self.directory.name, **kwargs)

    def test_success_and_cwd(self):
        result = self.child('import os,sys;print(os.getcwd());sys.stderr.write("warning")')
        self.assertEqual(result.state, 'ok')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.decode().strip(), self.directory.name)
        self.assertEqual(result.stderr, b'warning')

    def test_failure_is_not_success_banner(self):
        result = self.child('import sys;print("Tagging successful");sys.exit(7)')
        self.assertEqual((result.state, result.returncode), ('failed', 7))

    def test_secret_output_not_in_repr(self):
        result = self.child('print("private-key-value")')
        self.assertNotIn('private-key-value', repr(result))
        self.assertNotIn('-c', repr(result))

    def test_missing_executable_and_bad_cwd(self):
        self.assertEqual(run(['/no/such/command'], cwd=self.directory.name).state, 'unavailable')
        self.assertEqual(run([sys.executable], cwd='/no/such/directory').state, 'unavailable')

    def test_stdin_is_closed(self):
        self.assertEqual(self.child('import sys;print(repr(sys.stdin.read()))').stdout, b"''\n")

    def test_timeout_kills_and_reaps_child(self):
        start = time.monotonic()
        result = self.child('import os,time;print(os.getpid(),flush=True);time.sleep(10)', timeout=0.2)
        self.assertEqual(result.state, 'timed_out')
        self.assertLess(time.monotonic()-start, 2.2)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(result.stdout), 0)

    def test_child_with_closed_output_still_has_deadline(self):
        result = self.child('import os,time;os.close(1);os.close(2);time.sleep(10)', timeout=0.2)
        self.assertEqual(result.state, 'timed_out')

    def test_descendant_holding_pipes_does_not_hang(self):
        start = time.monotonic()
        result = self.child('import os,time;pid=os.fork();print(os.getpid(),flush=True) if pid==0 else None;time.sleep(10) if pid==0 else None', timeout=0.2)
        self.assertEqual(result.state, 'timed_out')
        self.assertLess(time.monotonic()-start, 2.2)
        pid = int(result.stdout)
        # A grandchild can briefly remain a zombie until the OS reaps it.
        stat = Path('/proc')/str(pid)/'stat'
        for _ in range(50):
            if not stat.exists() or stat.read_text().split(') ')[1][0] == 'Z':
                break
            time.sleep(0.01)
        else:
            self.fail('Tagger descendant is still running')

    def test_combined_output_is_bounded(self):
        result = self.child('import os\nwhile True: os.write(1,b"a"*8192);os.write(2,b"b"*8192)', max_output=16384)
        self.assertEqual(result.state, 'output_limit')
        self.assertEqual(len(result.stdout)+len(result.stderr), 16384)

    def test_exact_bound_is_allowed(self):
        result = self.child('import os;os.write(1,b"a"*100)', max_output=100)
        self.assertEqual(result.state, 'ok')
        self.assertEqual(len(result.stdout), 100)

    def test_rejects_shell_string_and_invalid_bounds(self):
        for args in ('echo unsafe', [], ['bad\0arg']):
            with self.assertRaises(ValueError):
                run(args, cwd=self.directory.name)
        for timeout in (0, -1, True, math.inf, math.nan):
            with self.assertRaises(ValueError):
                self.child('pass', timeout=timeout)
        for bound in (0, True, MAX_OUTPUT+1):
            with self.assertRaises(ValueError):
                self.child('pass', max_output=bound)

    def test_arguments_are_literal(self):
        result = run([sys.executable, '-c', 'import sys;print(sys.argv[1])', '$(touch unexpected)'], cwd=self.directory.name)
        self.assertEqual(result.stdout, b'$(touch unexpected)\n')
        self.assertFalse((Path(self.directory.name)/'unexpected').exists())


if __name__ == '__main__':
    unittest.main()
