"""Exercise the export publisher with local fixtures and no Docker or live data."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
import shutil


SCRIPT = Path(__file__).resolve().parents[1] / "calibre-kavita-sync.sh"
MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, shutil, stat, subprocess, sys, tempfile, zipfile
root = pathlib.Path(os.environ['SYNC_FIXTURE'])
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
def record(value):
    with (root/'calls').open('a') as f: f.write(value+'\n')
def epub(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('mimetype', 'application/epub+zip')
        z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="package.opf"/></rootfiles></container>')
        z.writestr('package.opf','<package version="'+('1.0' if value.startswith('legacy:') else '2.0')+'"/>')
        z.writestr('content.txt',value)
if name == 'findmnt':
    if os.environ.get('MOUNT_FAIL'): sys.exit(1)
    if os.environ.get('MOUNT_DISAPPEARS') and '-M' in args:
        counter=root/'mount-count'
        count=int(counter.read_text()) if counter.exists() else 0
        counter.write_text(str(count+1))
        if count>=2: sys.exit(1)
    print('/' if os.environ.get('COVERING_MOUNT_FAIL') and '-T' in args else root/'media')
elif name == 'runuser':
    command=args[args.index('--')+1:]
    os.execvp(command[0],command)
elif name == 'sqlite3': print('fixture-key')
elif name == 'rsync':
    record('publish')
    source,dest=map(pathlib.Path,args[-2:])
    shutil.copytree(source,dest,dirs_exist_ok=True)
elif name == 'ebook-convert':
    record('convert:'+pathlib.Path(args[0]).suffix)
    if os.environ.get('CONVERT_FAIL'): sys.exit(1)
    if zipfile.is_zipfile(args[0]):
        assert args[2:]==['--epub-version','2']
        with zipfile.ZipFile(args[0]) as archive: value=archive.read('content.txt').decode().removeprefix('legacy:')
    else: value=pathlib.Path(args[0]).read_text()
    epub(pathlib.Path(args[1]),value)
elif name == 'calibre-catalog-import':
    manifest=pathlib.Path(args[args.index('--manifest')+1])
    assert stat.S_IMODE(manifest.parent.stat().st_mode)==0o700
    candidates=json.loads((root/'candidates.json').read_text())
    record('planner')
    if os.environ.get('RAW_SOURCE_DRIFT') and (root/'planner-ran').exists():
        pathlib.Path(candidates[0]['path']).write_bytes(b'changed')
    (root/'planner-ran').touch()
    plan={'kind':'calibre-catalog-import-plan','version':1,'libraryPath':str(root/'media'/'books'),
          'counts':{'candidateBooks':len(candidates)},'candidates':candidates}
    with manifest.open('x') as f: json.dump(plan,f)
    manifest.chmod(0o600)
    print(json.dumps({'counts':plan['counts'],'manifestWritten':True}))
elif name == 'docker':
    if args[0]=='inspect':
        print(root/'media'/'books' if '.Mounts' in args[2] else 'true')
        sys.exit(0)
    args=args[1:]
    if args[0]=='--user': args=args[2:]
    if args[0]=='-i': args=args[1:]
    config_environment = None
    if args[0]=='--env':
        config_environment=args[1]; args=args[2:]
    container,command=args[0],args[1:]
    if command[0]=='calibre-debug':
        assert config_environment and config_environment.startswith('CALIBRE_CONFIG_DIRECTORY=/tmp/kavita-export.') and config_environment.endswith('/config')
        assert command[1]=='-e' and command[3]=='--'
        wrapper=pathlib.Path(command[2]).read_text()
        assert wrapper.index('DB.expire_old_trash =') < wrapper.index('from calibre.db.cli.main import main')
        assert "__version__.split('.')[:2] != ['9', '16']" in wrapper
        record('preserved-cli:'+command[4])
        if os.environ.get('UNSUPPORTED_CALIBRE'): sys.exit(1)
        command=['calibredb',*command[4:]]
    if command[0]=='mkdir':
        sys.exit(subprocess.run(command).returncode)
    elif command[0]=='mktemp':
        stage=subprocess.check_output(['mktemp','-d','/tmp/kavita-export.XXXXXX'],text=True).strip()
        record('stage:'+stage)
        print(stage)
    elif command[:2]==['calibredb','list']:
        counter=root/'list-count'
        count=int(counter.read_text()) if counter.exists() else 0
        counter.write_text(str(count+1))
        rows=json.loads((root/'registered.json').read_text())
        if os.environ.get('CATALOG_DRIFT') and count%2:
            rows[0]['last_modified']='changed'
        print(json.dumps(rows))
    elif command[:2]==['calibredb','export']:
        stage=pathlib.Path(command[command.index('--to-dir')+1])
        for filename,value in json.loads((root/'formats.json').read_text()).items():
            target=stage/filename
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.suffix.lower()=='.epub' and value!='corrupt': epub(target,value)
            else: target.write_text(value)
    elif command[:2]==['bash','-s']:
        assert '-i' in sys.argv[1:]
        result=subprocess.run(command,input=sys.stdin.buffer.read())
        sys.exit(result.returncode)
    elif command[0]=='python3':
        assert '-i' in sys.argv[1:]
        result=subprocess.run(command,input=sys.stdin.buffer.read())
        sys.exit(result.returncode)
    elif command[0]=='tar':
        if os.environ.get('DROP_RAW_EXPORT') and '-cf' in command:
            stage=pathlib.Path(command[command.index('-C')+1])
            shutil.rmtree(stage/'Uncataloged',ignore_errors=True)
        sys.exit(subprocess.run(command).returncode)
    elif command[:2]==['rm','-rf']:
        target=pathlib.Path(command[-1])
        assert str(target).startswith('/tmp/kavita-export.')
        shutil.rmtree(target,ignore_errors=True)
    elif command[0]=='sh':
        if '-i' in args: sys.stdin.buffer.read()
    else: raise SystemExit('Unexpected fixture Docker operation')
else: raise SystemExit('Unexpected fixture command')
'''


class CalibreKavitaSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("docker", "findmnt", "runuser", "rsync", "sqlite3", "ebook-convert", "calibre-catalog-import"):
            path = self.bin / name
            path.write_text(MOCK)
            path.chmod(0o755)
        source = self.root / "media" / "books"
        source.mkdir(parents=True)
        (source / "metadata.db").touch()
        self.destination = self.root / "media" / "export"
        self.database = self.root / "kavita.db"
        self.database.touch()
        self.environment = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                            "SYNC_FIXTURE": str(self.root), "KAVITA_EXPORT_DIR": str(self.destination),
                            "KAVITA_EXPORT_USER": "fixture", "KAVITA_DB": str(self.database),
                            "CALIBRE_SOURCE_MOUNT": str(self.root / "media"),
                            "KAVITA_EXPORT_MOUNT": str(self.root / "media"),
                            "CALIBRE_INCLUDE_UNREGISTERED_EPUBS": "false", "CALIBRE_NORMALIZE_LEGACY_EPUBS": "false",
                            "CALIBRE_IMPORT_PLANNER": str(self.bin / "calibre-catalog-import"),
                            "KAVITA_SYNC_LOCK": str(self.root / "sync.lock")}
        self.registered([1])
        self.formats({"Series/Series - 1.epub": "native"})
        (self.root / 'candidates.json').write_text('[]')

    def tearDown(self):
        for entry in self.calls():
            if entry.startswith('stage:/tmp/kavita-export.'):
                shutil.rmtree(entry.removeprefix('stage:'), ignore_errors=True)
        self.temp.cleanup()

    def registered(self, identifiers):
        (self.root / "registered.json").write_text(json.dumps([
            {"id": identifier, "uuid": "fixture-" + str(identifier), "last_modified": "unchanged"}
            for identifier in identifiers]))

    def formats(self, entries):
        (self.root / "formats.json").write_text(json.dumps(entries))

    def candidates(self, count=1, version='2.0'):
        records = []
        for index in range(count):
            path = self.root / 'media' / 'books' / 'loose' / f'private-source-{index}.epub'
            path.parent.mkdir(exist_ok=True)
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('mimetype', 'application/epub+zip')
                archive.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="package.opf"/></rootfiles></container>')
                archive.writestr('package.opf', f'<package version="{version}"/>')
                archive.writestr('content.txt', ('legacy:' if version == '1.0' else '') + str(index))
            records.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'format': 'EPUB'})
        (self.root / 'candidates.json').write_text(json.dumps(records))
        return records

    def source_hashes(self):
        source = self.root / 'media' / 'books'
        return {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in source.rglob('*') if path.is_file()}

    def run_sync(self, **extra):
        return subprocess.run(["bash", str(SCRIPT)], env={**self.environment, **extra},
                              capture_output=True, text=True, timeout=20)

    def calls(self):
        path = self.root / "calls"
        return path.read_text().splitlines() if path.exists() else []

    def exported_content(self):
        with zipfile.ZipFile(self.destination / "Series" / "Series - 1.epub") as archive:
            return archive.read("content.txt").decode()

    def test_all_native_catalog_reads_preserve_trash_with_private_stdin_wrapper(self):
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call for call in self.calls() if call.startswith('preserved-cli:')],
                         ['preserved-cli:list', 'preserved-cli:export', 'preserved-cli:list'])
        self.assertFalse(any(path.name.endswith('.py') for path in self.destination.rglob('*')))
        for call in self.calls():
            if call.startswith('stage:'):
                self.assertFalse(Path(call.removeprefix('stage:')).exists())

    def test_unsupported_calibre_version_refuses_before_publication(self):
        result = self.run_sync(UNSUPPORTED_CALIBRE='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('publish', self.calls())

    def test_native_epub_survives_other_formats_without_conversion(self):
        self.formats({"Series/Series - 1.epub": "native", "Series/Series - 1.azw3": "azw3",
                      "Series/Series - 1.mobi": "mobi"})
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.exported_content(), "native")
        self.assertFalse(any(call.startswith("convert:") for call in self.calls()))
        self.assertIn("Validated export for 1 registered books", result.stdout)

    def test_azw3_precedes_mobi_deterministically(self):
        self.formats({"Series/Series - 1.mobi": "mobi", "Series/Series - 1.azw3": "azw3"})
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.exported_content(), "azw3")
        self.assertEqual([call for call in self.calls() if call.startswith("convert:")], ["convert:.azw3"])

    def test_mobi_is_used_when_no_epub_or_azw3_exists(self):
        self.formats({"Series/Series - 1.mobi": "mobi"})
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.exported_content(), "mobi")

    def test_missing_or_wrong_mount_never_creates_destination_or_publishes(self):
        for setting in ("MOUNT_FAIL", "COVERING_MOUNT_FAIL"):
            result = self.run_sync(**{setting: "1"})
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.destination.exists())
            self.assertNotIn("publish", self.calls())

    def test_partial_empty_or_corrupt_export_never_publishes(self):
        for registered, formats in (([1, 2], {"Series/Series - 1.epub": "native"}),
                                    ([1], {"Series/Series - 2.epub": "wrong-id"}),
                                    ([1], {}), ([1], {"Series/Series - 1.epub": "corrupt"}),
                                    ([], {})):
            with self.subTest(registered=registered, formats=len(formats)):
                self.registered(registered)
                self.formats(formats)
                result = self.run_sync()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("publish", self.calls())

    def test_mount_disappearance_before_publication_preserves_destination(self):
        self.destination.mkdir()
        marker = self.destination / 'existing-file'
        marker.write_text('preserved')
        result = self.run_sync(MOUNT_DISAPPEARS='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('publish', self.calls())
        self.assertEqual(marker.read_text(), 'preserved')

    def test_uppercase_native_epub_is_preserved(self):
        self.formats({'Series/Series - 1.EPUB': 'native', 'Series/Series - 1.azw3': 'azw3'})
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(self.destination / 'Series' / 'Series - 1.EPUB') as archive:
            self.assertEqual(archive.read('content.txt'), b'native')
        self.assertFalse(any(call.startswith('convert:') for call in self.calls()))

    def test_catalog_drift_prevents_publication(self):
        result = self.run_sync(CATALOG_DRIFT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed during export", result.stderr)
        self.assertNotIn("publish", self.calls())

    def test_lock_prevents_overlap_before_any_export_activity(self):
        with (self.root / "sync.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already running", result.stdout)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.calls(), [])

    def test_each_run_has_unique_staging_and_cleans_only_its_own_directory(self):
        for _ in range(2):
            result = self.run_sync()
            self.assertEqual(result.returncode, 0, result.stderr)
        stages = [call.removeprefix("stage:") for call in self.calls() if call.startswith("stage:")]
        self.assertEqual(len(set(stages)), 2)
        self.assertTrue(all(not Path(path).exists() for path in stages))
        self.assertEqual(list((self.root / "media").glob(".kavita-books-stage.*")), [])

    def test_unregistered_export_is_disabled_by_default(self):
        self.candidates()
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.destination / 'Uncataloged').exists())
        self.assertNotIn('planner', self.calls())

    def test_confirmed_raw_batch_is_copied_with_exact_hash_names_and_sources_unchanged(self):
        records = self.candidates(65)
        baseline = self.source_hashes()
        result = self.run_sync(CALIBRE_INCLUDE_UNREGISTERED_EPUBS='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.source_hashes(), baseline)
        expected = {record['sha256'] for record in records}
        files = list((self.destination / 'Uncataloged').glob('*.epub'))
        self.assertEqual(len(files), 65)
        self.assertEqual({path.stem.removeprefix('uncataloged-') for path in files}, expected)
        self.assertEqual({hashlib.sha256(path.read_bytes()).hexdigest() for path in files}, expected)
        self.assertEqual(self.calls().count('planner'), 2)
        self.assertNotIn('private-source', result.stdout + result.stderr)

    def test_wrong_raw_source_hash_refuses_publication(self):
        records = self.candidates()
        records[0]['sha256'] = '0' * 64
        (self.root / 'candidates.json').write_text(json.dumps(records))
        baseline = self.source_hashes()
        result = self.run_sync(CALIBRE_INCLUDE_UNREGISTERED_EPUBS='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.source_hashes(), baseline)
        self.assertNotIn('publish', self.calls())

    def test_changed_raw_source_after_copy_refuses_publication(self):
        self.candidates()
        result = self.run_sync(CALIBRE_INCLUDE_UNREGISTERED_EPUBS='true', RAW_SOURCE_DRIFT='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('publish', self.calls())
        self.assertNotIn('private-source', result.stdout + result.stderr)

    def test_missing_raw_export_refuses_publication_even_when_registered_set_matches(self):
        self.candidates()
        result = self.run_sync(CALIBRE_INCLUDE_UNREGISTERED_EPUBS='true', DROP_RAW_EXPORT='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('raw EPUB count differs', result.stderr)
        self.assertNotIn('publish', self.calls())

    def test_legacy_package_requires_explicit_normalization_opt_in(self):
        self.formats({'Series/Series - 1.epub': 'legacy:native'})
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CALIBRE_NORMALIZE_LEGACY_EPUBS', result.stderr)
        self.assertNotIn('publish', self.calls())

    def test_legacy_registered_export_copy_is_normalized_only_when_enabled(self):
        self.formats({'Series/Series - 1.epub': 'legacy:native'})
        baseline = self.source_hashes()
        result = self.run_sync(CALIBRE_NORMALIZE_LEGACY_EPUBS='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.exported_content(), 'native')
        self.assertEqual(self.source_hashes(), baseline)
        self.assertEqual([call for call in self.calls() if call.startswith('convert:')], ['convert:.epub'])

    def test_legacy_raw_copy_keeps_source_hash_identity_and_verified_conversion_receipt(self):
        record = self.candidates(version='1.0')[0]
        baseline = self.source_hashes()
        result = self.run_sync(CALIBRE_INCLUDE_UNREGISTERED_EPUBS='true', CALIBRE_NORMALIZE_LEGACY_EPUBS='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        exported = self.destination / 'Uncataloged' / ('uncataloged-' + record['sha256'] + '.epub')
        self.assertTrue(exported.is_file())
        self.assertNotEqual(hashlib.sha256(exported.read_bytes()).hexdigest(), record['sha256'])
        self.assertEqual(self.source_hashes(), baseline)

    def test_normalization_failure_never_publishes_or_changes_source(self):
        self.candidates(version='1.0')
        baseline = self.source_hashes()
        result = self.run_sync(CALIBRE_INCLUDE_UNREGISTERED_EPUBS='true',
                               CALIBRE_NORMALIZE_LEGACY_EPUBS='true', CONVERT_FAIL='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.source_hashes(), baseline)
        self.assertNotIn('publish', self.calls())

    def test_fallback_conversion_failure_never_publishes(self):
        self.formats({'Series/Series - 1.azw3': 'azw3'})
        result = self.run_sync(CONVERT_FAIL='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('publish', self.calls())


if __name__ == "__main__":
    unittest.main()
