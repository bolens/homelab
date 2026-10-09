"""Prospective owning five-member reader/native producer, no CLI grants.

The exact stopped lifecycle invocation, existing Controller/Writer and installed
component source map are mandatory. This module does not create those proofs.
"""
import importlib
import json
import hashlib
import weakref
_SEALS=weakref.WeakKeyDictionary()
from pathlib import Path
import threading
_KEY=object()
class Held(ValueError):pass
def check(v,r):
 if not v:raise Held(r)
def installed(name):
 try:m=importlib.import_module('mylar.'+name)
 except ModuleNotFoundError:raise Held('owning-aggregate-component-not-installed') from None
 p=Path(m.__file__);check(p.parent==Path('/app/mylar3/mylar') and p.resolve()==p,'installed-owning-aggregate-component');return m
class NegativeReaderAggregate:
 def __init__(self,key,reservation,start_journal,commit_journal,modules):
  check(key is _KEY,'owning-aggregate-factory');transition,start,commit,terminal,rollback_terminal=modules
  check(type(reservation) is transition.NegativeBatchReservation,'exact-owning-five-reservation')
  check(callable(getattr(start,'prepare_existing',None)) and callable(getattr(commit,'from_pending',None))
      and callable(getattr(getattr(commit,'ReaderSQLCommit',None),'close_owned_connection',None))
      and callable(getattr(terminal,'from_retired',None)) and callable(getattr(rollback_terminal,'from_original',None))
      and callable(getattr(rollback_terminal,'from_reversed',None)),'all-owning-consumers-before-SQL')
  self.reservation=reservation;self.reader=reservation.reader;self.modules=modules
  self.start_journal=Path(start_journal);self.commit_journal=Path(commit_journal)
  self.thread=threading.get_ident();self.phase='prepared';self.start=None;self.sql_commit=None;self.terminal=None
  self.identity=(id(reservation),id(self.reader),reservation.core,self.thread)
  self.core=self._core();self._seal()
 def _core(self):return hashlib.sha256(json.dumps([self.identity,str(self.start_journal),str(self.commit_journal),*[id(m) for m in self.modules]],separators=(',',':')).encode()).hexdigest()
 def _seal(self):_SEALS[self]=(self.core,self.phase,id(self.start),id(self.sql_commit),id(self.terminal))
 def _life(self):
  check(self._core()==self.core and _SEALS.get(self)==(self.core,self.phase,id(self.start),id(self.sql_commit),id(self.terminal)),'immutable-aggregate-state')
  check(self.identity==(id(self.reservation),id(self.reader),self.reservation.core,threading.get_ident()),'same-owning-aggregate-lifetime')
 def execute(self):
  self._life();check(self.phase=='prepared','single-owning-five-execution')
  self.phase='staging';self._seal();self.reservation.stage_all();self.phase='staged';self._seal()
  self.start=self.modules[1].prepare_existing(self.reader,self.reservation,self.start_journal,self.commit_journal)
  self.phase='SQL-opening';self._seal();self.start.open_pending();self.start.close_pending();self.phase='SQL-pending';self._seal()
  if self.start.sql.mode=='wal':
   check(callable(getattr(self.modules[2],'from_pending_wal',None)) and self.start.wal_phase is self.reader.wal_phase,'exact-owning-WAL-commit-factory')
   self.sql_commit=self.modules[2].from_pending_wal(self.start.sql,self.reader,self.reservation,self.start.wal_phase)
  else:self.sql_commit=self.modules[2].from_pending(self.start.sql,self.reader,self.reservation)
  self._seal()
  check(type(self.sql_commit) is self.modules[2].ReaderSQLCommit,'exact-owning-reader-COMMIT')
  self.sql_commit.commit();self.phase='SQL-committed';self._seal()
  for preparation in self.reservation.batch.preparations:preparation.consume(self.reservation)
  self.phase='sources-retained';self._seal()
  if self.start.sql.mode=='wal':
   self.sql_commit.close_owned_connection()
  self.terminal=self.modules[3].from_retired(self.reservation,self.sql_commit)
  # The terminal owns both successor hold and original marker transitions.
  # No ordinary Writer acquisition or boolean pending exemption occurs here.
  self._seal();result=self.terminal.clear();self.phase='terminal';self._seal();return result
 def rollback(self):
  self._life()
  check(self.phase in ('staging','staged','SQL-opening','SQL-pending','SQL-committed','sources-retained'),'owned-five-rollback-phase')
  reversed_commit=False
  if self.sql_commit is not None:
   check(self.sql_commit.phase=='committed','uncertain-COMMIT-retains-marker-and-custody')
   self.sql_commit.reverse();reversed_commit=True
   if self.start.sql.mode=='wal':
    self.sql_commit.close_owned_connection()
  elif self.start is not None and self.start.sql is not None:
   # Owned still-open SQL rollback cannot authorize a committed DB restore.
   check(self.start.sql.pending is not None,'uncertain-first-body-retains-marker-and-connection')
   self.start.close_pending();self.start.sql.rollback_owned();self.reader.accept_uncommitted_rollback(self.start.sql,self.reservation)
  elif self.start is not None and hasattr(self.start,'connection'):
   raise Held('SQL-opening-uncertainty-marker-and-owned-connection-retained')
  self.reservation.rollback_staging()
  if not reversed_commit and self.start is not None and self.start.sql is not None and self.start.sql.mode=='wal':
   self.start.close_original_wal()
  self.phase='rolled-back';self._seal()
  module=self.modules[4]
  self.terminal=module.from_reversed(self.reservation,self.sql_commit) if reversed_commit else module.from_original(self.reservation,self.reader)
  self._seal();result=self.terminal.clear();self.phase='rollback-terminal';self._seal();return result

def from_staged_preparation(reservation,start_journal,commit_journal):
 modules=tuple(installed(n) for n in ('publication_negative_batch_transition','publication_reader_sql_start','publication_reader_sql_commit','publication_negative_batch_terminal','publication_negative_batch_rollback_terminal'))
 return NegativeReaderAggregate(_KEY,reservation,start_journal,commit_journal,modules)
if __name__=='__main__':print(json.dumps(dict(executable=False,installed=False,publication_acceptance=False,missing='owning installed lifecycle/admission factories, durable terminal successor guard and selected-runtime/NFS acceptance')))
