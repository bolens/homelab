"""Prospective typed reader COMMIT/reverse custody; not installed or a grant.

The exact installed reader successor and staged native reservation must own the
lifetime. No generic callback, receipt, boolean or ordinary Writer bypass mints it.
"""
import copy
import hashlib
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
def check(v,r):
    if not v:raise Held(r)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def s9(z):return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def s5(z):return [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
def sig(p):return s9(os.lstat(p))
def modules():
    names=('publication_reader_sql_custody','publication_reader_phase','publication_negative_batch_transition')
    result=[]
    for name in names:
        try:m=importlib.import_module('mylar.'+name)
        except ModuleNotFoundError:raise Held('owning-SQL-commit-modules-not-installed') from None
        p=Path(m.__file__);check(p==Path('/app/mylar3/mylar')/(name+'.py') and p.resolve()==p,'installed-SQL-commit-module');result.append(m)
    return result+[result[1]]

def merge(vectors):
    files={};nodes={};absent=set()
    for vector in vectors:
        check(type(vector) in (tuple,list) and len(vector) in (2,3),'typed-SQL-control-vector')
        f,n=vector[:2];a=vector[2] if len(vector)==3 else ()
        for p,v in f.items():
            p=Path(p)
            if v is None:absent.add(p);continue
            check(p not in files or files[p]==list(v),'conflicting-SQL-control');files[p]=list(v)
        for p,v in n.items():
            p=Path(p);value=None if v is None else list(v)
            check(p not in nodes or nodes[p]==value,'conflicting-SQL-ancestor');nodes[p]=value
        absent.update(map(Path,a))
    check(not absent.intersection(files),'conflicting-SQL-absence');return files,nodes,absent

class ReaderSQLCommit:
    """One exact connection, five approved rows, immutable observed successors."""
    def __init__(self,key,sql,reader,reservation,modules_,*,wal_phase=None):
        check(key is _KEY,'owning-SQL-commit-factory');custody,phase,batch,transition=modules_
        check(type(sql) is custody.SQLWritingCustody and type(reader) is phase.StoppedReaderPhase and
              type(reservation) is batch.NegativeBatchReservation,'exact-SQL-reader-staged-types')
        self.wal=wal_phase;self.wal_core=None;self.closed=False;self.reverse_sql=None;self.opening_files={};self.opening_nodes={};self.opening_names=None
        if wal_phase is None:check(sql.mode=='delete','WAL-COMMIT-needs-supported-reverse-phase')
        else:
            wal_module=importlib.import_module('mylar.publication_reader_wal_phase')
            wp=Path(wal_module.__file__);check(wp==Path('/app/mylar3/mylar/publication_reader_wal_phase.py') and wp.resolve()==wp,'installed-WAL-commit-producer')
            check(type(wal_phase) is wal_module.WALReaderPhase and sql.mode=='wal'
                  and sql.wal_phase is wal_phase and reader.wal_phase is wal_phase
                  and wal_phase.reader is reader and wal_phase.reservation is reservation
                  and wal_phase.connection is sql.connection and wal_phase.phase=='begun'
                  and wal_phase.current==sql.baseline,'exact-owned-WAL-COMMIT-lifetime')
            wal_phase._life();self.wal_core=wal_phase.core
            start=wal_phase.start;start._life()
            check(start.sql is sql and start.phase=='opened' and start.receipt is not None,'exact-durable-WAL-opening-before-COMMIT')
            self.opening_files={start.journal:copy.deepcopy(start.directories[start.journal]),start.journal/'opening.json':copy.deepcopy(start.receipt['signature9'])}
            self.opening_nodes=copy.deepcopy(start.nodes);self.opening_names=(start.journal,{'opening.json'})
            check(start.close_pending() is sql,'owning-opening-pending-COMMIT-handoff')
        check(type(sql.connection) is sqlite3.Connection and sql.connection.in_transaction and sql.phase=='writing' and sql.pending is not None,'owned-pending-connection')
        check(reader.sql is sql and reader.batch is reservation and reservation.reader is reader and
              tuple(reader.preparations)==tuple(reservation.batch.preparations) and len(reader.preparations)==5,'exact-five-SQL-native-reader-binding')
        self.sql=sql;self.reader=reader;self.reservation=reservation;self.modules=modules_;self.transition=transition
        self.thread=threading.get_ident();self.connection=sql.connection;self.db=sql.db;self.root=sql.parent
        self.tasks=Path(reader.tasks_database);check(self.tasks.parent==self.root and self.tasks!=self.db,'same-reviewed-tasks-root')
        self.scratch=Path(reader.scratch);check(self.scratch.resolve()==self.scratch and self.scratch.is_dir() and stat.S_IMODE(os.lstat(self.scratch).st_mode)==0o700 and not self.scratch.is_relative_to(self.root) and not self.root.is_relative_to(self.scratch),'private-SQL-observation-scratch')
        self.tasks_pair=copy.deepcopy(reader.tasks_pair);self.main_original=copy.deepcopy(sql.baseline)
        self.preparation_ids=tuple(id(p) for p in reader.preparations)
        self.before=copy.deepcopy(sql.before);self.after=copy.deepcopy(sql.after);self.plan=copy.deepcopy(sql.plan)
        self.phase='pending';self.current=None;self.directory=None;self.records={};self.journal=Path(reader.sql_operation)
        check(self.journal.is_absolute() and self.journal.resolve()==self.journal and self.journal!=self.root and
              not self.journal.is_relative_to(self.root) and not self.root.is_relative_to(self.journal),'private-SQL-journal-scope')
        self.nodes={p:s5(os.lstat(p)) for p in (self.journal,*self.journal.parents,self.scratch,*self.scratch.parents)}
        j=sig(self.journal);check(stat.S_ISDIR(j[5]) and stat.S_IMODE(j[5])==0o700 and j[6]==os.geteuid() and not os.listdir(self.journal),'empty-private-SQL-journal')
        self.journal9=j;self.core=self._core();self._seal();self._precommit()
    def _core(self):return hashlib.sha256(encode(dict(opening_files={str(p):v for p,v in self.opening_files.items()},opening_nodes={str(p):v for p,v in self.opening_nodes.items()},opening_names=[str(self.opening_names[0]),sorted(self.opening_names[1])] if self.opening_names is not None else None,wal=[id(self.wal),self.wal_core],before=self.before,after=self.after,plan=self.plan,original=self.main_original,tasks=self.tasks_pair,db=str(self.db),tasks_path=str(self.tasks),root=str(self.root),module_ids=[id(m) for m in self.modules],transition=id(self.transition),journal=str(self.journal),scratch=str(self.scratch),nodes={str(p):v for p,v in self.nodes.items()},objects=[id(self.sql),id(self.reader),id(self.reservation),id(self.connection),*self.preparation_ids],thread=self.thread))).hexdigest()
    def _state(self):return hashlib.sha256(encode(dict(closed=self.closed,reverse_sql=id(self.reverse_sql),phase=self.phase,current=self.current,directory=self.directory,journal=self.journal9,records={str(p):v for p,v in self.records.items()}))).hexdigest()
    def _seal(self):
        self.state=self._state();_SEALS[self]=(self.core,self.state)
    def _life(self):check(threading.get_ident()==self.thread and self._core()==self.core and self._state()==self.state and _SEALS.get(self)==(self.core,self.state),'immutable-SQL-commit-custody')
    def _record(self,name):
        self._life();check(set(os.listdir(self.journal))=={p.name for p in self.records},'SQL-journal-census')
        raw=encode(dict(version=1,kind='owning-reader-SQL-phase',phase=name,core=self.core,preparations=list(self.preparation_ids),publication_acceptance=False))
        d=os.open(self.journal,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            check(s9(os.fstat(d))==self.journal9,'SQL-journal-FD-CAS')
            fd=os.open(name+'.json',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
            try:
                count=0
                while count<len(raw):count+=os.write(fd,raw[count:])
                os.fsync(fd);os.fsync(d);os.lseek(fd,0,os.SEEK_SET)
                check(os.read(fd,len(raw)+1)==raw,'SQL-intended-receipt');value=s9(os.fstat(fd))
                check(s9(os.stat(name+'.json',dir_fd=d,follow_symlinks=False))==value,'SQL-receipt-FD-leaf')
            finally:os.close(fd)
            directory=s9(os.fstat(d));check(sig(self.journal)==directory,'SQL-journal-path-CAS')
        finally:os.close(d)
        self.records[self.journal/(name+'.json')]=dict(signature9=value,sha256=hashlib.sha256(raw).hexdigest());self.journal9=directory;self._seal()
    def _sql_vectors(self,pair,directory):
        files={self.root:directory,**{self.root/name:v for name,v in self.sql.names.items()}}
        absent=[]
        for db,values in ((self.db,pair),(self.tasks,self.tasks_pair)):
            for suffix in ('','-wal','-shm','-journal'):
                p=Path(str(db)+suffix)
                if suffix in values:files[p]=values[suffix]['signature9']
                else:absent.append(p)
        return files,self.sql.nodes,absent
    def _direct(self,vectors,pending_pair=None):
        vectors=copy.deepcopy(vectors)
        files,nodes,absent=merge([*vectors,(copy.deepcopy(self.opening_files),copy.deepcopy(self.opening_nodes))])
        opening_names=copy.deepcopy(self.opening_names)
        files.update({self.journal:self.journal9,**{p:v['signature9'] for p,v in self.records.items()}})
        for p,v in self.nodes.items():check(p not in nodes or nodes[p]==v,'shared-SQL-journal-ancestor');nodes[p]=v
        check(set(os.listdir(self.journal))=={p.name for p in self.records},'closed-SQL-journal')
        pair=pending_pair if pending_pair is not None else (self.sql.pending if self.phase in ('pending','commit-intent') else self.current)
        check(set(os.listdir(self.root))==set(self.sql.names)|{self.db.name+s for s in pair},'closed-SQL-reader-root')
        for p in absent:
            try:os.lstat(p)
            except FileNotFoundError:continue
            raise Held('terminal-SQL-companion')
        for p,v in files.items():check(s9(os.lstat(p))==v,'terminal-SQL-file')
        for p,v in nodes.items():
            try:actual=s5(os.lstat(p))
            except FileNotFoundError:actual=None
            check(actual==v,'terminal-SQL-ancestor')
        # All copied output and replaceable semantic/signature helpers finish
        # before the direct kernel closure. No s9/s5/check/merge/copy callback is
        # invoked after this boundary or before the caller's SQLite syscall.
        result=copy.deepcopy(files),copy.deepcopy(nodes),tuple(absent)
        journal_names={p.name for p in self.records}
        root_names=set(self.sql.names)|{self.db.name+s for s in pair}
        journal_path=self.journal;root_path=self.root
        self._life()
        files,nodes,absent=result
        if opening_names is not None and set(os.listdir(opening_names[0]))!=opening_names[1]:raise Held('terminal-SQL-opening-journal-final')
        if set(os.listdir(journal_path))!=journal_names:raise Held('terminal-SQL-journal-final')
        if set(os.listdir(root_path))!=root_names:raise Held('terminal-SQL-root-final')
        for p,v in nodes.items():
            try:
                z=os.lstat(p);actual=[z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
            except FileNotFoundError:actual=None
            if actual!=v:raise Held('terminal-SQL-ancestor-final')
        for p,v in files.items():
            z=os.lstat(p)
            if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=v:
                raise Held('terminal-SQL-file-final')
        for p in absent:
            try:os.lstat(p)
            except FileNotFoundError:continue
            raise Held('terminal-SQL-companion-final')
        return result
    def _precommit(self):
        self._life();self.sql.close_pending();self.reader.revalidate_sql_writing(self.sql,self.reservation)
        self.reservation.close_native_precommit(self.reader)
        reader=self.reader.sql_syscall_controls(self.sql,self.reservation);native=self.reservation.native_sql_controls(self.reader)
        check(self.modules[0].raw_pair(self.tasks)==self.tasks_pair,'tasks-pair-unchanged')
        self.sql.close_pending()
        self._direct([reader,native,self._sql_vectors(self.sql.pending,self.sql.directory)],self.sql.pending)
    def _capture(self,expected):
        pair=self.modules[0].raw_pair(self.db);directory=sig(self.root)
        check(not self.connection.in_transaction and self.sql.disk.observe_copy(self.db,self.plan,self.scratch)==expected,'committed-SQL-exact-all-tables')
        check(self.modules[0].raw_pair(self.db)==pair and self.modules[0].raw_pair(self.tasks)==self.tasks_pair,'postcommit-pair-CAS')
        old=self.main_original[''];new=pair[''];check(all(old['signature9'][i]==new['signature9'][i] for i in (0,1,5,6,7,8)) and old['xattrs']==new['xattrs'],'committed-main-identity-attrs')
        self.current=pair;self.directory=directory;self._seal()
        self._direct([self._sql_vectors(pair,directory)])
    def commit(self):
        self._life();check(self.phase=='pending','single-reader-COMMIT')
        self._precommit();self._record('commit-intent')
        # State/hash sealing is semantic work, so it precedes the last passive
        # closure rather than executing between that closure and COMMIT.
        self.phase='commit-uncertain';self._seal();self._precommit()
        # A lost response never replays COMMIT or fabricates a committed phase.
        self.connection.commit()
        self._capture(self.after);self.phase='committed';self._seal();self._record('committed')
        if self.wal is not None:self.wal.accept_committed_pair(self)
        self.reader.accept_committed(self)
        self.close_committed(self.reservation);return self
    def _close_observed(self,reservation,expected,phase):
        self._life();check(reservation is self.reservation and self.phase==phase,'exact-SQL-successor-phase')
        self.reader.revalidate_sql_observed(self,reservation)
        check(self.sql.disk.observe_copy(self.db,self.plan,self.scratch)==expected and (self.closed or not self.connection.in_transaction),'current-SQL-all-tables')
        check(self.modules[0].raw_pair(self.db)==self.current and self.modules[0].raw_pair(self.tasks)==self.tasks_pair,'current-SQL-pairs')
        for p,v in self.records.items():check(hashlib.sha256(p.read_bytes()).hexdigest()==v['sha256'],'SQL-receipt-bytes')
        reader=self.reader.sql_observed_controls(self,reservation)
        return self._direct([reader,self._sql_vectors(self.current,self.directory)])
    def close_committed(self,reservation):return self._close_observed(reservation,self.after,'committed')
    def close_reversed(self,reservation):return self._close_observed(reservation,self.before,'reversed')
    def reverse(self):
        if self.wal is not None:return self._reverse_wal()
        self.close_committed(self.reservation)
        # Frozen custody does not grant a newly opened WAL reader's SHM
        # transition. Refuse before reversal intent, BEGIN or any SQL write.
        check(self.sql.mode=='delete','WAL-reversal-needs-owned-connection-phase')
        self._record('reverse-intent');self.close_committed(self.reservation)
        self.reservation.close_native_reverse(self.reader)
        native=self.reservation.native_sql_controls(self.reader)
        self.close_committed(self.reservation);self._direct([native,self._sql_vectors(self.current,self.directory)])
        self.phase='reverse-uncertain';self._seal()
        # A fresh sole-main connection avoids SQLite's connection-local TEMP
        # schema without relaxing the reviewed original custody constructor.
        reverse_connection=self.sql.disk.connect(self.db)
        try:
            self.close_committed_for_reverse_open(native)
            reverse_connection.execute('BEGIN IMMEDIATE')
            reverse=self.modules[0].SQLWritingCustody(self.modules[0]._KEY,reverse_connection,self.db,self.sql.disk,self.plan,self.after,self.before,self.current)
            self.close_committed_for_reverse_open(native)
            reverse.apply_body(lambda connection,disk,plan,*_ :self.transition.sql_five_transition(connection,disk,plan,self.before,self.after,rollback=True));reverse.close_pending()
            self.reader.revalidate_sql_reversing(self,reverse,self.reservation)
            self.reservation.close_native_reverse(self.reader)
            reader=self.reader.sql_reverse_controls(self,reverse,self.reservation);native=self.reservation.native_sql_controls(self.reader)
            reverse.close_pending();self._direct([reader,native,self._sql_vectors(reverse.pending,reverse.directory)],reverse.pending)
            reverse_connection.commit()
        finally:reverse_connection.close()
        self._capture(self.before);self.phase='reversed';self._seal();self._record('reversed')
        self.reader.accept_reversed(self);self.close_reversed(self.reservation);return self
    def _reverse_wal(self):
        self._life();check(not self.closed and self.phase=='committed','owned-open-WAL-before-reverse')
        self.close_committed(self.reservation);self._record('reverse-intent')
        self.close_committed(self.reservation);self.reservation.close_native_reverse(self.reader)
        self.phase='reverse-uncertain';self._seal()
        # Exact producer owns the same-connection BEGIN/read-mark transition.
        self.wal.begin_reverse(self)
        reverse=self.modules[0].from_wal_begin(self.wal,self.sql.disk,self.plan,self.after,self.before)
        self.reverse_sql=reverse;self._seal()
        reverse.apply_body(self._wal_reverse_body)
        reverse.close_pending();self.reader.revalidate_sql_reversing(self,reverse,self.reservation)
        self.reservation.close_native_reverse(self.reader)
        reader=self.reader.sql_reverse_controls(self,reverse,self.reservation)
        native=self.reservation.native_sql_controls(self.reader)
        reverse.close_pending();self._direct([reader,native,self._sql_vectors(reverse.pending,reverse.directory)],reverse.pending)
        self.connection.commit()
        self._capture(self.before);self.phase='reversed';self._seal();self._record('reversed')
        self.wal.accept_committed_pair(self);self.reader.accept_reversed(self)
        self.close_reversed(self.reservation);return self
    def _wal_reverse_body(self,connection,disk,plan,before,after):
        reverse=self.reverse_sql
        check(type(connection) is sqlite3.Connection and reverse is not None
              and connection is self.connection is reverse.connection and connection.in_transaction
              and before==self.after and after==self.before,'exact-owned-WAL-five-reverse-body')
        disk.healthy(connection)
        check((disk.master(connection),disk.k.snapshot(connection),disk.book_rows(connection,plan))==self.after,
              'WAL-reverse-five-logical-preimage')
        parameters=[]
        for bid in plan['active_wrong_ids']:
            row=disk.k.row_decode(plan['before_rows'][bid]);current=disk.k.row_decode(plan['after_rows'][bid])
            parameters.append((row[11],row[2],bid,current[11],current[2]))
        check(len(parameters)==5,'exact-WAL-five-reverse-parameters')
        reverse._close_before_write()
        self.reservation.close_native_reverse(self.reader)
        reader=self.reader.sql_observed_controls(self,self.reservation)
        native=self.reservation.native_sql_controls(self.reader)
        self._direct([reader,native,self._sql_vectors(reverse.baseline,reverse.initial_directory)],reverse.baseline)
        for row in parameters:
            check(connection.execute('UPDATE BOOK SET DELETED_DATE=?, LAST_MODIFIED_DATE=? WHERE ID=? AND DELETED_DATE IS ? AND LAST_MODIFIED_DATE IS ?',row).rowcount==1,
                  'exact-WAL-five-reverse-row-CAS')
        check((disk.master(connection),disk.k.snapshot(connection),disk.book_rows(connection,plan))==self.before,
              'WAL-reverse-only-five-field-delta')
        disk.healthy(connection)
    def close_owned_connection(self):
        self._life();check(self.wal is not None and not self.closed and self.phase in ('committed','reversed'),
                           'single-owned-WAL-connection-close')
        check((self.phase=='committed' and self.reservation.projection.phases==['retained']*5)
              or (self.phase=='reversed' and len(self.reservation.projection.phases)==5
                  and all(p in ('linked','retained') for p in self.reservation.projection.phases)),
              'native-phase-before-owned-WAL-close')
        expected=self.after if self.phase=='committed' else self.before
        self._close_observed(self.reservation,expected,self.phase)
        self._record('connection-close-intent')
        self._close_observed(self.reservation,expected,self.phase)
        self.wal.close_connection(self)
        return self.accept_closed_pair(self.wal)
    def accept_closed_pair(self,wal_phase):
        self._life()
        check(wal_phase is self.wal and self.wal_core==wal_phase.core and not self.closed
              and wal_phase.phase=='closed' and self.phase in ('committed','reversed'),
              'one-exact-closed-WAL-pair-successor')
        wal_phase._life()
        pair=copy.deepcopy(wal_phase.current);directory=copy.deepcopy(wal_phase.directory)
        check(set(pair)=={''},'closed-WAL-main-only-required')
        expected=self.after if self.phase=='committed' else self.before
        check(self.sql.disk.observe_copy(self.db,self.plan,self.scratch)==expected
              and self.modules[0].raw_pair(self.db)==pair
              and self.modules[0].raw_pair(self.tasks)==self.tasks_pair,'closed-WAL-logical-and-pair-CAS')
        reader=self.reader.sql_observed_controls(self,self.reservation)
        native=self.reservation.native_sql_controls(self.reader)
        # Copied terminal successor vectors precede every last helper/callback.
        carried=[]
        for vector in (reader,native):
            files,nodes,absent=merge([vector]);files.update({p:None for p in absent});carried.append((files,nodes))
        wal_phase._direct(pair,directory,tuple(carried))
        self.current=pair;self.directory=directory;self.closed=True;self._seal()
        self._record('connection-closed')
        self._close_observed(self.reservation,expected,self.phase)
        return self
    def close_committed_for_reverse_open(self,native):
        self._life();check(self.phase=='reverse-uncertain','owned-reverse-open-phase')
        check(self.sql.disk.observe_copy(self.db,self.plan,self.scratch)==self.after and not self.connection.in_transaction,'reverse-original-logical-CAS')
        check(self.modules[0].raw_pair(self.db)==self.current and self.modules[0].raw_pair(self.tasks)==self.tasks_pair,'reverse-open-pair-CAS')
        self._direct([native,self._sql_vectors(self.current,self.directory)])
    @property
    def sql_custody(self):return self.sql
    def close_passive(self):
        self._life()
        pair=self.sql.pending if self.phase=='pending' else self.current
        directory=self.sql.directory if self.phase=='pending' else self.directory
        check(pair is not None and directory is not None,'observed-SQL-phase-required')
        return self._direct([self._sql_vectors(pair,directory)],pair)
    def vectors(self):
        files,nodes,absent=self.close_passive()
        for p in absent:files[p]=None
        return files,nodes
    def revalidate_committed(self):return self.close_committed(self.reservation)
    def revalidate_reversed(self):return self.close_reversed(self.reservation)
    @property
    def binding(self):
        self._life();return copy.deepcopy(dict(version=1,core=self.core,phase=self.phase,connection_closed=self.closed,wal_phase=(self.wal.phase if self.wal is not None else None),preparation_ids=list(self.preparation_ids),reservation_id=id(self.reservation),receipt=(dict(path=str(self.journal/'committed.json'),**self.records[self.journal/'committed.json']) if self.journal/'committed.json' in self.records else None),before=self.before,after=self.after,main=str(self.db),tasks=str(self.tasks),main_pair=self.current,tasks_pair=self.tasks_pair,receipts={str(p):v for p,v in self.records.items()},publication_acceptance=False,mutation_authority=False,final_ack_required=True))

def from_pending(sql,reader,reservation):return ReaderSQLCommit(_KEY,sql,reader,reservation,modules())
def from_pending_wal(sql,reader,reservation,wal_phase):return ReaderSQLCommit(_KEY,sql,reader,reservation,modules(),wal_phase=wal_phase)
if __name__=='__main__':print(json.dumps(dict(executable=False,installed=False,publication_acceptance=False,missing='installed owning SQL-writing reader and staged batch factories plus actual stopped lifecycle/backup/native custody')))
