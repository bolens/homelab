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

if __name__=='__main__':unittest.main()
