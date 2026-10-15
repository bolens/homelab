"""Default/registry refusals and legacy body parity; no NFS grant projected."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import ast
import importlib.util
from pathlib import Path
import threading
import unittest
import comic_nfs_factual_successor as m

class Boundary(unittest.TestCase):
    def test_bare_facts_cannot_create_retained_observation(self):
        class Owner:
            def left(self):pass
        with self.assertRaisesRegex(m.Held,'existing-owning-parent'):m.RetainedObservation(Owner(),object(),dict(binding={'platform_supported':True}))
    def test_unregistered_actual_parent_refuses_before_engine(self):
        spec=importlib.util.spec_from_file_location('retained_original_parent',Path(__file__).with_name('comic_reader_lifecycle_parent.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        owner=module.LifecycleParent.__new__(module.LifecycleParent);owner.core=b'unadmitted';owner.thread=threading.get_ident()
        with self.assertRaisesRegex(m.Held,'existing-owning-parent'):m.run_active_retained(owner)
    def test_original_direct_factory_bodies_remain_exact(self):
        old=Path(__file__).parent/'_configured_parent_fixtures/nfs_factual_predecessor.py'
        original={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(old.read_bytes()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        current={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(Path(m.__file__).read_bytes()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name,body in original.items():
            if name!='stop_owned':self.assertEqual(current[name],body,name)
        # The original direct stop remains byte-for-AST exact through its return.
        # Only the configured retained route adds a completed-exit successor tail.
        old=next(n for n in ast.parse(old.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='stop_owned')
        new=next(n for n in ast.parse(Path(m.__file__).read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='stop_owned')
        self.assertEqual([ast.dump(n,include_attributes=False) for n in new.body[:len(old.body)-1]],
                         [ast.dump(n,include_attributes=False) for n in old.body[:-1]])
        self.assertEqual(ast.dump(new.body[-1],include_attributes=False),ast.dump(old.body[-1],include_attributes=False))
        self.assertEqual(len(new.body),len(old.body)+1)
        tail=new.body[-2]
        self.assertIsInstance(tail,ast.If)
        self.assertEqual(ast.unparse(tail.test),'type(r[\'canary\']) is RetainedObservation')
    def test_retained_boundary_is_not_active_canary_type(self):
        self.assertNotEqual(m.RetainedObservation.__name__,'ActiveNFSCanaryObservation')
        self.assertFalse(hasattr(m,'ActiveNFSCanaryObservation'))

if __name__=='__main__':unittest.main()
