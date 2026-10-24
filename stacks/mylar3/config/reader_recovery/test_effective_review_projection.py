"""Original seven-file projection controls; no effective observer/Docker grants.

Real files/Tree and owning retention method are exercised. Parent constructor,
container namespace and the effective observer's factual outcomes are projected.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_child_control_projection as c
import comic_nfs_child_input_projection as inputs
import comic_reader_lifecycle_parent as p
import comic_negative_nfs_active_parent as active

class EffectiveReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.op=self.root/'op';self.op.mkdir(mode=0o700)
        self.data=self.root/'protected';self.data.mkdir(mode=0o700)
        self.config=self.data/'config.yml';self.config.write_bytes(b'public: fixture\n');self.config.chmod(0o600)
        self.absent=self.data/'absent.yml'
        self.roles=('producer','parent_source','report','ack','runtime','acceptance','parent_ack')
        report=dict(config_files={str(self.config):dict(sha256=hashlib.sha256(self.config.read_bytes()).hexdigest(),signature9=list(p.nine(self.config.lstat())))},absent_config_files=[str(self.absent)],scopes=dict(config=dict(host_path=str(self.data))),optional_absent_scopes={})
        self.review={};self.original={}
        for role in self.roles:
            value=report if role=='report' else {'fixture_role':role,'report_sha256':self.review['report']['sha256'] if 'report' in self.review else 'fixed-original-hash'}
            path=self.root/(role+'.json');path.write_bytes(p.encode(value));path.chmod(0o600)
            self.review[role]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest());self.original[str(path)]=path.read_bytes()
        self.doc=self.root/'review.json';self.doc.write_bytes(p.encode(self.review));self.doc.chmod(0o600)
        self.ref=dict(path=str(self.doc),sha256=hashlib.sha256(self.doc.read_bytes()).hexdigest())
        self.owner=SimpleNamespace(files={str(self.doc):p.nine(self.doc.lstat())},nodes=p.parents(self.doc),mapping=p.Paths([dict(host=str(self.data),child=str(self.data),write=False)]))
        # Weak source-owned state requires an actual object identity, not a dict.
        class Holder:pass
        holder=Holder();holder.__dict__.update(self.owner.__dict__);self.owner=holder
        self.addCleanup(p._NFS_EFFECTIVE_ABSENCES.pop,self.owner,None)
        p._NFS_DATA_ROOTS[self.owner]=(str(self.data),str(self.root))
        self.addCleanup(p._NFS_DATA_ROOTS.pop,self.owner,None)
    def retain(self):
        p.LifecycleParent.nfs_effective_originals(self.owner,{'effective_observer_review':self.ref},[str(self.data)])
    def projection(self):
        self.retain();self.tree=c.Tree(self.root/'child','/_operation',self.op,lambda ref,private=True:p.read(ref,private=private),uid=os.geteuid(),gid=os.getegid())
        owner=self.owner;owner.generated={};owner.left=lambda:self.tree.check()
        def project(ref):self.tree.reserve_nfs_control(ref);return self.tree.projected(ref)
        def emit(name,document):
            path=self.op/name;path.write_bytes(p.encode(document));path.chmod(0o600)
            ref=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(p.nine(path.lstat())));owner.generated[str(path)]=ref;return ref
        owner.nfs_child_ref=project;owner.emit=emit
        value=object.__new__(inputs.Inputs);value.owner=owner;value.g=dict(read=p.read,decode=p.decode);value.emitted={}
        return value
    def test_real_projection_preserves_all_original_bytes_hashes_and_report_paths(self):
        value=self.projection();derived=value.effective_review(self.ref);review=value.document_projected(derived)
        self.assertEqual(set(review),set(self.roles))
        for role in self.roles:
            self.assertNotEqual(review[role]['path'],self.review[role]['path']);self.assertEqual(review[role]['sha256'],self.review[role]['sha256'])
            child=Path(self.tree.host(review[role]['path']));self.assertEqual(child.read_bytes(),self.original[self.review[role]['path']])
            self.assertEqual(Path(self.review[role]['path']).read_bytes(),self.original[self.review[role]['path']])
        report=json.loads(Path(self.tree.host(review['report']['path'])).read_bytes())
        self.assertIn(str(self.config),report['config_files']);self.assertEqual(report['absent_config_files'],[str(self.absent)])
        self.assertEqual(tuple(self.owner.files[str(self.config)]),tuple(p.nine(self.config.lstat())));self.tree.check()
    def test_missing_or_foreign_seven_role_original_refuses(self):
        for kind in ('missing','foreignhash','extra'):
            with self.subTest(kind=kind):
                review=copy.deepcopy(self.review)
                if kind=='missing':del review['ack']
                elif kind=='extra':review['other']=review['ack']
                else:review['runtime']['sha256']='0'*64
                self.doc.write_bytes(p.encode(review));self.ref['sha256']=hashlib.sha256(self.doc.read_bytes()).hexdigest();self.owner.files[str(self.doc)]=p.nine(self.doc.lstat())
                with self.assertRaises(p.Held):self.retain()
    def test_embedded_config_outside_original_ro_mount_refuses(self):
        p._NFS_DATA_ROOTS[self.owner]=(str(self.root/'foreign'),str(self.root))
        with self.assertRaisesRegex(p.Held,'same-path-protected-mount'):self.retain()
    def test_original_config_incarnation_and_hash_refuse(self):
        self.config.write_bytes(b'changed\n')
        with self.assertRaisesRegex(p.Held,'config-original9'):self.retain()
    def test_absent_original_reappeared_refuses(self):
        self.absent.write_bytes(b'foreign');self.absent.chmod(0o600)
        with self.assertRaisesRegex(p.Held,'original-absence'):self.retain()
    def test_nested_document_replacement_during_last_read_refuses_original9(self):
        real=p.read;fired=[];target=Path(self.review['runtime']['path'])
        def changed(ref,*args,**kwargs):
            result=real(ref,*args,**kwargs)
            if ref['path']==self.review['parent_ack']['path'] and not fired:
                other=target.with_suffix('.other');other.write_bytes(target.read_bytes());other.chmod(0o600);os.replace(other,target);fired.append(True)
            return result
        with patch.object(p,'read',changed),self.assertRaises(p.Held):self.retain()
        self.assertTrue(fired)
    def test_projection_late_role_change_refuses_original_hash(self):
        value=self.projection();target=Path(self.review['ack']['path']);target.write_bytes(b'foreign')
        with self.assertRaises(p.Held):value.effective_review(self.ref)

    def valid_effective(self):
        # Existing observer facts are explicitly projected. File/copy/hash/root
        # checks and the complete owning validator execute without mocks.
        def put(role,value):
            path=Path(self.review[role]['path']);path.write_bytes(p.encode(value));path.chmod(0o600)
            self.review[role]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest();self.original[str(path)]=path.read_bytes()
        runtime=dict(kind='reviewed-komga-effective-scope-runtime',jar_sha256=active.JAR_SHA,source_commit=active.KOMGA_COMMIT,container={'Id':'fixture-cid'},pid=123,start_time=456,observed=int(time.time()))
        put('runtime',runtime)
        scopes={};identities={};presence={}
        for role in ('config','database','tasks','index','fonts'):
            path=self.data/role
            if role in ('config','index'):path.mkdir(mode=0o700)
            elif role!='fonts':path.write_bytes(b'fixture-state');path.chmod(0o600)
            scopes[role]=dict(host_path=str(path));presence[role]=role!='fonts'
            if role!='fonts':identities[str(path)]=[p.nine(path.lstat())[i] for i in (0,1,5,6,7)]
        report=dict(kind='komga-effective-persistent-scope-observation',source_sha256=self.review['producer']['sha256'],runtime_sha256=self.review['runtime']['sha256'],image=active.KOMGA,jar_sha256=active.JAR_SHA,source_commit=active.KOMGA_COMMIT,scope_observation_verified=False,final_ack_required=True,unsupported_imports_observed=False,all_library_settings_verified=False,process_verified_by_parent=False,container_id='fixture-cid',pid=123,start_time=456,scopes=scopes,scope_presence=presence,scope_identities=identities,optional_absent_scopes={str(self.data/'fonts'):dict(nearest_existing_ancestor=str(self.data),ancestor_identity=[p.nine(self.data.lstat())[i] for i in (0,1,5,6,7)])},config_files={str(self.config):dict(sha256=hashlib.sha256(self.config.read_bytes()).hexdigest(),signature9=list(p.nine(self.config.lstat())))},absent_config_files=[str(self.absent)])
        put('report',report)
        flags=dict(backup_verified=False,publication_acceptance=False,mutation_authority=False)
        put('ack',dict(scope_observation_verified=True,report_sha256=self.review['report']['sha256'],**flags))
        put('acceptance',dict(kind='accepted-komga-effective-scope',scope_observation_verified=False,final_ack_required=True,same_process_verified=True,report_sha256=self.review['report']['sha256'],source_sha256=self.review['parent_source']['sha256'],helper_sha256=self.review['producer']['sha256'],**flags))
        put('parent_ack',dict(scope_observation_verified=True,same_process_verified=True,acceptance_sha256=self.review['acceptance']['sha256'],report_sha256=self.review['report']['sha256'],**flags))
        self.doc.write_bytes(p.encode(self.review));self.ref['sha256']=hashlib.sha256(self.doc.read_bytes()).hexdigest();self.owner.files[str(self.doc)]=p.nine(self.doc.lstat())
        return report
    def test_actual_effective_validator_reads_projected_seven_and_preserves_hash_joins(self):
        report=self.valid_effective();value=self.projection();ref=value.effective_review(self.ref);review=value.document_projected(ref)
        # Actual bind namespace is projected to the physical copy in this host
        # fixture; paths alone differ, original bytes and hashes stay exact.
        local={role:dict(v,path=self.tree.host(v['path'])) for role,v in review.items()}
        with patch.object(active,'EFFECTIVE_HELPER_SHA',self.review['producer']['sha256']),patch.object(active,'EFFECTIVE_PARENT_SHA',self.review['parent_source']['sha256']):
            controls,runtime,actual=active.active_effective_controls(local,[self.data])
        self.assertEqual(actual,report);self.assertEqual(runtime['container']['Id'],'fixture-cid');self.assertIn(self.config,controls)
        for path,raw in self.original.items():self.assertEqual(Path(path).read_bytes(),raw)
    def test_actual_effective_validator_rejects_foreign_acceptance_hash_join(self):
        self.valid_effective();value=self.projection();ref=value.effective_review(self.ref);review=value.document_projected(ref)
        local={role:dict(v,path=self.tree.host(v['path'])) for role,v in review.items()}
        target=Path(local['parent_ack']['path']);document=json.loads(target.read_bytes());document['acceptance_sha256']='0'*64;target.write_bytes(p.encode(document));local['parent_ack']['sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
        with patch.object(active,'EFFECTIVE_HELPER_SHA',self.review['producer']['sha256']),patch.object(active,'EFFECTIVE_PARENT_SHA',self.review['parent_source']['sha256']),self.assertRaisesRegex(active.Held,'effective-parent-root-final-ack'):
            active.active_effective_controls(local,[self.data])

class LegacyDuplicateReadInputs(inputs.Inputs):
    """Explicit predecessor fixture: duplicate generic read, owning projection unchanged."""
    def ref(self,value):
        inputs.need(type(value) is dict and set(value)=={'path','sha256'},'nfs-input-two-field-ref')
        owner,g=self.owner,self.g;path=value['path']
        inputs.need(path in owner.files,'nfs-input-original-file-unbound')
        original=dict(value,signature9=list(owner.files[path]));g['read'](original)
        child=owner.nfs_child_ref(original);owner.left()
        return dict(path=child['path'],sha256=child['sha256'])

class CohortReferencePolicyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.op=self.root/'op';self.op.mkdir(mode=0o700);self.refs={}
  def put(name,raw,mode=0o600):
   f=self.root/name;f.write_bytes(raw);f.chmod(mode);ref=dict(path=str(f),sha256=hashlib.sha256(raw).hexdigest(),signature9=list(p.nine(f.stat())));self.refs[str(f)]=ref;return ref
  self.put=put;self.public=put('source.py',b'# disposable original public source\n',0o644);self.fact=put('fact.json',b'{}');self.stdout=put('stdout.log',b'Ran source controls\n');self.stderr=put('stderr.log',b'')
  raw=Path(__file__).with_name('comic_negative_nfs_active_parent.py').read_bytes();self.parent_original=put('original-parent.py',raw,0o644);self.installed_parent=put('comic_negative_nfs_active_parent.py',raw)
  pair=lambda ref:{k:ref[k]for k in ('path','sha256')};self.pair=pair
  roles=('probe','hardlink_kernel','scope_projection','lifecycle','readiness','readiness_input','parity','native_map','selected_sdk','writer','tests','effective_helper','effective_parent','core_parent','core_tests','writer_fixture')
  logs=dict(stdout=pair(self.stdout),stderr=pair(self.stderr));self.receipt=put('receipt.json',p.encode(dict(stdout=logs['stdout'],stderr=logs['stderr'])))
  cohort=dict(version=1,kind='approved-disposable-nfs-current-source-cohort',images={},sources={k:pair(self.public)for k in roles},writer_root=str(self.root/'writer'),writer_sha256='a'*64,native_map_count=180,selected_module_count=25,parent=pair(self.parent_original),receipt=pair(self.receipt),logs=logs,effective_jar_sha256='b'*64,effective_commit='fixture')
  self.cohort=put('cohort.json',p.encode(cohort));review={k:pair(self.public if k in('producer','parent_source')else self.fact)for k in ('producer','parent_source','report','ack','runtime','acceptance','parent_ack')};self.review=put('review.json',p.encode(review));self.scope=put('scope.json',p.encode(dict(sources={})))
  active=dict(source_cohort=pair(self.cohort),active_scope=pair(self.scope),effective_observer_review=pair(self.review),native_controls=pair(self.receipt))
  owner=object.__new__(p.LifecycleParent);self.owner=owner;owner.op=self.op;owner.generated={};owner.files={k:tuple(v['signature9'])for k,v in self.refs.items()};owner.plan_ref=self.fact;owner.source_ref=self.public;owner.plan=dict(nfs=dict(active_parent=self.installed_parent,active_input=self.fact))
  self.context=({}, {}, p.encode(active), b'{}', None);p._NFS_SOURCE_CONTEXTS[owner]=self.context;self.addCleanup(p._NFS_SOURCE_CONTEXTS.pop,owner,None)
  owner.mapping=SimpleNamespace(plan13=lambda:False,child=lambda x:x,host=lambda x:x)
  owner.left=lambda:self.tree.check()
  self.tree=c.Tree(self.root/'child','/_operation',self.op,owner.read_child_original,uid=os.geteuid(),gid=os.getegid());p._CHILD_TREES[owner]=self.tree;self.addCleanup(p._CHILD_TREES.pop,owner,None)
  def emit(name,document):
   f=self.op/name;f.write_bytes(p.encode(document));f.chmod(0o600);ref=dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),signature9=list(p.nine(f.stat())));owner.generated[str(f)]=ref;return ref
  owner.emit=emit
 def projector(self,kind=inputs.Inputs):
  obj=object.__new__(kind);obj.owner=self.owner;obj.g=p.__dict__;obj.emitted={};return obj
 def test_actual_cohort_stderr_old_red_owner_policy_new_green(self):
  with self.assertRaisesRegex(p.Held,'ref-attributes'):self.projector(LegacyDuplicateReadInputs).cohort(self.pair(self.cohort))
  # Same original empty private600/euid file is admitted only in its cohort role.
  self.assertEqual(p.read_cohort_stderr(self.cohort,self.stderr),b'')
  value=self.projector();derived=value.cohort(self.pair(self.cohort));document=value.document_projected(derived)
  self.assertEqual(document['logs']['stderr']['sha256'],self.stderr['sha256']);self.assertEqual(Path(self.tree.host(document['logs']['stderr']['path'])).read_bytes(),b'');self.assertEqual(list(p.nine(Path(self.stderr['path']).stat())),self.stderr['signature9']);self.tree.check()
 def test_public_source_old_red_owning_classification_new_green(self):
  with self.assertRaisesRegex(p.Held,'ref-attributes'):self.projector(LegacyDuplicateReadInputs).ref(self.pair(self.public))
  result=self.projector().ref(self.pair(self.public));self.assertEqual(result['sha256'],self.public['sha256']);self.tree.check()
 def test_foreign_hash_and_foreign_empty_role_refuse(self):
  wrong=dict(self.pair(self.public),sha256='0'*64)
  with self.assertRaises((p.Held,c.Held)):self.projector().ref(wrong)
  foreign=self.put('foreign-empty.log',b'');self.owner.files[foreign['path']]=tuple(foreign['signature9'])
  with self.assertRaises((p.Held,c.Held)):self.projector().ref(self.pair(foreign))
  with self.assertRaisesRegex(p.Held,'cohort-empty-stderr-role'):self.owner.read_child_original(foreign)
  wrong_stdout=dict(self.pair(self.stdout),sha256='0'*64)
  with self.assertRaisesRegex(p.Held,'ref-hash'):self.projector().ref(wrong_stdout)
 def test_ordinary_empty_and_private_mode_stay_strict(self):
  with self.assertRaisesRegex(p.Held,'ref-attributes'):p.read(self.stderr)
  wrong=self.put('private-mode.json',b'{}',0o644);self.owner.files[wrong['path']]=tuple(wrong['signature9'])
  with self.assertRaises((p.Held,c.Held)):self.projector().ref(self.pair(wrong))


 def outer_mapping(self):
  # Real owning Paths, /_operation mount and three distinct output namespaces.
  owner=self.owner;owner.plan.update(version=13,kind='reviewed-archive-one-lifecycle-protocol')
  owner.mapping=p.Paths([dict(host=str(self.root),child='/mapped-inputs',write=False),dict(host=str(self.op),child='/_operation',write=True)]);owner.mapping.owner=owner
  protected=self.root/'nfs';original=self.root/'original-output';physical=self.tree.root/'nfs'/'active-output';virtual=str(self.tree.child_root/'nfs'/'active-output')
  scope=dict(sources={},forbidden_roots=[str(protected)])
  path=Path(self.scope['path']);path.write_bytes(p.encode(scope));self.scope.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(p.nine(path.stat())));owner.files[str(path)]=tuple(self.scope['signature9'])
  before=dict(version=1,kind='reviewed-nfs-active-input',active_scope=self.pair(self.scope),parent_admission=dict(path=str(protected/'fixture'),grandparent_signature=[1]*5,expected_device=123,mount_identity={'original':True}),probe_plan=dict(scope=self.pair(self.scope),library_root=str(protected/'L'),fixture_parent=str(protected/'fixture'),output_root=str(original/'probe')),operation_output=str(original),native_controls=self.pair(self.receipt),effective_observer_review=self.pair(self.review),source_cohort=self.pair(self.cohort))
  outer=self.put('active-input.json',p.encode(before));owner.files[outer['path']]=tuple(outer['signature9'])
  p._NFS_SOURCE_CONTEXTS[owner]=({}, {}, p.encode(before),b'{}',None)
  p._NFS_DATA_ROOTS[owner]=(str(protected),str(protected))
  p._NFS_OUTPUT_PAIRS[owner]=(str(original),str(physical),virtual,(1,2,3,4,5))
  self.addCleanup(p._NFS_DATA_ROOTS.pop,owner,None);self.addCleanup(p._NFS_OUTPUT_PAIRS.pop,owner,None)
  return before,outer,physical,virtual
 def test_outer_real_paths_original_host_output_red_then_virtual_green(self):
  before,outer,physical,virtual=self.outer_mapping();value=self.projector()
  # Exact predecessor expression fails before owning child execution.
  with self.assertRaisesRegex(p.Held,'unmapped-child'):value.child(value.host(before['operation_output']))
  projected=value.document_projected(value.outer(self.pair(outer)))
  self.assertEqual(projected['operation_output'],virtual);self.assertNotEqual(virtual,str(physical));self.assertNotEqual(virtual,before['operation_output'])
  self.assertEqual(projected['probe_plan']['output_root'],str(Path(virtual)/'probe'))
  self.assertEqual(projected['probe_plan']['library_root'],before['probe_plan']['library_root'])
  self.assertEqual(projected['parent_admission'],before['parent_admission'])
  self.assertEqual(self.owner.mapping.nfs_host(projected['operation_output']),str(physical))
  self.assertEqual(self.owner.mapping.nfs_child(str(Path(before['operation_output'])/'probe')),str(Path(virtual)/'probe'));self.tree.check()
 def test_real_paths_ordinary_mapping_and_unmapped_output_refusal(self):
  before,outer,physical,virtual=self.outer_mapping();value=self.projector()
  self.assertEqual(value.child(str(self.root/'writer')),'/mapped-inputs/writer')
  self.assertEqual(value.host('/mapped-inputs/writer'),str(self.root/'writer'))
  self.assertEqual(value.child(before['parent_admission']['path']),before['parent_admission']['path'])
  with self.assertRaisesRegex(p.Held,'unmapped-host'):value.child('/foreign-host/output')
  with self.assertRaisesRegex(p.Held,'unmapped-child'):value.host('/foreign-child/output')
  self.assertEqual(value.host(str(Path(virtual)/'probe')),str(physical/'probe'))

class VectorProjectionTests(unittest.TestCase):
 """Actual Parent.left/Tree/Inputs.outer; constructor and application facts projected."""
 setUp=CohortReferencePolicyTests.setUp
 projector=CohortReferencePolicyTests.projector
 outer_mapping=CohortReferencePolicyTests.outer_mapping
 def configured(self):
  import test_nfs_stopped_handoff as stopped
  before,outer,physical,virtual=self.outer_mapping();owner=self.owner
  scope=p.decode(Path(self.scope['path']).read_bytes());scope['sources']={str(i):self.pair(self.public) for i in range(7)}
  path=Path(self.scope['path']);path.write_bytes(p.encode(scope));self.scope.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(p.nine(path.stat())));owner.files[str(path)]=tuple(self.scope['signature9'])
  before['active_scope']=self.pair(self.scope);before['probe_plan']['scope']=self.pair(self.scope)
  path=Path(outer['path']);path.write_bytes(p.encode(before));outer.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(p.nine(path.stat())));owner.files[str(path)]=tuple(outer['signature9'])
  sample=stopped.fixture_owner();owner.thread=sample.thread;owner.deadline=sample.deadline;owner.engine=sample.engine;owner.nodes={}
  owner.source_ref=sample.source_ref;owner.plan_ref=self.fact;owner.plan['operation']=str(owner.op);owner.plan['nfs']['active_input']=outer
  del owner.left
  p._CONFIGURED_OVERLAYS[owner]=p._CONFIGURED_OVERLAY_SEALS[owner]=();p._CONFIGURED_IMAGE_LABELS[owner]=p._CONFIGURED_IMAGE_SEALS[owner]=()
  p._NFS_EFFECTIVE_ABSENCES[owner]=p.encode([])
  p._NFS_SOURCE_CONTEXTS[owner]=({}, {},p.encode(before),p.encode({}),before['operation_output'])
  p._NFS_SOURCE_SEALS[owner]=p.encode(dict(refs={},raw_sha={},active=before,probe={},output=before['operation_output'],effective_absences=[]))
  phase=self.tree.phase('nfs');p._NFS_OUTPUT_PAIRS[owner]=(before['operation_output'],str(physical),virtual,tuple(p.five(phase.stat())))
  emit=owner.emit
  def sealed_emit(name,document):
   result=emit(name,document);p._GENERATED[owner]=p.encode(owner.generated);return result
  owner.emit=sealed_emit;stopped.seal_fixture_owner(owner)
  for registry in (p._CORES,p._GENERATED,p._CONFIGURED_OVERLAYS,p._CONFIGURED_OVERLAY_SEALS,p._CONFIGURED_IMAGE_LABELS,p._CONFIGURED_IMAGE_SEALS,p._NFS_EFFECTIVE_ABSENCES,p._NFS_SOURCE_SEALS):self.addCleanup(registry.pop,owner,None)
  owner.left();return before,outer
 def host_projection(self):
  import sys,types
  before,outer=self.configured();owner=self.owner
  source=self.put('private-inputs.py',Path(inputs.__file__).read_bytes());owner.files[source['path']]=tuple(source['signature9'])
  module=types.ModuleType('_vector_private_inputs');module.__file__=source['path'];exec(compile(Path(source['path']).read_bytes(),source['path'],'exec'),module.__dict__)
  sys.modules[module.__name__]=module;self.addCleanup(sys.modules.pop,module.__name__,None)
  refs={'comic_nfs_child_input_projection.py':source};raws={next(iter(refs)):Path(source['path']).read_bytes()}
  p._NFS_SOURCE_CONTEXTS[owner]=(refs,raws,p.encode(before),p.encode({}),before['operation_output'])
  p._NFS_SOURCE_SEALS[owner]=p.encode(dict(refs=refs,raw_sha={k:hashlib.sha256(v).hexdigest() for k,v in raws.items()},active=before,probe={},output=before['operation_output'],effective_absences=[]))
  functions=tuple((module.Inputs,name,value,value.__code__) for name,value in module.Inputs.__dict__.items() if hasattr(value,'__code__'))
  modules={next(iter(refs)):module};entry=(next(iter(refs)),module,module.__name__,functions)
  p._NFS_HOST_MODULES[owner]=modules;p._NFS_HOST_MODULE_SEALS[owner]=(tuple(modules.items()),(entry,))
  for registry in (p._NFS_HOST_MODULES,p._NFS_HOST_MODULE_SEALS):self.addCleanup(registry.pop,owner,None)
  import test_nfs_stopped_handoff as stopped
  stopped.seal_fixture_owner(owner);return module
 def test_actual_prepare_uses_original_private_projection_module(self):
  self.host_projection();result=self.owner.prepare_nfs_inputs();original=self.tree.original(result)
  value=p.decode(p.read(original));self.assertEqual(value['kind'],'reviewed-nfs-active-input');self.owner.left();self.tree.check()
 def test_prepare_rejects_projector_instance_replacement(self):
  self.host_projection();self.owner.nfs_child_refs=lambda values:values
  with self.assertRaisesRegex(p.Held,'original-projector'):self.owner.prepare_nfs_inputs()
 def test_prepare_rejects_projection_module_code_change_during_copy(self):
  module=self.host_projection();method=module.Inputs.refs;code=method.__code__;reader=self.tree.read_original;calls=[]
  def changed(ref,**kwargs):
   result=reader(ref,**kwargs);calls.append(True)
   if len(calls)==2:method.__code__=(lambda self,values,project:values).__code__
   return result
  self.tree.read_original=changed;identity=list(self.tree.identity);identity[5]=id(changed);self.tree.identity=tuple(identity);self.tree._seal()
  try:
   with self.assertRaisesRegex(p.Held,'host-original-callable'):self.owner.prepare_nfs_inputs()
  finally:method.__code__=code
 def test_prepare_rejects_projection_code_change_during_final_emit(self):
  module=self.host_projection();method=module.Inputs.refs;code=method.__code__;emit=self.owner.emit;fired=[]
  def changed(name,document):
   result=emit(name,document)
   if name=='nfs-active-input.json':method.__code__=(lambda self,values,project:values).__code__;fired.append(True)
   return result
  self.owner.emit=changed
  try:
   with self.assertRaisesRegex(p.Held,'host-original-callable'):self.owner.prepare_nfs_inputs()
  finally:method.__code__=code
  self.assertTrue(fired)
 def test_outer_three_batches_preserve_original_facts_and_bytes(self):
  before,outer=self.configured();originals={path:Path(path).read_bytes() for path in self.owner.files};widths=[]
  def project(refs):widths.append(len(refs));return self.owner.nfs_child_refs(refs)
  value=self.projector();result=value.document_projected(value.outer(self.pair(outer),_project=project))
  self.assertEqual(widths,[18,7,7]);self.assertEqual(result['parent_admission'],before['parent_admission'])
  scope=value.document_projected(result['active_scope']);original_scope=p.decode(originals[self.scope['path']]);self.assertEqual(scope['forbidden_roots'],original_scope['forbidden_roots'])
  self.assertEqual({path:Path(path).read_bytes() for path in originals},originals);self.owner.left();self.tree.check()
 def test_batch_two_parent_closures_without_per_file_parent_calls(self):
  self.configured();calls=[];real=p.none_network_profile_contract
  # The original guard runs once per actual Parent.left; no Parent method replacement.
  def count():calls.append(True);return real()
  method=p.LifecycleParent.left;defaults=method.__defaults__
  try:
   method.__defaults__=(count,count.__code__)
   # Batch captured the original defaults at definition, so changing them refuses.
   with self.assertRaisesRegex(p.Held,'original-binding'):self.owner.nfs_child_refs([self.public]*7)
  finally:method.__defaults__=defaults
  self.assertEqual(calls,[])
  # Count actual closure entry with a trace hook without replacing guarded code.
  import sys
  def trace(frame,event,arg):
   if event=='call' and frame.f_code is method.__code__:calls.append(True)
  old=sys.getprofile();sys.setprofile(trace)
  try:self.owner.nfs_child_refs([self.public]*7)
  finally:sys.setprofile(old)
  self.assertEqual(len(calls),2)
 def test_conflicting_duplicates_refuse_before_parent_or_copy(self):
  self.configured();bad=dict(self.public,sha256='0'*64)
  with patch.object(self.tree,'reserve_nfs_control',side_effect=AssertionError('must not copy')) as reserve:
   with self.assertRaisesRegex(p.Held,'vector-conflict'):self.owner.nfs_child_refs([self.public,bad])
  reserve.assert_not_called()
 def test_foreign_declared_path_and_wrong_hash_refuse(self):
  self.configured()
  for ref in (dict(self.public,path=str(self.root/'foreign')),dict(self.public,sha256='0'*64)):
   with self.subTest(ref=ref['sha256'][:4]),self.assertRaises((p.Held,c.Held)):self.owner.nfs_child_refs([ref])
 def mutate_during_copy(self,change):
  self.configured();read=self.tree.read_original;calls=[]
  def callback(ref,**kwargs):
   result=read(ref,**kwargs);calls.append(ref['path'])
   if len(calls)==2:change()
   return result
  # Constructor-projected I/O callback is retained in the real Tree's identity.
  self.tree.read_original=callback;identity=list(self.tree.identity);identity[5]=id(callback);self.tree.identity=tuple(identity);self.tree._seal()
  with self.assertRaises((p.Held,c.Held)):self.owner.nfs_child_refs([self.public,self.fact,self.stdout])
  self.assertGreaterEqual(len(calls),2)
 def test_source_mutation_during_second_copy_refuses(self):
  self.mutate_during_copy(lambda:Path(self.stdout['path']).write_bytes(b'changed'))
 def test_registry_replacement_during_second_copy_refuses(self):
  self.mutate_during_copy(lambda:p._NFS_SOURCE_CONTEXTS.__setitem__(self.owner,tuple(list(p._NFS_SOURCE_CONTEXTS[self.owner]))))
 def test_original_tree_code_mutation_during_second_copy_refuses(self):
  method=c.Tree.projected;code=method.__code__
  try:self.mutate_during_copy(lambda:setattr(method,'__code__',(lambda self,ref:ref).__code__))
  finally:method.__code__=code
 def test_ledger_loss_during_second_copy_refuses(self):
  self.mutate_during_copy(lambda:setattr(self.tree,'nfs_controls',()))
 def test_final_parent_tree_callback_core_mutation_refuses(self):
  self.configured();reader=c.owner_stat;lefts=[];fired=[]
  import sys
  def trace(frame,event,arg):
   if event=='call' and frame.f_code is p.LifecycleParent.left.__code__:lefts.append(True)
  def changed(actor,path):
   result=reader(actor,path)
   if len(lefts)>=2 and not fired:self.owner.files.clear();fired.append(True)
   return result
  old=sys.getprofile();sys.setprofile(trace)
  try:
   with patch.object(c,'owner_stat',changed),self.assertRaisesRegex(p.Held,'original-logical-state'):self.owner.nfs_child_refs([self.public])
  finally:sys.setprofile(old)
  self.assertTrue(fired);self.assertEqual(len(lefts),2)
 def test_original_tree_scope_append_after_final_parent_refuses(self):
  self.configured();extra=self.root/'foreign-scope';extra.mkdir(mode=0o700);returns=[]
  import sys
  def trace(frame,event,arg):
   if event=='return' and frame.f_code is p.LifecycleParent.left.__code__:
    returns.append(True)
    if len(returns)==2:self.tree.scope(str(extra),'scratch')
  old=sys.getprofile();sys.setprofile(trace)
  try:
   with self.assertRaisesRegex(p.Held,'retained-ledgers'):self.owner.nfs_child_refs([self.public])
  finally:sys.setprofile(old)
  self.assertEqual(len(returns),2);self.assertTrue(self.tree.scopes);self.tree.check()
 def test_original_tree_unrequested_projection_after_final_parent_refuses(self):
  self.configured();returns=[]
  import sys
  def trace(frame,event,arg):
   if event=='return' and frame.f_code is p.LifecycleParent.left.__code__:
    returns.append(True)
    if len(returns)==2:self.tree.reserve_nfs_control(self.fact);self.tree.projected(self.fact)
  old=sys.getprofile();sys.setprofile(trace)
  try:
   with self.assertRaisesRegex(p.Held,'requested-ledgers'):self.owner.nfs_child_refs([self.public])
  finally:sys.setprofile(old)
  self.assertEqual(len(returns),2);self.tree.check()
 def test_foreign_initial_state_method_is_never_called(self):
  self.configured()
  with patch.object(self.tree,'_state',side_effect=AssertionError('foreign callback must not run')) as state:
   with self.assertRaisesRegex(p.Held,'original-tree-code'):self.owner.nfs_child_refs([self.public])
  state.assert_not_called()
 def test_parent_core_mutation_during_second_copy_refuses(self):
  self.mutate_during_copy(lambda:self.owner.files.clear())

if __name__=='__main__':unittest.main()
