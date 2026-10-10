"""Owning finite-copy failures; fixtures only, never fake owning-suite success."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).absolute().parent
class CopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='authenticated-copy-fault-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'config';self.root.mkdir()
        self.map=self.root/'standalone_launch_control_sources.json';shutil.copyfile(ROOT/self.map.name,self.map)
        for row in json.loads(self.map.read_bytes()):
            target=self.root/row['path']
            if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/row['path'],target)
        source=ROOT/'run_authenticated_standalone_controls.py';spec=importlib.util.spec_from_file_location('authenticated_copy_fixture',source)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m);self.m.ROOT=self.root
    def invoke(self):
        with patch.object(sys,'argv',['runner','--family','broker','--backend','target']):self.m.main()
    def test_parser_held_rows_cannot_change_validated_copy_targets(self):
        real_json=self.m.json.loads;real_read=self.m.read_original;aliased=[];fired=[];observed=[]
        original_target=real_json(self.map.read_bytes())[0]['target']
        def decode(raw):
            rows=real_json(raw);aliased.append(rows);return rows
        def read(path,*args):
            data=real_read(path,*args)
            if aliased and not fired:
                aliased[0][0]['target']='foreign-public-copy.py';fired.append(True)
            return data
        class Observed(Exception):pass
        def observe(argv,**kwargs):
            private=Path(kwargs['cwd']);observed.append(True)
            self.assertFalse((private/'foreign-public-copy.py').exists())
            self.assertTrue((private/original_target).exists());raise Observed
        with patch.object(self.m.json,'loads',decode),patch.object(self.m,'read_original',read),patch.object(self.m.subprocess,'run',observe),self.assertRaises(Observed):self.invoke()
        self.assertEqual(fired,[True]);self.assertEqual(observed,[True])
    def test_unknown_valid_hash_row_refuses_before_subprocess(self):
        rows=json.loads(self.map.read_bytes());rows[0]['path']='foreign-public.py';self.map.write_text(json.dumps(rows))
        with patch.object(self.m.subprocess,'run',side_effect=AssertionError('subprocess reached')),self.assertRaisesRegex(ValueError,'finite original graph'):self.invoke()
    def test_corrupt_source_pin_refuses_before_subprocess(self):
        rows=json.loads(self.map.read_bytes());rows[0]['sha256']='0'*64;self.map.write_text(json.dumps(rows))
        with patch.object(self.m.subprocess,'run',side_effect=AssertionError('subprocess reached')),self.assertRaisesRegex(ValueError,'source pin'):self.invoke()
    def test_manifest_parent_callback_drift_refuses_before_subprocess(self):
        real=self.m.json.loads;original=self.root.stat().st_mode & 0o777;fired=[]
        def drift(raw):
            result=real(raw);os.chmod(self.root,0o700 if original!=0o700 else 0o750);fired.append(True);return result
        try:
            with patch.object(self.m.json,'loads',drift),patch.object(self.m.subprocess,'run',side_effect=AssertionError('subprocess reached')),self.assertRaisesRegex(ValueError,'ancestor conflict'):self.invoke()
            self.assertEqual(fired,[True])
        finally:os.chmod(self.root,original)
    def test_actual_child_failure_is_propagated_without_later_family(self):
        real=subprocess.run;fired=[]
        def failure(argv,**kwargs):
            fired.append(argv);return real([sys.executable,'-I','-B','-c','raise SystemExit(7)'],**kwargs)
        with patch.object(self.m.subprocess,'run',failure),self.assertRaisesRegex(ValueError,'count/failure/skip'):self.invoke()
        self.assertEqual(len(fired),1)
    def test_last_actual_broker_callback_source_drift_is_refused(self):
        real=subprocess.run;rows=json.loads(self.map.read_bytes());leaf=self.root/rows[0]['path'];fired=[]
        def drift(argv,**kwargs):
            result=real(argv,**kwargs);self.assertEqual(result.returncode,0);self.assertIn('Ran 26 tests',result.stderr)
            os.chmod(leaf,0o444);fired.append(True);return result
        with patch.object(self.m.subprocess,'run',drift),self.assertRaisesRegex(ValueError,'read drift|original FD'):self.invoke()
        self.assertEqual(fired,[True])
if __name__=='__main__':unittest.main()
