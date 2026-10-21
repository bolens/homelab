"""Portable source/refusal controls; actual ABI/CLI acceptance runs in the image."""
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from fetch_tagger_sources import fetch

STACK = Path(__file__).resolve().parents[1]
PYTHON_URL = 'https://www.python.org/ftp/python/3.13.16/Python-3.13.16.tar.xz'
PYTHON_SHA = 'f4b1bfb3c79b5bb11b8d228a12504163b4c0dab4d679828d8f5f26b6cb6ab35d'


class SourceContract(unittest.TestCase):
    def python_source(self):
        return next(row for row in json.loads((STACK/'tagger-sources.json').read_text())
                    if row['name'] == 'cpython')

    def test_authenticated_source_pin_and_original_corresponding_sources(self):
        rows = json.loads((STACK/'tagger-sources.json').read_text())
        self.assertEqual(len(rows), 4)
        self.assertEqual({row['name'] for row in rows}, {'cpython', 'comicfn2dict', 'chardet', 'isocodes'})
        self.assertEqual(self.python_source(), dict(name='cpython', version='3.13.16',
            filename='Python-3.13.16.tar.xz', url=PYTHON_URL, sha256=PYTHON_SHA))

    def test_only_modern_interpreter_changes_and_both_runtime_copies_exist(self):
        docker = (STACK/'Dockerfile').read_text()
        stages = re.findall(r'^FROM (.+)', docker, re.M)
        bases = [line.split(' AS ')[0] for line in stages if 'linuxserver/mylar3:' in line]
        self.assertEqual(len(set(bases)), 1)
        self.assertEqual(len(bases), 4)
        build = docker.split('\nFROM ', 1)[0]
        self.assertIn('./configure --prefix=/opt/tagger-python --without-static-libpython', build)
        self.assertIn('--disable-test-modules --with-ensurepip=install', build)
        self.assertIn('/opt/tagger-python/bin/python3.13 -m venv --without-pip /opt/comictagger', build)
        self.assertIn('--require-hashes --no-deps --no-build-isolation', build)
        self.assertEqual(docker.count('COPY --from=tagger-build /opt/tagger-python/ /opt/tagger-python/'), 2)
        self.assertNotRegex(docker, r'(?m)^ENV (?:PATH|LD_LIBRARY_PATH)=')
        self.assertNotIn('update-alternatives', docker)
        ddl = docker.split(' AS ddl-build\n', 1)[1].split('\nFROM ', 1)[0]
        self.assertIn('RUN python3 -m venv --without-pip /opt/ddl-transport', ddl)
        self.assertIn('prefix=[sys.executable,SCRIPT', (STACK/'config/tagger_legacy.py').read_text())
        self.assertIn("EXECUTABLE = '/opt/comictagger/bin/comictagger'", (STACK/'config/tagger_cli.py').read_text())

    def test_daemon_probe_version_is_separate_from_modern_tagger(self):
        import ast
        from types import SimpleNamespace
        docker=(STACK/'Dockerfile').read_text()
        self.assertIn("assert sys.version_info[:3]==(3,13,16)",docker)
        self.assertIn("assert sys.base_prefix=='/opt/tagger-python'",docker)
        self.assertIn("subprocess.check_output(['/usr/bin/python3','-I','-B','-c','import sys;print(sys.version_info[:2])'],text=True).strip()=='(3, 10)'",docker)
        source=(STACK/'config/reader_recovery/genuine_source_cohort.py').read_text()
        tree=ast.parse(source)
        program=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name)and t.id=='RUNTIME_PROGRAM'for t in n.targets)))
        emitter=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='Emitter')
        probe=next(n for n in emitter.body if isinstance(n,ast.FunctionDef)and n.name=='probe')
        argv_literals={n.value for n in ast.walk(probe)if isinstance(n,ast.Constant)and type(n.value)is str}
        self.assertIn('/lsiopy/bin/python3',argv_literals)
        self.assertNotIn('/opt/comictagger/bin/python',argv_literals)
        assertions=[n for n in ast.parse(program).body if isinstance(n,ast.Assert)and'sys.version_info'in ast.get_source_segment(program,n)]
        self.assertEqual(len(assertions),1)
        guard=compile(ast.Module(body=assertions,type_ignores=[]),'<owning-native-version>','exec')
        exec(guard,{'sys':SimpleNamespace(version_info=(3,10,22))})
        with self.assertRaises(AssertionError):exec(guard,{'sys':SimpleNamespace(version_info=(3,13,16))})

    def test_runtime_library_pairs_are_exact_and_build_tools_not_copied(self):
        docker = (STACK/'Dockerfile').read_text()
        for dev, runtime, version in (('libssl-dev', 'libssl3', '3.0.2-0ubuntu1.30'),
                                       ('libffi-dev', 'libffi8', '3.4.2-4'),
                                       ('libsqlite3-dev', 'libsqlite3-0', '3.37.2-2ubuntu0.8')):
            self.assertIn(dev + '=' + version, docker)
            self.assertIn(runtime + '=' + version, docker)
        self.assertIn('libicu-dev=70.1-2', docker)
        self.assertNotIn('COPY --from=tagger-build /opt/tagger-build', docker)
        self.assertIn('/opt/tagger-python/lib/python3.13/ensurepip', docker)
        self.assertIn('/opt/tagger-python/lib/python3.13/site-packages/pip-*.dist-info', docker)
        self.assertIn('install -m 644 LICENSE /opt/tagger-python/LICENSE', docker)
        self.assertIn('install -m 644 Doc/license.rst /opt/tagger-python/LICENSES.rst', docker)
        self.assertIn("CFLAGS='-O2 -g0' ./configure", docker)

    def test_pillow_has_exact_supported_cp313_amd64_artifact(self):
        lock = (STACK/'requirements.txt').read_text()
        block = re.search(r'^pillow==[^\n]+\n(?:    --hash=[^\n]+\n)+', lock, re.M).group()
        self.assertEqual(block, 'pillow==13.0.0 \\\n    --hash=sha256:5f56499c1a74d2b862beb0c33b8016f99d095858455df9d21583bbbc1c15b582\n')
        self.assertNotIn('--ignore-requires-python', (STACK/'Dockerfile').read_text())
        notices = (STACK/'tagger-NOTICES.md').read_text()
        self.assertIn('python3.13/site-packages', notices)
        self.assertIn('thomas@python.org', notices)
        self.assertIn('https://accounts.google.com', notices)

    def exercise_fetch(self, row, content=b'fixture-source'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root/'manifest.json'
            manifest.write_text(json.dumps([row]))
            with patch('fetch_tagger_sources.urllib.request.urlopen', return_value=io.BytesIO(content)) as call:
                fetch(manifest, root/'sources')
                self.assertEqual(call.call_args.args[0], row['url'])
                self.assertEqual((root/'sources'/row['filename']).read_bytes(), content)
                self.assertEqual((root/'sources/manifest.json').read_bytes(), manifest.read_bytes())

    def test_exact_python_origin_fetch_retains_hash_checked_fixture_bytes(self):
        row = self.python_source()
        row['sha256'] = hashlib.sha256(b'fixture-source').hexdigest()
        self.exercise_fetch(row)

    def test_original_pypi_source_route_unchanged(self):
        row = dict(name='fixture', version='1', filename='fixture-1.tar.gz',
                   url='https://files.pythonhosted.org/packages/fixture-1.tar.gz',
                   sha256=hashlib.sha256(b'fixture-source').hexdigest())
        self.exercise_fetch(row)

    def test_python_origin_version_filename_and_other_host_substitutions_refuse(self):
        changes = ({'version':'3.13.17'}, {'filename':'Python-3.13.17.tar.xz'},
                   {'filename':'../Python-3.13.16.tar.xz'},
                   {'url':'https://www.python.org.attacker.invalid/Python-3.13.16.tar.xz'},
                   {'url':PYTHON_URL + '?other=1'},
                   {'url':'https://files.pythonhosted.org/Python-3.13.16.tar.xz'},
                   {'name':'other-python'})
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                row = dict(self.python_source(), **change)
                root = Path(directory);manifest = root/'manifest.json'
                manifest.write_text(json.dumps([row]))
                with patch('fetch_tagger_sources.urllib.request.urlopen') as call:
                    with self.assertRaises(ValueError):fetch(manifest, root/'sources')
                    call.assert_not_called()
                self.assertFalse((root/'sources/manifest.json').exists())

    def test_changed_archive_bytes_never_create_source_or_success_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);manifest = root/'manifest.json'
            manifest.write_text(json.dumps([self.python_source()]))
            with patch('fetch_tagger_sources.urllib.request.urlopen', return_value=io.BytesIO(b'changed')):
                with self.assertRaises(ValueError):fetch(manifest, root/'sources')
            self.assertEqual(list((root/'sources').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
