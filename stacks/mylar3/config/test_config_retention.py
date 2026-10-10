"""Actual configure cleanup AST with genuine disposable archive preservation."""
import ast
import glob
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('retention', HERE / 'patch_config_retention.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
SOURCE = Path(os.environ['MYLAR_WORKFLOW_SOURCE']) / 'config.py'


def actual_cleanup(source):
    tree = ast.parse(source)
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'configure')
    node = next(n for n in function.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'self.CLEANUP_CACHE')
    f = ast.FunctionDef(name='cleanup', args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='self')], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[node], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[f], type_ignores=[]))
    namespace = dict(glob=glob, os=os, shutil=shutil, Path=Path, logger=types.SimpleNamespace(fdebug=lambda *args: None, warn=lambda *args: None))
    exec(compile(module, str(SOURCE), 'exec'), namespace)
    return namespace['cleanup']


class Retention(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = SOURCE.read_text()
        if cls.current.count(p.MARKER) != 1 or cls.current.count(p.REPLACEMENT) != 1:
            raise AssertionError('Native configuration retention guard is not installed')
        if p.patched_source(cls.current) != cls.current:
            raise AssertionError('Native configuration retention guard changed')
        cls.prior = cls.current.replace(p.REPLACEMENT, p.PRIOR, 1)

    def archive_fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        cache, ddl, library = (root / n for n in ('cache', 'ddl', 'library'))
        for path in (cache, ddl, library):
            path.mkdir()
        nested = cache / 'mylar_unconfirmed'
        nested.mkdir()
        files = [base / ('unconfirmed' + suffix) for base in (cache, ddl, nested) for suffix in ('.cbz', '.cbr', '.zip')]
        for path in files:
            path.write_bytes(b'disposable retained archive')
        config = types.SimpleNamespace(CLEANUP_CACHE=True, CLEANUP_STRAYS=False, CACHE_DIR=str(cache), DDL_LOCATION=str(ddl), DESTINATION_DIR=str(library))
        return config, files

    def test_default_cleanup_preserves_nested_unconfirmed_archives(self):
        config, files = self.archive_fixture()
        before = {path: path.read_bytes() for path in files}
        actual_cleanup(self.current)(config)
        self.assertEqual({path: path.read_bytes() for path in files}, before)
        self.assertTrue(config.CLEANUP_CACHE)
        self.assertFalse(config.CLEANUP_STRAYS)

    def test_strays_cleanup_preserves_all_cache_and_DDL_archive_formats(self):
        config, files = self.archive_fixture()
        config.CLEANUP_STRAYS = True
        before = {path: path.read_bytes() for path in files}
        actual_cleanup(self.current)(config)
        self.assertEqual({path: path.read_bytes() for path in files}, before)
        self.assertTrue(config.CLEANUP_STRAYS)

    def test_actual_predecessor_reproduces_pre_admission_deletion(self):
        config, files = self.archive_fixture()
        config.CLEANUP_STRAYS = True
        actual_cleanup(self.prior)(config)
        self.assertTrue(all(not path.exists() for path in files))

    def test_exact_roundtrip_and_flags_and_outside_bytes(self):
        self.assertEqual(p.patched_source(self.current), self.current)
        self.assertEqual(self.current.replace(p.REPLACEMENT, p.PRIOR, 1), self.prior)
        self.assertEqual(self.current.replace(p.REPLACEMENT, '', 1), self.prior.replace(p.PRIOR, '', 1))
        self.assertIn("'CLEANUP_CACHE': (bool, 'General', True)", self.current)
        self.assertIn("'CLEANUP_STRAYS': (bool, 'General', False)", self.current)

    def test_installer_changes_only_configuration_cleanup_and_repeats(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config.py').write_text(self.prior)
            protected = root / 'PostProcessor.py'
            protected.write_bytes(b'owning ACK cleanup remains unchanged')
            p.main(root)
            self.assertEqual((root / 'config.py').read_text(), self.current)
            p.main(root)
            self.assertEqual((root / 'config.py').read_text(), self.current)
            self.assertEqual(protected.read_bytes(), b'owning ACK cleanup remains unchanged')

    def test_uninstalled_native_source_fails_the_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config.py').write_text(self.prior)
            result = subprocess.run(
                [sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                 'Retention.test_default_cleanup_preserves_nested_unconfirmed_archives'],
                env=dict(os.environ, MYLAR_WORKFLOW_SOURCE=str(root)),
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Native configuration retention guard is not installed', result.stderr)

    def test_malformed_original_or_relocated_patch_refused(self):
        for altered in (self.prior.replace('shutil.rmtree(f)', 'shutil.rmtree(f, ignore_errors=True)', 1), self.current.replace(p.MARKER, p.MARKER + p.MARKER, 1), self.current.replace('if self.CLEANUP_CACHE:', 'if True:', 1)):
            with self.assertRaises(ValueError):
                p.patched_source(altered)


if __name__ == '__main__':
    unittest.main()
