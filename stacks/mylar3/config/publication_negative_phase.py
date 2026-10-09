"""Prospective native negative phase protocol. NOT installed in current SDK.

Ordinary Writer/native/worker admission must call admission(writer_root) before
media access. A present fence always holds ordinary admission. Only an exact
same-thread owning phase object can continue its private prepared transition.
Existing registered archive and nlink1 rules are unchanged for other callers.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import threading

NAME='negative-retirement-v1.pending'
PROTOCOL='native-negative-retirement-phase-v1'
KERNEL_PATH=Path('/app/mylar3/mylar/publication_negative_namespace_kernel.py')
KERNEL_SHA='f35887c5dad8985baf41fb5861423c18f556db1311f0e4fde202021f4cb59633'
LOADER_SHA='406d27948d2dd16f63eb8b70506daf46165a30f48b50db8d116750556d189a44'
_KEY=object()
class Held(ValueError):pass

def check(v,why):
    if not v:raise Held(why)
def compact(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sig(p):
    z=os.lstat(p);return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def canonical(p):
    p=Path(p);check(p.is_absolute() and '..' not in p.parts and p.resolve()==p
       and not any(q.is_symlink() for q in (p,*p.parents)),'canonical');return p
def private(p):
    p=canonical(p);s=sig(p);check(stat.S_ISREG(s[5]) and s[6]==os.geteuid()
       and stat.S_IMODE(s[5])==0o600 and s[8]==1 and 0<s[2]<=1024**2,'private-protocol')
    b=p.read_bytes();check(sig(p)==s,'protocol-incarnation');return b,s

def admission(writer_root):
    """Proposed ordinary admission hook: no receipt can grant continuation.

    Install in media_writer outer hold, native_writers startup/ordinary admission,
    guard authority/media status and worker pending admission. Missing installation
    is an execution prerequisite gap, not evidence that the current SDK holds it.
    """
    root=canonical(writer_root)
    try:os.lstat(root/'negative-retirement-v1.terminal-pending')
    except FileNotFoundError:pass
    except OSError:raise Held('negative-terminal-unavailable-held') from None
    else:raise Held('negative-terminal-pending-held')
    path=root/NAME
    try:os.lstat(path)
    except FileNotFoundError:return
    try:
        raw,_=private(path)
        def unique(items):
            out={}
            for k,v in items:check(k not in out,'duplicate-protocol');out[k]=v
            return out
        body=json.loads(raw,object_pairs_hook=unique)
        check(type(body) is dict and set(body)=={'version','protocol','nonce','binding_sha256','journal'}
            and type(body['version']) is int and body['version']==1 and body['protocol']==PROTOCOL,
            'phase-protocol')
        check(all(type(body[k]) is str and len(body[k])==64
              and all(c in '0123456789abcdef' for c in body[k])
              for k in ('nonce','binding_sha256')) and type(body['journal']) is str
              and len(body['journal'])<=4096 and Path(body['journal']).is_absolute()
              and '..' not in Path(body['journal']).parts,'phase-protocol-values')
    except (OSError,ValueError,TypeError,KeyError):raise Held('negative-phase-malformed-held') from None
    raise Held('negative-phase-pending-held')

def kernel():
    module=importlib.import_module('mylar.publication_negative_namespace')
    path=Path(module.__file__).absolute()
    check(path==Path('/app/mylar3/mylar/publication_negative_namespace.py')
          and path.resolve()==path,'installed-namespace-loader')
    before=sig(path);raw=path.read_bytes()
    check(sig(path)==before and hashlib.sha256(raw).hexdigest()==LOADER_SHA
          and module.KERNEL_SHA==KERNEL_SHA,'kernel-pin')
    return module.kernel()

def sdk():
    modules=tuple(importlib.import_module('mylar.'+n) for n in
        ('publication_api','media_writer','publication_guard','publication_negative'))
    for m in modules:
        p=Path(m.__file__).absolute();check(p.parent==Path('/app/mylar3/mylar')
            and p.resolve()==p,'installed-native-phase-required')
    return modules

class NativePhaseFence:
    """Owned durable hold; not an API token or a serialized mutation capability."""
    def __init__(self,key,preparation,reader_phase,journal,nonce,modules):
        check(key is _KEY,'owning-phase-factory')
        self.api,self.writers,self.guard,self.negative=modules
        check(type(preparation) is self.negative.NativeNegativePreparation,'exact-negative-preparation')
        # No operational reader phase exists in current SDK. Its reviewed source
        # must provide this exact installed class and owning factory before apply.
        try:reader_module=importlib.import_module('mylar.publication_reader_phase')
        except ModuleNotFoundError:raise Held('owning-reader-phase-not-installed-before-SQL') from None
        rp=Path(reader_module.__file__).absolute()
        check(rp.parent==Path('/app/mylar3/mylar') and rp.resolve()==rp
              and type(reader_phase) is reader_module.StoppedReaderPhase,'installed-typed-reader-phase')
        reader_phase.revalidate_before_native(preparation)
        before=preparation.revalidate();self.preparation=preparation
        self.reader=reader_phase;self.writer=preparation._writer;self.controller=preparation._controller
        check(type(self.controller) is self.api.Controller and type(self.writer) is self.writers.Writer,
              'exact-existing-native-pair')
        self.thread=threading.get_ident();self.local=self.writer.local
        self.identity=tuple(self.guard.writer_identity(self.writer));self.projection=self.negative._projection(self.controller)
        check(type(nonce) is str and len(nonce)==64 and all(c in '0123456789abcdef' for c in nonce),'operation-nonce')
        self.journal=canonical(journal);self.path=self.writer.root/NAME
        s=sig(self.journal);check(stat.S_ISDIR(s[5]) and s[6]==os.geteuid()
              and stat.S_IMODE(s[5])==0o700 and not any(self.journal.iterdir()),'empty-private-journal')
        check(not any(self.journal.is_relative_to(Path(root)) for root in self.controller.roots),
              'journal-outside-libraries')
        self.nodes={q:tuple(sig(q)[i] for i in (0,1,5,6,7))
            for p in [self.journal,self.writer.root,*map(Path,before['file_facts'])] for q in canonical(p).parents}
        self.writer_names=set(os.listdir(self.writer.root))|{NAME}
        self.bound=before;self.census,self.records=self.guard.registry_snapshot(
            self.controller.database,self.writer.root/'publication-v1.json')
        check(self.census==before['census'],'reviewed-current-census')
        self.native_control={p:sig(p) for p in (self.controller.database,self.controller.native_database,
            self.writer.root/'publication-v1.json',self.writer.lock)}
        check(self.native_control[self.controller.native_database]==before['complete_catalog_absence']['database']['signature9'],
              'prepared-complete-catalog-CAS')
        self.seal=hashlib.sha256(compact(dict(binding=before,census=self.census,records=self.records,
            native={str(p):s for p,s in self.native_control.items()},identity=self.identity,
            projection=self.projection,thread=self.thread,
            objects=[id(self.reader),id(self.writer),id(self.controller),id(self.local)],
            nodes={str(p):v for p,v in self.nodes.items()}))).hexdigest()
        body=dict(version=1,protocol=PROTOCOL,nonce=nonce,binding_sha256=self.seal,journal=str(self.journal))
        check(not os.path.lexists(self.path),'foreign-negative-fence')
        raw=compact(body);fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        d=os.open(self.writer.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(d)
        finally:os.close(d)
        self.writer_root_fact=sig(self.writer.root)
        self.fence_fact=sig(self.path);self.fence_sha=hashlib.sha256(raw).hexdigest()
        self.fence_seal=hashlib.sha256(compact([self.fence_fact,self.fence_sha,str(self.path),str(self.journal),
            self.writer_root_fact,sorted(self.writer_names)])).hexdigest()
        self.check()
    def check(self):
        check(threading.get_ident()==self.thread and self.writer.local is self.local
              and getattr(self.local[1],'depth',0)>0 and self.negative._projection(self.controller)==self.projection
              and tuple(self.guard.writer_identity(self.writer))==self.identity,'owning-writer-lifetime')
        check(hashlib.sha256(compact(dict(binding=self.bound,census=self.census,records=self.records,
            native={str(p):s for p,s in self.native_control.items()},identity=self.identity,
            projection=self.projection,thread=self.thread,
            objects=[id(self.reader),id(self.writer),id(self.controller),id(self.local)],
            nodes={str(p):v for p,v in self.nodes.items()}))).hexdigest()==self.seal,'immutable-native-phase')
        check(self.path==self.writer.root/NAME and hashlib.sha256(compact([self.fence_fact,
            self.fence_sha,str(self.path),str(self.journal),self.writer_root_fact,sorted(self.writer_names)])).hexdigest()==self.fence_seal,'immutable-phase-fence')
        raw,s=private(self.path);check(s==self.fence_fact and hashlib.sha256(raw).hexdigest()==self.fence_sha,'exact-phase-fence')
        census,records=self.guard.registry_snapshot(self.controller.database,self.writer.root/'publication-v1.json')
        check(self.guard.same_json(census,self.census) and self.guard.same_json(records,self.records),'phase-current-census')
        observed=self.controller.observe(self.writer,{'allowed':[self.bound['owner']]})
        check(len(observed['observed'])==1 and observed['observed'][0]['catalog']['path']==self.bound['counterpart'],
              'phase-current-correct-owner')
        check(self.negative._protected_paths(self.controller,self.writer)==set(map(Path,self.bound['protected_paths'])),
              'phase-protected-originals')
        custody={}
        km=kernel()
        for name in ('counterpart',):
            path=Path(self.bound[name]);fact=km._fact(path,1);expected=self.bound['file_facts'][str(path)]
            check(fact['signature9']==expected['signature9'] and fact['sha256']==expected['sha256']
                  and self.negative.attrs(path)==self.bound['xattrs'][str(path)],'phase-current-correct-custody')
            custody[path]=fact['signature9']
        for path,expected in self.bound['file_facts'].items():
            if path in (self.bound['source'],self.bound['counterpart']):continue
            p=Path(path);fact=km._fact(p,1)
            check(fact['signature9']==expected['signature9'] and fact['sha256']==expected['sha256']
                  and self.negative.attrs(p)==self.bound['xattrs'][path],'phase-retained-custody')
            custody[p]=fact['signature9']
        projection=self.bound['complete_catalog_absence']
        z=os.lstat(projection['database']['path'])
        check([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==projection['database']['signature9'],
              'terminal-reviewed-complete-catalog')
        for path,expected in projection['passive_claim_files'].items():
            p=Path(path)
            try:actual=sig(p)
            except FileNotFoundError:actual=None
            check(actual==expected,'phase-catalog-claim')
        # The full native catalog and all claims remain byte/incarnation identical;
        # only the EXACT source/target hardlink transition is permitted by kernel.
        for p,s in self.native_control.items():check(sig(p)==s,'phase-native-control')
        self.reader.close_native_phase_passive(self)
        self._close_complete_claims_direct()
        check(sig(self.path)==self.fence_fact,'terminal-phase-fence')
        for p,s in self.native_control.items():check(sig(p)==s,'terminal-phase-native')
        for p,s in custody.items():check(sig(p)==s,'terminal-phase-custody')
        check(set(os.listdir(self.writer.root))==self.writer_names,'phase-writer-namespace')
        for p,expected in {**self.native_control,**custody,self.path:self.fence_fact,
                           self.writer.root:self.writer_root_fact}.items():
            z=os.lstat(p)
            check([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,
                   z.st_uid,z.st_gid,z.st_nlink]==expected,'terminal-direct-phase-control')
        for p,expected in self.nodes.items():
            z=os.lstat(p);check((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==expected,'terminal-direct-phase-ancestor')


    def _close_complete_claims_direct(self):
        projection=self.bound['complete_catalog_absence']
        z=os.lstat(projection['database']['path'])
        check([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==projection['database']['signature9'],
              'terminal-reviewed-complete-catalog')
        for path,expected in projection['passive_claim_files'].items():
            try:z=os.lstat(path)
            except FileNotFoundError:actual=None
            else:actual=[z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
            check(actual==expected,'terminal-complete-claim')
        for group in ('passive_claim_ancestors','passive_scope_ancestors'):
            for path,expected in projection[group].items():
                try:z=os.lstat(path)
                except FileNotFoundError:actual=None
                else:actual=[z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
                check(actual==expected,'terminal-complete-claim-ancestor')

    def syscall_guard(self,k,old,known,fds):
        """No semantic callback after this complete direct syscall seal."""
        km=kernel()
        # Fresh kernel proof validates namespaces against its immutable original
        # projection before the last reader semantic callback. Never adopt a new
        # directory/receipt baseline after that callback.
        k._proof(os.path.lexists(k.source),os.path.lexists(k.target))
        directories={p:sig(p) for p in (k.source.parent,k.target.parent,k.journal)}
        namespaces={p:km._namespace(p) for p in directories}
        for p,expected in directories.items():check(sig(p)==expected,'syscall-capture-directory')
        reader_files,reader_nodes=self.reader.native_syscall_controls(self)
        check(type(reader_files) is dict and type(reader_nodes) is dict,'typed-reader-syscall-vector')
        files={**self.native_control,self.path:self.fence_fact,self.writer.root:self.writer_root_fact,
               Path(old):known['signature9']}
        for path,f in self.bound['file_facts'].items():
            if path!=self.bound['source']:files[Path(path)]=f['signature9']
        for path,expected in reader_files.items():
            p=Path(path);check(p not in files or files[p]==expected,'conflicting-phase-reader-vector')
            files[p]=expected
        nodes=dict(self.nodes)
        for path,expected in reader_nodes.items():
            p=Path(path)
            check(p not in nodes or tuple(nodes[p])==tuple(expected),'conflicting-phase-reader-ancestor')
            nodes[p]=expected
        for p,namespace in namespaces.items():
            check(set(os.listdir(p))==set(namespace),'syscall-namespace')
            for name,expected in namespace.items():files[p/name]=expected
        files.update(directories)
        self._close_complete_claims_direct()
        for fd,parent in fds:
            z=os.fstat(fd)
            check((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==tuple(k.parents[parent]),'syscall-parent-FD')
        for p,expected in files.items():
            z=os.lstat(p)
            check([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,
                   z.st_uid,z.st_gid,z.st_nlink]==list(expected),'syscall-phase-file')
        for p,expected in nodes.items():
            z=os.lstat(p)
            check((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==tuple(expected),'syscall-phase-ancestor')


def begin_existing(preparation,reader_phase,journal,nonce):
    """Owning prospective factory. Missing installed reader phase holds pre-SQL."""
    return NativePhaseFence(_KEY,preparation,reader_phase,journal,nonce,sdk())

class SplitTransition:
    """Split exact kernel phases. Factory determines native vs fixture scope."""
    def __init__(self,key,k):
        check(key is _KEY,'typed-split-transition');self.k=k;self.thread=threading.get_ident()
        self.k.prepare();self.phase='prepared'
    def stage(self):
        check(self.phase=='prepared' and threading.get_ident()==self.thread,'stage-once')
        self.k._proof(True,False);self.k._append('link-intent',pending=True)
        current=self.k._proof(True,False)[self.k.source]
        self.k._link(self.k.source,self.k.target,current)
        pair=self.k._proof(True,True,transition=True)
        self.k._append('linked',pair=pair[self.k.source],pending=True)
        self.k._proof(True,True);self.phase='linked'
        return dict(staged=True,source_retained=True,reader_sql_applied=False,native_grant=False)
    def retire(self,reader_reservation):
        check(self.phase=='linked','linked-phase-required')
        # This exact method must exist only on the installed typed reader phase;
        # no arbitrary callback or boolean can authorize source removal.
        check(type(self.k.scope) is NativePhaseFence,'owning-native-phase-required')
        check(reader_reservation is self.k.scope.reader,'exact-owning-reader-phase')
        reader_reservation.revalidate_committed(self.k.scope)
        pair=self.k._proof(True,True);self.k._append('unlink-intent',pair=pair[self.k.source],pending=True)
        pair=self.k._proof(True,True)
        reader_reservation.close_native_phase_passive(self.k.scope)
        self.k._unlink(self.k.source,pair[self.k.source])
        retained=self.k._proof(False,True,transition=True)[self.k.target]
        self.k._append('retained',retained=retained,pending=True);self.k._proof(False,True)
        self.phase='retained';return dict(filesystem_retained=True,publication_acceptance=False,final_ack_required=True)
    def abandon_staging(self):
        check(self.phase=='linked','linked-rollback-only')
        pair=self.k._proof(True,True);self.k._append('stage-rollback-intent',pair=pair[self.k.source],pending=True)
        pair=self.k._proof(True,True);self.k._unlink(self.k.target,pair[self.k.target])
        restored=self.k._proof(True,False,transition=True)[self.k.source]
        self.k._append('stage-rolled-back',restored=restored,pending=True);self.k._proof(True,False)
        self.phase='stage-rolled-back';return dict(staging_rollback_verified=True,native_grant=False)


def stage_existing(fence,target):
    check(type(fence) is NativePhaseFence,'owning-native-phase-required');fence.check()
    target=Path(target);check(not os.path.lexists(target),'foreign-target')
    parent=canonical(target.parent);s=sig(parent)
    check(stat.S_ISDIR(s[5]) and s[6]==os.geteuid() and stat.S_IMODE(s[5])==0o700,
          'private-quarantine-parent')
    check(not any(target.is_relative_to(Path(r)) for r in fence.controller.roots),'target-outside-libraries')
    km=kernel()
    class PhaseKernel(km._Kernel):
        def _link(self,old,new,known):
            self.scope.check()
            a=os.open(old.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            b=os.open(new.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:
                check(not os.path.lexists(new),'foreign-link-target')
                self.scope.syscall_guard(self,old,known,[(a,old.parent),(b,new.parent)])
                os.link(old.name,new.name,src_dir_fd=a,dst_dir_fd=b,follow_symlinks=False)
            finally:os.close(a);os.close(b)
            km._sync(old);km._sync(old.parent);km._sync(new.parent)
        def _unlink(self,path,known):
            self.scope.check()
            fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:
                self.scope.syscall_guard(self,path,known,[(fd,path.parent)])
                os.unlink(path.name,dir_fd=fd)
            finally:os.close(fd)
            km._sync(path.parent)
    k=PhaseKernel(fence,fence.bound['source'],target,fence.journal)
    transition=SplitTransition(_KEY,k)
    expected=fence.bound['file_facts'][fence.bound['source']]
    check(k.trusted_original['signature9']==expected['signature9']
          and k.trusted_original['sha256']==expected['sha256']
          and fence.negative.attrs(k.source)==fence.bound['xattrs'][fence.bound['source']],
          'prepared-source-full9-payload-CAS')
    transition.stage()
    return NegativeCommitReservation(_KEY,fence,transition)


class NegativeCommitReservation:
    """Exact owning phase/reader pair, minted before SQL; never accepts JSON."""
    def __init__(self,key,fence,transition):
        check(key is _KEY and type(fence) is NativePhaseFence and
              type(transition) is SplitTransition and transition.k.scope is fence,'typed-negative-reservation')
        self.fence=fence;self.transition=transition;self.thread=threading.get_ident()
    def consume_native(self,preparation):
        check(threading.get_ident()==self.thread and preparation is self.fence.preparation
              and self.transition.k.scope is self.fence,'negative-reservation-binding')
        self.fence.check()
        result=self.transition.retire(self.fence.reader)
        # Fence intentionally remains durable. The outer owning coordinator must
        # verify all five transitions + exact reader state before terminal closure.
        return dict(result,negative_fence_retained=True,operation_verified=False)
    def rollback_staging(self):
        check(self.transition.phase=='linked','staged-before-retirement-required')
        self.fence.reader.revalidate_rollback_ready(self.fence)
        return self.transition.abandon_staging()

if __name__=='__main__':
    print(json.dumps({'executable':False,'installed':False,'sql_authority':False,
        'missing':'installed publication_reader_phase.StoppedReaderPhase and ordinary negative admission hooks'}))
