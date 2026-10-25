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
        for name in ('run_active_factual','WriterLease','SourceCohort','validate','mount_identity','configured_writer_mapping','native_gate'):
            self.assertEqual(before[name],after[name],name)
    def test_only_canary_static_loop_changes_for_owned_reader_stop(self):
        def canary(path):return next(n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.ClassDef) and n.name=='ActiveNFSCanaryObservation')
        old,new=canary(OLD),canary(ROOT/'comic_negative_nfs_active_parent.py')
        old_current=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='current')
        new_current=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='current')
        old_loop=next(n for n in old_current.body if isinstance(n,ast.For))
        new_loop=next(n for n in new_current.body if isinstance(n,ast.For))
        expected=ast.parse("""for name in original:
    keys = ROLE_STATIC
    accepted = reader_stopped_static({k: original[name][k] for k in keys}, {k: current[name][k] for k in keys}, name) if stopped and name == self.reader_id else all(current[name].get(k) == original[name].get(k) for k in keys)
    if not accepted:
        raise Held('active-factual-static-drift')
""").body[0]
        self.assertEqual(ast.dump(new_loop,include_attributes=False),ast.dump(expected,include_attributes=False))
        new_current.body[new_current.body.index(new_loop)]=old_loop
        self.assertEqual(ast.dump(old,include_attributes=False),ast.dump(new,include_attributes=False))
    def test_disabled_configured_entry_refuses_before_interface_or_reads(self):
        with self.assertRaisesRegex(m.Held,'host-lease-interface-module'):
            m.run_active_host_factual(SimpleNamespace(execute=False),None,interface_module=None,lease_interface=None,interface_ref={},roles=None)
if __name__=='__main__':unittest.main()
