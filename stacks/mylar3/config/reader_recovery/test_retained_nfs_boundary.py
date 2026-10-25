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


def legacy_metadata_tree(raw):
    """Permit only the reviewed owning metadata adapters in legacy parity."""
    class Metadata(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            if (isinstance(node.func, ast.Name)
                    and node.func.id in ('_host_stat', '_host_names')
                    and len(node.args) == 2 and not node.keywords
                    and isinstance(node.args[0], ast.Name)
                    and node.args[0].id == 'owner'
                    and not isinstance(node.args[1], ast.Starred)):
                operation = 'lstat' if node.func.id == '_host_stat' else 'listdir'
                return ast.copy_location(ast.Call(func=ast.Attribute(
                    value=ast.Name(id='os', ctx=ast.Load()), attr=operation,
                    ctx=ast.Load()), args=[node.args[1]], keywords=[]), node)
            return node
    return Metadata().visit(ast.parse(raw))

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
        current={n.name:ast.dump(n,include_attributes=False) for n in legacy_metadata_tree(Path(m.__file__).read_bytes()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name,body in original.items():
            if name!='stop_owned':self.assertEqual(current[name],body,name)
        # The original direct stop remains byte-for-AST exact through its return.
        # Only the configured retained route adds a completed-exit successor tail.
        old=next(n for n in ast.parse(old.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='stop_owned')
        new=next(n for n in legacy_metadata_tree(Path(m.__file__).read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='stop_owned')
        self.assertEqual([ast.dump(n,include_attributes=False) for n in new.body[:len(old.body)-1]],
                         [ast.dump(n,include_attributes=False) for n in old.body[:-1]])
        self.assertEqual(ast.dump(new.body[-1],include_attributes=False),ast.dump(old.body[-1],include_attributes=False))
        self.assertEqual(len(new.body),len(old.body)+1)
        tail=new.body[-2]
        self.assertIsInstance(tail,ast.If)
        self.assertEqual(ast.unparse(tail.test),'type(r[\'canary\']) is RetainedObservation')
    def test_metadata_normalization_preserves_owner_arguments_and_other_body(self):
        def body(raw):
            return ast.dump(legacy_metadata_tree(raw), include_attributes=False)
        for adapter, original in (('_host_stat', 'lstat'), ('_host_names', 'listdir')):
            expected = body('def check(owner, p):\n return os.' + original + '(p)')
            self.assertEqual(body('def check(owner, p):\n return ' + adapter + '(owner, p)'), expected)
            for call in (adapter + '(foreign, p)', adapter + '(owner, changed)',
                         adapter + '(owner)', adapter + '(owner, p, extra)',
                         adapter + '(owner, p, extra=True)', adapter + '(owner, *p)',
                         adapter + '(owner, p, **extra)', 'foreign.' + adapter + '(owner, p)'):
                with self.subTest(call=call):
                    self.assertNotEqual(body('def check(owner, p):\n return ' + call), expected)
            self.assertNotEqual(body('def check(owner, p):\n marker = 1\n return ' + adapter + '(owner, p)'), expected)
            self.assertNotEqual(body('def check(owner, p):\n return os.unlink(p)'), expected)

    def retained_metadata_join(self, changed_field=None):
        # Parent admission, ready session and final proxy close are projected.
        # Parent.parents and Tree retain their actual filesystem representations.
        import copy
        import os
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        import comic_reader_lifecycle_parent as parent
        import comic_child_control_projection as projection
        import comic_nfs_parent_session as sessions
        class Owner:pass
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);operation=base/'operation';operation.mkdir(mode=0o700)
            owner=Owner();owner.nodes=parent.parents(operation);before=copy.deepcopy(owner.nodes)
            tree=projection.Tree(operation/'child','/_operation',operation,parent.read,uid=os.geteuid(),gid=os.getegid())
            common=next(path for path,_ in tree.nodes if path in owner.nodes)
            self.assertIs(type(owner.nodes[common]),list)
            self.assertIs(type(dict(tree.nodes)[common]),tuple)
            if changed_field is not None:owner.nodes[common][changed_field]+=1
            session=object.__new__(sessions.RetainedChild);session.owner=owner;session.state='ready';session.lease_replies=SimpleNamespace(done=True)
            owner.nfs_host_modules=lambda:{'comic_nfs_parent_session.py':sessions}
            owner.mapping=SimpleNamespace(plan13=lambda:False,host=lambda path:path)
            g={'_NFS_LIVE_SESSIONS':{owner:session},'_CHILD_TREES':{owner:tree},'encode':parent.encode}
            binding=dict(disposable_probe_verified=True,platform_supported=True,owned_fixture_absence_verified=True,actual_library_platform_verified=False,future_mylar_destination_verified=False,native_grant=False,publication_authority=False,writer_lifecycle_resume_authorized=False)
            facts=dict(binding=binding,mount={'fstype':'nfs4'},device=1,files=[],nodes=[],names=[],absent=[])
            with patch.object(m,'parent_module',return_value=g),patch.object(m.RetainedObservation,'close'):
                result=m.RetainedObservation(owner,session,facts)
            self.assertEqual(owner.nodes,before)
            self.assertEqual(dict(result.nodes)[common],tuple(before[common]))
            self.assertTrue(all(type(value)is tuple for _,value in result.nodes))
    def test_actual_parent_list_and_tree_tuple_nodes_join_without_rebaseline(self):
        self.retained_metadata_join()
    def test_retained_node_join_still_refuses_each_identity_field_drift(self):
        for field in range(5):
            with self.subTest(field=field):
                with self.assertRaisesRegex(m.Held,'nfs-retained-host-node-conflict'):
                    self.retained_metadata_join(field)

    def test_retained_route_requests_finite_remaining_parent_budget(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        class Captured(Exception):pass
        for remaining,expected in ((800,800),(1500,900),(87,87)):
            captured=[]
            def prepare(seconds):captured.append(seconds);raise Captured()
            owner=SimpleNamespace(baselines={},left=lambda:remaining,prepare_nfs_packet=prepare)
            with patch.object(m,'preflight',return_value=({},None)):
                with self.assertRaises(Captured):m.run_active_retained(owner)
            self.assertEqual(captured,[expected])

    def test_retained_boundary_is_not_active_canary_type(self):
        self.assertNotEqual(m.RetainedObservation.__name__,'ActiveNFSCanaryObservation')
        self.assertFalse(hasattr(m,'ActiveNFSCanaryObservation'))

if __name__=='__main__':unittest.main()
