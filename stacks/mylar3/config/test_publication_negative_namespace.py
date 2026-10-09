from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('namespace_loader', str(_PORTABLE_ROOT / 'publication_negative_namespace.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Controls(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name) / 'installed'
        self.parent.mkdir()
        self.path = self.parent / 'kernel.py'
        self.raw = b'value = 17\n'
        self.path.write_bytes(self.raw)
        self.path.chmod(420)
        self.digest = hashlib.sha256(self.raw).hexdigest()

    def load(self):
        return m._load(self.path, self.digest)

    def test_checked_buffer(self):
        self.assertEqual(self.load().value, 17)

    def test_no_public_parameters(self):
        with self.assertRaises(TypeError):
            m.kernel(self.path)

    def test_changed_source_never_executes(self):
        witness = self.parent / 'executed'
        self.path.write_text('open(' + repr(str(witness)) + ', "w").close()\n')
        with self.assertRaises(m.Held):
            self.load()
        self.assertFalse(witness.exists())

    def test_leaf_alias_held(self):
        other = self.parent / 'other'
        self.path.rename(other)
        self.path.symlink_to(other)
        with self.assertRaises(m.Held):
            self.load()

    def test_parent_alias_held(self):
        other = self.parent.with_name('other')
        self.parent.rename(other)
        self.parent.symlink_to(other, target_is_directory=True)
        with self.assertRaises(m.Held):
            self.load()

    def test_hardlink_held(self):
        os.link(self.path, self.parent / 'alias')
        with self.assertRaises(m.Held):
            self.load()

    def test_writable_source_held(self):
        self.path.chmod(438)
        with self.assertRaises(m.Held):
            self.load()

    def test_oversized_source_held(self):
        self.path.write_bytes(b'x' * (m.MAX_SOURCE + 1))
        with self.assertRaises(m.Held):
            self.load()

    def test_late_compile_replacement_held(self):
        real = compile

        def replace(*args, **kwargs):
            code = real(*args, **kwargs)
            self.path.unlink()
            self.path.write_bytes(self.raw)
            return code
        with patch('builtins.compile', side_effect=replace):
            with self.assertRaises(m.Held):
                self.load()

    def test_late_compile_ancestor_replacement_held(self):
        real = compile

        def replace(*args, **kwargs):
            code = real(*args, **kwargs)
            old = self.parent.with_name('old')
            self.parent.rename(old)
            self.parent.symlink_to(old, target_is_directory=True)
            return code
        with patch('builtins.compile', side_effect=replace):
            with self.assertRaises(m.Held):
                self.load()

    def test_fd_read_substitution_held(self):
        real = os.read

        def substitute(*args):
            value = real(*args)
            if value:
                return b'value = 99\n'
            return value
        with patch.object(m.os, 'read', side_effect=substitute):
            with self.assertRaises(m.Held):
                self.load()

    def test_private_original_kernel_compatibility(self):
        actual = Path(str(_PORTABLE_ROOT / 'publication_negative_namespace_kernel.py'))
        checked = m._load(actual, m.KERNEL_SHA)
        self.assertTrue(callable(checked._fact))
        self.assertTrue(callable(checked._Kernel))
if __name__ == '__main__':
    unittest.main()
