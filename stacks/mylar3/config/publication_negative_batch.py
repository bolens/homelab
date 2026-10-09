"""Prospective owning five-source PREPARE and durable ordinary hold.

No current installed factory is assumed. Stage/SQL/terminal continuation remains
held until the shared namespace/native-reader custody adapter is installed.
"""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import threading
_KEY=object()
NAME='negative-retirement-v1.pending'
PROTOCOL='native-negative-retirement-phase-v1'
class Held(ValueError):pass
def check(value,reason):
    if not value:raise Held(reason)
def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sig(p):
    z=os.lstat(p);return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def canonical(p):
    p=Path(p);check(p.is_absolute() and p.resolve()==p and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'canonical');return p
def sdk():
    names=('publication_api','media_writer','publication_guard','publication_negative','publication_reader_phase')
    modules=[]
    for name in names:
        try:m=importlib.import_module('mylar.'+name)
        except ModuleNotFoundError:raise Held('owning-batch-modules-not-installed') from None
        p=Path(m.__file__);check(p.parent==Path('/app/mylar3/mylar') and p.resolve()==p,'installed-owning-module');modules.append(m)
    return modules

class NativeBatchPreparation:
    """One genuine held Writer, five immutable purposes, one durable hold."""
    def __init__(self,key,controller,writer,preparations,reader,journal,nonce,modules):
        check(key is _KEY,'owning-batch-factory');api,writers,guard,negative,reader_module=modules
        check(type(controller) is api.Controller and type(writer) is writers.Writer
              and type(reader) is reader_module.StoppedReaderPhase,'exact-owning-pair-and-reader')
        check(type(preparations) in (list,tuple) and len(preparations)==5
              and all(type(p) is negative.NativeNegativePreparation for p in preparations),'five-exact-native-preparations')
        check(all(p._controller is controller and p._writer is writer and p._external for p in preparations),'same-existing-owning-native-context')
        check(getattr(writer.local[1],'depth',0)>0,'existing-held-Writer')
        check(type(nonce) is str and len(nonce)==64 and all(c in '0123456789abcdef' for c in nonce),'owning-operation-nonce')
        self.thread=threading.get_ident();self.controller=controller;self.writer=writer;self.local=writer.local
        self.guard=guard;self.negative=negative;self.reader=reader;self.preparations=tuple(preparations)
        self.identity=guard.writer_identity(writer);self.projection=negative._projection(controller)
        self.journal=canonical(journal);self.marker=writer.root/NAME
        j=sig(self.journal);check(stat.S_ISDIR(j[5]) and j[6]==os.geteuid() and stat.S_IMODE(j[5])==0o700 and not os.listdir(self.journal),'empty-private-batch-journal')
        check(not any(self.journal.is_relative_to(Path(r)) or Path(r).is_relative_to(self.journal) for r in controller.roots),'batch-journal-outside-publication')
        self.nodes={p:[sig(p)[i] for i in (0,1,5,6,7)] for leaf in (self.journal,writer.root,*controller.roots) for p in (leaf,*leaf.parents)}
        bound=[]
        for p in self.preparations:
            reader.revalidate_before_native(p);bound.append(copy.deepcopy(p.revalidate()))
        check(len({b['source'] for b in bound})==5 and len({guard.canonical_digest(b['owner']) for b in bound})==5,'five-distinct-sources-and-correct-owners')
        census,records=guard.registry_snapshot(controller.database,writer.root/'publication-v1.json')
        check(all(guard.same_json(b['census'],census) for b in bound),'same-reviewed-complete-census')
        native=sig(controller.native_database)
        check(all(b['complete_catalog_absence']['database']['signature9']==native for b in bound),'same-reviewed-all-row-native-catalog')
        self.bound=bound;self.census=census;self.records=records;self.nonce=nonce
        self.files={p:sig(p) for p in (controller.database,controller.native_database,writer.root/'publication-v1.json',writer.lock)}
        self.files[self.journal]=j
        for b in bound:
            for path,fact in b['file_facts'].items():
                p=Path(path);check(p not in self.files or self.files[p]==fact['signature9'],'conflicting-batch-file');self.files[p]=fact['signature9']
        self.binding=dict(version=1,kind='owning-five-negative-batch-prepared',nonce=nonce,
            census=census,native=bound,reader_core=reader.core,writer_identity=self.identity,
            source_retirement_authority=False,reader_sql_authority=False,publication_acceptance=False)
        self.core=self._core();self._direct_originals()
        check(not os.path.lexists(self.marker),'foreign-negative-batch-fence')
        self.writer_names=set(os.listdir(writer.root))|{NAME}
        raw=encode(dict(version=1,protocol=PROTOCOL,nonce=nonce,binding_sha256=self.core,journal=str(self.journal)))
        d=os.open(writer.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            z=os.fstat(d);check([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==self.nodes[writer.root],'owning-Writer-root-FD')
            self._direct_originals()
            fd=os.open(NAME,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
            with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            os.fsync(d)
        finally:os.close(d)
        self.marker_fact=sig(self.marker);self.marker_sha=hashlib.sha256(raw).hexdigest();self.root_fact=sig(writer.root)
        check(self.marker.read_bytes()==raw,'intended-batch-fence')
        self.state=self._state();self.close_prepared()
    def _core(self):
        return hashlib.sha256(encode(dict(binding=self.binding,files={str(p):v for p,v in self.files.items()},nodes={str(p):v for p,v in self.nodes.items()},objects=[id(self.controller),id(self.writer),id(self.local),id(self.reader),*[id(p) for p in self.preparations]],thread=self.thread,projection=self.projection,records=self.records))).hexdigest()
    def _state(self):return hashlib.sha256(encode(dict(marker=self.marker_fact,sha=self.marker_sha,root=self.root_fact,names=sorted(self.writer_names)))).hexdigest()
    def _direct_originals(self):
        check(threading.get_ident()==self.thread and self.writer.local is self.local and getattr(self.local[1],'depth',0)>0
            and self.negative._projection(self.controller)==self.projection and self._core()==self.core,'immutable-owning-batch')
        self.reader.close_native_phase_passive(None)
        for database in (self.controller.database,self.controller.native_database):
            for suffix in ('-wal','-shm','-journal'):
                try:os.lstat(str(database)+suffix)
                except FileNotFoundError:pass
                else:raise Held('terminal-native-database-companion')
        for b in self.bound:
            projection=b['complete_catalog_absence']
            for path,fact in projection['passive_claim_files'].items():
                try:z=os.lstat(path)
                except FileNotFoundError:actual=None
                else:actual=[z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
                check(actual==fact,'complete-batch-catalog-claim')
            for group in ('passive_claim_ancestors','passive_scope_ancestors'):
                for path,fact in projection[group].items():
                    try:z=os.lstat(path)
                    except FileNotFoundError:actual=None
                    else:actual=[z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
                    check(actual==fact,'complete-batch-claim-ancestor')
        for p,expected in self.files.items():
            z=os.lstat(p);check([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==expected,'batch-prepared-original-CAS')
        for p,expected in self.nodes.items():
            z=os.lstat(p);check([z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]==expected,'batch-original-ancestor')
    def close_prepared(self):
        check(self._state()==self.state,'immutable-prepared-hold');self._direct_originals()
        check(set(os.listdir(self.writer.root))==self.writer_names and not os.listdir(self.journal),'prepared-hold-closed-namespace')
        check(hashlib.sha256(self.marker.read_bytes()).hexdigest()==self.marker_sha,'exact-owned-batch-fence')
        self._direct_originals()
        for p,expected in ((self.marker,self.marker_fact),(self.writer.root,self.root_fact)):
            z=os.lstat(p);check([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==expected,'prepared-hold-final-incarnation')
    def stage_all(self,*args,**kwargs):
        self.close_prepared();raise Held('owning-batch-namespace-syscall-adapter-not-installed-before-SQL')
    def commit_reader(self,*args,**kwargs):
        self.close_prepared();raise Held('owning-batch-native-reader-SQL-custody-handshake-not-installed-before-SQL')
    def terminal(self,*args,**kwargs):
        raise Held('aggregate-terminal-closure-not-installed-fence-retained')

def prepare_existing(controller,writer,preparations,reader,journal,nonce):
    return NativeBatchPreparation(_KEY,controller,writer,preparations,reader,journal,nonce,sdk())
if __name__=='__main__':print(json.dumps(dict(executable=False,installed=False,publication_acceptance=False,missing='owning staged batch/reader SQL custody/terminal continuation')))
