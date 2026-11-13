"""Private collector runtime guards never alter AIL's importer interpreter."""
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'pystemon_runtime', ROOT / 'stacks/ail-framework/install-pystemon-runtime.py')
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class PystemonRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = 'prefix\n' + RUNTIME.IMPORTER + '\n' + RUNTIME.COLLECTOR + '\nsuffix\n'
        self.contract = {'sha256': hashlib.sha256(self.original.encode()).hexdigest()}

    def test_only_collector_changes_and_repeat_is_identical(self):
        result = RUNTIME.launcher_text(self.original, self.contract, Path('/opt/pystemon-runtime'))
        self.assertIn(RUNTIME.IMPORTER, result)
        self.assertEqual(result.replace('/opt/pystemon-runtime/venv/bin/python', '${ENV_PY}'),
                         self.original)
        self.assertEqual(RUNTIME.launcher_text(result, self.contract,
                                              Path('/opt/pystemon-runtime')), result)

    def test_launcher_source_command_duplicates_and_unsafe_prefix_fail_closed(self):
        for text in (self.original + '# drift', self.original + RUNTIME.COLLECTOR,
                     self.original.replace('PystemonImporter.py', 'Other.py')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                RUNTIME.launcher_text(text, self.contract, Path('/opt/pystemon-runtime'))
        with self.assertRaises(ValueError):
            RUNTIME.launcher_text(self.original, self.contract, Path('/tmp/a;command'))

    def test_source_census_rejects_changed_additional_missing_and_symlink_files(self):
        source = self.root / 'source'
        source.mkdir()
        file = source / 'pystemon.py'
        file.write_text('pass\n')
        contract = {'pythonFiles': {'pystemon.py': RUNTIME.sha(file)}}
        RUNTIME.verify_source(source, contract)
        file.write_text('changed\n')
        with self.assertRaises(ValueError):
            RUNTIME.verify_source(source, contract)

        file.write_text('pass\n')
        extra = source / 'extra.py'
        extra.write_text('pass\n')
        with self.assertRaises(ValueError):
            RUNTIME.verify_source(source, contract)
        extra.unlink()
        file.unlink()
        with self.assertRaises(ValueError):
            RUNTIME.verify_source(source, contract)
        file.symlink_to('../outside.py')
        (self.root / 'outside.py').write_text('pass\n')
        with self.assertRaises(ValueError):
            RUNTIME.verify_source(source, contract)


    def test_launcher_drift_is_rejected_before_download_or_runtime_creation(self):
        source = self.root / 'source'
        source.mkdir()
        (source / 'pystemon.py').write_text('pass\n')
        manifest = self.root / 'contract.json'
        manifest.write_text(json.dumps({
            'pystemon': {'pythonFiles': {'pystemon.py': RUNTIME.sha(source / 'pystemon.py')}},
            'launcher': self.contract}))
        requirements = self.root / 'requirements.txt'
        requirements.write_text('fixture')
        launcher = self.root / 'LAUNCH.sh'
        launcher.write_text(self.original + '# unexpected upstream change')
        prefix = self.root / 'runtime'
        with patch.object(RUNTIME, 'download') as download, self.assertRaises(ValueError):
            RUNTIME.install(manifest, requirements, source, launcher, prefix)
        download.assert_not_called()
        self.assertFalse(prefix.exists())
    def archive(self, name, kind=tarfile.REGTYPE, link=''):
        path = self.root / 'archive.tar'
        with tarfile.open(path, 'w') as output:
            info = tarfile.TarInfo(name)
            info.type, info.linkname = kind, link
            info.size = 4 if kind == tarfile.REGTYPE else 0
            output.addfile(info, io.BytesIO(b'pass') if info.size else None)
        return path

    def test_archive_rejects_escape_and_special_entries_before_writing(self):
        target = self.root / 'target'
        target.mkdir()
        for name, kind, link in (('../outside', tarfile.REGTYPE, ''),
                                 ('/absolute', tarfile.REGTYPE, ''),
                                 ('python/link', tarfile.SYMTYPE, '../../outside'),
                                 ('python/hard', tarfile.LNKTYPE, 'python/file'),
                                 ('python/device', tarfile.CHRTYPE, '')):
            with self.subTest(name=name), self.assertRaises((ValueError, tarfile.FilterError)):
                RUNTIME.extract(self.archive(name, kind, link), target)
            self.assertEqual(list(target.iterdir()), [])

    def test_archive_preserves_internal_python_symlink_and_executable(self):
        archive = self.root / 'valid.tar'
        with tarfile.open(archive, 'w') as output:
            info = tarfile.TarInfo('python/bin/python3.13')
            info.size, info.mode = 4, 0o755
            output.addfile(info, io.BytesIO(b'pass'))
            info = tarfile.TarInfo('python/bin/python3')
            info.type, info.linkname = tarfile.SYMTYPE, 'python3.13'
            output.addfile(info)
        RUNTIME.extract(archive, self.root / 'target')
        self.assertEqual((self.root / 'target/python/bin/python3').read_bytes(), b'pass')
        self.assertTrue((self.root / 'target/python/bin/python3.13').stat().st_mode & 0o111)


if __name__ == '__main__':
    unittest.main()
