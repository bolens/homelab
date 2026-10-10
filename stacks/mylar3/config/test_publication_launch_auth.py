"""Disposable public-source install controls; UID fixture is not root enrollment."""
import ast
import hashlib
import json
import importlib.util
from pathlib import Path
import os
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = self.root / 'sources'
        shutil.copytree(ROOT / 'standalone_launch_auth', self.source)
        self.target = self.root / 'public-install' / 'auth'
        spec = importlib.util.spec_from_file_location('auth_install_under_test', ROOT / 'patch_publication_launch_auth.py')
        self.installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.installer)
        self.installer.ROOT = self.source
        # The production predicate requires UID/GID0; fixtures are explicitly
        # non-root and preserve readonly/non-symlink conditions in private trees.
        self.security = patch.object(self.installer, 'security', self.fixture_security)
        self.security.start(); self.addCleanup(self.security.stop)

    def fixture_security(self, z):
        if z.st_mode & 0o022 and not stat.S_ISDIR(z.st_mode):
            raise ValueError('Fixture nonwritable leaf')
        if z.st_uid not in (0, os.geteuid()): raise ValueError('Fixture owner')

    def install(self): self.installer.main(self.target)

    def test_exact_three_public_leaves_and_idempotent_originals(self):
        self.install(); before = {p.name:self.installer.full(p.stat()) for p in self.target.iterdir()}
        self.install(); self.assertEqual(before, {p.name:self.installer.full(p.stat()) for p in self.target.iterdir()})
        self.assertEqual(set(before), set(self.installer.SOURCES))
        self.assertEqual(set(p.name for p in self.target.parent.iterdir()), {'auth'})
        for p in self.target.iterdir(): self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o444)

    def test_production_security_refuses_unprivileged_fixture(self):
        self.security.stop()
        with self.assertRaises(ValueError): self.install()

    def test_unknown_source_refused_before_destination_birth(self):
        p = self.source / 'v3_auth_core.py'; p.chmod(0o644); p.write_bytes(b'# Unknown\n')
        with self.assertRaisesRegex(ValueError, 'byte pin'): self.install()
        self.assertFalse(self.target.parent.exists())

    def test_unknown_installed_source_retained(self):
        self.install(); p = self.target / 'v3_auth_core.py'; p.chmod(0o644); p.write_bytes(b'# Foreign\n'); p.chmod(0o444)
        with self.assertRaisesRegex(ValueError, 'predecessor'): self.install()
        self.assertEqual(p.read_bytes(), b'# Foreign\n')

    def test_no_bytecode_or_source_sibling_admitted(self):
        for name in ('__pycache__', 'standalone_launch_auth.pyc', 'foreign.py'):
            with self.subTest(name=name):
                p = self.source / name; p.write_bytes(b'unknown')
                with self.assertRaisesRegex(ValueError, 'namespace'): self.install()
                p.unlink()
        self.assertFalse(self.target.parent.exists())

    def test_no_anchor_key_enrollment_or_private_key_publication(self):
        self.install()
        for name in ('installation-v1.json', 'inventory-v1.json', 'public-ed25519.der', 'enrollment-v1.json', 'root-signing-ed25519.der'):
            with self.subTest(name=name):
                p = self.target.parent / name; p.write_bytes(b'NOT A KEY OR AUTHORITY')
                with self.assertRaisesRegex(ValueError, 'public-only namespace'): self.install()
                p.unlink()

    def test_readwrite_installed_leaf_is_not_repaired(self):
        self.install(); p = self.target / 'private_crypto.py'; p.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'predecessor'): self.install()
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o644)

    def test_late_source_hash_callback_drift_refused(self):
        real = self.installer.hashlib.sha256; fired = []
        p = self.source / 'private_crypto.py'
        def late(data):
            result = real(data)
            if not fired: p.chmod(0o640); fired.append(True)
            return result
        with patch.object(self.installer.hashlib, 'sha256', late):
            with self.assertRaisesRegex(ValueError, 'source FD|original changed'): self.install()
        self.assertTrue(fired); self.assertFalse(self.target.parent.exists())

    def test_created_fd_mode_before_fsync_is_retained(self):
        real = self.installer.os.fsync; fired = []
        def late(fd):
            real(fd)
            if not fired: os.fchmod(fd, 0o640); fired.append(True)
        with patch.object(self.installer.os, 'fsync', late):
            with self.assertRaisesRegex(ValueError, 'created source changed'): self.install()
        self.assertTrue(fired)

    def test_final_verification_callback_bytecode_refused(self):
        real = self.installer.verify_installed; fired = []
        def late(directory):
            real(directory); (self.target / '__pycache__').mkdir(); fired.append(True)
        with patch.object(self.installer, 'verify_installed', late):
            with self.assertRaisesRegex(ValueError, 'final exact public namespace'): self.install()
        self.assertTrue(fired)

    def test_final_verification_callback_source_drift_refused(self):
        real = self.installer.verify_installed; fired = []
        def late(directory):
            real(directory); (self.source / 'private_crypto.py').chmod(0o640); fired.append(True)
        with patch.object(self.installer, 'verify_installed', late):
            with self.assertRaisesRegex(ValueError, 'final original source'): self.install()
        self.assertTrue(fired)


class AuthMap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'fixes'; self.root.mkdir()
        names = ('patch_publication_launch_auth.py', 'test_publication_launch_auth.py',
                 'standalone_launch_auth/standalone_launch_auth.py',
                 'standalone_launch_auth/v3_auth_core.py', 'standalone_launch_auth/private_crypto.py')
        self.rows = []
        for name in names:
            target = self.root / name; target.parent.mkdir(parents=True, exist_ok=True)
            data = (ROOT / name).read_bytes(); target.write_bytes(data)
            self.rows.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest()})
        (self.root / 'standalone_launch_auth_sources.json').write_text(json.dumps(self.rows))
        # Explicit minimal public copy graph; no native/SDK authority is mocked.
        (self.root / 'ordinary_fixture.py').write_bytes(b'# finite copy fixture\n')
        digest = hashlib.sha256((self.root / 'ordinary_fixture.py').read_bytes()).hexdigest()
        (self.root / 'import_api_control_sources.json').write_text(json.dumps([{'path':'ordinary_fixture.py','sha256':digest}]))
        (self.root / 'reader_recovery').mkdir()
        (self.root / 'reader_recovery/source-manifest.json').write_text(json.dumps({'files':{}}))
        (self.root / 'test_publication_archive_route_history.py').write_bytes(b'# explicit owning copy fixture\n')
        tree = ast.parse((ROOT / 'verify_image.py').read_text())
        owning = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'owning_sources')
        namespace = {'Path':Path, 'os':os, 'json':json, 'stat':stat, 'hashlib':hashlib, 'FIXES':self.root}
        exec(compile(ast.Module(body=[owning], type_ignores=[]), 'actual-owning-sources', 'exec'), namespace)
        self.copy = namespace['owning_sources']; self.destination = Path(self.tmp.name) / 'copied'; self.destination.mkdir()

    def test_exact_auth_five_paths_are_copied(self):
        self.copy(self.destination)
        for row in self.rows:
            self.assertEqual((self.destination / row['path']).read_bytes(), (self.root / row['path']).read_bytes())

    def test_valid_hash_unknown_auth_path_refused_before_any_copy(self):
        path = self.root / 'reader_recovery/foreign-auth-fixture.py'; path.write_bytes(b'# foreign public fixture\n')
        self.rows[0] = {'path':'reader_recovery/foreign-auth-fixture.py', 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        (self.root / 'standalone_launch_auth_sources.json').write_text(json.dumps(self.rows))
        with self.assertRaises(AssertionError): self.copy(self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_auth_gate_occurs_once_at_unconditional_module_level(self):
        tree = ast.parse((ROOT / 'verify_image.py').read_text())
        def is_gate(node):
            return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'run'
                and any(isinstance(x, ast.Constant) and x.value == 'test_publication_launch_auth.py'
                        for x in ast.walk(node.value)))
        self.assertEqual(sum(is_gate(x) for x in tree.body), 1)
        self.assertEqual(sum(is_gate(x) for x in ast.walk(tree)), 1)


if __name__ == '__main__': unittest.main()
