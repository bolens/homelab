"""Finite API copy destinations; stop before test transport, never fake suite success."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).parent


class APICopy(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'public';self.root.mkdir()
        self.rows=json.loads((ROOT/'import_api_control_sources.json').read_text())
        for row in self.rows:
            source=ROOT/row['path'];target=self.root/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        (self.root/'import_api_control_sources.json').write_text(json.dumps(self.rows))
        spec=importlib.util.spec_from_file_location('api_copy_under_test',ROOT/'run_import_api_controls.py')
        self.runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.runner);self.runner.ROOT=self.root
    def test_exact_standalone_siblings_kept_nested_before_real_family_launch(self):
        fired=[]
        def transport(argv,*,cwd,env):
            copied=Path(cwd)
            for name in self.runner.STANDALONE_FIXTURES:
                self.assertEqual((copied/name).read_bytes(),(self.root/name).read_bytes())
            self.assertEqual((copied/self.runner.STANDALONE_MANIFEST).read_bytes(),(self.root/self.runner.STANDALONE_MANIFEST).read_bytes())
            self.assertFalse((copied/'comic_retained_standalone_action.py').exists())
            self.assertTrue((copied/'comic_reader_backup_primitives.py').is_file())
            self.assertIn('test_ordinary_import_observation',argv)
            fired.append(True);raise RuntimeError('actual copied tree inspected before transport')
        with patch.object(self.runner.subprocess,'run',transport):
            with self.assertRaisesRegex(RuntimeError,'actual copied tree inspected'):self.runner.main('observation')
        self.assertEqual(fired,[True])
    def unknown(self,name):
        leaf=self.root/name;leaf.parent.mkdir(parents=True,exist_ok=True);leaf.write_bytes(b'{}')
        self.rows.append({'path':name,'sha256':hashlib.sha256(leaf.read_bytes()).hexdigest()})
        (self.root/'import_api_control_sources.json').write_text(json.dumps(self.rows));calls=[]
        def transport(*args,**kwargs):calls.append(True);raise RuntimeError('unexpected transport')
        with patch.object(self.runner.subprocess,'run',transport):
            with self.assertRaises(AssertionError):self.runner.main('observation')
        self.assertEqual(calls,[])
    def test_unknown_reader_sibling_is_refused(self):self.unknown('reader_recovery/unreviewed.py')
    def test_unknown_root_json_is_refused(self):self.unknown('unreviewed_control_sources.json')


if __name__=='__main__':unittest.main()
