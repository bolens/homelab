"""Private actors can mutate their fixtures; tracked input copies remain intact."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('private_controls', ROOT / 'scripts/run-private-comic-controls.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class Controls(unittest.TestCase):
    def setUp(self):
        self.git_environment = {key: value for key, value in os.environ.items()
                                if not key.startswith('GIT_')}
        self.git_environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.file = self.source / 'actor.py'
        self.file.write_bytes(b'# public actor\n')
        self.file.chmod(0o644)
        self.document = {'version': 1, 'mode': 'worker', 'files': {
            'actor.py': {'sha256': hashlib.sha256(self.file.read_bytes()).hexdigest(), 'mode': 0o644}}}
        self.destination = self.root / 'private'

    def test_ignored_secret_and_cache_not_copied(self):
        (self.source / 'secret.ini').write_text('synthetic ignored secret')
        (self.source / '__pycache__').mkdir()
        m.copy_public(self.source, self.document, self.destination)
        self.assertEqual(sorted(p.name for p in self.destination.iterdir()), ['actor.py'])

    def test_actual_actor_chmod_and_parent_fault_preserves_original(self):
        before = m.signature(self.file)
        files, nodes = m.copy_public(self.source, self.document, self.destination)
        code = "from pathlib import Path; p=Path('actor.py'); p.chmod(0o640); Path('.').chmod(0o750); p.write_bytes(b'changed')"
        subprocess.run([sys.executable, '-I', '-B', '-c', code], cwd=self.destination, check=True)
        m.close_originals(files, nodes)
        self.assertEqual(m.signature(self.file), before)
        self.assertEqual(self.file.read_bytes(), b'# public actor\n')

    def test_later_common_ancestor_cannot_replace_original(self):
        other = self.source / 'later.py'
        other.write_bytes(b'# public later actor\n')
        real = Path.lstat
        fired = []
        def late(path):
            if path == self.file and not fired:
                self.source.chmod(0o750)
                fired.append(True)
            return real(path)
        with patch.object(Path, 'lstat', late), self.assertRaisesRegex(ValueError, 'ancestor changed during capture'):
            m.capture(self.source, ['actor.py', 'later.py'])
        self.assertTrue(fired)

    def test_byte_drift_refused(self):
        self.file.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError, 'bytes differ'):
            m.copy_public(self.source, self.document, self.destination)

    def test_symlink_and_hardlink_refused(self):
        saved = self.root / 'saved'
        self.file.rename(saved)
        self.file.symlink_to(saved)
        with self.assertRaisesRegex(ValueError, 'regular single-link'):
            m.copy_public(self.source, self.document, self.destination)
        self.file.unlink()
        os.link(saved, self.file)
        with self.assertRaisesRegex(ValueError, 'regular single-link'):
            m.copy_public(self.source, self.document, self.destination)

    def test_unsafe_manifest_path_refused(self):
        self.document['files'] = {'../escape': self.document['files']['actor.py']}
        with self.assertRaisesRegex(ValueError, 'Unsafe public source path'):
            m.copy_public(self.source, self.document, self.destination)

    def test_copy_callback_original_drift_refused(self):
        real = Path.read_bytes
        def late(path):
            raw = real(path)
            if path == self.destination / 'actor.py':
                self.file.chmod(0o640)
            return raw
        with patch.object(Path, 'read_bytes', late), self.assertRaisesRegex(ValueError, 'Original public source file changed'):
            m.copy_public(self.source, self.document, self.destination)

    def test_child_failure_remains_checked(self):
        self.assertEqual(m.command('mylar', self.destination), [sys.executable, '-B', str(self.destination / 'verify_image.py')])
        self.assertEqual(m.command('worker', self.destination), [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(self.destination), '-p', 'test_*.py'])
        with self.assertRaises(ValueError):
            m.command('arbitrary', self.destination)
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.run([sys.executable, '-c', 'raise SystemExit(13)'], check=True)

    def test_inventory_only_git_tracked_public_sources_and_exclusive_output(self):
        repo = self.root / 'repo'
        scripts = repo / 'scripts'
        scripts.mkdir(parents=True)
        source = repo / m.SCOPES['worker']
        source.mkdir(parents=True)
        (source / 'public.py').write_text('# public\n')
        (source / 'ignored.ini').write_text('synthetic ignored')
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, env=self.git_environment)
        subprocess.run(['git', '-C', str(repo), 'add', 'stacks/komga/normalizer/public.py'], check=True, env=self.git_environment)
        output = self.root / 'inventory.json'
        foreign = self.root / 'foreign.git'
        with patch.object(m, '__file__', str(scripts / 'run-private-comic-controls.py')), \
                patch.dict(os.environ, GIT_DIR=str(foreign), GIT_WORK_TREE=str(self.root / 'foreign-tree'),
                           GIT_INDEX_FILE=str(self.root / 'foreign-index')):
            m.inventory('worker', output)
            with self.assertRaises(FileExistsError):
                m.inventory('worker', output)
        self.assertEqual(set(json.loads(output.read_bytes())['files']), {'public.py'})
        self.assertFalse(foreign.exists())
        self.assertFalse((self.root / 'foreign-index').exists())

    def runtime(self, failing=False):
        test = self.source / 'test_actor.py'
        test.write_text("from pathlib import Path\nimport unittest\nclass T(unittest.TestCase):\n def test_actor(self):\n  p=Path(__file__);p.chmod(0o640);p.parent.chmod(0o750)\n  self.assertEqual(" + ('1,2' if failing else '1,1') + ")\n")
        test.chmod(0o644)
        self.document['files']['test_actor.py'] = {'sha256': hashlib.sha256(test.read_bytes()).hexdigest(), 'mode': 0o644}
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps(self.document))
        before = m.signature(test)
        with patch.object(m, 'MANIFEST', manifest), patch.dict(m.MOUNTS, worker=self.source):
            if failing:
                with self.assertRaises(subprocess.CalledProcessError):
                    m.run('worker')
            else:
                m.run('worker')
        self.assertEqual(m.signature(test), before)

    def test_real_fixed_worker_run_mutates_only_private_copy(self):
        self.runtime()

    def test_real_fixed_worker_failure_propagates(self):
        self.runtime(failing=True)

    @unittest.skipUnless(os.geteuid() in (0, 1000), 'Local worker fixture requires Root or UID1000')
    def test_local_worker_inventories_repository_and_preserves_originals(self):
        self.root.chmod(0o755)
        repo = self.root / 'repo'
        scripts = repo / 'scripts'
        scripts.mkdir(parents=True)
        source = repo / m.SCOPES['worker']
        source.mkdir(parents=True)
        test = source / 'test_actor.py'
        test.write_text("import os,unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n def test_actor(self):\n  self.assertEqual(os.geteuid(),1000)\n  self.assertTrue(Path(os.environ['ARCHIVING_UTILS_BIN']).is_file())\n  Path(__file__).chmod(0o600)\n")
        test.chmod(0o644)
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, env=self.git_environment)
        subprocess.run(['git', '-C', str(repo), 'add', 'stacks/komga/normalizer/test_actor.py'],
                       check=True, env=self.git_environment)
        before = m.signature(test)
        backend = self.root / 'sdk' / 'bin' / 'archiving-utils'
        backend.parent.mkdir(parents=True)
        backend.write_text('#!/bin/sh\nexit 0\n')
        backend.chmod(0o755)
        with patch.object(m, '__file__', str(scripts / 'run-private-comic-controls.py')), \
                patch.dict(os.environ, ARCHIVING_UTILS_ROOT=str(backend.parent.parent), ARCHIVING_UTILS_BIN=''):
            m.run_local_worker()
        self.assertEqual(m.signature(test), before)

    def test_complete_worker_refuses_skipped_controls(self):
        actor = self.source / 'test_actor.py'
        actor.write_text("import unittest\nclass T(unittest.TestCase):\n @unittest.skip('synthetic absent tool')\n def test_actor(self): pass\n")
        actor.chmod(0o644)
        self.document['files']['test_actor.py'] = {
            'sha256': hashlib.sha256(actor.read_bytes()).hexdigest(), 'mode': 0o644}
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps(self.document))
        before = m.signature(actor)
        with patch.dict(os.environ, ARCHIVING_UTILS_BIN=sys.executable):
            with self.assertRaises(subprocess.CalledProcessError):
                m._run('worker', self.source, manifest, local=True)
        self.assertEqual(m.signature(actor), before)

    def test_local_worker_missing_backend_fails_without_skipping_actor(self):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps(self.document))
        with patch.dict(os.environ, ARCHIVING_UTILS_ROOT=str(self.root / 'missing'), ARCHIVING_UTILS_BIN=''), \
                patch.object(m.subprocess, 'run') as child:
            with self.assertRaisesRegex(ValueError, 'Local worker requires executable'):
                m._run('worker', self.source, manifest, local=True)
        child.assert_not_called()

    def test_local_worker_refuses_unsupported_identity_before_inventory(self):
        with patch.object(m.os, 'geteuid', return_value=2000), \
                patch.object(m, 'inventory') as inventory:
            with self.assertRaisesRegex(ValueError, 'Root or UID1000'):
                m.run_local_worker()
        inventory.assert_not_called()

    def cleanup_runtime(self, primary=None, cleanup=None):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps(self.document))
        real = m.tempfile.TemporaryDirectory

        class LateCleanup:
            def __init__(inner, **kw):
                inner.value = real(**kw)
            def __enter__(inner):
                return inner.value.__enter__()
            def __exit__(inner, *args):
                result = inner.value.__exit__(*args)
                self.file.chmod(0o640)
                if cleanup is not None:
                    raise cleanup
                return result

        def child(*args, **kw):
            if primary is not None:
                raise primary
            return subprocess.CompletedProcess(args, 0)

        with patch.object(m, 'MANIFEST', manifest), patch.dict(m.MOUNTS, worker=self.source), \
                patch.object(m.tempfile, 'TemporaryDirectory', LateCleanup), \
                patch.object(m.subprocess, 'run', side_effect=child):
            m.run('worker')

    def test_originals_close_after_temporary_cleanup(self):
        with self.assertRaisesRegex(ValueError, 'Original public source file changed'):
            self.cleanup_runtime()

    def test_primary_child_failure_survives_late_cleanup_drift(self):
        primary = subprocess.CalledProcessError(13, ['fixture'])
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            self.cleanup_runtime(primary)
        self.assertIs(caught.exception, primary)
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_child_failure_survives_raising_cleanup_and_final_drift(self):
        primary = subprocess.CalledProcessError(13, ['fixture'])
        cleanup = OSError('cleanup failure')
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            self.cleanup_runtime(primary, cleanup)
        self.assertIs(caught.exception, primary)
        self.assertIs(primary.__cause__, cleanup)
        self.assertIsInstance(cleanup.__cause__, ValueError)

    def test_inventory_closes_after_output_callback(self):
        repo = self.root / 'repo'
        scripts = repo / 'scripts'
        scripts.mkdir(parents=True)
        source = repo / m.SCOPES['worker']
        source.mkdir(parents=True)
        file = source / 'public.py'
        file.write_text('# public\n')
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, env=self.git_environment)
        subprocess.run(['git', '-C', str(repo), 'add', 'stacks/komga/normalizer/public.py'], check=True, env=self.git_environment)
        real = open
        primary = OSError('output close failure')
        class Output:
            def __init__(inner, *args):
                inner.file = real(*args)
            def __enter__(inner):
                return inner.file.__enter__()
            def __exit__(inner, *args):
                inner.file.__exit__(*args)
                file.chmod(0o640)
                raise primary
        with patch.object(m, '__file__', str(scripts / 'run-private-comic-controls.py')), \
                patch.object(m, 'open', Output, create=True), self.assertRaises(OSError) as caught:
            m.inventory('worker', self.root / 'output.json')
        self.assertIs(caught.exception, primary)
        self.assertIsInstance(primary.__cause__, ValueError)

    def test_workflow_keeps_readonly_inputs_and_fixed_modes(self):
        workflow = (ROOT / '.github/workflows/repository-validation.yml').read_text()
        verifier = (ROOT / 'stacks/mylar3/verify-image.sh').read_text()
        for source in (workflow, verifier):
            self.assertIn('--network=none --read-only --user=1000:1000', source)
            self.assertIn('--cap-drop=ALL --security-opt=no-new-privileges', source)
            self.assertIn('dst=/ci-controls.py,readonly', source)
            self.assertIn('dst=/ci-source-map.json,readonly', source)
        self.assertIn('dst=/app,readonly', workflow)
        self.assertIn('dst=/fixes,readonly', verifier)
        self.assertIn('-I -B /ci-controls.py worker', workflow)
        self.assertIn('-I -B /ci-controls.py mylar', verifier)


if __name__ == '__main__':
    unittest.main()
