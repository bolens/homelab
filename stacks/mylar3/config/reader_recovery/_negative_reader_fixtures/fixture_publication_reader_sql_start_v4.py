"""Prospective durable SQL-opening producer under an already held native batch.

No CLI application, lifecycle proof minting, ordinary admission bypass, or COMMIT.
Installed exact owning types and the stopped-reader factory remain prerequisites.
"""
import hashlib
import copy
import importlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import threading
import weakref
_KEY=object()
_SEALS=weakref.WeakKeyDictionary()
class Held(ValueError):pass
def check(value,reason):
    if not value:raise Held(reason)
def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def s9(z):return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def s5(z):return [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
def installed(name):
    try:m=importlib.import_module('mylar.'+name)
    except ModuleNotFoundError:raise Held('owning-SQL-opening-component-not-installed') from None
    p=Path(m.__file__);check(p.parent==Path('/app/mylar3/mylar') and p.resolve()==p,'installed-SQL-opening-component');return m
class ReaderSQLStart:
    def __init__(self,key,reader,reservation,journal,commit_journal,modules):
        check(key is _KEY,'owning-SQL-opening-factory')
        phase,transition,custody=modules
        check(type(reader) is phase.StoppedReaderPhase and type(reservation) is transition.NegativeBatchReservation,
              'exact-SQL-opening-types')
        self.reader=reader;self.reservation=reservation;self.modules=modules;self.thread=threading.get_ident()
        self.journal=Path(journal);self.commit_journal=Path(commit_journal);self.nodes={};self.directories={}
        for root in (self.journal,self.commit_journal):
            check(root.is_absolute() and root.resolve()==root and not any(root.is_relative_to(other) or other.is_relative_to(root)
                for other in (reader.root,reader.restore,reader.scratch,*reservation.batch.controller.roots)), 'SQL-intent-outside-source-roots')
            z=os.lstat(root);check(stat.S_ISDIR(z.st_mode) and stat.S_IMODE(z.st_mode)==0o700 and z.st_uid==os.geteuid() and not os.listdir(root),'fresh-owned-SQL-journal')
            self.directories[root]=s9(z)
            for p in (root,*root.parents):self.nodes[p]=s5(os.lstat(p))
        check(self.journal!=self.commit_journal and not self.journal.is_relative_to(self.commit_journal) and not self.commit_journal.is_relative_to(self.journal),'disjoint-SQL-journals')
        self.native_core=reservation.core;self.reader_core=reader.core;self.phase='prepared';self.receipt=None;self.original_close_receipt=None;self.sql=None
        self.wal_phase=None;self.wal_module=None;self.wal_commit=None;self.mode=self._source_mode()
        if self.mode=='wal':
            try:
                self.wal_module=installed('publication_reader_wal_phase');self.wal_commit=installed('publication_reader_sql_commit')
            except Held:raise Held('WAL-forward-refused-without-owning-COMMIT-reverse') from None
            check(callable(getattr(self.wal_commit,'from_pending_wal',None)) and callable(getattr(self.wal_module,'from_opening',None))
                  and callable(getattr(self.modules[2],'from_wal_begin',None))
                  and callable(getattr(reader,'accept_wal_begin',None))
                  and callable(getattr(reader,'accept_original_wal_close',None))
                  and callable(getattr(self.wal_module.WALReaderPhase,'close_original',None))
                  and callable(getattr(reservation,'native_original_sql_controls',None)), 'WAL-forward-refused-without-owning-COMMIT-reverse')
            check(set(reader.pairs['database.sqlite'])=={''},'WAL-existing-companions-unsupported')
        self.core=self._core()
        self._seal();reader.validate_sql_start(reservation);self._direct()
    def _core(self):return hashlib.sha256(encode(dict(mode=self.mode,wal_components=[id(self.wal_module),id(self.wal_commit)],native=self.native_core,reader=self.reader_core,objects=[id(self.reader),id(self.reservation),*[id(m) for m in self.modules]],journal=str(self.journal),commit=str(self.commit_journal),nodes={str(p):v for p,v in self.nodes.items()},thread=self.thread))).hexdigest()
    def _state(self):return hashlib.sha256(encode(dict(wal_phase=id(self.wal_phase),phase=self.phase,receipt=self.receipt,original_close_receipt=self.original_close_receipt,directories={str(p):v for p,v in self.directories.items()},sql=id(self.sql)))).hexdigest()
    def _seal(self):self.state=self._state();_SEALS[self]=(self.core,self.state)
    def _life(self):
        check(self.thread==threading.get_ident() and self._core()==self.core and _SEALS.get(self)==(self.core,self.state) and self._state()==self.state
            and self.reader.core==self.reader_core and self.reservation.core==self.native_core,'immutable-SQL-opening-custody')
    def _direct(self,vectors=()):
        files=copy.deepcopy(self.directories);nodes=copy.deepcopy(self.nodes);vectors=copy.deepcopy(vectors)
        receipt=copy.deepcopy(self.receipt);close_receipt=copy.deepcopy(self.original_close_receipt);self._life()
        if receipt:files[self.journal/'opening.json']=receipt['signature9']
        if close_receipt:files[self.journal/'original-close-intent.json']=close_receipt['signature9']
        for f,n in vectors:
            for p,v in f.items():
                p=Path(p);check(p not in files or files[p]==(list(v) if v is not None else None),'conflicting-opening-file')
                files[p]=None if v is None else list(v)
            for p,v in n.items():
                p=Path(p);value=None if v is None else list(v);check(p not in nodes or nodes[p]==value,'conflicting-opening-node');nodes[p]=value
        check(set(os.listdir(self.journal))==(({'opening.json'} if receipt else set())|({'original-close-intent.json'} if close_receipt else set())) and not os.listdir(self.commit_journal),'closed-SQL-opening-journals')
        for p,v in files.items():
            try:
                z=os.lstat(p);actual=[z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
            except FileNotFoundError:actual=None
            check(actual==v,'terminal-SQL-opening-leaf')
        for p,v in nodes.items():
            try:
                z=os.lstat(p);actual=[z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
            except FileNotFoundError:actual=None
            check(actual==v,'terminal-SQL-opening-ancestor')
    def _source_mode(self):
        # A WAL forward commit cannot be admitted until its exact SHM-aware
        # reverse BEGIN producer exists. Header mode is read without SQLite.
        db=self.reader.root/'database.sqlite';expected=self.reader.pairs['database.sqlite']['']['signature9']
        fd=os.open(db,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            check(s9(os.fstat(fd))==expected,'SQL-mode-source-CAS')
            header=os.read(fd,20)
            check(header[:16]==b'SQLite format 3\x00' and header[18:20] in (b'\x01\x01',b'\x02\x02'),'supported-existing-reader-journal-header')
            check(s9(os.fstat(fd))==expected and s9(os.lstat(db))==expected,'SQL-mode-after-read-CAS')
        finally:os.close(fd)
        return 'wal' if header[18:20]==b'\x02\x02' else 'delete'
    def _intent(self):
        raw=encode(dict(version=1,kind='reader-SQL-opening-intent',core=self.core,native_core=self.native_core,
            reader_core=self.reader_core,before=self.reader.before,after=self.reader.after,
            physical=self.reader.pairs,publication_acceptance=False,final_ack_required=True))
        d=os.open(self.journal,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            check(s9(os.fstat(d))==self.directories[self.journal],'SQL-opening-journal-FD')
            fd=os.open('opening.json',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
            try:
                done=0
                while done<len(raw):done+=os.write(fd,raw[done:])
                os.fsync(fd);os.fsync(d);os.lseek(fd,0,os.SEEK_SET)
                check(os.read(fd,len(raw)+1)==raw,'intended-SQL-opening-receipt')
                fact=s9(os.fstat(fd));check(s9(os.stat('opening.json',dir_fd=d,follow_symlinks=False))==fact,'SQL-opening-receipt-CAS')
            finally:os.close(fd)
            directory=s9(os.fstat(d));check(s9(os.lstat(self.journal))==directory,'SQL-opening-journal-path')
        finally:os.close(d)
        self.receipt=dict(signature9=fact,sha256=hashlib.sha256(raw).hexdigest());self.directories[self.journal]=directory;self.phase='intent';self._seal()
    def open_pending(self):
        self._life();check(self.phase=='prepared','single-SQL-opening')
        self._intent();reader=self.reader;batch=self.reservation;custody=self.modules[2]
        reader.validate_sql_start(batch);reader.bind_sql_operation(self.commit_journal)
        batch.close_native_precommit(reader)
        vectors=(reader.native_syscall_controls(None),batch.native_sql_controls(reader))
        self._direct(vectors)
        # Existing canonical database was proved immediately above. This owning
        # operation creates no replacement DB and never supplies a fallback.
        connection=None
        try:
            if self.mode=='wal':
                self.wal_phase=self.wal_module.from_opening(self);self._seal()
                self.wal_phase.open_begin();connection=self.wal_phase.connection
                reader.accept_wal_begin(self.wal_phase,batch)
                sql=custody.from_wal_begin(self.wal_phase,reader.disk,reader.plan,
                    reader.before['database.sqlite'],reader.after['database.sqlite'])
            else:
                connection=reader.disk.connect(reader.root/'database.sqlite')
                reader.validate_sql_start(batch);batch.close_native_precommit(reader)
                self._direct((reader.native_syscall_controls(None),batch.native_sql_controls(reader)))
                check(connection.execute('PRAGMA journal_mode').fetchone()[0]=='delete','existing-delete-mode-required')
                connection.execute('BEGIN IMMEDIATE')
                sql=custody.SQLWritingCustody(custody._KEY,connection,reader.root/'database.sqlite',reader.disk,
                    reader.plan,reader.before['database.sqlite'],reader.after['database.sqlite'],reader.pairs['database.sqlite'])
            reader.register_sql(sql,batch);self.sql=sql;self.phase='opened';self._seal()
            sql.apply_body(self._body)
            reader.revalidate_sql_writing(sql,batch);batch.close_native_precommit(reader)
            self._direct((reader.sql_syscall_controls(sql,batch),batch.native_sql_controls(reader)))
        except BaseException:
            # Never replay/restart or pretend an uncertain connection is safe.
            # Caller retains marker, intent and exact connection for recovery.
            self.connection=connection if connection is not None else (self.wal_phase.connection if self.wal_phase is not None else None);raise
        return self
    def _body(self,connection,disk,plan,before,after):
        check(type(connection) is sqlite3.Connection and connection is self.sql.connection and connection.in_transaction,'exact-opening-owned-connection')
        disk.healthy(connection);check((disk.master(connection),disk.k.snapshot(connection),disk.book_rows(connection,plan))==before,'exact-opening-logical-preimage')
        parameters=[[disk.k.untyped(v) for v in p] for p in plan['parameters']]
        check(len(parameters)==5,'exact-opening-five-updates')
        self.reservation.close_native_precommit(self.reader)
        self._direct((self.reader.sql_syscall_controls(self.sql,self.reservation),self.reservation.native_sql_controls(self.reader)))
        for row in parameters:check(connection.execute(disk.k.SQL,row).rowcount==1,'exact-opening-five-row-CAS')
        check((disk.master(connection),disk.k.snapshot(connection),disk.book_rows(connection,plan))==after,'exact-opening-all-table-postimage')
        disk.healthy(connection)
    def close_original_intent(self):
        self._life()
        check(self.mode=='wal' and self.phase=='opened' and self.sql is not None
              and self.sql.phase=='rolled-back' and self.reader.phase=='rolled-back'
              and self.original_close_receipt is not None,'owned-original-WAL-close-intent')
        raw=(self.journal/'original-close-intent.json').read_bytes()
        check(hashlib.sha256(raw).hexdigest()==self.original_close_receipt['sha256'],
              'original-WAL-close-intended-bytes')
        self.reader.close_native_phase_passive(None)
        self.reservation.close_native_original_rollback(self.reader)
        self._direct((self.reader.native_syscall_controls(None),self.reservation.native_original_sql_controls(self.reader)))
    def close_original_wal(self):
        self._life()
        check(self.mode=='wal' and self.phase=='opened' and self.wal_phase is self.reader.wal_phase
              and self.sql is self.reader.sql and self.sql.phase=='rolled-back'
              and self.reader.phase=='rolled-back' and self.original_close_receipt is None,
              'single-original-WAL-close')
        self.reader.close_native_phase_passive(None)
        self.reservation.close_native_original_rollback(self.reader)
        self._direct((self.reader.native_syscall_controls(None),self.reservation.native_original_sql_controls(self.reader)))
        raw=encode(dict(version=1,kind='reader-original-WAL-close-intent',core=self.core,
            sql_core=self.sql.core,physical=self.sql.pending,before=self.reader.before,
            publication_acceptance=False,final_ack_required=True))
        d=os.open(self.journal,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            check(s9(os.fstat(d))==self.directories[self.journal],'original-close-journal-FD')
            fd=os.open('original-close-intent.json',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
            try:
                done=0
                while done<len(raw):done+=os.write(fd,raw[done:])
                os.fsync(fd);os.fsync(d);os.lseek(fd,0,os.SEEK_SET)
                check(os.read(fd,len(raw)+1)==raw,'original-close-intended-receipt')
                fact=s9(os.fstat(fd))
                check(s9(os.stat('original-close-intent.json',dir_fd=d,follow_symlinks=False))==fact,'original-close-receipt-CAS')
            finally:os.close(fd)
            directory=s9(os.fstat(d));check(s9(os.lstat(self.journal))==directory,'original-close-journal-path')
        finally:os.close(d)
        self.original_close_receipt=dict(signature9=fact,sha256=hashlib.sha256(raw).hexdigest())
        self.directories[self.journal]=directory;self._seal()
        self.close_original_intent();self.wal_phase.close_original(self)
        self.reader.accept_original_wal_close(self.wal_phase,self.reservation)
        return self.wal_phase
    def close_pending(self):
        self._life();check(self.phase=='opened' and self.sql is not None,'owned-opening-pending')
        check(hashlib.sha256((self.journal/'opening.json').read_bytes()).hexdigest()==self.receipt['sha256'],'opening-intent-bytes')
        self.reader.revalidate_sql_writing(self.sql,self.reservation);self.reservation.close_native_precommit(self.reader)
        self._direct((self.reader.sql_syscall_controls(self.sql,self.reservation),self.reservation.native_sql_controls(self.reader)))
        return self.sql

def prepare_existing(reader,reservation,journal,commit_journal):
    modules=tuple(installed(n) for n in ('publication_reader_phase','publication_negative_batch_transition','publication_reader_sql_custody'))
    return ReaderSQLStart(_KEY,reader,reservation,journal,commit_journal,modules)
if __name__=='__main__':print(json.dumps(dict(executable=False,installed=False,publication_acceptance=False,missing='installed owning stopped-reader/native aggregate factories and reviewed final COMMIT/terminal consumer')))
