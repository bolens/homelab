"""Real filesystem tests of owning control routing; no installed/pipe grant."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import comic_child_control_projection as c

class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='comic-owning-public-');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.op=self.base/'operation';self.op.mkdir(mode=0o700)
        self.source=self.op/'execute-input.json';self.source.write_bytes(b'{"public":true}');self.source.chmod(0o600)
        self.ref=dict(path=str(self.source),sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),signature9=list(c.nine(self.source.lstat())))
        self.tree=c.Tree(self.base/'child','/_operation',self.op,lambda ref:c.raw(ref,os.geteuid())[0],uid=os.geteuid(),gid=os.getegid())
    def test_original_and_child_pair_are_distinct_and_actual(self):
        child=self.tree.projected(self.ref)
        self.assertEqual(child['path'],'/_operation/execute-input.json')
        self.assertEqual(self.tree.original(child),self.ref)
        host=Path(self.tree.host(child['path']));self.assertEqual(host.read_bytes(),self.source.read_bytes())
        self.assertNotEqual(c.nine(host.lstat())[:2],tuple(self.ref['signature9'][:2]))
        self.tree.check();self.assertEqual(c.nine(self.source.lstat()),tuple(self.ref['signature9']))
    def test_birth_sibling_layout_and_late_sidecar_kind(self):
        child=self.tree.projected(self.ref)
        seed=self.op/'execute-input.birth.json';seed.write_bytes(b'{"public_seed":true}');seed.chmod(0o600)
        sr=dict(path=str(seed),sha256=hashlib.sha256(seed.read_bytes()).hexdigest(),signature9=list(c.nine(seed.lstat())))
        cr=self.tree.projected(sr);self.assertEqual(cr['path'],str(Path(child['path']).with_suffix('.birth.json')))
        self.assertFalse(Path(self.tree.host(str(Path(child['path']).with_suffix('.lifecycle.json')))).exists())
        side=self.op/'execute-input.lifecycle.json';side.write_bytes(b'{"public_sidecar":true}');side.chmod(0o600)
        rr=dict(path=str(side),sha256=hashlib.sha256(side.read_bytes()).hexdigest(),signature9=list(c.nine(side.lstat())))
        self.tree.projected(rr)
        readonly={p for p,_ in self.tree.readonly_files()}
        self.assertIn(self.tree.host(child['path']),readonly)
        self.assertIn(self.tree.host(cr['path']),readonly)
        self.assertNotIn(str(self.tree.root/side.name),readonly)
    def test_child_tampering_refuses_original_root_remains(self):
        ref=self.tree.projected(self.ref);host=Path(self.tree.host(ref['path']));host.write_bytes(b'changed')
        with self.assertRaisesRegex(c.Held,'child-control-final9'):self.tree.check()
        self.assertEqual(self.source.read_bytes(),b'{"public":true}')
    def test_root_original_tampering_refuses(self):
        self.tree.projected(self.ref);self.source.chmod(0o640)
        with self.assertRaisesRegex(c.Held,'child-control-final9'):self.tree.check()
    def test_first_consumer_swap_refuses_keeps_foreign(self):
        real=os.fsync;fired=[];target=self.tree.root/self.source.name
        def late(fd):
            real(fd)
            if target.exists() and not fired:
                target.rename(target.with_suffix('.retained'));target.write_bytes(b'foreign');target.chmod(0o600);fired.append(True)
        with patch.object(c.os,'fsync',late):
            with self.assertRaises(c.Held):self.tree.projected(self.ref)
        self.assertTrue(fired);self.assertEqual(target.read_bytes(),b'foreign');self.assertEqual(self.source.read_bytes(),b'{"public":true}')
    def test_exact_child_output_root_view_has_separate_identity(self):
        self.tree.projected(self.ref);out=self.tree.root/'execute-input.native-scope.json';out.write_bytes(b'{"factual":true}');out.chmod(0o600)
        ref=dict(path='/_operation/'+out.name,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),signature9=list(c.nine(out.lstat())))
        raw,view=self.tree.output(ref,ref['path'],'native_scope')
        self.assertEqual(raw,b'{"factual":true}');self.assertNotEqual(Path(view['path']),out)
        self.assertEqual(Path(view['path']).read_bytes(),out.read_bytes());self.tree.check()
    def test_returned_child_original_identity_must_match_mapped_host(self):
        out=self.tree.root/'execute-input.native-scope.json';out.write_bytes(b'{"factual":true}');out.chmod(0o600)
        original=c.nine(out.lstat());ref=dict(path='/_operation/'+out.name,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),signature9=list(original))
        ref['signature9'][1]+=1
        with self.assertRaisesRegex(c.Held,'child-output-returned-original9'):self.tree.output(ref,ref['path'],'native_scope')
        self.assertEqual(c.nine(out.lstat()),original);self.assertEqual(out.read_bytes(),b'{"factual":true}')
        self.assertFalse((self.op/'child-output-views').exists())
    def test_foreign_output_path_refuses(self):
        out=self.tree.root/'other.json';out.write_bytes(b'{}');out.chmod(0o600)
        ref=dict(path='/_operation/other.json',sha256=hashlib.sha256(b'{}').hexdigest(),signature9=list(c.nine(out.lstat())))
        with self.assertRaisesRegex(c.Held,'child-output-exact-path'):self.tree.output(ref,'/_operation/execute-report.json','report')
    def test_tree_identity_and_pair_mutation_refuses(self):
        self.tree.projected(self.ref);self.tree.pairs=()
        with self.assertRaisesRegex(c.Held,'child-tree-logical-seal'):self.tree.check()
    def test_original_directory_late_change(self):
        self.tree.projected(self.ref);self.op.chmod(0o750)
        with self.assertRaisesRegex(c.Held,'child-control-final5'):self.tree.check()
    def test_private_scope_existing_owner_does_not_relabel(self):
        scratch=self.op/'scratch';scratch.mkdir(mode=0o700);before=c.five(scratch.lstat())
        actual=self.tree.scope(scratch,'scratch');self.assertEqual(actual,str(scratch));self.assertEqual(c.five(scratch.lstat()),before)
        self.assertEqual(self.tree.scope_owner(actual),os.geteuid())
        child=self.tree.child(actual);self.assertEqual(self.tree.host(child),actual)
        self.assertNotEqual(child,'/_operation/scratch')
        self.assertEqual(self.tree.host(str(Path(child)/'preserved')),str(scratch/'preserved'))
    def test_foreign_pair_refuses(self):
        ref=self.tree.projected(self.ref);ref['sha256']='a'*64
        with self.assertRaisesRegex(c.Held,'child-pair-original-binding'):self.tree.original(ref)
    def test_output_original_is_idempotent_root_view_without_rebaseline(self):
        out=self.tree.root/'execute-input.native-scope.json';out.write_bytes(b'{"factual":true}');out.chmod(0o600)
        ref=dict(path='/_operation/'+out.name,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),signature9=list(c.nine(out.lstat())))
        first=self.tree.output(ref,ref['path'],'native_scope')
        self.assertEqual(self.tree.output(ref,ref['path'],'native_scope'),first)
        self.assertEqual(self.tree.original(ref),first[1])
        self.assertEqual(self.tree.projected(first[1]),ref)
        out.chmod(0o640)
        with self.assertRaises(c.Held):self.tree.output(ref,ref['path'],'native_scope')
    def test_read_callback_cannot_reseal_original_tree_identity(self):
        real=self.tree.read_original;fired=[]
        def changed(ref):
            result=real(ref);self.tree.child_root=Path('/foreign');fired.append(True);return result
        # Reader identity is fixed at Tree birth; install the callback in a new Tree.
        self.tree=c.Tree(self.base/'child-other','/_operation',self.op,changed,uid=os.geteuid(),gid=os.getegid())
        with self.assertRaisesRegex(c.Held,'child-tree-original-before-commit'):self.tree.project(self.ref)
        self.assertTrue(fired);self.assertEqual(self.source.read_bytes(),b'{"public":true}')
    def test_unknown_control_namespace_is_retained_and_refused(self):
        self.tree.projected(self.ref);foreign=self.tree.root/'foreign';foreign.write_bytes(b'preserved')
        with self.assertRaisesRegex(c.Held,'child-tree-root-namespace'):self.tree.check()
        self.assertEqual(foreign.read_bytes(),b'preserved')
    def proof_consumer(self):
        spec=importlib.util.spec_from_file_location('owning_proof_parent',Path(__file__).with_name('comic_reader_lifecycle_parent.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        class Holder:
            def child_control(owner,ref,expected_path):return m.LifecycleParent.child_control(owner,ref,expected_path)
        owner=Holder();owner.mapping=m.Paths([dict(host=str(self.tree.root),child=str(self.tree.child_root),write=True)])
        m._CHILD_TREES[owner]=self.tree
        out=self.tree.root/'execute-input.native-scope.json';out.write_bytes(b'{"factual":true}');out.chmod(0o600)
        ref=dict(path='/_operation/'+out.name,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),signature9=list(c.nine(out.lstat())))
        return m,owner,out,ref
    def test_owning_proof_membership_required_before_root_view_copy(self):
        m,owner,out,ref=self.proof_consumer()
        with self.assertRaisesRegex(m.Held,'archive-terminal-history-baseline-original9'):m.LifecycleParent.child_control_from_proof(owner,ref,{})
        self.assertFalse((self.op/'child-output-views').exists())
        self.assertEqual(out.read_bytes(),b'{"factual":true}')
    def test_owning_proof_member_returns_distinct_derived_view(self):
        m,owner,out,ref=self.proof_consumer();original={str(out):tuple(ref['signature9'])};before=dict(original)
        view=m.LifecycleParent.child_control_from_proof(owner,ref,original)
        self.assertEqual(original,before);self.assertNotEqual(view['path'],str(out));self.assertEqual(Path(view['path']).read_bytes(),out.read_bytes())
    def test_owning_proof_mismatch_and_late_rebase_refuse(self):
        m,owner,out,ref=self.proof_consumer();wrong=list(ref['signature9']);wrong[1]+=1
        with self.assertRaisesRegex(m.Held,'archive-terminal-history-baseline-original9'):m.LifecycleParent.child_control_from_proof(owner,ref,{str(out):tuple(wrong)})
        original={str(out):tuple(ref['signature9'])};real=os.fsync;fired=[]
        def changed(fd):
            real(fd)
            if not fired:original[str(out)]=tuple(wrong);fired.append(True)
        with patch.object(c.os,'fsync',changed),self.assertRaisesRegex(m.Held,'archive-terminal-history-proof-unchanged'):m.LifecycleParent.child_control_from_proof(owner,ref,original)
        self.assertTrue(fired);self.assertEqual(out.read_bytes(),b'{"factual":true}')
    def mapped_owner(self):
        spec=importlib.util.spec_from_file_location('owning_empty_parent',Path(__file__).with_name('comic_reader_lifecycle_parent.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        mapping=m.Paths([dict(host=str(self.op),child='/_operation',write=True)])
        class Holder:
            def left(owner):self.tree.check()
        owner=Holder();m._CHILD_TREES[owner]=self.tree;mapping.owner=owner
        return m,mapping
    def test_host_lease_source_ref_is_physical_original_child_pair(self):
        _,mapping=self.mapped_owner();copy=mapping.child_host_ref(self.ref);virtual=mapping.child_ref(self.ref)
        self.assertEqual(copy['path'],self.tree.host(virtual['path']));self.assertEqual(copy['sha256'],virtual['sha256']);self.assertEqual(copy['signature9'],virtual['signature9'])
        self.assertNotEqual(copy['path'],self.ref['path']);self.assertNotEqual(copy['signature9'][:2],self.ref['signature9'][:2])
    def test_child_lease_empty_exclusive_creator_metadata(self):
        m,mapping=self.mapped_owner();empty=mapping.child_empty('nfs-lease-empty-config');p=Path(empty['path'])
        self.assertEqual(tuple(empty['signature9']),c.nine(p.lstat()));self.assertEqual(list(p.iterdir()),[])
        self.assertEqual(p.stat().st_uid,os.geteuid());self.assertEqual(p.stat().st_mode&0o777,0o700)
        with self.assertRaisesRegex(m.Held,'configured-child-empty-exclusive'):mapping.child_empty('nfs-lease-empty-config')
    def test_child_lease_empty_last_namespace_callback_drift_refuses(self):
        m,mapping=self.mapped_owner();real=os.listdir;fired=[]
        def changed(path):
            result=real(path)
            if Path(path).name=='nfs-lease-empty-config' and not fired:
                (Path(path)/'foreign').write_bytes(b'preserved');fired.append(True)
            return result
        with patch.object(m.os,'listdir',changed),self.assertRaisesRegex(m.Held,'configured-child-empty-original9'):mapping.child_empty('nfs-lease-empty-config')
        self.assertTrue(fired);self.assertEqual((self.tree.root/'nfs-lease-empty-config'/'foreign').read_bytes(),b'preserved')
    def test_parent_paths_actual_methods_consume_pair_metadata(self):
        spec=importlib.util.spec_from_file_location('owning_parent',Path(__file__).with_name('comic_reader_lifecycle_parent.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        mapping=m.Paths([dict(host=str(self.op),child='/_operation',write=True)])
        class Holder:
            def left(self):self.tree.check()
        owner=Holder();owner.tree=self.tree;m._CHILD_TREES[owner]=self.tree;mapping.owner=owner
        ref=mapping.child_ref(self.ref)
        self.assertEqual(ref['signature9'],list(c.nine(Path(self.tree.host(ref['path'])).lstat())))
        self.assertEqual(mapping.original_ref(ref),self.ref)
        self.assertEqual(mapping.original_host(mapping.host(ref['path'])),str(self.source))
        self.assertFalse(m.CHILD_CONTROL_PROJECTION_ENABLED);self.assertIsNone(m.CHILD_CONTROL_SOURCE_SHA)

    def test_declared_nfs_controls_have_finite_separate_budget(self):
        for index in range(40):
            source=self.op/('nfs-control-'+str(index)+'.json');source.write_bytes(b'{"public":true}');source.chmod(0o600)
            ref=dict(path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),signature9=list(c.nine(source.lstat())))
            self.tree.reserve_nfs_control(ref);self.tree.project(ref)
        self.assertEqual(len(self.tree.nfs_controls),40);self.tree.check()
    def test_default_budget_does_not_expand_without_declared_nfs_originals(self):
        for index in range(32):
            source=self.op/('normal-'+str(index)+'.json');source.write_bytes(b'{}');source.chmod(0o600)
            ref=dict(path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),signature9=list(c.nine(source.lstat())))
            self.tree.project(ref)
        with self.assertRaisesRegex(c.Held,'child-control-bound'):self.tree.project(self.ref)
    def test_declared_nfs_budget_refuses_changed_original(self):
        self.tree.reserve_nfs_control(self.ref);foreign=dict(self.ref,sha256='a'*64)
        with self.assertRaisesRegex(c.Held,'original-conflict'):self.tree.reserve_nfs_control(foreign)
    def test_nfs_phase_keeps_fixed_absent_active_output(self):
        directory=self.tree.phase('nfs');self.assertEqual(directory,self.tree.root/'nfs');self.assertFalse((directory/'active-output').exists());self.tree.check()

if __name__=='__main__':unittest.main()
