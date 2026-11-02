"""Finite UID1000 namespace metadata launcher; no privilege or application calls."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import json
import os
import subprocess
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import comic_nfs_parent_session as m


class OwnerNodes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.leaf = self.base / 'nested'; self.leaf.mkdir(mode=0o700)
        self.fd = os.open(self.base, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.fd)
        self.root5 = m.five(os.fstat(self.fd)); self.paths = ('/nested',)
        self.deadline = time.monotonic() + 90
        self.calls = []; self.mutate = None
        def run(argv, **kwargs):
            self.calls.append((argv, kwargs))
            self.assertEqual(argv[:4], [sys.executable, '-I', '-B', '-c'])
            self.assertIn('os.stat(', argv[4]); self.assertNotIn('exec(', argv[4])
            request = json.loads(argv[5]); self.assertEqual(request['fd'], self.fd)
            self.assertEqual(kwargs['pass_fds'], (self.fd,))
            self.assertEqual((kwargs['user'], kwargs['group'], kwargs['extra_groups']), (1000, 1000, ()))
            self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
            self.assertGreater(kwargs['timeout'], 0); self.assertLessEqual(kwargs['timeout'], 90)
            value = dict(uid=[1000]*3, gid=[1000]*3, groups=[], root5=list(self.root5),
                         nodes={'/nested': list(m.five(self.leaf.stat()))})
            if self.mutate is not None:
                self.mutate(value)
            return types.SimpleNamespace(returncode=0, stdout=m.encode(value), stderr=b'')
        for p in (patch.object(m.os, 'getresuid', return_value=(0,0,0)),
                  patch.object(m.os, 'getresgid', return_value=(0,0,0)), patch.object(m.subprocess, 'run', run)):
            p.start(); self.addCleanup(p.stop)

    def call(self):
        return m.readonly_namespace_nodes(self.fd, self.root5, self.paths, self.deadline)

    def test_fixed_principal_original_fd_and_original_deadline(self):
        self.assertEqual(self.call(), {'/nested': list(m.five(self.leaf.stat()))})
        self.assertEqual(len(self.calls), 1)

    def test_incomplete_or_foreign_census_refuses(self):
        self.mutate = lambda value: value.update(nodes={})
        with self.assertRaisesRegex(m.Held, 'owner-node-census'):
            self.call()

    def test_wrong_uid_refuses(self):
        self.mutate = lambda value: value.update(uid=[0,0,0])
        with self.assertRaises(m.Held):
            self.call()

    def test_supplementary_groups_refuse(self):
        self.mutate = lambda value: value.update(groups=[0])
        with self.assertRaises(m.Held):
            self.call()

    def test_non_directory_or_bool_node_refuses(self):
        self.mutate = lambda value: value['nodes']['/nested'].__setitem__(2, 0o100600)
        with self.assertRaises(m.Held):
            self.call()
        self.mutate = lambda value: value['nodes']['/nested'].__setitem__(3, False)
        with self.assertRaises(m.Held):
            self.call()

    def test_original_root_fd_substitution_refuses(self):
        other = self.base / 'other'; other.mkdir()
        def replace(_):
            fd = os.open(other, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.dup2(fd, self.fd)
            finally:
                os.close(fd)
        self.mutate = replace
        with self.assertRaisesRegex(m.Held, 'original-FD-deadline'):
            self.call()

    def test_helper_timeout_has_no_fallback(self):
        with patch.object(m.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixed-metadata-helper', 1)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.call()
            self.assertEqual(run.call_count, 1)

    def test_nonzero_exit_has_no_fallback(self):
        with patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=1, stdout=b'', stderr=b'held')) as run:
            with self.assertRaisesRegex(m.Held, 'node-helper-result'):
                self.call()
            self.assertEqual(run.call_count, 1)

    def test_expired_original_deadline_refuses_before_launch(self):
        self.deadline = time.monotonic() - 1
        with self.assertRaisesRegex(m.Held, 'node-request'):
            self.call()
        self.assertEqual(self.calls, [])

    def test_deadline_elapsed_during_reply_refuses(self):
        self.deadline = 101
        clock = [100]
        self.mutate = lambda _: clock.__setitem__(0, 102)
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(m.Held, 'original-FD-deadline'):
                self.call()


if __name__ == '__main__':
    unittest.main()
