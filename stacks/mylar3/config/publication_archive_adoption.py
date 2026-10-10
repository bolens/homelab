"""Dedicated same-path repair purpose. Exceptional evidence never enters ordinary require."""
import copy
import ctypes
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import threading
import time
import weakref
from contextlib import closing
from mylar import publication_archive_owned as o
from mylar import publication_archive_reader as reader

_KEY=object(); _SEALS=weakref.WeakKeyDictionary()
PENDING='archive-repair-v1.pending'; TERMINAL='archive-repair-v1.terminal-pending'
OTHER_PENDING=('negative-retirement-v1.pending','negative-retirement-v1.terminal-pending','normalizer-v1.pending','tagger-v2.pending','release-v1.pending','tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending')

def installed():
    for p in (Path(__file__),Path(reader.__file__),Path(o.__file__)):
        o.check(p==Path('/app/mylar3/mylar')/p.name and p.resolve()==p,'installed-repair-adoption')

def direct(files,nodes,absent):reader.direct(files,nodes,absent)
def exchange(a,b,an,bn,af,bf,controls):
    """No pathname replacement or overwrite fallback; exact admitted parent FDs."""
    with o.directory_fd(a.parent,an) as x,o.directory_fd(b.parent,bn) as y:
        libc=ctypes.CDLL(None,use_errno=True);fn=getattr(libc,'renameat2',None)
        o.check(fn is not None,'exchange-platform')
        fn.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
        o.check(o.stat9(os.stat(a.name,dir_fd=x,follow_symlinks=False))==af and o.stat9(os.stat(b.name,dir_fd=y,follow_symlinks=False))==bf,'repair-exchange-leaf-CAS')
        aa,bb=os.fsencode(a.name),os.fsencode(b.name)
        files,nodes,absent,claims=controls
        for path,value in files.items():
            info=os.lstat(path)
            if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink]!=value:raise o.Held('repair-syscall-file')
        for path,value in nodes.items():
            info=os.lstat(path)
            if [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]!=value:raise o.Held('repair-syscall-node')
        for path in absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise o.Held('repair-syscall-absence')
        for path,value in claims.items():
            try:info=os.lstat(path)
            except FileNotFoundError:
                if value is not None:raise o.Held('repair-syscall-claim')
                continue
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode & 0o170000==0o040000 else info.st_nlink)!=value:raise o.Held('repair-syscall-claim')
        if fn(x,aa,y,bb,2)!=0:raise o.Held('exchange-errno-'+str(ctypes.get_errno()))
        os.fsync(x);os.fsync(y)

def _valid_fd(fd):
    try:os.fstat(fd);return True
    except OSError:return False

def snapshot(db,deadline):return reader.logical(db,deadline)
def transition(before,owner,size):
    after=copy.deepcopy(before);table=after['tables'][owner['table']]
    names=[r[1][1] for r in table['columns']];o.check(all(k in names for k in ('IssueID','ComicID','ComicSize')),'repair-catalog-columns')
    rows=[r for r in table['rows'] if r[names.index('IssueID')]==['text',owner['issueid']]]
    o.check(len(rows)==1 and rows[0][names.index('ComicID')]==['text',owner['parentcomicid']],'repair-catalog-owner')
    i=names.index('ComicSize');o.check(rows[0][i][0] in ('int','text'),'repair-catalog-size-type')
    rows[0][i]=reader.cell(str(size) if rows[0][i][0]=='text' else size)
    table['rows']=sorted(table['rows'],key=reader.encoded);return after

def connect_existing(path,expected):
    """Existing-only open plus actual Linux SQLite FD provenance before BEGIN.

    SQLite's own canonicalization is not a path-incarnation proof. A transient
    alias opening an identical foreign DB must be rejected before any SQL write.
    """
    before={}
    for name in os.listdir('/proc/self/fd'):
        try:before[name]=o.stat9(os.fstat(int(name)))
        except OSError:pass
    conn=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=0)
    try:
        opened=[];matching=False
        for name in os.listdir('/proc/self/fd'):
            try:s=os.fstat(int(name))
            except OSError:continue
            if stat.S_ISREG(s.st_mode):
                value=o.stat9(s);matching=matching or value==expected
                if before.get(name)!=value:opened.append(value)
        o.check(matching and all(v==expected for v in opened) and conn.execute('PRAGMA database_list').fetchall()==[(0,'main',str(path))] and o.signature(path)==expected,'repair-actual-SQLite-FD')
        return conn
    except BaseException:conn.close();raise

def _set_size(db,owner,before,after,deadline):
    o.check(snapshot(db,deadline)==before,'catalog-logical-before-CAS')
    table=before['tables'][owner['table']];names=[r[1][1] for r in table['columns']]
    row=next(r for r in after['tables'][owner['table']]['rows'] if r[names.index('IssueID')]==['text',owner['issueid']])
    new=row[names.index('ComicSize')];value=int(new[1]) if new[0]=='int' else new[1]
    o.check(db.execute('UPDATE '+reader.quoted(owner['table'])+' SET ComicSize=? WHERE IssueID=? AND ComicID=?',(value,owner['issueid'],owner['parentcomicid'])).rowcount==1,'catalog-update-one')
    o.check(snapshot(db,deadline)==after,'catalog-only-size-transition')

def _copy_derivative(prep,destination):
    f=prep._binding['derivative'];raw=o.read_checked(Path(f['path']),f['signature9'],512*1024**2+2,prep._deadline)
    o.write(destination,raw,o.stat5(os.lstat(destination.parent)))
    # Derivative retains original access attributes/xattrs; mtime is explicit new
    # revision time, so the reader's normal scanner can detect the replacement.
    attrs=copy.deepcopy(prep._binding['source_attributes']);attrs['mtime_ns']=time.time_ns()
    initial=o.signature(destination)
    with o.directory_fd(destination.parent,o.stat5(os.lstat(destination.parent))) as parent:
        fd=os.open(destination.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
        try:
            o.check(o.stat9(os.fstat(fd))==initial,'derivative-attribute-FD')
            os.fchmod(fd,stat.S_IMODE(attrs['mode']))
            o.check(os.fstat(fd).st_uid==attrs['uid'] and os.fstat(fd).st_gid==attrs['gid'],'derivative-ownership')
            for k,v in attrs['xattrs'].items():os.setxattr(fd,k,bytes.fromhex(v))
            os.utime(fd,ns=(os.fstat(fd).st_atime_ns,attrs['mtime_ns']));os.fsync(fd)
            final=o.stat9(os.fstat(fd));o.check(o.stat9(os.stat(destination.name,dir_fd=parent,follow_symlinks=False))==final,'derivative-attribute-path')
        finally:os.close(fd)
    result=o.fact(destination,512*1024**2+2,prep._deadline)
    o.check(result['sha256']==f['sha256'] and o.attributes(destination)==attrs,'derivative-copy')
    return result,attrs

class RepairAdoption:
    __slots__=('preparation','reader','root','source','stage','journal','_owner','_before','_after','_files','_nodes','_absent','_source_attrs','_stage_attrs','_census','_records','_claims','_phase','_names','_thread','_objects','_receipt','_dirs','_contents','_source_names','__weakref__')
    def __init__(self,key,prep,lease,root,before,after,files,nodes,absent,stage_attrs):
        o.check(key is _KEY,'repair-owning-factory');self.preparation=prep;self.reader=lease;self.root=root
        self.source=Path(prep._binding['source']['path']);self.stage=root/'swap.arc';self.journal=root/'journal'
        self._owner=copy.deepcopy(prep._binding['owner']);self._before=before;self._after=after;self._files=files;self._nodes=nodes;self._absent=absent
        self._source_attrs=copy.deepcopy(prep._binding['source_attributes']);self._stage_attrs=stage_attrs
        self._census=copy.deepcopy(prep._census);self._records=copy.deepcopy(prep._records);self._claims=copy.deepcopy(prep._claims)
        self._phase='prepared';self._names={'swap.arc','journal'};self._thread=threading.get_ident();self._objects=[id(prep),id(lease),id(prep._writer),id(prep._controller)];self._receipt=None;self._source_names=set(os.listdir(self.source.parent));self._dirs={p:o.signature(p) for p in (root,self.journal,self.source.parent)};self._contents={p:o.fact(p,max(v[2],1),prep._deadline)['sha256'] for p,v in files.items()};self._seal()
    def _core(self):return o.digest({'objects':self._objects,'phase':self._phase,'thread':self._thread,'paths':list(map(str,(self.root,self.source,self.stage,self.journal))),'files':{str(p):v for p,v in self._files.items()},'nodes':{str(p):v for p,v in self._nodes.items()},'absent':sorted(map(str,self._absent)),'before':self._before,'after':self._after,'owner':self._owner,'source_attrs':self._source_attrs,'stage_attrs':self._stage_attrs,'census':self._census,'records':self._records,'claims':{str(p):v for p,v in self._claims.items()},'names':sorted(self._names),'receipt':self._receipt,'dirs':{str(p):v for p,v in self._dirs.items()},'contents':{str(p):v for p,v in self._contents.items()},'source_names':sorted(self._source_names)})
    def _seal(self):_SEALS[self]=self._core()
    def _life(self):o.check(_SEALS.get(self)==self._core() and threading.get_ident()==self._thread and time.monotonic()<self.preparation._deadline and self._objects==[id(self.preparation),id(self.reader),id(self.preparation._writer),id(self.preparation._controller)],'repair-lifetime')
    def _record(self,name,value):
        raw=o.compact(value);p=self.journal/name;o.write(p,raw,self._nodes[self.journal]);f=o.fact(p,1024**2,self.preparation._deadline)
        o.check(f['sha256']==hashlib.sha256(raw).hexdigest(),'repair-intended-receipt');self._files[p]=f['signature9'];self._contents[p]=f['sha256'];o.check(set(os.listdir(self.journal))=={q.name for q in self._files if q.parent==self.journal},'repair-record-census');self._dirs[self.journal]=o.signature(self.journal);self._receipt={'path':str(p),'sha256':f['sha256'],'signature9':f['signature9']};self._seal()
        return f
    def _native(self):
        p=self.preparation;g=p._modules[2];w=p._writer
        o.check(getattr(w.local[1],'depth',0)>0 and w.local is p._local and g.writer_identity(w)==p._identity,'repair-existing-writer')
        current=g.registry_snapshot(p._controller.database,w.root/'publication-v1.json');g.cleanup_admission(p._controller.database)
        o.check(current==(self._census,self._records),'repair-full-census')
        for path,v in self._claims.items():
            expected=v
            if path==self.source and self._phase=='uncertain':continue
            if path==self.source:expected=(self._files[path][0],self._files[path][1],self._files[path][5],self._files[path][6],self._files[path][7],self._files[path][8])
            o.check(g._claim_identity(path)==expected,'repair-complete-claim')
    def close(self):
        self._life();self.reader.revalidate();self._native()
        for p,v in ((self.source,self._source_attrs if self._phase in ('prepared','reversed','rollback-complete') else self._stage_attrs),(self.stage,self._stage_attrs if self._phase in ('prepared','reversed','rollback-complete') else self._source_attrs)):
            o.check(o.attributes(p)==v,'repair-access-attributes')
        o.check(set(os.listdir(self.source.parent))==self._source_names,'repair-source-parent-census');o.check(set(os.listdir(self.root))==self._names,'repair-root-census')
        o.check(set(os.listdir(self.journal))=={p.name for p in self._files if p.parent==self.journal},'repair-journal-census')
        for p,s in self._files.items():
            f=o.fact(p,max(s[2],1),self.preparation._deadline);o.check(f['signature9']==s and f['sha256']==self._contents[p],'repair-readback')
        # All SDK/reader/hash callbacks precede complete raw closure.
        direct({**self._files,**self._dirs},self._nodes,self._absent)
        for path,v in self._claims.items():
            if path==self.source:v=(self._files[path][0],self._files[path][1],self._files[path][5],self._files[path][6],self._files[path][7],self._files[path][8])
            try:s=os.lstat(path)
            except FileNotFoundError:o.check(v is None,'repair-terminal-claim');continue
            o.check((s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if stat.S_ISDIR(s.st_mode) else s.st_nlink)==v,'repair-terminal-claim')
        direct({**self._files,**self._dirs},self._nodes,self._absent)
        for path,value in {**self._files,**self._dirs}.items():
            info=os.lstat(path)
            if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink]!=value:raise o.Held('repair-inline-file')
        for path,value in self._nodes.items():
            info=os.lstat(path)
            if [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]!=value:raise o.Held('repair-inline-node')
        for path in self._absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise o.Held('repair-inline-absence')
        for path,value in self._claims.items():
            if path==self.source:value=(self._files[path][0],self._files[path][1],self._files[path][5],self._files[path][6],self._files[path][7],self._files[path][8])
            try:info=os.lstat(path)
            except FileNotFoundError:
                if value is not None:raise o.Held('repair-inline-claim')
                continue
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode & 0o170000==0o040000 else info.st_nlink)!=value:raise o.Held('repair-inline-claim')
    def _change(self,reverse=False):
        self.close();o.check(self._phase==('installed' if reverse else 'prepared'),'repair-phase')
        before,after=(self._after,self._before) if reverse else (self._before,self._after);p=self.preparation
        if not reverse:
            p.revalidate() # No marker exists yet, ordinary ownership is unchanged.
            marker=p._writer.root/PENDING
            raw=o.compact({'version':1,'purpose':'same-path-owned-archive-repair','operation_id':p._binding['operation_id'],'owner':self._owner,'preparation':p._binding['token'],'reader':self.reader.binding})
            o.write(marker,raw,o.stat5(os.lstat(p._writer.root)));self._files[marker]=o.signature(marker);self._contents[marker]=hashlib.sha256(raw).hexdigest();self._absent.remove(marker);self._seal()
        intent='reverse-intent.json' if reverse else 'install-intent.json'
        self._record(intent,{'version':1,'phase':intent,'source':self._files[self.source],'stage':self._files[self.stage],'owner':self._owner,'reader_sha256':o.digest(self.reader.binding)})
        self.close();dbpath=p._controller.native_database
        o.check(not any(os.path.lexists(str(dbpath)+s) for s in ('-wal','-shm','-journal')),'repair-catalog-companion')
        conn=connect_existing(dbpath,self._files[dbpath])
        exchanged=False
        try:
            conn.execute('PRAGMA trusted_schema=OFF');o.check(conn.execute('PRAGMA journal_mode').fetchone()==('delete',),'repair-native-delete-mode');conn.execute('BEGIN IMMEDIATE')
            o.check(snapshot(conn,p._deadline)==before,'repair-full-catalog-CAS');self.close()
            # All callbacks are complete; exact FD/path/source/database CAS precedes exchange.
            direct(self._files,self._nodes,self._absent)
            syscall_claims=copy.deepcopy(self._claims);sf=self._files[self.source];syscall_claims[self.source]=(sf[0],sf[1],sf[5],sf[6],sf[7],sf[8])
            exchange(self.source,self.stage,self._nodes[self.source.parent],self._nodes[self.stage.parent],self._files[self.source],self._files[self.stage],(copy.deepcopy({**self._files,**self._dirs}),copy.deepcopy(self._nodes),set(self._absent),syscall_claims));exchanged=True
            # Bind the finite exchange immediately, before SQL/helper callbacks.
            exchanged_files=copy.deepcopy(self._files)
            for path,prior in ((self.source,self._files[self.stage]),(self.stage,self._files[self.source])):
                actual=o.stat9(os.lstat(path));o.check([actual[i] for i in (0,1,2,3,5,6,7,8)]==[prior[i] for i in (0,1,2,3,5,6,7,8)],'repair-precommit-known-inode');exchanged_files[path]=actual
            exchanged_dirs={path:o.stat9(os.lstat(path)) for path in self._dirs}
            _set_size(conn,self._owner,before,after,p._deadline)
            # The journal is owned by this sole existing SQLite connection. Never
            # ignore an arbitrary companion or an alias under the pending phase.
            journal=Path(str(dbpath)+'-journal');js=o.stat9(os.lstat(journal))
            o.check(stat.S_ISREG(js[5]) and js[6]==os.geteuid() and js[8]==1 and any(o.stat9(os.fstat(int(n)))==js for n in os.listdir('/proc/self/fd') if n.isdigit() and _valid_fd(int(n))),'repair-owned-SQL-journal')
            exchanged_files[journal]=js
            for path,value in {**exchanged_files,**exchanged_dirs}.items():
                info=os.lstat(path)
                if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink]!=value:raise o.Held('repair-precommit-file')
            for path,value in self._nodes.items():
                info=os.lstat(path)
                if [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]!=value:raise o.Held('repair-precommit-node')
            for path in self._absent-{journal}:
                try:os.lstat(path)
                except FileNotFoundError:continue
                raise o.Held('repair-precommit-companion')
            for path,value in self._claims.items():
                if path==self.source:
                    sf=exchanged_files[path];value=(sf[0],sf[1],sf[5],sf[6],sf[7],sf[8])
                try:info=os.lstat(path)
                except FileNotFoundError:
                    if value is not None:raise o.Held('repair-precommit-claim')
                    continue
                if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode & 0o170000==0o040000 else info.st_nlink)!=value:raise o.Held('repair-precommit-claim')
            conn.commit()
        except BaseException:
            if conn.in_transaction:conn.rollback()
            self._phase='uncertain';self._seal()
            # A lost response never authorizes automatic replay or destructive undo.
            raise o.Held('repair-transition-uncertain-retain-marker') from None
        finally:conn.close()
        try:
            o.check(exchanged,'repair-exchange')
            # Known finite transition: only source/stage inodes exchanged, native sole
            # catalog cell changed; no arbitrary caller-supplied expected dictionary.
            expected_source=self._files[self.stage];expected_stage=self._files[self.source]
            expected_source_sha=self._contents[self.stage];expected_stage_sha=self._contents[self.source]
            for path,expected in ((self.source,expected_source),(self.stage,expected_stage)):
                actual=o.signature(path);o.check([actual[i] for i in (0,1,2,3,5,6,7,8)]==[expected[i] for i in (0,1,2,3,5,6,7,8)],'repair-exchanged-inode-CAS')
            o.check(o.fact(self.source,max(expected_source[2],1),p._deadline)['sha256']==expected_source_sha and o.fact(self.stage,max(expected_stage[2],1),p._deadline)['sha256']==expected_stage_sha,'repair-exchanged-bytes')
            o.check([o.signature(dbpath)[i] for i in (0,1,5,6,7,8)]==[self._files[dbpath][i] for i in (0,1,5,6,7,8)],'repair-catalog-incarnation')
            self._files[self.source]=o.signature(self.source);self._files[self.stage]=o.signature(self.stage);self._files[dbpath]=o.signature(dbpath)
            self._contents[self.source]=expected_source_sha;self._contents[self.stage]=expected_stage_sha;self._contents[dbpath]=o.fact(dbpath,256*1024**2,p._deadline)['sha256']
            o.check(set(os.listdir(self.source.parent))==self._source_names and set(os.listdir(self.root))==self._names,'repair-finite-namespace-transition')
            self._dirs[self.root]=o.signature(self.root);self._dirs[self.source.parent]=o.signature(self.source.parent)
            self._phase='reversed' if reverse else 'installed';self._seal()
            with closing(sqlite3.connect(dbpath.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:o.check(snapshot(db,p._deadline)==after,'repair-post-catalog')
            self._record('reversed.json' if reverse else 'installed.json',{'version':1,'phase':self._phase,'operation_id':p._binding['operation_id'],'native_catalog_sha256':o.digest(after),'reader_all_tables':self.reader.binding['all_tables_sha256'],'publication_acceptance':False})
            self.close();return self.binding
        except BaseException:
            self._phase='uncertain';self._seal();raise o.Held('repair-post-transition-uncertain-retain-marker') from None
    def install(self):return self._change(False)
    def reverse(self):return self._change(True)
    def uncertain_status(self):
        """Fresh finite-state observation only; no replay, reseal or completion."""
        self._life();o.check(self._phase=='uncertain','repair-status-phase');directories={x:o.stat9(os.lstat(x)) for x in (self.root,self.journal,self.source.parent)};self.reader.revalidate();self._native()
        p=self.preparation;dbpath=p._controller.native_database
        observations={x:o.fact(x,512*1024**2+2,p._deadline) for x in (self.source,self.stage)}
        expected_original=p._binding['source'];expected_derivative=p._binding['derivative']
        hashes=(observations[self.source]['sha256'],observations[self.stage]['sha256'])
        old=(expected_original['sha256'],expected_derivative['sha256']);new=(old[1],old[0])
        o.check(hashes in (old,new),'repair-status-content')
        expected=(self._files[self.source],self._files[self.stage]) if hashes==old else (self._files[self.stage],self._files[self.source])
        for path,v in zip((self.source,self.stage),expected):o.check([observations[path]['signature9'][i] for i in (0,1,2,3,5,6,7,8)]==[v[i] for i in (0,1,2,3,5,6,7,8)],'repair-status-known-inodes')
        dbfact=o.fact(dbpath,256*1024**2,p._deadline);o.check([dbfact['signature9'][i] for i in (0,1,5,6,7,8)]==[self._files[dbpath][i] for i in (0,1,5,6,7,8)],'repair-status-native-incarnation')
        with closing(sqlite3.connect(dbpath.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:current=snapshot(db,p._deadline)
        o.check(current in (self._before,self._after),'repair-status-catalog')
        o.check(o.fact(dbpath,256*1024**2,p._deadline)==dbfact,'repair-status-catalog-CAS')
        result='held-before-transition' if hashes==old and current==self._before else ('held-after-swap-before-catalog' if hashes==new and current==self._before else 'held-after-swap-and-catalog' if hashes==new and current==self._after else 'held-contradictory-transition')
        files={x:v for x,v in self._files.items() if x not in (self.source,self.stage,dbpath)}
        files.update({x:v['signature9'] for x,v in observations.items()});files[dbpath]=dbfact['signature9']
        # This is an observation vector, not adoption of changed phase baselines.
        self.reader.close()
        o.check(set(os.listdir(self.root))==self._names and set(os.listdir(self.journal))=={x.name for x in self._files if x.parent==self.journal},'repair-status-census')
        for x,v in self._claims.items():
            if x==self.source:continue
            try:s=os.lstat(x)
            except FileNotFoundError:o.check(v is None,'repair-status-missing-claim');continue
            o.check((s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if stat.S_ISDIR(s.st_mode) else s.st_nlink)==v,'repair-status-claim')
        direct({**files,**directories},self._nodes,self._absent)
        return {'version':1,'outcome':result,'mutation_authority':False,'publication_acceptance':False,'automatic_replay':False}

    def complete(self):
        """Consume the exact installed phase; never accept a serialized receipt.

        Reader indexing remains separately observable. This accepts archive and
        exact existing reader references, not general current-library admission.
        """
        self.close();o.check(self._phase=='installed','repair-complete-phase');p=self.preparation;w=p._writer
        raw=o.read_checked(self.source,self._files[self.source],512*1024**2+2,p._deadline)
        inventory,metadata=p._modules[5].independent(raw,p._modules[2],p._deadline)
        witness=p._binding['exceptional_witness']
        o.check(inventory==witness['virtual_original_inventory'] and metadata==witness['root_metadata_sha256'],'repair-complete-payload-and-metadata')
        self.reader.revalidate();self.close()
        terminal=w.root/TERMINAL;pending=w.root/PENDING
        successor=o.compact({'version':1,'purpose':'archive-repair-terminal','operation_id':p._binding['operation_id'],'owner':self._owner,'source_sha256':self._contents[self.source],'reader_all_tables':self.reader.binding['all_tables_sha256']})
        o.write(terminal,successor,self._nodes[w.root]);self._files[terminal]=o.signature(terminal);self._contents[terminal]=hashlib.sha256(successor).hexdigest();self._absent.remove(terminal);self._seal()
        self._record('complete-intent.json',{'version':1,'phase':'archive-and-references-verified','source_sha256':self._contents[self.source],'reader_all_tables':self.reader.binding['all_tables_sha256'],'publication_acceptance':False})
        self.close()
        # A durable terminal successor exists before the first marker unlink.
        with o.directory_fd(w.root,self._nodes[w.root]) as fd:
            direct(self._files,self._nodes,self._absent)
            o.check(o.stat9(os.stat(PENDING,dir_fd=fd,follow_symlinks=False))==self._files[pending],'repair-pending-unlink-CAS')
            for path,value in {**self._files,**self._dirs}.items():
                info=os.lstat(path)
                if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink]!=value:raise o.Held('repair-inline-file')
            for path,value in self._nodes.items():
                info=os.lstat(path)
                if [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]!=value:raise o.Held('repair-inline-node')
            for path in self._absent:
                try:os.lstat(path)
                except FileNotFoundError:continue
                raise o.Held('repair-inline-absence')
            for path,value in self._claims.items():
                if path==self.source:value=(self._files[path][0],self._files[path][1],self._files[path][5],self._files[path][6],self._files[path][7],self._files[path][8])
                try:info=os.lstat(path)
                except FileNotFoundError:
                    if value is not None:raise o.Held('repair-inline-claim')
                    continue
                if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode & 0o170000==0o040000 else info.st_nlink)!=value:raise o.Held('repair-inline-claim')
            os.unlink(PENDING,dir_fd=fd);os.fsync(fd)
        del self._files[pending];del self._contents[pending];self._absent.add(pending);self._seal()
        self._record('complete.json',{'version':1,'phase':'complete','operation_id':p._binding['operation_id'],'source_sha256':self._contents[self.source],'reader_reference_preservation':True,'publication_acceptance':False})
        self.close()
        # The complete receipt is durable before clearing its successor. Any
        # unknown response restores only our absent successor, never foreign data.
        try:
            with o.directory_fd(w.root,self._nodes[w.root]) as fd:
                direct(self._files,self._nodes,self._absent)
                o.check(o.stat9(os.stat(TERMINAL,dir_fd=fd,follow_symlinks=False))==self._files[terminal],'repair-terminal-unlink-CAS')
                for path,value in {**self._files,**self._dirs}.items():
                    info=os.lstat(path)
                    if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink]!=value:raise o.Held('repair-inline-file')
                for path,value in self._nodes.items():
                    info=os.lstat(path)
                    if [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]!=value:raise o.Held('repair-inline-node')
                for path in self._absent:
                    try:os.lstat(path)
                    except FileNotFoundError:continue
                    raise o.Held('repair-inline-absence')
                for path,value in self._claims.items():
                    if path==self.source:value=(self._files[path][0],self._files[path][1],self._files[path][5],self._files[path][6],self._files[path][7],self._files[path][8])
                    try:info=os.lstat(path)
                    except FileNotFoundError:
                        if value is not None:raise o.Held('repair-inline-claim')
                        continue
                    if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode & 0o170000==0o040000 else info.st_nlink)!=value:raise o.Held('repair-inline-claim')
                os.unlink(TERMINAL,dir_fd=fd);os.fsync(fd)
            del self._files[terminal];del self._contents[terminal];self._absent.add(terminal);self._phase='complete';self._seal();self.close()
        except BaseException:
            if not os.path.lexists(terminal):o.write(terminal,successor,self._nodes[w.root])
            self._phase='uncertain';self._seal();raise o.Held('repair-terminal-unknown-retain-successor') from None
        try:return self.binding
        except BaseException:
            if not os.path.lexists(terminal):o.write(terminal,successor,self._nodes[w.root])
            self._phase='uncertain';self._seal();raise o.Held('repair-final-unknown-retain-successor') from None
    def complete_reversed(self):
        """Consume only the exact reversed phase; never accept a serialized receipt.

        Reader indexing remains separately observable. This accepts archive and
        exact existing reader references, not general current-library admission.
        """
        self.close();o.check(self._phase=='reversed','repair-rollback-complete-phase');p=self.preparation;w=p._writer
        raw=o.read_checked(self.source,self._files[self.source],512*1024**2+2,p._deadline)
        o.check(hashlib.sha256(raw).hexdigest()==p._binding['source']['sha256'],'repair-rollback-original-bytes')
        plan=p._modules[4].classify(raw,p._modules[2],p._deadline)
        o.check(plan['status']=='repair-candidate','repair-rollback-supported-original')
        witness=o.witness(raw,p._binding['source'],plan,p._modules,p._deadline)
        o.check(witness==p._binding['exceptional_witness'],'repair-rollback-original-witness')
        with o.checked_stream(p._controller.native_database,self._files[p._controller.native_database]) as fd,closing(sqlite3.connect('file:/proc/self/fd/'+str(fd.fileno())+'?mode=ro&immutable=1',uri=True)) as db:
            o.check(snapshot(db,p._deadline)==self._before,'repair-rollback-full-native-preimage')
        self.reader.revalidate();self.close()
        terminal=w.root/TERMINAL;pending=w.root/PENDING
        successor=o.compact({'version':1,'purpose':'archive-repair-rollback-terminal','operation_id':p._binding['operation_id'],'owner':self._owner,'source_sha256':self._contents[self.source],'reader_all_tables':self.reader.binding['all_tables_sha256']})
        try:
            # A write may be durable before its caller receives the result. Keep
            # every marker on an unknown initial successor/intent response.
            o.write(terminal,successor,self._nodes[w.root]);self._files[terminal]=o.signature(terminal);self._contents[terminal]=hashlib.sha256(successor).hexdigest();self._absent.remove(terminal);self._seal()
            self._record('rollback-complete-intent.json',{'version':1,'phase':'original-native-and-reader-preimage-verified','source_sha256':self._contents[self.source],'reader_all_tables':self.reader.binding['all_tables_sha256'],'publication_acceptance':False})
            self.close()
        except BaseException:
            self._phase='uncertain';self._seal();raise o.Held('repair-rollback-successor-unknown-retain-markers') from None
        try:
            # A durable terminal successor exists before the first marker unlink.
            with o.directory_fd(w.root,self._nodes[w.root]) as fd:
                direct(self._files,self._nodes,self._absent)
                o.check(o.stat9(os.stat(PENDING,dir_fd=fd,follow_symlinks=False))==self._files[pending],'repair-pending-unlink-CAS')
                for path,value in {**self._files,**self._dirs}.items():
                    info=os.lstat(path)
                    if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink]!=value:raise o.Held('repair-inline-file')
                for path,value in self._nodes.items():
                    info=os.lstat(path)
                    if [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]!=value:raise o.Held('repair-inline-node')
                for path in self._absent:
                    try:os.lstat(path)
                    except FileNotFoundError:continue
                    raise o.Held('repair-inline-absence')
                for path,value in self._claims.items():
                    if path==self.source:value=(self._files[path][0],self._files[path][1],self._files[path][5],self._files[path][6],self._files[path][7],self._files[path][8])
                    try:info=os.lstat(path)
                    except FileNotFoundError:
                        if value is not None:raise o.Held('repair-inline-claim')
                        continue
                    if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode & 0o170000==0o040000 else info.st_nlink)!=value:raise o.Held('repair-inline-claim')
                os.unlink(PENDING,dir_fd=fd);os.fsync(fd)
            del self._files[pending];del self._contents[pending];self._absent.add(pending);self._seal()
            self._record('rollback-complete.json',{'version':1,'phase':'rollback-complete','operation_id':p._binding['operation_id'],'source_sha256':self._contents[self.source],'reader_reference_preservation':True,'publication_acceptance':False})
            self.close()
        except BaseException:
            self._phase='uncertain';self._seal();raise o.Held('repair-rollback-pending-unknown-retain-successor') from None
        # The complete receipt is durable before clearing its successor. Any
        # unknown response restores only our absent successor, never foreign data.
        try:
            with o.directory_fd(w.root,self._nodes[w.root]) as fd:
                direct(self._files,self._nodes,self._absent)
                o.check(o.stat9(os.stat(TERMINAL,dir_fd=fd,follow_symlinks=False))==self._files[terminal],'repair-terminal-unlink-CAS')
                for path,value in {**self._files,**self._dirs}.items():
                    info=os.lstat(path)
                    if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink]!=value:raise o.Held('repair-inline-file')
                for path,value in self._nodes.items():
                    info=os.lstat(path)
                    if [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]!=value:raise o.Held('repair-inline-node')
                for path in self._absent:
                    try:os.lstat(path)
                    except FileNotFoundError:continue
                    raise o.Held('repair-inline-absence')
                for path,value in self._claims.items():
                    if path==self.source:value=(self._files[path][0],self._files[path][1],self._files[path][5],self._files[path][6],self._files[path][7],self._files[path][8])
                    try:info=os.lstat(path)
                    except FileNotFoundError:
                        if value is not None:raise o.Held('repair-inline-claim')
                        continue
                    if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode & 0o170000==0o040000 else info.st_nlink)!=value:raise o.Held('repair-inline-claim')
                os.unlink(TERMINAL,dir_fd=fd);os.fsync(fd)
            del self._files[terminal];del self._contents[terminal];self._absent.add(terminal);self._phase='rollback-complete';self._seal();self.close()
        except BaseException:
            if not os.path.lexists(terminal):o.write(terminal,successor,self._nodes[w.root])
            self._phase='uncertain';self._seal();raise o.Held('repair-terminal-unknown-retain-successor') from None
        try:return self.binding
        except BaseException:
            if not os.path.lexists(terminal):o.write(terminal,successor,self._nodes[w.root])
            self._phase='uncertain';self._seal();raise o.Held('repair-final-unknown-retain-successor') from None
    @property
    def binding(self):
        value={'version':1,'kind':'same-path-owned-archive-repair','phase':self._phase,'operation_id':self.preparation._binding['operation_id'],'owner':copy.deepcopy(self._owner),'source':str(self.source),'reader_reference_preservation':True,'reader_index_acceptance':False,'native_archive_installed':self._phase in ('installed','complete'),'repair_accepted':self._phase=='complete','receipt':copy.deepcopy(self._receipt),'publication_acceptance':False,'ordinary_import_grant':False}
        if self._phase=='rollback-complete':value['rollback_verified']=True
        self.close();return value

def prepare_existing(preparation,lease,retention_root):
    installed();o.check(type(preparation) is o.RepairPreparation and type(lease) is reader.RepairReaderLease,'exact-repair-types')
    prep=preparation;implementation_paths=[Path(__file__),Path(reader.__file__),Path(__file__).with_name('publication_archive_rollback.py')];implementation_nodes=o.ancestors(implementation_paths);implementation_files={p:o.fact(p,4*1024**2,prep._deadline) for p in implementation_paths};prep.revalidate();lease.revalidate()
    source=Path(prep._binding['source']['path']);o.check(source.suffix.lower()=='.cbz','repair-supported-CBZ-same-path');o.check(lease.source==source,'reader-native-same-path');o.check(set(lease.binding['page_names'])==set(prep._binding['exceptional_witness']['virtual_original_inventory']['pages']),'reader-source-page-bijection')
    root=o.canonical(retention_root);nodes=copy.deepcopy(prep._nodes);o.merge_nodes(nodes,implementation_nodes);o.merge_nodes(nodes,o.ancestors([root,source]));nodes[root]=o.stat5(os.lstat(root));o.check(stat.S_IMODE(os.lstat(root).st_mode)==0o700 and os.lstat(root).st_uid==os.geteuid(),'repair-private-retention')
    o.check(all(not root.is_relative_to(r) and not r.is_relative_to(root) for r in map(Path,prep._controller.roots)) and os.lstat(root).st_dev==os.lstat(source).st_dev,'repair-retention-same-FS-outside-library')
    op=root/('adopt-'+prep._binding['operation_id']);o.check(not os.path.lexists(op),'repair-exclusive-operation')
    for name in (PENDING,TERMINAL,*OTHER_PENDING):o.check(not os.path.lexists(prep._writer.root/name),'repair-pending-purpose')
    with closing(sqlite3.connect(prep._controller.native_database.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:before=snapshot(db,prep._deadline)
    after=transition(before,prep._binding['owner'],prep._binding['derivative']['signature9'][2]);prep.revalidate();lease.close()
    with o.directory_fd(root,nodes[root]) as fd:os.mkdir(op.name,0o700,dir_fd=fd);os.fsync(fd)
    with o.directory_fd(op) as fd:os.mkdir('journal',0o700,dir_fd=fd);os.fsync(fd)
    o.merge_nodes(nodes,o.ancestors([op,op/'journal']));nodes[op]=o.stat5(os.lstat(op));nodes[op/'journal']=o.stat5(os.lstat(op/'journal'))
    stage,attrs=_copy_derivative(prep,op/'swap.arc');files={p:f['signature9'] for p,f in {**prep._files,**implementation_files}.items()};files[op/'swap.arc']=stage['signature9']
    rf,rn,ra=lease.vectors();o.merge_nodes(nodes,rn);files.update(rf)
    absent=set(ra)|{prep._writer.root/n for n in (PENDING,TERMINAL,*OTHER_PENDING)}
    for db in (prep._controller.native_database,prep._controller.database):absent.update(Path(str(db)+s) for s in ('-wal','-shm','-journal'))
    o.check(all(o.stat5(os.lstat(p))==v for p,v in nodes.items()),'repair-admission-ancestor')
    cap=RepairAdoption(_KEY,prep,lease,op,before,after,files,nodes,absent,attrs);cap.close()
    # An immutable native preimage is evidence for a later independent reader/
    # catalog verifier, never a serialized capability. Capture before mutation.
    original_db=prep._controller.native_database
    original_fact=o.fact(original_db,256*1024**2,prep._deadline)
    preimage=op/'native-before.sqlite'
    o.write(preimage,o.read_checked(original_db,original_fact['signature9'],256*1024**2,prep._deadline),nodes[op])
    pf=o.fact(preimage,256*1024**2,prep._deadline)
    o.check(pf['sha256']==original_fact['sha256'] and o.fact(original_db,256*1024**2,prep._deadline)==original_fact,'repair-native-preimage')
    with closing(sqlite3.connect(preimage.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        o.check(snapshot(db,prep._deadline)==before,'repair-native-preimage-logical')
    cap._files[preimage]=pf['signature9'];cap._contents[preimage]=pf['sha256'];cap._names.add(preimage.name);cap._dirs[op]=o.signature(op);cap._seal()
    cap._record('baseline.json',{'version':1,'kind':'repair-local-preimage-observation','preparation':copy.deepcopy(prep._binding),'reader':lease.binding,'native_before':pf,'native_after_sha256':o.digest(after),'adoption_root':str(op),'swap_before':stage,'swap_attributes':attrs,'mutation_authority':False,'publication_acceptance':False})
    cap.close();return cap

# Opaque live factual exports. A saved dictionary cannot enter this registry.
_TERMINAL_EXPORTS=weakref.WeakKeyDictionary()
_TERMINAL_RECORDS=weakref.WeakKeyDictionary()

class TerminalOriginals:
    __slots__=('__weakref__',)
    def __init__(self,key):
        o.check(key is _KEY,'repair-terminal-owning-export')

def _terminal_physical(cap):
    p=cap.preparation;c=p._controller;w=p._writer
    return (id(c),id(w),id(p),id(cap.reader),id(w.local),str(c.root),
            tuple(map(str,c.roots)),str(c.tool_root),str(w.root),
            str(c.database),str(c.native_database),tuple(p._identity))

def _terminal_close(cap,record):
    o.check(type(cap) is RepairAdoption and record['cap']() is cap
            and _SEALS.get(cap)==record['cap_seal']
            and threading.get_ident()==record['thread'] and os.getpid()==record['pid'],
            'repair-terminal-live-original')
    cap.close()
    modules=o.sdk();o.writer_pair(cap.preparation._controller,cap.preparation._writer,modules)
    o.check(_terminal_physical(cap)==record['physical']
            and tuple(modules[2].writer_identity(cap.preparation._writer))==record['physical'][-1]
            and cap.preparation._writer.local is cap.preparation._local
            and getattr(cap.preparation._writer.local[1],'depth',0)>0,
            'repair-terminal-original-writer-controller')
    for path,value in record['hashes']:
        f=o.fact(Path(path),max(dict(record['files'])[path][2],1),record['deadline'])
        o.check(tuple(f['signature9'])==dict(record['files'])[path]
                and f['sha256']==value,'repair-terminal-original-readback')
    o.check(_SEALS.get(cap)==record['cap_seal'] and cap._core()==record['cap_seal'],
            'repair-terminal-cap-seal')

def _terminal_core_projection(cap):
    logical = {'objects':cap._objects,'phase':cap._phase,'thread':cap._thread,'paths':list(map(str,(cap.root,cap.source,cap.stage,cap.journal))),'files':{str(p):v for p,v in cap._files.items()},'nodes':{str(p):v for p,v in cap._nodes.items()},'absent':sorted(map(str,cap._absent)),'before':cap._before,'after':cap._after,'owner':cap._owner,'source_attrs':cap._source_attrs,'stage_attrs':cap._stage_attrs,'census':cap._census,'records':cap._records,'claims':{str(p):v for p,v in cap._claims.items()},'names':sorted(cap._names),'receipt':cap._receipt,'dirs':{str(p):v for p,v in cap._dirs.items()},'contents':{str(p):v for p,v in cap._contents.items()},'source_names':sorted(cap._source_names)}
    pending=[logical];projection=[]
    while pending:
        value=pending.pop();kind=type(value)
        if kind is dict:
            keys=tuple(sorted(value));projection.append(('dict',keys))
            for name in reversed(keys):pending.append(value[name])
        elif kind in (list,tuple):
            projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
        elif kind in (str,int,bool,float,type(None)):projection.append((kind.__name__,value))
        else:raise o.Held('repair-terminal-core-projection-type')
    return tuple(projection)

def terminal_original_vectors(handle,cap):
    """Return copied facts only for the registered live owning export/cap pair."""
    o.check(type(handle) is TerminalOriginals and handle in _TERMINAL_RECORDS,
            'repair-terminal-exact-export')
    record=_TERMINAL_RECORDS[handle];original_record=tuple(record.items())
    # Build all return bytes/containers before the last semantic helper.
    answer={k:record[k] for k in ('files','nodes','absent','claims','namespaces','hashes',
        'physical','phase','owner','operation_id','baseline','metadata','stage','receipt','pid','thread')}
    _terminal_close(cap,record)
    # Complete primitive originals after every SDK/hash/cap helper.
    if _TERMINAL_RECORDS.get(handle) is not record or _TERMINAL_EXPORTS.get(cap) is not handle or tuple(record.items())!=original_record:
        raise o.Held('repair-terminal-export-original-registry')
    p=cap.preparation;c=p._controller;w=p._writer
    actual=(id(c),id(w),id(p),id(cap.reader),id(w.local),str(c.root),tuple(map(str,c.roots)),str(c.tool_root),str(w.root),str(c.database),str(c.native_database),tuple(p._identity))
    if actual!=record['physical'] or tuple(w.root_identity)+tuple(w.lock_identity)!=record['physical'][-1] or w.local is not p._local or not getattr(w.local[1],'depth',0) or any(getattr(w.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')) or os.getpid()!=record['pid'] or threading.get_ident()!=record['thread'] or cap._phase!=record['phase'] or tuple(sorted(cap._owner.items()))!=record['owner'] or tuple(cap._objects)!=(record['physical'][2],record['physical'][3],record['physical'][1],record['physical'][0]) or cap._thread!=record['thread'] or _SEALS.get(cap)!=record['cap_seal']:
        raise o.Held('repair-terminal-export-original-owner')
    if time.monotonic()>=record['deadline']:raise o.Held('repair-terminal-export-deadline')
    for path,names in record['namespaces']:
        if frozenset(os.listdir(path))!=frozenset(names):raise o.Held('repair-terminal-export-census')
    for path,value in record['nodes']:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise o.Held('repair-terminal-export-node')
    for path,value in record['files']:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise o.Held('repair-terminal-export-file')
    for path in record['absent']:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('repair-terminal-export-absence')
    for path,value in record['claims']:
        try:z=os.lstat(path)
        except FileNotFoundError:
            if value is not None:raise o.Held('repair-terminal-export-missing-claim')
            continue
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=value:raise o.Held('repair-terminal-export-claim')
    if _TERMINAL_RECORDS.get(handle) is not record or _TERMINAL_EXPORTS.get(cap) is not handle or tuple(record.items())!=original_record:
        raise o.Held('repair-terminal-export-original-registry')
    p=cap.preparation;c=p._controller;w=p._writer
    actual=(id(c),id(w),id(p),id(cap.reader),id(w.local),str(c.root),tuple(map(str,c.roots)),str(c.tool_root),str(w.root),str(c.database),str(c.native_database),tuple(p._identity))
    if actual!=record['physical'] or tuple(w.root_identity)+tuple(w.lock_identity)!=record['physical'][-1] or w.local is not p._local or not getattr(w.local[1],'depth',0) or any(getattr(w.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')) or os.getpid()!=record['pid'] or threading.get_ident()!=record['thread'] or cap._phase!=record['phase'] or tuple(sorted(cap._owner.items()))!=record['owner'] or tuple(cap._objects)!=(record['physical'][2],record['physical'][3],record['physical'][1],record['physical'][0]) or cap._thread!=record['thread'] or _SEALS.get(cap)!=record['cap_seal']:
        raise o.Held('repair-terminal-export-original-owner')
    if time.monotonic()>=record['deadline']:raise o.Held('repair-terminal-export-deadline')
    logical = {'objects':cap._objects,'phase':cap._phase,'thread':cap._thread,'paths':list(map(str,(cap.root,cap.source,cap.stage,cap.journal))),'files':{str(p):v for p,v in cap._files.items()},'nodes':{str(p):v for p,v in cap._nodes.items()},'absent':sorted(map(str,cap._absent)),'before':cap._before,'after':cap._after,'owner':cap._owner,'source_attrs':cap._source_attrs,'stage_attrs':cap._stage_attrs,'census':cap._census,'records':cap._records,'claims':{str(p):v for p,v in cap._claims.items()},'names':sorted(cap._names),'receipt':cap._receipt,'dirs':{str(p):v for p,v in cap._dirs.items()},'contents':{str(p):v for p,v in cap._contents.items()},'source_names':sorted(cap._source_names)}
    pending=[logical];projection=[]
    while pending:
        value=pending.pop();kind=type(value)
        if kind is dict:
            keys=tuple(sorted(value));projection.append(('dict',keys))
            for name in reversed(keys):pending.append(value[name])
        elif kind in (list,tuple):
            projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
        elif kind in (str,int,bool,float,type(None)):projection.append((kind.__name__,value))
        else:raise o.Held('repair-terminal-core-projection-type')
    if tuple(projection)!=record['core_projection']:raise o.Held('repair-terminal-export-original-complete-core')
    return answer

def terminal_originals(cap):
    """Opaque same-process completed owning cap; no reconstruction from receipts."""
    if type(cap) is not RepairAdoption or _SEALS.get(cap) is None:
        raise o.Held('repair-terminal-exact-live-adoption')
    if cap in _TERMINAL_EXPORTS:
        handle=_TERMINAL_EXPORTS[cap];terminal_original_vectors(handle,cap);return handle
    # Retain every original before the first replaceable installed/close/SDK read.
    cap_seal=_SEALS[cap];core_projection=_terminal_core_projection(cap);phase=cap._phase;prep=cap.preparation
    owner=tuple(sorted(cap._owner.items()));operation=prep._binding['operation_id'];deadline=prep._deadline;original_thread=threading.get_ident();original_pid=os.getpid()
    files={str(p):tuple(v) for p,v in cap._files.items()}
    for p,v in cap._dirs.items():
        p=str(p);v=tuple(v)
        if p in files and files[p]!=v:raise o.Held('repair-terminal-original-file-conflict')
        files[p]=v
    stage=str(prep._operation);directory=tuple(prep._directory)
    if stage in files and files[stage]!=directory:raise o.Held('repair-terminal-original-stage-conflict')
    files[stage]=directory
    nodes={str(p):tuple(v) for p,v in cap._nodes.items()}
    for p,v in prep._nodes.items():
        p=str(p);v=tuple(v)
        if p in nodes and nodes[p]!=v:raise o.Held('repair-terminal-original-node-conflict')
        nodes[p]=v
    hashes=tuple((str(p),v) for p,v in cap._contents.items())
    absent=tuple(sorted(map(str,cap._absent)))
    claims={str(p):None if v is None else tuple(v) for p,v in cap._claims.items()}
    s=files[str(cap.source)];claims[str(cap.source)]=(s[0],s[1],s[5],s[6],s[7],s[8])
    namespaces=((str(cap.root),tuple(sorted(cap._names))),
                (str(cap.journal),tuple(sorted(p.name for p in cap._files if p.parent==cap.journal))),
                (str(cap.source.parent),tuple(sorted(cap._source_names))),
                (stage,('intent.json','original.arc','preparation.json','prepared.cbz','restored-original.arc')))
    physical=_terminal_physical(cap)
    metadata=str(prep._operation/'preparation.json');baseline=str(cap.journal/'baseline.json')
    receipt=cap._receipt
    if phase not in ('complete','rollback-complete'):raise o.Held('repair-terminal-incomplete-cap')
    expected=str(cap.journal/('complete.json' if phase=='complete' else 'rollback-complete.json'))
    contents=dict(hashes)
    if type(receipt) is not dict or set(receipt)!={'path','sha256','signature9'} or receipt['path']!=expected or tuple(receipt['signature9'])!=files.get(expected) or receipt['sha256']!=contents.get(expected):raise o.Held('repair-terminal-owning-receipt')
    # Cap sources already have sealed original rows; capture all additional
    # source ancestors together before source-read/installed callbacks.
    for path in (Path(__file__),Path(reader.__file__),Path(o.__file__)):
        value=(lambda z:(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink))(os.lstat(path))
        if files.get(str(path))!=value:raise o.Held('repair-terminal-original-source')
        for parent in path.parents:
            z=os.lstat(parent);value=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid);name=str(parent)
            if name in nodes and nodes[name]!=value:raise o.Held('repair-terminal-original-source-node')
            nodes[name]=value
    installed();cap.close()
    record=dict(cap=weakref.ref(cap),cap_seal=cap_seal,core_projection=core_projection,thread=original_thread,pid=original_pid,
        deadline=deadline,files=tuple(files.items()),nodes=tuple(nodes.items()),absent=absent,
        claims=tuple(claims.items()),namespaces=namespaces,hashes=hashes,physical=physical,phase=phase,
        owner=owner,operation_id=operation,
        baseline=(baseline,files[baseline],contents[baseline]),metadata=(metadata,files[metadata],contents[metadata]),
        stage=(stage,directory),receipt=(expected,files[expected],contents[expected]))
    handle=TerminalOriginals(_KEY);_TERMINAL_RECORDS[handle]=record;_TERMINAL_EXPORTS[cap]=handle
    try:terminal_original_vectors(handle,cap)
    except BaseException:
        _TERMINAL_RECORDS.pop(handle,None);_TERMINAL_EXPORTS.pop(cap,None);raise
    return handle
