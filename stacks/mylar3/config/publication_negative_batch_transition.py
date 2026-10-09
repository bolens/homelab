"""Prospective five-member stage/retire adapter. Installation required.

Only exact installed batch and namespace classes can enter the public factory.
SQL and final marker removal remain separate owning custody operations.
"""
import copy
import hashlib
import importlib
import json
import os
import stat
from pathlib import Path
import threading
_KEY=object()
class Held(ValueError):pass
def check(v,r):
    if not v:raise Held(r)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sig(p):
    z=os.lstat(p);return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def direct(p,v):
    try:s=sig(p)
    except FileNotFoundError:s=None
    check(s==v,'transition-direct-leaf')
class NegativeBatchReservation:
    def __init__(self,key,batch,projection):
        check(key is _KEY,'owning-transition-factory')
        self.batch=batch;self.reader=batch.reader;self.projection=projection;self.thread=threading.get_ident()
        self.original_core=batch.core;self.original_state=batch.state
        self.bound=copy.deepcopy(batch.bound)
        check([m['source'] for m in projection.members]==[b['source'] for b in self.bound],'exact-five-phase-sources')
        self.sources={Path(b['source']) for b in self.bound}
        for member in projection.members:
            target=Path(member['target']);parent=sig(target.parent)
            check(not any(target.is_relative_to(Path(root)) or Path(root).is_relative_to(target.parent) for root in batch.controller.roots),'retained-alias-outside-all-publication-roots')
            check(stat.S_ISDIR(parent[5]) and stat.S_IMODE(parent[5])==0o700 and parent[6]==os.geteuid() and parent[0]==member['original']['signature9'][0],'private-same-filesystem-retention')
            check(str(target) not in {p for bound in self.bound for p in bound['file_facts']},'retention-disjoint-custody')
        self.files={p:list(v) for p,v in batch.files.items() if p not in self.sources and p!=batch.journal}
        self.nodes=copy.deepcopy(batch.nodes)
        self.core=self._core()
        self.close()
    def _core(self):
        return hashlib.sha256(encode(dict(original=[self.original_core,self.original_state],bound=self.bound,files={str(p):v for p,v in self.files.items()},nodes={str(p):v for p,v in self.nodes.items()},objects=[id(self.batch),id(self.reader),id(self.projection)],projection=self.projection.core,thread=self.thread))).hexdigest()
    def _lifetime(self):
        b=self.batch
        check(threading.get_ident()==self.thread and self._core()==self.core and b._core()==self.original_core and b._state()==self.original_state and b.writer.local is b.local and getattr(b.local[1],'depth',0)>0,'immutable-batch-transition')
        check(b.negative._projection(b.controller)==b.projection and b.guard.writer_identity(b.writer)==b.identity,'same-held-owning-Writer')
    def _close_native_semantics(self):
        self._lifetime();b=self.batch
        census,records=b.guard.registry_snapshot(b.controller.database,b.writer.root/'publication-v1.json')
        check(b.guard.same_json(census,b.census) and b.guard.same_json(records,b.records),'current-complete-census')
        for bound in self.bound:
            observed=b.controller.observe(b.writer,{'allowed':[bound['owner']]})
            check(len(observed['observed'])==1 and observed['observed'][0]['catalog']['path']==bound['counterpart'],'current-exact-proper-owner')
            check(b.negative._protected_paths(b.controller,b.writer)==set(map(Path,bound['protected_paths'])),'protected-originals-unchanged')
            for path,f in bound['file_facts'].items():
                if Path(path) in self.sources:continue
                actual=self.projection.k._fact(Path(path),1)
                check(actual['signature9']==f['signature9'] and actual['sha256']==f['sha256'] and b.negative.attrs(Path(path))==bound['xattrs'][path],'current-preserved-custody')
        check(hashlib.sha256(b.marker.read_bytes()).hexdigest()==b.marker_sha,'owned-master-marker')
        self.projection.close()
    def close(self):
        self._close_native_semantics();self.reader.close_native_phase_passive(None);self._direct()
    def close_native_precommit(self,reader):
        check(reader is self.reader and self.projection.phases==['linked']*5,'exact-staged-native-SQL-handshake')
        self._close_native_semantics();self._direct()
    def close_native_reverse(self,reader):
        check(reader is self.reader and all(v in ('linked','retained') for v in self.projection.phases),'exact-owned-native-reverse')
        self._close_native_semantics();self._direct()
    def close_native_original_rollback(self,reader):
        check(reader is self.reader and self.projection.phases==['source']*5,'exact-original-native-rollback')
        self._close_native_semantics();self._direct()
    def native_original_sql_controls(self,reader):
        check(reader is self.reader and self.projection.phases==['source']*5,'exact-original-native-SQL-vectors')
        return self._native_sql_controls()
    def native_sql_controls(self,reader):
        check(reader is self.reader and all(v in ('linked','retained') for v in self.projection.phases),'exact-staged-native-SQL-vectors')
        return self._native_sql_controls()
    def _native_sql_controls(self):
        self._lifetime();self._direct()
        b=self.batch;q=self.projection
        files={**self.files,b.marker:b.marker_fact,b.writer.root:b.root_fact,q.journal:q.directory}
        nodes=dict(self.nodes)
        for db in (b.controller.database,b.controller.native_database):
            for suffix in ('-wal','-shm','-journal'):files[Path(str(db)+suffix)]=None
        for bound in self.bound:
            c=bound['complete_catalog_absence']
            for p,v in c['passive_claim_files'].items():
                p=Path(p);check(p not in files or files[p]==v,'conflicting-native-SQL-leaf');files[p]=v
            for group in ('passive_claim_ancestors','passive_scope_ancestors'):
                for p,v in c[group].items():
                    p=Path(p);check(p not in nodes or nodes[p]==v,'conflicting-native-SQL-node');nodes[p]=v
        for parent,values in q.expected_namespaces().items():
            files[parent]=q.parents[parent]
            for name,value in values.items():files[parent/name]=value
        for p,(fact,digest) in q.receipts.items():files[p]=fact
        for p,v in q.nodes.items():
            check(p not in nodes or nodes[p]==v,'conflicting-phase-SQL-node');nodes[p]=v
        return copy.deepcopy(files),copy.deepcopy(nodes)
    def _direct(self):
        b=self.batch
        # Called AFTER every reader/native/namespace callback before syscall.
        for db in (b.controller.database,b.controller.native_database):
            for suffix in ('-wal','-shm','-journal'):direct(str(db)+suffix,None)
        for bound in self.bound:
            c=bound['complete_catalog_absence']
            for p,v in c['passive_claim_files'].items():direct(p,v)
            for group in ('passive_claim_ancestors','passive_scope_ancestors'):
                for p,v in c[group].items():
                    try:z=os.lstat(p);actual=[z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
                    except FileNotFoundError:actual=None
                    check(actual==v,'complete-claim-ancestor')
        check(set(os.listdir(b.writer.root))==b.writer_names,'closed-owning-Writer')
        for p,v in {**self.files,b.marker:b.marker_fact,b.writer.root:b.root_fact}.items():direct(p,v)
        for p,v in self.nodes.items():
            z=os.lstat(p);check([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==v,'original-control-ancestor')
        # Namespace semantics were already read; direct vector/census now seals
        # all unrelated children and EXACT five projected participant states.
        q=self.projection;q._lifetime()
        check(set(os.listdir(q.journal))=={p.name for p in q.receipts},'closed-phase-journal')
        for parent,values in q.expected_namespaces().items():
            check(set(os.listdir(parent))==set(values),'closed-phase-parent')
            direct(parent,q.parents[parent])
            for name,value in values.items():direct(parent/name,value)
        direct(q.journal,q.directory)
        for p,(fact,digest) in q.receipts.items():direct(p,fact)
        for p,v in q.nodes.items():
            z=os.lstat(p);check([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==v,'phase-ancestor')
    def _move(self,index,action):
        self.close();q=self.projection;q.intent(index,action)
        src=Path(q.members[index]['source']);dst=Path(q.members[index]['target'])
        a=os.open(src.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        c=os.open(dst.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            self.close()
            reader_files,reader_nodes=self.reader.native_syscall_controls(None)
            for p,v in reader_files.items():
                if Path(p) in self.files:check((None if v is None else list(v))==self.files[Path(p)],'conflicting-reader-file')
            for p,v in reader_nodes.items():
                if Path(p) in self.nodes:check((None if v is None else list(v))==self.nodes[Path(p)],'conflicting-reader-ancestor')
            for fd,parent in ((a,src.parent),(c,dst.parent)):
                z=os.fstat(fd);check([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==q.nodes[parent],'phase-parent-FD')
            self._direct()
            for p,v in reader_files.items():direct(p,None if v is None else list(v))
            for p,v in reader_nodes.items():
                try:z=os.lstat(p);actual=[z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
                except FileNotFoundError:actual=None
                check(actual==(None if v is None else list(v)),'reader-final-ancestor')
            if action=='link':os.link(src.name,dst.name,src_dir_fd=a,dst_dir_fd=c,follow_symlinks=False)
            elif action=='restore':os.link(dst.name,src.name,src_dir_fd=c,dst_dir_fd=a,follow_symlinks=False)
            else:os.unlink(src.name if action=='retire' else dst.name,dir_fd=a if action=='retire' else c)
            os.fsync(a);os.fsync(c)
        finally:os.close(a);os.close(c)
        q.observe_transition(index);self.close()
    def stage_all(self):
        check(self.projection.phases==['source']*5,'single-stage-predecessor')
        for i in range(5):self._move(i,'link')
        return dict(staged_verified=True,reader_sql_authority=False,publication_acceptance=False,final_ack_required=True)
    def rollback_staging(self):
        self.reader.revalidate_rollback_ready(None)
        for i in reversed(range(5)):
            if self.projection.phases[i]=='retained':self._move(i,'restore')
            if self.projection.phases[i]=='linked':self._move(i,'unstage')
            else:check(self.projection.phases[i]=='source','exact-owned-rollback-phase')
        return dict(staging_rollback_verified=True,publication_acceptance=False,final_ack_required=True)
    def revalidate_staged(self,reader,preparations):
        check(reader is self.reader and tuple(preparations)==self.batch.preparations and self.projection.phases==['linked']*5,'exact-five-staged-native-reader')
        self.close()
    def retire_all(self):
        self.reader.revalidate_committed(None)
        check(self.projection.phases==['linked']*5,'all-five-linked-before-retirement')
        for i in range(5):self._move(i,'retire')
        return dict(retained_verified=True,publication_acceptance=False,final_ack_required=True)
    def consume_native(self,preparation):
        matches=[i for i,p in enumerate(self.batch.preparations) if p is preparation]
        check(len(matches)==1,'exact-original-five-native-purpose')
        self.reader.revalidate_committed(None)
        index=matches[0]
        check(self.projection.phases[index]=='linked' and all(v in ('linked','retained') for v in self.projection.phases),'finite-one-member-consume')
        self._move(index,'retire')
        return dict(index=index,filesystem_retained=True,publication_acceptance=False,final_ack_required=True,marker_retained=True)
    def terminal(self):raise Held('owning-reader-SQL-commit-and-terminal-marker-clear-not-installed')
def from_prepared(batch,targets):
    modules=[]
    for name in ('publication_negative_batch','publication_negative_batch_projection'):
        try:m=importlib.import_module('mylar.'+name)
        except ModuleNotFoundError:raise Held('owning-batch-components-not-installed') from None
        p=Path(m.__file__);check(p.parent==Path('/app/mylar3/mylar') and p.resolve()==p,'installed-owning-component');modules.append(m)
    check(type(batch) is modules[0].NativeBatchPreparation and type(targets) in (list,tuple) and len(targets)==5,'exact-owning-prepared-and-targets')
    batch.close_prepared()
    participants=[];k=modules[1].kernel()
    for bound,target in zip(batch.bound,targets):
        f=bound['file_facts'][bound['source']]
        actual=k._fact(Path(bound['source']),1)
        check(actual['signature9']==f['signature9'] and actual['sha256']==f['sha256'] and batch.negative.attrs(Path(bound['source']))==bound['xattrs'][bound['source']],'reviewed-original-source')
        participants.append(dict(source=bound['source'],target=str(target),original=actual))
    projection=modules[1].BatchNamespace(modules[1]._KEY,participants,batch.journal)
    return NegativeBatchReservation(_KEY,batch,projection)
