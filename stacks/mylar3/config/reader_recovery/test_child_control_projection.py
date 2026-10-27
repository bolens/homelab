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
        for index in range(48):
            source=self.op/('nfs-control-'+str(index)+'.json');source.write_bytes(b'{"public":true}');source.chmod(0o600)
            ref=dict(path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),signature9=list(c.nine(source.lstat())))
            self.tree.reserve_nfs_control(ref);self.tree.project(ref)
        self.assertEqual(len(self.tree.nfs_controls),48);self.tree.check()
        with self.assertRaisesRegex(c.Held,'nfs-control-declared-bound'):self.tree.reserve_nfs_control(self.ref)
    def test_default_budget_does_not_expand_without_declared_nfs_originals(self):
        for index in range(32):
            source=self.op/('normal-'+str(index)+'.json');source.write_bytes(b'{}');source.chmod(0o600)
            ref=dict(path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),signature9=list(c.nine(source.lstat())))
            self.tree.project(ref)
        with self.assertRaisesRegex(c.Held,'child-control-bound'):self.tree.project(self.ref)

    def budget_input(self,index,*,nfs=False):
        source=self.op/('budget-'+str(index)+'.json');source.write_bytes(b'{}');source.chmod(0o600)
        ref=dict(path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),signature9=list(c.nine(source.lstat())))
        if nfs:self.tree.reserve_nfs_control(ref)
        self.tree.project(ref)
        return ref

    def budget_output(self,index):
        phase=self.tree.phase('execute');source=phase/('factual-'+str(index)+'.json')
        source.write_bytes(b'{"factual":true}');source.chmod(0o600)
        return dict(path=self.tree.child(str(source)),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),signature9=list(c.nine(source.lstat())))

    def test_plan13_terminal_projection_retains_all_11_proof_views(self):
        import comic_reader_lifecycle_parent as parent
        for index in range(26):self.budget_input(index)
        for index in range(26,66):self.budget_input(index,nfs=True)
        class Owner:
            child_control=parent.LifecycleParent.child_control
            def left(self):self.tree.check()
        owner=Owner();owner.tree=self.tree
        owner.mapping=parent.Paths([dict(host=str(self.op),child='/_operation',write=True)])
        owner.mapping.owner=owner;parent._CHILD_TREES[owner]=self.tree
        proof={};views=[]
        # Six existing views precede baseline, preparation, two histories and
        # the causal fixture receipt, in both forward and rollback dialogues.
        for index in range(11):
            ref=self.budget_output(index);physical=self.tree.host(ref['path'])
            proof[physical]=list(ref['signature9']);original=dict(proof)
            view=parent.LifecycleParent.child_control_from_proof(owner,ref,proof)
            self.assertEqual(proof,original);self.assertEqual(Path(view['path']).read_bytes(),b'{"factual":true}')
            self.assertEqual(parent.LifecycleParent.child_control_from_proof(owner,ref,proof),view)
            views.append(view)
        self.assertEqual(len(self.tree.pairs),66);self.assertEqual(len(self.tree.outputs),11)
        self.assertEqual(len({v['path']for v in views}),11);self.tree.check()
        foreign=dict(ref,signature9=list(ref['signature9']));foreign['signature9'][1]+=1
        with self.assertRaisesRegex(parent.Held,'archive-terminal-history-baseline-original9'):
            parent.LifecycleParent.child_control_from_proof(owner,foreign,proof)

    def test_outputs_leave_all_32_ordinary_input_slots_available(self):
        for index in range(16):
            ref=self.budget_output(index);self.tree.output(ref,ref['path'],'factual_record')
        for index in range(32):self.budget_input(index)
        with self.assertRaisesRegex(c.Held,'child-control-bound'):self.tree.project(self.ref)
        self.assertEqual(len(self.tree.pairs),32);self.assertEqual(len(self.tree.outputs),16);self.tree.check()

    def test_output_budget_refuses_seventeenth_without_copying_or_losing_existing_view(self):
        for index in range(16):
            ref=self.budget_output(index);_,view=self.tree.output(ref,ref['path'],'factual_record')
        original=self.tree.outputs;extra=self.budget_output(16)
        with self.assertRaisesRegex(c.Held,'child-output-bound'):self.tree.output(extra,extra['path'],'factual_record')
        self.assertEqual(self.tree.outputs,original)
        self.assertEqual(self.tree.output(ref,ref['path'],'factual_record')[1],view)
        self.assertEqual(Path(self.tree.host(extra['path'])).read_bytes(),b'{"factual":true}');self.tree.check()

    def test_shared_80_record_bound_still_covers_inputs_and_outputs(self):
        for index in range(32):self.budget_input(index)
        for index in range(32,69):self.budget_input(index,nfs=True)
        for index in range(11):
            ref=self.budget_output(index);self.tree.output(ref,ref['path'],'factual_record')
        self.assertEqual(len(self.tree.pairs)+len(self.tree.outputs),80)
        extra=self.budget_output(11);original=self.tree.outputs
        with self.assertRaisesRegex(c.Held,'child-control-total-bound'):self.tree.output(extra,extra['path'],'factual_record')
        with self.assertRaisesRegex(c.Held,'child-control-total-bound'):self.budget_input(69,nfs=True)
        self.assertEqual(self.tree.outputs,original);self.tree.check()
    def test_declared_nfs_budget_refuses_changed_original(self):
        self.tree.reserve_nfs_control(self.ref);foreign=dict(self.ref,sha256='a'*64)
        with self.assertRaisesRegex(c.Held,'original-conflict'):self.tree.reserve_nfs_control(foreign)
    def test_nfs_phase_keeps_fixed_absent_active_output(self):
        directory=self.tree.phase('nfs');self.assertEqual(directory,self.tree.root/'nfs');self.assertFalse((directory/'active-output').exists());self.tree.check()

    def test_only_explicit_source_role_projects_public0644_original(self):
        import comic_reader_lifecycle_parent as parent
        tree=c.Tree(self.base/'public-child','/_public',self.op,parent.read,uid=os.geteuid(),gid=os.getegid())
        path=self.base/'canonical-source.py';path.write_bytes(b'# disposable public source\n');path.chmod(0o644)
        ref=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(c.nine(path.lstat())))
        tree.reserve_nfs_control(ref,public=True);copy=tree.project(ref);tree.check()
        self.assertEqual(Path(copy['path']).read_bytes(),path.read_bytes());self.assertEqual(path.stat().st_mode&0o777,0o644)
        self.assertEqual(copy['signature9'][5]&0o777,0o600)
        path.write_bytes(b'late original drift')
        with self.assertRaises(c.Held):tree.check()

    def test_private_projection_does_not_infer_public_policy_from_mode(self):
        import comic_reader_lifecycle_parent as parent
        tree=c.Tree(self.base/'unclassified-child','/_unclassified',self.op,parent.read,uid=os.geteuid(),gid=os.getegid())
        path=self.base/'unclassified.py';path.write_bytes(b'# unclassified\n');path.chmod(0o644)
        ref=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(c.nine(path.lstat())))
        with self.assertRaises(parent.Held):tree.reserve_nfs_control(ref)
        tree.reserve_nfs_control(ref,public=True)
        with self.assertRaisesRegex(c.Held,'original-conflict'):tree.reserve_nfs_control(ref,public=False)

    def test_real_parent_callback_joins_public_source_roles_through_tree(self):
        import json
        import comic_reader_lifecycle_parent as parent
        owner=parent.LifecycleParent.__new__(parent.LifecycleParent)
        # Explicit constructor-context fixture; this proves the real bound callback, not Parent admission.
        owner.plan={'version':13,'action':'negative-five'};owner.files={}
        def ref(path):
            return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(parent.nine(path.lstat())))
        source=self.base/'original-source.py';source.write_bytes(b'# public original\n');source.chmod(0o644);original=ref(source)
        private=self.base/'private-report.json';private.write_bytes(b'{}');private.chmod(0o600);private_ref=ref(private)
        two=lambda value:{key:value[key] for key in ('path','sha256')}
        cohort_path=self.base/'cohort.json';cohort_path.write_text(json.dumps(dict(sources={'actual':two(original)},parent=two(original))));cohort_path.chmod(0o600)
        cohort=ref(cohort_path)
        review_path=self.base/'effective.json';review_path.write_text(json.dumps({role:two(original if role in ('producer','parent_source') else private_ref) for role in ('producer','parent_source','report','ack','runtime','acceptance','parent_ack')}));review_path.chmod(0o600)
        review=ref(review_path)
        for value in (original,private_ref,cohort,review):owner.files[value['path']]=tuple(value['signature9'])
        parent._NFS_SOURCE_CONTEXTS[owner]=({}, {}, parent.encode(dict(source_cohort=two(cohort),effective_observer_review=two(review))),b'',str(self.op))
        self.addCleanup(parent._NFS_SOURCE_CONTEXTS.pop,owner,None)
        tree=c.Tree(self.base/'real-parent-public','/_parent-public',self.op,owner.read_child_original,uid=os.geteuid(),gid=os.getegid())
        with self.assertRaises(parent.Held):tree.reserve_nfs_control(original)
        tree.reserve_nfs_control(original,public=True);projected=tree.project(original);tree.check()
        self.assertEqual(Path(projected['path']).read_bytes(),source.read_bytes())
        self.assertEqual(source.stat().st_mode&0o777,0o644)
        self.assertEqual(owner.read_child_original(private_ref),b'{}')
        with self.assertRaisesRegex(parent.Held,'public-source-role'):owner.read_child_original(private_ref,private=False)
        with self.assertRaisesRegex(parent.Held,'private-policy'):owner.read_child_original(original,private=0)
        unconfigured=parent.LifecycleParent.__new__(parent.LifecycleParent)
        with self.assertRaisesRegex(parent.Held,'public-unconfigured'):unconfigured.read_child_original(original,private=False)
        with self.assertRaisesRegex(parent.Held,'public-source-role'):owner.read_child_original(dict(original,sha256='a'*64),private=False)
        changed=dict(original,signature9=list(original['signature9']));changed['signature9'][3]+=1
        with self.assertRaisesRegex(parent.Held,'public-source-role'):owner.read_child_original(changed,private=False)
        outsider=self.base/'unclassified.py';outsider.write_bytes(b'# not an admitted role\n');outsider.chmod(0o644);outside=ref(outsider);owner.files[outside['path']]=tuple(outside['signature9'])
        with self.assertRaisesRegex(parent.Held,'public-source-role'):owner.read_child_original(outside,private=False)
        source.write_bytes(b'late source replacement')
        with self.assertRaises((parent.Held,c.Held)):tree.check()

    def test_real_parent_callback_projects_exact_empty_cohort_stderr(self):
        import json
        import comic_reader_lifecycle_parent as parent
        owner=parent.LifecycleParent.__new__(parent.LifecycleParent)
        owner.plan={'version':13,'action':'negative-five'};owner.files={}
        def ref(path):return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(parent.nine(path.lstat())))
        stderr=self.base/'controls.stderr';stderr.write_bytes(b'');stderr.chmod(0o600);original=ref(stderr)
        stdout=self.base/'controls.stdout';stdout.write_bytes(b'{"tests":1}');stdout.chmod(0o600)
        pair=lambda value:{k:value[k] for k in ('path','sha256')}
        cohort={'version':1,'kind':'approved-disposable-nfs-current-source-cohort','logs':{'stdout':pair(ref(stdout)),'stderr':pair(original)}}
        path=self.base/'cohort.json';path.write_text(json.dumps(cohort));path.chmod(0o600);cohort_ref=ref(path)
        owner.files[str(path)]=tuple(cohort_ref['signature9']);owner.files[str(stderr)]=tuple(original['signature9'])
        parent._NFS_SOURCE_CONTEXTS[owner]=({}, {}, parent.encode(dict(source_cohort=pair(cohort_ref))),b'',str(self.op))
        self.addCleanup(parent._NFS_SOURCE_CONTEXTS.pop,owner,None)
        tree=c.Tree(self.base/'empty-log-child','/_empty-log',self.op,owner.read_child_original,uid=os.geteuid(),gid=os.getegid())
        with self.assertRaises(parent.Held):parent.read(original)
        tree.reserve_nfs_control(original);projected=tree.project(original);tree.check()
        self.assertEqual(Path(projected['path']).read_bytes(),b'')
        self.assertEqual(projected['sha256'],hashlib.sha256(b'').hexdigest())
        with self.assertRaises(c.Held):c.raw(projected,os.geteuid())
        stderr.write_bytes(b'late changed log')
        with self.assertRaises((c.Held,parent.Held)):tree.check()

    def test_real_parent_cohort_prechild_block_only_allows_original_stderr_empty(self):
        import ast
        import types
        import comic_reader_lifecycle_parent as parent
        def ref(path):return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(parent.nine(path.lstat())))
        log=self.base/'controls.stderr';log.write_bytes(b'');log.chmod(0o600);stderr=ref(log)
        pair=lambda value:{k:value[k] for k in ('path','sha256')}
        cohort={'version':1,'kind':'approved-disposable-nfs-current-source-cohort','logs':{'stdout':pair(self.ref),'stderr':pair(stderr)}}
        path=self.base/'cohort.json';path.write_bytes(parent.encode(cohort));path.chmod(0o600);cref=pair(ref(path))
        files={str(log):tuple(stderr['signature9']),str(path):tuple(ref(path)['signature9']),self.ref['path']:tuple(self.ref['signature9'])}
        tree=ast.parse(Path(parent.__file__).read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='LifecycleParent')
        init=next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name=='__init__')
        loops=[n for n in ast.walk(init)if isinstance(n,ast.For)and isinstance(n.iter,ast.Name)and n.iter.id=='private_facts']
        self.assertEqual(len(loops),1)
        block=compile(ast.Module(body=loops,type_ignores=[]),str(Path(parent.__file__)),'exec')
        env=dict(parent.__dict__,self=types.SimpleNamespace(files=files),cohort=cohort,cref=cref,private_facts=[pair(stderr)])
        exec(block,env)
        # A different empty ordinary fact remains invalid even with retained full9.
        other=self.base/'ordinary-empty';other.write_bytes(b'');other.chmod(0o600);other_ref=ref(other);files[str(other)]=tuple(other_ref['signature9']);env['private_facts']=[pair(other_ref)]
        with self.assertRaises(parent.Held):exec(block,env)

    def duplicate_original_facts(self):
        self.tree.projected(self.ref)
        other=self.op/'other.json';other.write_bytes(self.source.read_bytes());other.chmod(0o600)
        ref=dict(path=str(other),sha256=self.ref['sha256'],signature9=list(c.nine(other.lstat())))
        self.tree.projected(ref)
        first,second=self.tree.pairs
        self.tree.pairs=(first,(first[0],second[1],first[2],second[3]))
        self.tree.nodes+=((str(self.op),c.five(self.op.lstat())),)
        self.tree._seal()

    def test_duplicate_facts_checked_once_in_each_closure_pass(self):
        self.duplicate_original_facts();calls={};original=c.owner_stat
        def counted(actor,path):
            calls[str(path)]=calls.get(str(path),0)+1
            return original(actor,path)
        with patch.object(c,'owner_stat',counted):self.tree.check()
        self.assertEqual(calls[str(self.source)],2)
        self.assertEqual(calls[str(self.op)],2)
        self.assertEqual(set(calls.values()),{2})

    def test_conflicting_node_facts_refuse_before_callbacks(self):
        self.duplicate_original_facts();path,row=self.tree.nodes[-1]
        self.tree.nodes+=((path,(*row[:2],row[2]^0o010,*row[3:])),);self.tree._seal()
        with patch.object(c,'close',side_effect=AssertionError('callback')):
            with self.assertRaisesRegex(c.Held,'child-tree-node-fact-conflict'):self.tree.check()

    def test_conflicting_file_facts_refuse_before_callbacks(self):
        self.duplicate_original_facts();first,second=self.tree.pairs;path,digest,row=second[0]
        conflicting=(path,digest,(*row[:2],row[2]+1,*row[3:]))
        self.tree.pairs=(first,(conflicting,*second[1:]));self.tree._seal()
        with patch.object(c,'close',side_effect=AssertionError('callback')):
            with self.assertRaisesRegex(c.Held,'child-tree-file-fact-conflict'):self.tree.check()

    def test_duplicated_file_late_namespace_callback_change_refuses(self):
        self.duplicate_original_facts();original=c.os.listdir
        def changed(path):
            result=original(path)
            if Path(path)==self.tree.root:self.source.chmod(0o640)
            return result
        with patch.object(c.os,'listdir',changed):
            with self.assertRaisesRegex(c.Held,'child-tree-original9'):self.tree.check()

    def test_duplicated_node_late_namespace_callback_change_refuses(self):
        self.duplicate_original_facts();original=c.os.listdir
        def changed(path):
            result=original(path)
            if Path(path)==self.tree.root:self.op.chmod(0o750)
            return result
        with patch.object(c.os,'listdir',changed):
            with self.assertRaisesRegex(c.Held,'child-tree-original5'):self.tree.check()

    def test_duplicate_closure_rechecks_next_invocation(self):
        self.duplicate_original_facts();self.tree.check();self.source.chmod(0o640)
        with self.assertRaisesRegex(c.Held,'child-control-final9'):self.tree.check()

    def terminal_consumer(self):
        m,owner,out,ref=self.proof_consumer()
        self.tree.output(ref,ref['path'],'factual_record')
        owner.plan={'version':13,'kind':'reviewed-archive-one-lifecycle-protocol','mounts':[dict(host=str(self.op),child='/_operation',write=True)]}
        owner.mapping=m.Paths(owner.plan['mounts']);owner.mapping.owner=owner;owner.source_ref=self.ref
        return m,owner,out,ref,m.LifecycleParent.terminal_mapper(owner)
    def test_terminal_partition_uses_actual_child_inode_and_history_join(self):
        import comic_archive_terminal_vectors as v
        m,owner,out,ref,mapper=self.terminal_consumer()
        image='/app/mylar3/mylar/publication_api.py'
        report=dict(kind='archive-one-independent-terminal-observation',outcome='observed-forward',reader_index_acceptance=False,ordinary_import_grant=False,publication_acceptance=False,mutation_authority=False,automatic_replay=False,original_vectors=dict(files=[[ref['path'],ref['signature9']],[image,[1,2,3,4,5,0o100644,1000,1000,1]]],nodes=[],claims=[],absent=[],censuses=[]))
        vectors=v.partition(report,path_mapper=mapper,sdk_map={'publication_api.py':'a'*64},mounts=owner.plan['mounts'],image_sources={path:dict(path=path,sha256='b'*64,signature9=[1,2,3,4,5,0o100644,1000,1000,1]) for path in ('/app/mylar3/mylar/config.py','/app/mylar3/Mylar.py')})
        self.assertEqual(vectors['files'],{str(out):tuple(ref['signature9'])});self.assertIn(image,vectors['child_image_files'])
        view=m.LifecycleParent.child_control_from_proof(owner,ref,vectors['files'])
        self.assertNotEqual(view['signature9'][:2],ref['signature9'][:2]);self.assertEqual(Path(view['path']).read_bytes(),out.read_bytes())
    def test_terminal_maps_control_pair_and_private_scope(self):
        self.tree.projected(self.ref);scratch=self.op/'scratch';scratch.mkdir(mode=0o700);self.tree.scope(scratch,'scratch')
        m,owner,out,ref,mapper=self.terminal_consumer()
        self.assertEqual(mapper(self.tree.child(self.source)),str(self.tree.root/self.source.name))
        self.assertEqual(mapper(self.tree.child(scratch/'leaf')),str(scratch/'leaf'))
        self.assertRaises(m.Held,mapper,'/foreign/file')
    def test_terminal_mapper_refuses_replaced_tree_or_namespace(self):
        m,owner,out,ref,mapper=self.terminal_consumer()
        m._CHILD_TREES.pop(owner)
        with self.assertRaisesRegex(m.Held,'terminal-original-child-tree'):mapper(ref['path'])
        m._CHILD_TREES[owner]=self.tree;self.tree.child_root=Path('/foreign')
        with self.assertRaisesRegex(m.Held,'terminal-original-tree-namespace'):mapper(ref['path'])

    def test_terminal_mapper_freezes_namespace_ledgers_before_callbacks(self):
        m,owner,out,ref,mapper=self.terminal_consumer()
        for field,value in (('pairs',(('foreign',),)),('scopes',(('foreign',),)),('outputs',())):
            original=getattr(self.tree,field);setattr(self.tree,field,value)
            with self.subTest(field=field),self.assertRaisesRegex(m.Held,'terminal-original-tree-namespace'):mapper(ref['path'])
            setattr(self.tree,field,original)
        absolute=m.absolute
        def late(value):
            path=absolute(value);self.tree.pairs=(('foreign',),);return path
        original_pairs=self.tree.pairs
        with patch.object(m,'absolute',late),self.assertRaisesRegex(m.Held,'terminal-original-tree-namespace'):mapper(str(self.source))
        self.tree.pairs=original_pairs
        with patch.object(c,'_SEALS',dict(c._SEALS)),self.assertRaisesRegex(m.Held,'terminal-original-tree-namespace'):mapper(ref['path'])
        original=c._SEALS[self.tree];c._SEALS[self.tree]=tuple(list(original))
        with self.assertRaisesRegex(m.Held,'terminal-original-tree-namespace'):mapper(ref['path'])

if __name__=='__main__':unittest.main()
