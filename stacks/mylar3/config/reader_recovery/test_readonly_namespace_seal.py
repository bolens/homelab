"""Fixed syscall program controls with simulated kernel calls; no privileges."""
import contextlib
import ctypes
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import comic_nfs_parent_session as p


class Call:
    def __init__(self, name, events):
        self.name, self.events, self.result = name, events, 0

    def __call__(self, *args):
        self.events.append((self.name, args))
        return self.result


class FixedProgram(unittest.TestCase):
    def setUp(self):
        self.program = next(v for v in p._seal_namespace_fds.__code__.co_consts
                            if isinstance(v, str) and v.startswith('import ctypes,'))
        self.events = []
        self.libc = types.SimpleNamespace(setns=Call('setns', self.events),
                                          mount=Call('mount', self.events))
        self.namespace = types.SimpleNamespace(st_dev=3, st_ino=44)
        self.own = types.SimpleNamespace(st_dev=3, st_ino=11)
        self.root = types.SimpleNamespace(st_dev=7, st_ino=88, st_mode=stat.S_IFDIR | 0o755,
                                         st_uid=0, st_gid=0)
        self.live_namespace = self.namespace
        self.actual_ticks = 777
        self.request = dict(namespace=10, root=11, namespace2=[3, 44],
                            root5=list(p.five(self.root)), pid=12345, ticks=777, deadline=30)
        self.clock = lambda: 1

    def execute(self):
        fields = ['R'] + ['0'] * 19
        fields[19] = str(self.actual_ticks)
        proc = '12345 (python) ' + ' '.join(fields)
        def fstat(fd):
            return {10: self.namespace, 11: self.root}[fd]
        def observed(path):
            return {'/proc/self/ns/mnt': self.own,
                    '/proc/12345/ns/mnt': self.live_namespace,
                    '/proc/12345/root': self.root}[path]
        def opened(path, *args, **kwargs):
            self.assertEqual(path, '/proc/12345/stat')
            return io.StringIO(proc)
        def written(fd, raw):
            self.events.append(('ack', (fd, raw)))
            return len(raw)
        with contextlib.ExitStack() as stack:
            for target, name, value in (
                (os, 'getresuid', lambda: (0, 0, 0)),
                (os, 'getresgid', lambda: (0, 0, 0)),
                (os, 'fstat', fstat), (os, 'stat', observed),
                (os, 'fchdir', lambda fd: self.events.append(('fchdir', (fd,)))),
                (os, 'chroot', lambda path: self.events.append(('chroot', (path,)))),
                (os, 'chdir', lambda path: self.events.append(('chdir', (path,)))),
                (os, 'write', written), (ctypes, 'CDLL', lambda *a, **k: self.libc),
                (ctypes, 'get_errno', lambda: 5), (time, 'monotonic', self.clock),
            ):
                stack.enter_context(patch.object(target, name, value))
            stack.enter_context(patch('builtins.open', opened))
            stack.enter_context(patch.object(sys, 'argv', ['fixed-helper', json.dumps(self.request)]))
            exec(compile(self.program, 'fixed-private-helper', 'exec'), {})

    def test_exact_original_namespace_then_private_seal_then_ack(self):
        self.execute()
        self.assertEqual(self.events, [
            ('setns', (10, 0x20000)), ('fchdir', (11,)), ('chroot', ('.',)),
            ('chdir', ('/',)), ('mount', (None, b'/', None, (1 << 14) | (1 << 18), None)),
            ('ack', (1, b'nfs-private-sealed\n')),
        ])

    def test_parent_namespace_refuses_before_any_mutation(self):
        self.own = self.namespace
        with self.assertRaises(AssertionError):
            self.execute()
        self.assertEqual(self.events, [])

    def test_changed_process_ticks_refuse_before_any_mutation(self):
        self.actual_ticks += 1
        with self.assertRaises(AssertionError):
            self.execute()
        self.assertEqual(self.events, [])

    def test_changed_live_namespace_refuses_before_any_mutation(self):
        self.live_namespace = types.SimpleNamespace(st_dev=3, st_ino=99)
        with self.assertRaises(AssertionError):
            self.execute()
        self.assertEqual(self.events, [])

    def test_changed_root_descriptor_refuses_before_any_mutation(self):
        self.request['root5'][1] += 1
        with self.assertRaises(AssertionError):
            self.execute()
        self.assertEqual(self.events, [])

    def test_expired_before_namespace_entry_refuses(self):
        self.clock = lambda: 31
        with self.assertRaises(AssertionError):
            self.execute()
        self.assertEqual(self.events, [])

    def test_deadline_expiring_after_entry_prevents_mount_and_ack(self):
        readings = iter((1, 31))
        self.clock = lambda: next(readings)
        with self.assertRaises(AssertionError):
            self.execute()
        self.assertEqual([name for name, _ in self.events], ['setns', 'fchdir', 'chroot', 'chdir'])

    def test_setns_failure_prevents_chroot_mount_and_ack(self):
        self.libc.setns.result = -1
        with self.assertRaises(OSError):
            self.execute()
        self.assertEqual([name for name, _ in self.events], ['setns'])

    def test_mount_failure_never_acknowledges(self):
        self.libc.mount.result = -1
        with self.assertRaises(OSError):
            self.execute()
        self.assertNotIn('ack', [name for name, _ in self.events])


class Primitive(unittest.TestCase):
    def setUp(self):
        self.namespace = types.SimpleNamespace(st_dev=3, st_ino=44)
        self.root = types.SimpleNamespace(st_dev=7, st_ino=88, st_mode=stat.S_IFDIR | 0o755,
                                         st_uid=0, st_gid=0)
        self.own = types.SimpleNamespace(st_dev=3, st_ino=11)
        self.runner = types.SimpleNamespace(returncode=0, stdout=b'nfs-private-sealed\n', stderr=b'')
        for patcher in (
            patch.object(p.os, 'getresuid', return_value=(0, 0, 0)),
            patch.object(p.os, 'getresgid', return_value=(0, 0, 0)),
            patch.object(p.os, 'fstat', side_effect=lambda fd: {10:self.namespace, 11:self.root}[fd]),
            patch.object(p.os, 'stat', side_effect=lambda path: self.own),
            patch.object(p.time, 'monotonic', return_value=1),
        ):
            patcher.start(); self.addCleanup(patcher.stop)
        self.run = patch.object(p.subprocess, 'run', side_effect=lambda *a, **k: self.runner)
        self.called = self.run.start(); self.addCleanup(self.run.stop)

    def call(self, deadline=30):
        return p._seal_namespace_fds(12345, 777, 10, 11, (3, 44), p.five(self.root), deadline)

    def test_only_exact_fixed_ack_is_accepted(self):
        self.call()
        args, kwargs = self.called.call_args
        self.assertEqual(kwargs['pass_fds'], (10, 11))
        self.assertEqual(args[0][1:3], ['-I', '-B'])

    def test_unknown_nonzero_malformed_typed_or_extra_ack_refuses(self):
        for code, out, err in ((1,b'nfs-private-sealed\n',b''),
                               (False,b'nfs-private-sealed\n',b''),
                               (0,b'{"sealed":1}',b''), (0,b'',b''),
                               (0,b'nfs-private-sealed\nextra',b''),
                               (0,b'nfs-private-sealed\n',b'unknown')):
            with self.subTest(code=code, out=out):
                self.runner.returncode, self.runner.stdout, self.runner.stderr = code, out, err
                with self.assertRaisesRegex(p.Held, 'acknowledgement'):
                    self.call()

    def test_parent_namespace_is_rejected_before_launch(self):
        self.own = self.namespace
        with self.assertRaisesRegex(p.Held, 'original-descriptors'):
            self.call()
        self.called.assert_not_called()

    def test_expired_and_unbounded_deadlines_refuse_before_launch(self):
        for deadline in (0, 1, float('inf'), float('nan'), True):
            with self.subTest(deadline=deadline), self.assertRaises(p.Held):
                self.call(deadline)
        self.called.assert_not_called()

    def test_duck_session_and_unregistered_instance_cannot_seal(self):
        for session in (types.SimpleNamespace(), object.__new__(p.RetainedChild)):
            with self.subTest(session=type(session).__name__), self.assertRaisesRegex(p.Held, 'original-.*session'):
                p.seal_readonly_namespace(session, {}, [], 30)
        self.called.assert_not_called()


class OriginalDescriptorCleanup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fds = []
        for name in ('original', 'foreign'):
            path = Path(self.temp.name) / name
            path.write_bytes(name.encode())
            self.fds.append(os.open(path, os.O_RDONLY | os.O_CLOEXEC))
        self.frames = [p.five(os.fstat(fd)) for fd in self.fds]
        self.close = os.close
        self.addCleanup(self.finish)

    def finish(self):
        for fd in self.fds:
            try:
                self.close(fd)
            except OSError:
                pass

    def test_only_original_owned_descriptor_is_closed(self):
        p._close_namespace_fds((self.fds[0], self.frames[0]))
        with self.assertRaises(OSError):
            os.fstat(self.fds[0])
        self.assertEqual(p.five(os.fstat(self.fds[1])), self.frames[1])

    def test_reused_number_does_not_close_foreign_descriptor(self):
        os.dup2(self.fds[1], self.fds[0])
        with self.assertRaisesRegex(p.Held, 'close-foreign-descriptor'):
            p._close_namespace_fds((self.fds[0], self.frames[0]))
        for fd in self.fds:
            self.assertEqual(p.five(os.fstat(fd)), self.frames[1])

    def test_cleanup_error_preserves_original_failure(self):
        primary = ValueError('original operation refused')
        with self.assertRaises(ValueError) as raised:
            try:
                raise primary
            finally:
                with patch.object(p.os, 'close', side_effect=OSError('close failed')):
                    p._close_namespace_fds((self.fds[0], self.frames[0]))
        self.assertIs(raised.exception, primary)
        self.assertEqual(primary.namespace_close_errors, ('OSError',))

    def test_one_failed_close_does_not_leak_other_original(self):
        def closed(fd):
            if fd == self.fds[0]:
                raise OSError('first close failed')
            self.close(fd)
        with patch.object(p.os, 'close', closed), self.assertRaises(OSError):
            p._close_namespace_fds(*zip(self.fds, self.frames))
        self.assertEqual(p.five(os.fstat(self.fds[0])), self.frames[0])
        with self.assertRaises(OSError):
            os.fstat(self.fds[1])

    def test_partial_acquisition_still_closes_acquired_original(self):
        p._close_namespace_fds((None, None), (self.fds[0], self.frames[0]))
        with self.assertRaises(OSError):
            os.fstat(self.fds[0])


if __name__ == '__main__':
    unittest.main()
