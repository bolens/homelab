"""Source-bound configured entry guards; no NFS/SDK/factory grant projected."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import ast
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('active_nfs',ROOT/'comic_negative_nfs_active_parent.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
OLD=ROOT/'_configured_parent_fixtures/active_parent_predecessor.py'
class Entry(unittest.TestCase):
    def test_configured_source_pin_is_actual_interface(self):
        self.assertEqual(m.HOST_LEASE_INTERFACE_SHA,hashlib.sha256((ROOT/'comic_nfs_lease_session.py').read_bytes()).hexdigest())
    def test_existing_entry_writer_and_nfs_gates_ast_exact(self):
        def leaves(path):
            return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        before,after=leaves(OLD),leaves(ROOT/'comic_negative_nfs_active_parent.py')
        for name in ('run_active_factual','WriterLease','SourceCohort','validate','mount_identity','configured_writer_mapping','native_gate','ActiveNFSCanaryObservation'):
            self.assertEqual(before[name],after[name],name)
    def test_disabled_configured_entry_refuses_before_interface_or_reads(self):
        with self.assertRaisesRegex(m.Held,'host-lease-interface-module'):
            m.run_active_host_factual(SimpleNamespace(execute=False),None,interface_module=None,lease_interface=None,interface_ref={},roles=None)
if __name__=='__main__':unittest.main()
