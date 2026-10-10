"""Original manifest ancestors must precede the first parser callback."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class ManifestOrigins(unittest.TestCase):
    def check_parent(self,outer):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'config';root.mkdir();leaf=root/'fixture.py';leaf.write_text('pass\n')
            rows=[{'path':'fixture.py','target':'fixture.py','sha256':hashlib.sha256(leaf.read_bytes()).hexdigest()}]
            manifest=root/'standalone_control_sources.json';raw=json.dumps(rows).encode();manifest.write_bytes(raw)
            spec=importlib.util.spec_from_file_location('standalone_gate_under_test',Path(__file__).with_name('run_standalone_controls.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=root
            original=module.json.loads;fired=[];invocations=[];parent=base if outer else root
            def late(data,*args,**kwargs):
                value=original(data,*args,**kwargs)
                if data==raw and not fired:parent.chmod(0o750);fired.append(True)
                return value
            def transport(*args,**kwargs):
                invocations.append(True);raise AssertionError('must refuse before subprocess')
            with patch.object(module.json,'loads',late),patch.object(module.subprocess,'run',transport),patch.object(sys,'argv',['run_standalone_controls.py','--family','mechanical']):
                with self.assertRaisesRegex(ValueError,'ancestor conflict'):module.main()
            self.assertEqual(fired,[True]);self.assertEqual(invocations,[])
    def test_original_manifest_root_before_decode(self):self.check_parent(False)
    def test_original_manifest_outer_parent_before_decode(self):self.check_parent(True)


if __name__=='__main__':unittest.main()
