"""Fixed gate receipts and real subprocess/private-copy mechanics; no runtime grant."""
from contextlib import redirect_stdout, redirect_stderr
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).absolute().parent))
import verify_tagging_stage as stage


class StageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.sources = self.root / 'sources'; self.sources.mkdir()
        for i in range(89):
            (self.sources / ('source_%02d.py' % i)).write_text('VALUE = %d\n' % i)
        (self.sources / stage.SUITE).write_text('# explicit source fixture, no genuine runtime claim\n')
        self.rows = [dict(path=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                     for p in sorted(self.sources.iterdir())]
        self.document = dict(version=1, suite=stage.SUITE, tests=117, files=self.rows)
        self.map = self.root / 'tagging_stage_sources.json'
        self.map.write_text(json.dumps(self.document))
        self.output = self.root / 'result.json'

    def make_receipt(self):
        self.output.write_text(json.dumps(stage.receipt(self.map.read_bytes(), self.rows)))
        return json.loads(self.output.read_bytes())

    def full_config(self):
        # Full configuration contains the selected90 and unrelated leaves.
        (self.sources / self.map.name).write_bytes(self.map.read_bytes())
        (self.sources / 'unrelated.json').write_text('{}')
        return self.sources

    def run_fixture(self, text, expected=1):
        private = self.root / 'private'; private.mkdir()
        (private / 'test_fixture.py').write_text(text)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            stage.run_child(private, 'test_fixture.py', expected)
        return private

    def test_exact_selected90_hashes_and_original_closure(self):
        witness, _, rows, payload, names = stage.inputs(self.sources, self.map, exact=True)
        self.assertEqual(len(rows), 90); self.assertEqual(set(payload), set(names))
        witness.close()

    def test_missing_extra_symlink_and_hash_drift_refuse(self):
        first = self.sources / self.rows[0]['path']; original = first.read_bytes()
        first.unlink()
        with self.assertRaises(ValueError): stage.inputs(self.sources, self.map, exact=True)
        first.write_bytes(original)
        extra = self.sources / 'extra.py'; extra.write_text('')
        with self.assertRaises(ValueError): stage.inputs(self.sources, self.map, exact=True)
        extra.unlink(); first.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'hash'): stage.inputs(self.sources, self.map, exact=True)
        first.unlink(); first.symlink_to(self.map)
        with self.assertRaises(ValueError): stage.inputs(self.sources, self.map, exact=True)

    def test_duplicate_unsorted_paths_bad_version_or_count_refuse(self):
        for edit in ('duplicate', 'unsorted', 'traversal', 'version', 'count'):
            document = copy.deepcopy(self.document)
            if edit == 'duplicate': document['files'][-1] = document['files'][0]
            elif edit == 'unsorted': document['files'].reverse()
            elif edit == 'traversal': document['files'][0]['path'] = '../source.py'
            elif edit == 'version': document['version'] = True
            else: document['tests'] = 116
            with self.subTest(edit=edit), self.assertRaises(ValueError): stage.manifest(document)

    def test_real_child_private_path_and_write_leave_original_unchanged(self):
        original = self.sources / 'source_00.py'; before = stage.nine(original.stat())
        private = self.run_fixture("import unittest\nfrom pathlib import Path\nclass Tests(unittest.TestCase):\n def test_path(self):\n  self.assertEqual(Path(__file__).parent.name,'private')\n  Path(__file__).with_name('owned.txt').write_text('private')\n")
        self.assertEqual((private / 'owned.txt').read_text(), 'private')
        self.assertEqual(stage.nine(original.stat()), before)

    def test_failed_actual_child_refuses(self):
        with self.assertRaisesRegex(ValueError, 'child-failed'):
            self.run_fixture("import unittest\nclass Tests(unittest.TestCase):\n def test_no(self):self.fail('fixture failure')\n")

    def test_skipped_actual_child_refuses(self):
        with self.assertRaisesRegex(ValueError, 'count-or-skips'):
            self.run_fixture("import unittest\nclass Tests(unittest.TestCase):\n @unittest.skip('explicit test skip')\n def test_no(self):pass\n")

    def test_wrong_actual_child_count_refuses(self):
        with self.assertRaisesRegex(ValueError, 'count-or-skips'):
            self.run_fixture("import unittest\nclass Tests(unittest.TestCase):\n def test_one(self):pass\n", expected=2)

    def test_nonzero_after_success_marker_refuses(self):
        with self.assertRaisesRegex(ValueError, 'child-failed'):
            self.run_fixture("raise SystemExit(8)\n")

    def test_current_receipt_accepts_selected90_in_full_config_only(self):
        self.make_receipt(); full = self.full_config()
        result = stage.verify_receipt(full, self.output)
        self.assertEqual(result['tests'], 117)
        self.assertTrue(all(result[k] is False for k in stage.FLAGS))

    def test_missing_receipt_and_changed_current_source_refuse(self):
        full = self.full_config()
        with self.assertRaises(FileNotFoundError): stage.verify_receipt(full, self.output)
        self.make_receipt(); (full / self.rows[0]['path']).write_text('drift')
        with self.assertRaises(ValueError): stage.verify_receipt(full, self.output)

    def test_stale_manifest_and_forged_count_skip_or_acceptance_refuse(self):
        full = self.full_config(); original = self.make_receipt()
        for key, value in (('tests', 116), ('skips', 1), ('success', False),
                           ('version', True), ('manifest_sha256', '0' * 64), ('ACK', True)):
            forged = copy.deepcopy(original); forged[key] = value
            self.output.write_text(json.dumps(forged))
            with self.subTest(key=key), self.assertRaises(ValueError): stage.verify_receipt(full, self.output)
        duplicated = json.dumps(original).replace('{', '{\"version\":1,', 1)
        self.output.write_text(duplicated)
        with self.assertRaisesRegex(ValueError, 'duplicate-json'): stage.verify_receipt(full, self.output)
        self.output.write_text(json.dumps(original))
        (full / self.map.name).write_bytes(self.map.read_bytes() + b'\n')
        with self.assertRaises(ValueError): stage.verify_receipt(full, self.output)

    def test_same_bytes_new_inode_and_late_metadata_drift_refuse(self):
        witness, _, _, _, _ = stage.inputs(self.sources, self.map, exact=True)
        first = self.sources / self.rows[0]['path']; raw = first.read_bytes()
        first.unlink(); first.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'final-drift'): witness.close()
        witness, _, _, _, _ = stage.inputs(self.sources, self.map, exact=True)
        first.chmod(0o640)
        with self.assertRaisesRegex(ValueError, 'final-drift'): witness.close()

    def test_exclusive_receipt_writer_preserves_existing_file(self):
        value = stage.receipt(self.map.read_bytes(), self.rows)
        stage.write_receipt(self.output, value)
        self.assertEqual(json.loads(self.output.read_bytes()), value)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        before = self.output.read_bytes()
        with self.assertRaises(ValueError): stage.write_receipt(self.output, value)
        self.assertEqual(self.output.read_bytes(), before)

    def test_production_route_always_fixed117_and_never_accepts_missing_runtime(self):
        with patch.object(stage.os, 'geteuid', return_value=1000), patch.object(stage.os, 'getegid', return_value=1000), patch.object(stage.Path, 'is_file', return_value=False):
            with self.assertRaisesRegex(ValueError, 'genuine-tagging-runtime'):
                stage.run_stage(self.sources, self.map, self.output)
        self.assertFalse(self.output.exists())

    def test_real_child_timeout_never_creates_success_receipt(self):
        with patch.object(stage.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture', 1200)):
            with self.assertRaises(subprocess.TimeoutExpired): stage.run_child(self.sources, stage.SUITE, 117)
        self.assertFalse(self.output.exists())

    def test_postchild_original_drift_refuses_without_receipt(self):
        def child(private, suite, expected):
            self.assertEqual((suite, expected), (stage.SUITE, 117))
            self.assertEqual(private.stat().st_uid, os.geteuid())
            (private / self.rows[0]['path']).write_text('allowed private copy change')
            (self.sources / self.rows[0]['path']).write_text('forbidden source change')
        real = Path.is_file
        def installed(path):
            return True if str(path) in ('/opt/archiving-utils/lib/archive_backend.py', '/opt/comictagger/bin/python', '/app/mylar3/comictagger.py') else real(path)
        with patch.object(stage.os, 'geteuid', return_value=1000), patch.object(stage.os, 'getegid', return_value=1000), patch.object(Path, 'is_file', installed), patch.dict(os.environ, ARCHIVING_UTILS_ROOT='/opt/archiving-utils'), patch.object(stage, 'run_child', side_effect=child):
            with self.assertRaisesRegex(ValueError, 'source-final-drift'):
                stage.run_stage(self.sources, self.map, self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
