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

    def test_early_installed_config_scope_pin_preflight(self):
        # Execute the actual verifier function without launching its broad suites.
        tree = ast.parse((HERE / 'verify_image.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'config_scope_preflight')
        namespace = dict(Path=Path, ast=ast, hashlib=__import__('hashlib'), FIXES=HERE)
        original = sys.modules.get('patch_config_retention')
        try:
            sys.modules['patch_config_retention'] = p
            exec(compile(ast.Module(body=[function], type_ignores=[]), '<actual-verifier-preflight>', 'exec'), namespace)
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / 'config.py').write_text(self.current)
                scope = (HERE / 'publication_native_configured_scope.py').read_bytes()
                (root / 'publication_native_configured_scope.py').write_bytes(scope)
                namespace['config_scope_preflight'](root, installed=True)
                stale = root / 'fixes'
                stale.mkdir()
                (stale / 'publication_native_configured_scope.py').write_bytes(scope.replace(
                    b'd8f02277daaf55b62f95832106e0deb97760d0d297bdf07640be98c910fbe570',
                    b'46bd21f2b117367dffdae510282558bf2757981300665e05f4d2bb2fab1557cc'))
                namespace['FIXES'] = stale
                with self.assertRaisesRegex(AssertionError, 'Configured scope Config pin stale'):
                    namespace['config_scope_preflight'](root, installed=True)
        finally:
            if original is None:
                sys.modules.pop('patch_config_retention', None)
            else:
                sys.modules['patch_config_retention'] = original

    def test_upstream_Config_full_order_before_prospective_preflight(self):
        def load(name):
            spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        old_path = list(sys.path)
        try:
            sys.path.insert(0, str(HERE))
            tagger = load('patch_tagger_backend')
            transport = load('patch_ddl_transport')
        finally:
            sys.path[:] = old_path
        # Reverse exactly the two reviewed insertions from real V11 bytes.
        upstream = self.prior
        anchor = '        for name, value in list(kwargs.items()):\n'
        for module, setting in ((transport, "    'ENABLE_DDL': (bool, 'DDL', False),"),
                                (tagger, "    'ENABLE_META': (bool, 'Metatagging', False),")):
            fixture = 'SETTINGS = {\n' + setting + '\n}\nclass Config:\n    def configure(self, **kwargs):\n' + anchor + '            pass\n'
            transformed = module.configuration(fixture)
            # The setting marker occupies three lines, not an inferred output fact.
            setting_patch = transformed[len('SETTINGS = {\n'):transformed.index('\n', transformed.index(setting))]
            prefix = transformed.split('    def configure(self, **kwargs):\n', 1)[1].split(anchor, 1)[0]
            self.assertEqual(upstream.count(setting_patch), 1)
            self.assertEqual(upstream.count(prefix + anchor), 1)
            upstream = upstream.replace(setting_patch, setting, 1).replace(prefix + anchor, anchor, 1)
        self.assertNotIn(tagger.MARKER, upstream)
        self.assertNotIn(transport.MARKER, upstream)
        self.assertEqual(transport.configuration(tagger.configuration(upstream)), self.prior)
        self.assertNotEqual(__import__('hashlib').sha256(p.patched_source(upstream).encode()).hexdigest(),
                            __import__('hashlib').sha256(self.current.encode()).hexdigest())
        self.assertEqual(p.patched_source(transport.configuration(tagger.configuration(upstream))), self.current)
        verifier = (HERE / 'verify_image.py').read_text()
        install_call = "subprocess.run([sys.executable, str(FIXES / 'apply_patches.py'), str(source)], check=True)"
        self.assertLess(verifier.index(install_call), verifier.index('config_scope_preflight(source, installed=False)'))

    def test_malformed_original_or_relocated_patch_refused(self):
        for altered in (self.prior.replace('shutil.rmtree(f)', 'shutil.rmtree(f, ignore_errors=True)', 1), self.current.replace(p.MARKER, p.MARKER + p.MARKER, 1), self.current.replace('if self.CLEANUP_CACHE:', 'if True:', 1)):
            with self.assertRaises(ValueError):
                p.patched_source(altered)


if __name__ == '__main__':
    unittest.main()
