"""Input/renderer controls; fixture catalogs are never runtime acceptance."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).absolute().parent
SPEC = importlib.util.spec_from_file_location('tagging_inputs_under_test', HERE / 'tagging_stage_inputs.py')
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)


class Inputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'config'; self.root.mkdir()
        self.pins = {}
        self.register(t.SUITE, b'import helper\n')
        self.register('helper.py', b'import json\n')
        self.docker = self.root.parent / 'Dockerfile'
        self.original_docker = 'FROM pinned-runtime\n' + t.BEGIN + '\n' + t.END + '\nRUN preserve\n'
        self.docker.write_text(self.original_docker)

    def register(self, name, raw):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw); self.pins[name] = hashlib.sha256(raw).hexdigest()
        rows = [dict(path=key, sha256=pin) for key, pin in sorted(self.pins.items())]
        (self.root / 'import_api_control_sources.json').write_text(json.dumps(rows))

    def store(self, value):
        (self.root / 'tagging_stage_sources.json').write_text(json.dumps(value))

    def test_actual_public_manifest_closes_without_repository_or_dockerfile(self):
        value = t.decode(t.read(HERE / 'tagging_stage_sources.json'))
        t.validate(HERE, value)
        names = {row['path'] for row in value['files']}
        self.assertIn(t.SUITE, names); self.assertIn('native_writers.py', names)
        self.assertIn('queue_progress.py', names)
        self.assertNotIn('genuine_plan13_producer.py', names)
        self.assertTrue(all('/' not in name for name in names))

    def test_changed_included_source_requires_catalog_and_manifest_refresh(self):
        before = t.build_manifest(self.root)
        (self.root / 'helper.py').write_bytes(b'import json\nchanged=True\n')
        with self.assertRaisesRegex(ValueError, 'source hash drift'):t.validate(self.root, before)
        self.register('helper.py', b'import json\nchanged=True\n')
        with self.assertRaisesRegex(ValueError, 'closure/hash mismatch'):t.validate(self.root, before)
        self.assertNotEqual(before, t.build_manifest(self.root))

    def test_unrelated_registered_reader_and_ignored_files_are_not_inputs(self):
        before = t.build_manifest(self.root)
        self.register('reader_recovery/unrelated.py', b'ignored reader implementation\n')
        (self.root / 'private-live.ini').write_text('not a public input')
        t.validate(self.root, before)
        (self.root / 'reader_recovery/unrelated.py').write_bytes(b'changed without catalog refresh\n')
        t.validate(self.root, before)
        self.assertEqual({row['path'] for row in before['files']}, {t.SUITE, 'helper.py'})

    def test_new_literal_dependency_must_be_registered_and_declared(self):
        self.register(t.SUITE, b"SOURCE='dynamic.py'\n")
        (self.root / 'dynamic.py').write_bytes(b'present but unregistered\n')
        with self.assertRaisesRegex(ValueError, 'unregistered local dependency'):t.build_manifest(self.root)
        self.register('dynamic.py', b'pass\n')
        value = t.build_manifest(self.root)
        self.assertEqual({row['path'] for row in value['files']}, {t.SUITE, 'dynamic.py'})
        value['files'] = [row for row in value['files'] if row['path'] != 'dynamic.py']
        with self.assertRaises(ValueError):t.validate(self.root, value)

    def test_new_local_import_cannot_fall_back_to_ambient_files(self):
        for source in (b'from . import missing\n', b'import missing\n',
                       b'from mylar.missing import field\n'):
            with self.subTest(source=source):
                self.register(t.SUITE, source)
                with self.assertRaisesRegex(ValueError, 'unregistered'):t.build_manifest(self.root)

    def test_native_and_sdk_dependencies_are_not_fabricated_local_sources(self):
        self.register(t.SUITE, b"from mylar import db\nimport archive_backend\nNATIVE='api.py'\n")
        self.assertEqual([row['path'] for row in t.build_manifest(self.root)['files']], [t.SUITE])

    def test_duplicate_unsafe_and_malformed_catalog_rows_refuse(self):
        original = json.loads((self.root / 'import_api_control_sources.json').read_bytes())
        for rows in (original + [original[0]], [dict(path='../escape.py', sha256='0'*64)],
                     [dict(path='/absolute.py', sha256='0'*64)],
                     [dict(path='helper.py', sha256='not a hash')]):
            with self.subTest(rows=rows):
                (self.root / 'import_api_control_sources.json').write_text(json.dumps(rows))
                with self.assertRaises(ValueError):t.build_manifest(self.root)

    def test_duplicate_json_keys_refuse(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            t.decode('{"version":1,"version":1}')

    def test_omitted_extra_unsorted_or_duplicate_manifest_inputs_refuse(self):
        value = t.build_manifest(self.root)
        self.register('extra.py', b'pass\n')
        variants = [dict(value, files=value['files'][1:]),
                    dict(value, files=list(reversed(value['files']))),
                    dict(value, files=value['files'] + [value['files'][0]]),
                    dict(value, files=sorted(value['files'] + [dict(path='extra.py', sha256=self.pins['extra.py'])], key=lambda r: r['path']))]
        for candidate in variants:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):t.validate(self.root, candidate)

    def test_manifest_shape_paths_hashes_and_boolean_counts_refuse(self):
        value = t.build_manifest(self.root)
        variants = [dict(value, version=True), dict(value, tests=True), dict(value, tests=116),
                    dict(value, unexpected=True)]
        for path in ('../escape.py', 'nested/source.py', '/source.py', 'bad.py \\'):
            candidate = deepcopy(value); candidate['files'][0]['path'] = path; variants.append(candidate)
        candidate = deepcopy(value); candidate['files'][0]['sha256'] = 'wrong'; variants.append(candidate)
        for candidate in variants:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):t.validate(self.root, candidate)

    def test_symlink_and_oversized_source_refuse(self):
        leaf = self.root / 'helper.py'; leaf.unlink()
        outside = self.root.parent / 'outside.py'; outside.write_bytes(b'import json\n')
        leaf.symlink_to(outside)
        with self.assertRaises(ValueError):t.build_manifest(self.root)
        leaf.unlink(); self.register('helper.py', b'#' * (t.MAX_SOURCE + 1))
        with self.assertRaises(ValueError):t.build_manifest(self.root)

    def test_renderer_and_marker_boundaries_are_exact(self):
        value = t.build_manifest(self.root); block = t.render(value)
        expected = (t.BEGIN + '\nCOPY config/helper.py \\\n'
                    '    config/test_publication_tagging.py \\\n'
                    '    /opt/mylar-tagging-inputs/\n' + t.END + '\n')
        self.assertEqual(block, expected)
        updated = t.replace_block(self.original_docker, block)
        self.assertEqual(updated, 'FROM pinned-runtime\n' + block + 'RUN preserve\n')
        for text in ('FROM base\n', self.original_docker + t.BEGIN,
                     t.END + '\n' + t.BEGIN + '\n',
                     self.original_docker.replace(t.BEGIN, 'prefix ' + t.BEGIN)):
            with self.subTest(text=text), self.assertRaises(ValueError):t.replace_block(text, block)

    def test_cli_render_is_read_only_and_explicit_write_closes_check(self):
        value = t.build_manifest(self.root); self.store(value)
        output = io.StringIO()
        with redirect_stdout(output):self.assertEqual(t.main(['--root', str(self.root), '--render']), 0)
        self.assertEqual(output.getvalue(), t.render(value))
        self.assertEqual(self.docker.read_text(), self.original_docker)
        with self.assertRaisesRegex(ValueError, 'COPY drift'):t.main(['--root', str(self.root), '--check'])
        self.assertEqual(t.main(['--root', str(self.root), '--write']), 0)
        self.assertEqual(t.main(['--root', str(self.root), '--check']), 0)
        self.docker.write_text(self.docker.read_text().replace('config/helper.py', 'config/foreign.py'))
        with self.assertRaisesRegex(ValueError, 'COPY drift'):t.main(['--root', str(self.root), '--check'])

    def test_write_refuses_missing_markers_before_changing_manifest(self):
        target = self.root / 'tagging_stage_sources.json'; target.write_bytes(b'preserve me')
        self.docker.write_text('FROM base\n')
        with self.assertRaises(ValueError):t.main(['--root', str(self.root), '--write'])
        self.assertEqual(target.read_bytes(), b'preserve me')


if __name__ == '__main__':
    unittest.main()
