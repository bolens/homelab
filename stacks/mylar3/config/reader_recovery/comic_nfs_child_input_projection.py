"""Schema-owned NFS child control projection; root originals remain authoritative.

Only named path/reference fields are transformed. Source/readiness outcomes,
counts, permissions and image/source hashes are never manufactured or changed.
"""
import copy
import hashlib
from pathlib import Path

class Held(ValueError):pass

def need(v,r):
    if not v:raise Held(r)

class Inputs:
    def __init__(self,owner):
        g=owner.left.__func__.__globals__
        need(type(owner) is g.get('LifecycleParent') and g.get('_CORES',{}).get(owner)==owner.core,'nfs-input-owning-parent')
        self.owner,self.g=owner,g;self.emitted={}
    def child(self,value):
        mapping=self.owner.mapping
        return (mapping.nfs_child if mapping.plan13() else mapping.child)(value)
    def host(self,value):
        mapping=self.owner.mapping
        return (mapping.nfs_host if mapping.plan13() else mapping.host)(value)
    def ref(self,value):
        need(type(value) is dict and set(value)=={'path','sha256'},'nfs-input-two-field-ref')
        owner,g=self.owner,self.g;path=value['path']
        need(path in owner.files,'nfs-input-original-file-unbound')
        original=dict(value,signature9=list(owner.files[path]));g['read'](original)
        child=owner.nfs_child_ref(original);owner.left()
        return dict(path=child['path'],sha256=child['sha256'])
    def document(self,value):
        need(type(value) is dict and set(value)=={'path','sha256'},'nfs-input-document-ref')
        path=value['path'];need(path in self.owner.files,'nfs-input-document-original-unbound')
        return self.g['decode'](self.g['read'](dict(value,signature9=list(self.owner.files[path]))))
    def emit(self,name,document):
        ref=self.owner.emit(name,document);child=self.owner.nfs_child_ref(ref)
        self.emitted[(child['path'],child['sha256'])]=copy.deepcopy(ref)
        return dict(path=child['path'],sha256=child['sha256'])
    def cohort(self,original):
        value=self.document(original);before=copy.deepcopy(value)
        need(set(value)=={'version','kind','images','sources','writer_root','writer_sha256','native_map_count','selected_module_count','parent','receipt','logs','effective_jar_sha256','effective_commit'},'nfs-input-cohort-schema')
        roles={'probe','hardlink_kernel','scope_projection','lifecycle','readiness','readiness_input','parity','native_map','selected_sdk','writer','tests','effective_helper','effective_parent','core_parent','core_tests','writer_fixture'}
        need(set(value['sources'])==roles and set(value['logs'])=={'stdout','stderr'},'nfs-input-cohort-roles')
        # Paths-only receipt projection preserves every factual outcome and hash.
        receipt=self.document(value['receipt']);receipt_before=copy.deepcopy(receipt)
        for role in ('stdout','stderr'):
            need(receipt[role]==value['logs'][role],'nfs-input-original-log-join')
            value['logs'][role]=self.ref(value['logs'][role]);receipt[role]=dict(value['logs'][role])
        for role in roles:value['sources'][role]=self.ref(value['sources'][role])
        value['parent']=self.ref(value['parent'])
        value['writer_root']=self.child(value['writer_root'])
        value['receipt']=self.emit('nfs-cohort-receipt-input.json',receipt)
        expected=copy.deepcopy(receipt_before)
        for role in ('stdout','stderr'):expected[role]=receipt[role]
        need(receipt==expected,'nfs-input-receipt-facts-unchanged')
        immutable={'version','kind','images','writer_sha256','native_map_count','selected_module_count','effective_jar_sha256','effective_commit'}
        need(all(value[k]==before[k] for k in immutable),'nfs-input-cohort-facts-unchanged')
        return self.emit('nfs-cohort-input.json',value)
    def effective_review(self,original):
        value=self.document(original)
        roles=('producer','parent_source','report','ack','runtime','acceptance','parent_ack')
        need(type(value) is dict and set(value)==set(roles),'nfs-input-effective-seven-roles')
        projected={role:self.ref(value[role]) for role in roles}
        # Only references change. Report/ACK/acceptance/runtime bytes and their
        # semantic hash joins remain the original producer's values.
        need(all(projected[role]['sha256']==value[role]['sha256'] for role in roles),'nfs-input-effective-original-hashes')
        return self.emit('nfs-effective-review-input.json',projected)
    def outer(self,original):
        value=self.document(original);before=copy.deepcopy(value)
        need(set(value)=={'version','kind','active_scope','parent_admission','probe_plan','operation_output','native_controls','effective_observer_review','source_cohort'},'nfs-input-outer-schema')
        value['source_cohort']=self.cohort(value['source_cohort'])
        # Native receipt is the same projected cohort receipt, not a new grant.
        cohort=self.document_projected(value['source_cohort'])
        need(before['native_controls']==self.document(before['source_cohort'])['receipt'],'nfs-input-native-receipt-original-join')
        value['native_controls']=dict(cohort['receipt'])
        scope=self.document(value['active_scope']);need(type(scope['sources']) is dict,'nfs-input-scope-sources')
        scope_before=copy.deepcopy(scope)
        for key,ref in tuple(scope['sources'].items()):scope['sources'][key]=self.ref(ref)
        scope_expected=copy.deepcopy(scope_before);scope_expected['sources']=scope['sources']
        need(scope==scope_expected,'nfs-input-scope-facts-unchanged');value['active_scope']=self.emit('nfs-scope-input.json',scope)
        value['effective_observer_review']=self.effective_review(value['effective_observer_review'])
        value['operation_output']=self.child(self.host(before['operation_output']))
        admission=value['parent_admission'];need(set(admission)=={'path','grandparent_signature','expected_device','mount_identity'},'nfs-input-parent-admission-schema')
        # Directory signatures/device/mount observation are actual originals;
        # no current directory is adopted during this path projection.
        admission['path']=self.child(admission['path'])
        core=value['probe_plan'];need(type(core) is dict and core['scope']==before['active_scope'],'nfs-input-probe-scope-original')
        core['scope']=dict(value['active_scope']);core['fixture_parent']=admission['path'];core['output_root']=str(Path(value['operation_output'])/'probe')
        for key in ('library_root',):core[key]=self.child(core[key])
        return self.emit('nfs-active-input.json',value)
    def document_projected(self,value):
        # Derived own input refs retain separate root creator/SHA9 metadata.
        original=self.emitted.get((value['path'],value['sha256']))
        need(original is not None and self.owner.generated.get(original['path'])==original,'nfs-input-own-derived-original')
        raw=self.g['read'](original);need(hashlib.sha256(raw).hexdigest()==value['sha256'],'nfs-input-own-derived-hash')
        return self.g['decode'](raw)
