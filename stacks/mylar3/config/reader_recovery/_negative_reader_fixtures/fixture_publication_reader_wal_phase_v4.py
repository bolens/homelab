"""Prospective owning WAL opening/read-mark/connection-close phases.

No CLI, caller boolean, or serialized proof grants this phase. Installation and
composition into SQLStart/ReaderSQLCommit remain required. Opening admits only
a stopped main-only WAL-header pair; existing WAL recovery is unsupported.
"""
import copy
import hashlib
import importlib
import json
import os
import sqlite3
from pathlib import Path
import stat
import struct
import threading
import weakref
_KEY=object()
_SEALS=weakref.WeakKeyDictionary()
class Held(ValueError):pass
def check(v,r):
    if not v:raise Held(r)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def nine(z):return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def five(z):return [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
def installed(name):
    try:m=importlib.import_module('mylar.'+name)
    except ModuleNotFoundError:raise Held('owning-WAL-component-not-installed') from None
    p=Path(m.__file__)
    check(p.parent==Path('/app/mylar3/mylar') and p.resolve()==p,'installed-WAL-component')
    return m

def read_shm(db,pair):
    p=Path(str(db)+'-shm');expected=pair['-shm'];fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        check(nine(os.fstat(fd))==expected['signature9'],'WAL-SHM-before-read')
        check(expected['signature9'][2]<=64*1024**2,'WAL-SHM-bound')
        raw=b''
        while len(raw)<expected['signature9'][2]:
            block=os.read(fd,min(1024**2,expected['signature9'][2]-len(raw)))
            check(bool(block),'WAL-SHM-short-read');raw+=block
        check(hashlib.sha256(raw).hexdigest()==expected['sha256'] and nine(os.fstat(fd))==expected['signature9']
              and nine(os.lstat(p))==expected['signature9'],'WAL-SHM-after-read')
        return raw
    finally:os.close(fd)

def header(raw):
    # Native-endian wal-index format 3007000: two identical 48-byte headers.
    check(type(raw) is bytes and len(raw)>=32768 and len(raw)%32768==0,'WAL-index-size')
    check(raw[:48]==raw[48:96],'WAL-index-header-copies')
    values=struct.unpack('=12I',raw[:48])
    check(values[0]==3007000 and raw[12]==1,'WAL-index-version-initialized')
    s0=s1=0
    for a,b in zip(values[:10:2],values[1:10:2]):
        s0=(s0+a+s1)&0xffffffff;s1=(s1+b+s0)&0xffffffff
    check(values[10:]==(s0,s1),'WAL-index-header-checksum')
    return values

def empty_open(before,after,raw):
    check(set(before)=={''} and set(after)=={'','-wal','-shm'} and after['']==before[''],'WAL-main-only-opening-CAS')
    h=header(raw);check(h[4]==0 and h[5]==0 and not any(raw[136:]),'WAL-empty-opening-index')
    check(after['-wal']['signature9'][2]==0 and after['-wal']['sha256']==hashlib.sha256(b'').hexdigest(),'WAL-empty-opening-log')
    for suffix in ('-wal','-shm'):
        s=after[suffix]['signature9'];old=before['']['signature9']
        check(stat.S_ISREG(s[5]) and s[8]==1 and s[0]==old[0]
              and s[5:8]==old[5:8] and not after[suffix]['xattrs'],'WAL-owned-new-companion')
    ckpt=struct.unpack('=10I',raw[96:136])
    check(ckpt==(0,0,0xffffffff,0xffffffff,0xffffffff,0xffffffff,0,0,0,0),'WAL-empty-opening-checkpoint')

def read_begin(before,after,old,new):
    check(set(before)==set(after)=={'','-wal','-shm'} and before['']==after['']
          and before['-wal']==after['-wal'],'WAL-BEGIN-main-log-unchanged')
    h=header(old);check(header(new)==h and len(old)==len(new),'WAL-BEGIN-header-unchanged')
    a=before['-shm'];b=after['-shm']
    check(all(a['signature9'][i]==b['signature9'][i] for i in (0,1,2,5,6,7,8))
          and a['xattrs']==b['xattrs'],'WAL-BEGIN-SHM-incarnation')
    # sqlite walTryBeginRead may change exactly one exclusive read-mark slot
    # 1..4 to the current mxFrame. No lock-byte/header/index waiver exists.
    changed=[i for i in range(1,5) if old[100+4*i:104+4*i]!=new[100+4*i:104+4*i]]
    check(len(changed)<=1,'WAL-BEGIN-single-readmark')
    if changed:
        i=changed[0];offset=100+4*i
        check(old[:offset]==new[:offset] and old[offset+4:]==new[offset+4:]
              and struct.unpack('=I',new[offset:offset+4])[0]==h[4],'WAL-BEGIN-exact-readmark')
    else:check(old==new,'WAL-BEGIN-no-other-SHM-change')

class WALReaderPhase:
    def __init__(self,key,start,custody):
        check(key is _KEY,'owning-WAL-factory')
        self.start=start;self.reader=start.reader;self.reservation=start.reservation;self.custody=custody
        self.db=self.reader.root/'database.sqlite';self.thread=threading.get_ident()
        self.original=copy.deepcopy(self.reader.pairs['database.sqlite']);self.connection=None;self.phase='intent'
        self.current=None;self.directory=None;self.shm=None
        self.files,self.nodes=self.reader.native_syscall_controls(None)
        # Only the exact reader main pair and root directory are phase-owned.
        self.files={Path(p):(list(v) if v is not None else None) for p,v in self.files.items()
                    if Path(p)!=self.reader.root and Path(p) not in {Path(str(self.db)+s) for s in ('','-wal','-shm','-journal')}}
        self.nodes={Path(p):(list(v) if v is not None else None) for p,v in self.nodes.items()}
        self.names=set(self.reader.names);self.core=self._core();self._seal()
        check(set(self.original)=={''},'WAL-existing-companions-unsupported')
    def _core(self):return hashlib.sha256(encode(dict(objects=[id(self.start),id(self.reader),id(self.reservation),id(self.custody)],start=self.start.core,reader=self.reader.core,native=self.reservation.core,db=str(self.db),thread=self.thread,original=self.original,names=sorted(self.names),files={str(p):v for p,v in self.files.items()},nodes={str(p):v for p,v in self.nodes.items()}))).hexdigest()
    def _state(self):return hashlib.sha256(encode(dict(phase=self.phase,connection=id(self.connection),current=self.current,directory=self.directory,shm_sha256=hashlib.sha256(self.shm).hexdigest() if self.shm is not None else None))).hexdigest()
    def _seal(self):_SEALS[self]=(self.core,self._state())
    def _life(self):check(self.thread==threading.get_ident() and self._core()==self.core and _SEALS.get(self)==(self.core,self._state()),'immutable-owning-WAL-phase')
    def _direct(self,pair,directory,native=()):
        # Copy all admitted vectors BEFORE any replaceable lifetime/helper call.
        files=copy.deepcopy(self.files);nodes=copy.deepcopy(self.nodes)
        native=tuple((copy.deepcopy(f),copy.deepcopy(n)) for f,n in native)
        root=Path(self.db.parent);names=set(self.names)|{self.db.name+s for s in pair if s}
        db=Path(self.db);directory=copy.deepcopy(directory);pair=copy.deepcopy(pair)
        self._life()
        for f,n in native:
            for p,v in f.items():
                p=Path(p);value=list(v) if v is not None else None;check(p not in files or files[p]==value,'WAL-control-conflict');files[p]=value
            for p,v in n.items():
                p=Path(p);value=list(v) if v is not None else None;check(p not in nodes or nodes[p]==value,'WAL-ancestor-conflict');nodes[p]=value
        files[root]=directory
        files.update({Path(str(db)+s):(pair[s]['signature9'] if s in pair else None) for s in ('','-wal','-shm','-journal')})
        check(set(os.listdir(root))==names,'WAL-closed-reader-namespace')
        for p,v in files.items():
            try:actual=nine(os.lstat(p))
            except FileNotFoundError:actual=None
            check(actual==(list(v) if v is not None else None),'terminal-WAL-file')
        for p,v in nodes.items():
            try:actual=five(os.lstat(p))
            except FileNotFoundError:actual=None
            check(actual==(list(v) if v is not None else None),'terminal-WAL-ancestor')
        # All semantic helpers (including nine/five/_life) have finished.
        # No mutable baseline or helper is consulted after this raw seal.
        if set(os.listdir(root))!=names:raise Held('terminal-WAL-namespace-final')
        for p,v in files.items():
            try:
                z=os.lstat(p);actual=[z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
            except FileNotFoundError:actual=None
            if actual!=(list(v) if v is not None else None):raise Held('terminal-WAL-file-final')
        for p,v in nodes.items():
            try:
                z=os.lstat(p);actual=[z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
            except FileNotFoundError:actual=None
            if actual!=(list(v) if v is not None else None):raise Held('terminal-WAL-ancestor-final')
    def _before_open(self):
        self._life();self.start._life();self.reader.validate_sql_start(self.reservation)
        self.reservation.close_native_precommit(self.reader)
        check(self.custody.raw_pair(self.db)==self.original,'WAL-before-opening-pair')
        self.start._direct((self.reader.native_syscall_controls(None),self.reservation.native_sql_controls(self.reader)))
    def open_begin(self):
        self._life();check(self.phase=='intent','single-WAL-opening');self._before_open()
        self.connection=self.reader.disk.connect(self.db)
        check(type(self.connection) is sqlite3.Connection,'exact-owned-WAL-connection')
        self.phase='opening';self._seal()
        self._before_open()
        # The already durable SQLStart receipt precedes ALL SQLite side effects.
        check(self.connection.execute('PRAGMA journal_mode').fetchone()[0]=='wal','existing-WAL-mode-required')
        pair=self.custody.raw_pair(self.db);raw=read_shm(self.db,pair);empty_open(self.original,pair,raw)
        check(self.custody.raw_pair(self.db)==pair,'WAL-opening-after-proof-CAS')
        self.current=pair;self.directory=nine(os.lstat(self.reader.root));self.shm=raw;self.phase='opened';self._seal()
        self.reservation.close_native_precommit(self.reader);native=self.reservation.native_sql_controls(self.reader)
        self._direct(pair,self.directory,(native,));self.phase='BEGIN-uncertain';self._seal()
        self._direct(pair,self.directory,(native,))
        self.connection.execute('BEGIN IMMEDIATE')
        begun=self.custody.raw_pair(self.db);new=read_shm(self.db,begun);read_begin(pair,begun,raw,new)
        check(self.custody.raw_pair(self.db)==begun,'WAL-BEGIN-after-proof-CAS')
        self.current=begun;self.shm=new;self.phase='begun';self._seal();self._direct(begun,self.directory,(native,))
        return self
    def begin_reverse(self,commit):
        module=installed('publication_reader_sql_commit')
        check(type(commit) is module.ReaderSQLCommit and commit.sql.connection is self.connection
              and commit.reader is self.reader and commit.reservation is self.reservation,'exact-same-connection-WAL-reverse')
        self._life();check(self.phase=='begun' and commit.phase=='reverse-uncertain'
                          and not self.connection.in_transaction,'owned-WAL-reverse-intent')
        check(any(p.name=='reverse-intent.json' for p in commit.records),'durable-WAL-reverse-intent')
        commit.close_committed_for_reverse_open(self.reservation.native_sql_controls(self.reader))
        pair=copy.deepcopy(commit.current);raw=read_shm(self.db,pair)
        check(self.custody.raw_pair(self.db)==pair,'WAL-reverse-before-pair')
        native=self.reservation.native_sql_controls(self.reader)
        self._direct(pair,commit.directory,(native,));self.phase='reverse-BEGIN-uncertain';self._seal()
        self._direct(pair,commit.directory,(native,));self.connection.execute('BEGIN IMMEDIATE')
        begun=self.custody.raw_pair(self.db);new=read_shm(self.db,begun);read_begin(pair,begun,raw,new)
        check(self.custody.raw_pair(self.db)==begun,'WAL-reverse-BEGIN-after-proof-CAS')
        self.current=begun;self.directory=commit.directory;self.shm=new;self.phase='reverse-begun';self._seal()
        self._direct(begun,self.directory,(native,));return self
    def close_original(self,start):
        module=installed('publication_reader_sql_start')
        check(type(start) is module.ReaderSQLStart and start is self.start
              and start.wal_phase is self and start.sql is self.reader.sql,
              'exact-original-WAL-opening-custody')
        self._life();start._life()
        sql=start.sql
        check(self.phase=='begun' and sql.phase=='rolled-back'
              and sql.connection is self.connection and not self.connection.in_transaction
              and self.reader.phase=='rolled-back' and self.reader.commit_custody is None,
              'proved-original-WAL-rollback-before-close')
        check(start.original_close_receipt is not None,'durable-original-WAL-close-intent')
        start.close_original_intent()
        pair=copy.deepcopy(sql.pending);directory=copy.deepcopy(sql.directory)
        check(self.custody.raw_pair(self.db)==pair,'original-WAL-close-pair')
        expected=self.reader.before['database.sqlite']
        check(self.reader.disk.observe_copy(self.db,self.reader.plan,self.reader.scratch)==expected,
              'original-WAL-close-all-tables')
        check(self.custody.raw_pair(self.db)==pair,'original-WAL-logical-after-pair')
        self.reservation.close_native_original_rollback(self.reader)
        native=self.reservation.native_original_sql_controls(self.reader)
        self._direct(pair,directory,(native,));self.phase='original-close-uncertain';self._seal()
        self._direct(pair,directory,(native,));self.connection.close()
        closed=self.custody.raw_pair(self.db)
        check(set(closed)=={''},'original-WAL-last-close-companions-retained')
        check(closed==self.original,'original-WAL-close-preserved-main')
        check(self.reader.disk.observe_copy(self.db,self.reader.plan,self.reader.scratch)==expected,
              'original-WAL-closed-all-tables')
        check(self.custody.raw_pair(self.db)==closed,'original-WAL-closed-pair-CAS')
        self.current=closed;self.directory=nine(os.lstat(self.reader.root));self.shm=None
        self.phase='closed-original';self._seal();self._direct(closed,self.directory,(native,))
        return self
    def close_connection(self,commit):
        module=installed('publication_reader_sql_commit')
        check(type(commit) is module.ReaderSQLCommit and commit.sql.connection is self.connection
              and commit.reader is self.reader and commit.reservation is self.reservation,'exact-owning-WAL-close')
        self._life();check(commit.phase in ('committed','reversed') and not self.connection.in_transaction,'only-proved-WAL-connection-close')
        check(any(p.name=='connection-close-intent.json' for p in commit.records),'durable-WAL-close-intent')
        expected=commit.after if commit.phase=='committed' else commit.before
        commit._close_observed(self.reservation,expected,commit.phase)
        pair=copy.deepcopy(commit.current);native=self.reservation.native_sql_controls(self.reader)
        self._direct(pair,commit.directory,(native,));self.phase='close-uncertain';self._seal()
        self._direct(pair,commit.directory,(native,));self.connection.close()
        closed=self.custody.raw_pair(self.db);check(set(closed)=={''},'WAL-last-close-companions-retained')
        old=self.original[''];new=closed['']
        check(all(old['signature9'][i]==new['signature9'][i] for i in (0,1,5,6,7,8))
              and old['xattrs']==new['xattrs'],'WAL-checkpoint-main-incarnation')
        check(self.reader.disk.observe_copy(self.db,self.reader.plan,self.reader.scratch)==expected,'WAL-closed-exact-all-tables')
        check(self.custody.raw_pair(self.db)==closed,'WAL-close-after-logical-CAS')
        self.current=closed;self.directory=nine(os.lstat(self.reader.root));self.shm=None;self.phase='closed';self._seal()
        self._direct(closed,self.directory,(native,));return self

def from_opening(start):
    module=installed('publication_reader_sql_start');custody=installed('publication_reader_sql_custody')
    check(type(start) is module.ReaderSQLStart and start.phase=='intent' and start.receipt is not None,'exact-durable-WAL-opening')
    start._life()
    return WALReaderPhase(_KEY,start,custody)
