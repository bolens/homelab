"""Stopped-reader disk mechanics proposal; operational admission is not installed.

Only disposable fixture admissions can currently be minted. No CLI opens a DB.
"""
from contextlib import closing
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import threading
import time

KERNEL_SHA='560b4ef9d3ed609af1f0dedb261c031e54fcae0a34e0ef8e297973fed735d9b5'
k=importlib.import_module('mylar.publication_reader_softdelete')
KERNEL=Path(k.__file__)
if KERNEL.parent!=Path('/app/mylar3/mylar') or KERNEL.resolve()!=KERNEL or hashlib.sha256(KERNEL.read_bytes()).hexdigest()!=KERNEL_SHA:
 raise RuntimeError('installed checked reader kernel')
Held=k.Held
_KEY=object()
def check(v,s):
 if not v:raise Held(s)
def sig(p):
 s=os.lstat(p);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
def canonical(p):
 p=Path(p);check(p.is_absolute() and p.resolve()==p and not any(q.is_symlink() for q in (p,*p.parents)),'canonical');return p
def parents(paths):
 return {q:tuple(sig(q)[i] for i in (0,1,5,6,7)) for p in paths for q in canonical(p).parents}
def close_parents(v):
 for p,s in v.items():check(tuple(sig(p)[i] for i in (0,1,5,6,7))==s,'ancestor drift')
def pair(db):
 check(not os.path.lexists(str(db)+'-journal'),'hot journal held')
 deadline=time.monotonic()+30
 result={}
 for suffix in ('','-wal','-shm'):
  p=Path(str(db)+suffix)
  if os.path.lexists(p):
   canonical(p);s=sig(p);check(stat.S_ISREG(s[5]) and s[8]==1 and s[2]<=1024**3,'pair regular')
   h=hashlib.sha256()
   with p.open('rb') as f:
    for b in iter(lambda:f.read(1024**2),b''):
     check(time.monotonic()<=deadline,'pair deadline');h.update(b)
   check(sig(p)==s,'pair drift');result[suffix]={'signature9':s,'sha256':h.hexdigest(),'xattrs':{n:os.getxattr(p,n).hex() for n in sorted(os.listxattr(p))}}
 check('' in result and (('-wal' in result)==('-shm' in result)),'coherent pair')
 return result
def emit(root,name,value):
 raw=k.encode(value);p=root/name
 with os.fdopen(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 fd=os.open(root,os.O_DIRECTORY|os.O_RDONLY);os.fsync(fd);os.close(fd)
 check(p.read_bytes()==raw,'intended receipt');return {'path':p,'signature9':sig(p),'sha256':hashlib.sha256(raw).hexdigest()}

def master(conn):return list(conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'))
def book_rows(conn,plan):
 ids=list(plan['before_rows']);q='SELECT '+','.join(k.quote(x) for x in k.COLUMNS)+' FROM BOOK WHERE ID IN ('+','.join('?' for _ in ids)+')'
 return {r[0]:k.row_encode(r) for r in conn.execute(q,ids)}
def connect(db):
 conn=sqlite3.connect(db.as_uri()+'?mode=rw',uri=True,timeout=0)
 conn.execute('PRAGMA foreign_keys=ON');conn.execute('PRAGMA trusted_schema=OFF')
 until=time.monotonic()+30;conn.set_progress_handler(lambda:int(time.monotonic()>until),1000);return conn
def healthy(conn):
 check(conn.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'integrity')
 check(not conn.execute('PRAGMA foreign_key_check').fetchall(),'foreign keys')

def observe_copy(db,plan,scratch):
 baseline=pair(db)
 with tempfile.TemporaryDirectory(prefix='reader-observation-',dir=scratch) as folder:
  root=Path(folder)
  for suffix,f in baseline.items():
   target=root/(db.name+suffix);shutil.copy2(Path(str(db)+suffix),target)
   check(hashlib.sha256(target.read_bytes()).hexdigest()==f['sha256'],'observation copy')
  check(pair(db)==baseline,'observation source CAS')
  with closing(sqlite3.connect((root/db.name).as_uri()+'?mode=ro',uri=True)) as c:
   c.execute('PRAGMA query_only=ON');c.execute('PRAGMA trusted_schema=OFF');healthy(c)
   result=(master(c),k.snapshot(c),book_rows(c,plan))
  check(pair(db)==baseline,'observation source changed')
 return result

class FixtureStoppedAdmission:
 __slots__=('root','_nodes','_thread','_key','operational')
 def __init__(self,root,key=None):
  check(key is _KEY,'no caller admission');self.root=canonical(root)
  check(self.root.is_relative_to(Path('/tmp')) and self.root.name.startswith('reader-disk-fixture-'),'fixture scope')
  self._nodes=parents([self.root]);self._thread=threading.get_ident();self._key=key;self.operational=False
 def revalidate(self):
  check(self._key is _KEY and threading.get_ident()==self._thread,'admission lifetime');close_parents(self._nodes)
def fixture_admission(root):return FixtureStoppedAdmission(root,_KEY)

def admit_stopped_reader(*args,**kwargs):
 raise Held('Owning fresh stopped-runtime/full-backup/native reservation producer not installed')

class ReaderPreservationReservation:
 __slots__=('_key','_admission','_db','_plan','_schema','_expected','_facts','_nodes','_thread','_used','_evidence','_output_stamp','_custody','_custody_stamp','operation','operational','rollback')
 def __init__(self,key,admission,db,plan,schema,expected,facts,nodes,operation,rollback):
  check(key is _KEY,'reservation mint');self._key=key;self._admission=admission;self._db=db;self._plan=plan;self._schema=schema;self._expected=expected;self._facts=facts;self._nodes=nodes;self._thread=threading.get_ident();self._used=False;self.operation=operation;self.operational=False;self.rollback=rollback
  self._evidence={p:(sig(p),hashlib.sha256(p.read_bytes()).hexdigest()) for p in operation.iterdir() if p.is_file()};self._output_stamp=sig(operation);self._custody=pair(rollback/db.name);self._custody_stamp=sig(rollback)
  check(set(p.name for p in operation.iterdir())=={'intent.json','committed.json','raw-restore'},'closed operation census')
 def revalidate(self):
  check(self._key is _KEY and not self._used and threading.get_ident()==self._thread,'reservation lifetime');self._admission.revalidate();close_parents(self._nodes)
  check(pair(self._db)==self._facts,'committed pair changed')
  observed=observe_copy(self._db,self._plan,self._admission.root)
  check(observed==(self._schema,self._expected,self._plan['after_rows']),'committed preservation changed')
  # SQLite may touch an existing SHM while observing a coherent WAL pair.
  # Require bytes/attrs to be unchanged: operational adapters must serialize readers.
  check(pair(self._db)==self._facts,'observation pair drift');close_parents(self._nodes);self._admission.revalidate()
  for p,(s,h) in self._evidence.items():check(sig(p)==s and hashlib.sha256(p.read_bytes()).hexdigest()==h,'operation evidence drift')
  # Semantic hashes/observations completed; direct namespace/leaf closure follows.
  close_parents(self._nodes)
  for p,(s,h) in self._evidence.items():check(sig(p)==s,'terminal evidence drift')
  check(pair(self.rollback/self._db.name)==self._custody,'rollback custody drift')
  close_parents(self._nodes)
  for p,(s,h) in self._evidence.items():check(sig(p)==s,'last evidence vector')
  for base,facts in ((self._db,self._facts),(self.rollback/self._db.name,self._custody)):
   for suffix,f in facts.items():check(sig(Path(str(base)+suffix))==f['signature9'],'terminal bound pair')
   for suffix in ('-journal','-wal','-shm'):
    if suffix not in facts:check(not os.path.lexists(str(base)+suffix),'terminal companion')
  check(sig(self.rollback)==self._custody_stamp and sig(self.operation)==self._output_stamp,'terminal operation namespace')
  return {'reference_values_retained':True,'selected_source_ids':6,'correct_ids':5,'reference_transfer_verified':False,'mutation_authority':False,'publication_acceptance':False}
 def consume_native(self,preparation):
  from publication_negative_v3 import NativeNegativePreparation
  check(type(preparation) is NativeNegativePreparation,'owning native type')
  preparation.revalidate();self.revalidate()
  raise Held('Fixture reader reservation is not operational authority; native consumer not installed')

def apply_fixture_disk(admission,db,document,manifest,output,hook=None):
 check(type(admission) is FixtureStoppedAdmission and admission._key is _KEY,'typed admission')
 admission.revalidate();db=canonical(db);output=canonical(output)
 check(db.is_relative_to(admission.root) and output.is_relative_to(admission.root) and not db.is_relative_to(output) and not any(output.iterdir()),'owned empty output')
 nodes=parents([db,output,KERNEL]);baseline=pair(db);plan=k.compile_plan(document,manifest)
 # Kernel required final native commit remains a final acceptance requirement,
 # never a fabricated/circular reader PREPARE grant.
 expected_master=[(o['type'],o['name'],o['table'],o['sql']) for o in k.schema_admission(document)['database.sqlite']]
 custody=output/'raw-restore';custody.mkdir(mode=0o700)
 for suffix,fact in baseline.items():
  p=Path(str(db)+suffix);target=custody/(db.name+suffix);shutil.copy2(p,target)
  for name,value in fact['xattrs'].items():os.setxattr(target,name,bytes.fromhex(value))
  check(hashlib.sha256(target.read_bytes()).hexdigest()==fact['sha256'],'raw restore copy')
 check(pair(db)==baseline,'copy source CAS');close_parents(nodes)
 restored=observe_copy(custody/db.name,plan,admission.root)[1]
 with closing(connect(db)) as c:
  check(pair(db)==baseline,'open source CAS');c.execute('BEGIN IMMEDIATE')
  try:
   healthy(c);check(master(c)==expected_master,'exact installed schema');check(book_rows(c,plan)==plan['before_rows'],'eleven row CAS')
   before=k.snapshot(c);check(before==restored,'independent restore logical equality')
   expected=k.snapshot(c,{bid:k.row_decode(plan['after_rows'][bid]) for bid in plan['active_wrong_ids']})
   emit(output,'intent.json',{'phase':'prepared','before':before,'expected':expected,'plan':plan,'baseline_pair':baseline,'live_apply_enabled':False})
   admission.revalidate();check(pair(db)==baseline,'before write source CAS');close_parents(nodes)
   for parameters in plan['parameters']:
    check(c.execute(k.SQL,[k.untyped(v) for v in parameters]).rowcount==1,'active CAS')
   if hook:hook('before_commit',c)
   check(master(c)==expected_master and k.snapshot(c)==expected and book_rows(c,plan)==plan['after_rows'],'all-table preservation')
   healthy(c);admission.revalidate();close_parents(nodes);c.commit()
   if hook:hook('after_commit',c)
  except BaseException:
   if c.in_transaction:c.rollback()
   # Unknown committed result is deliberately not an accepted reservation.
   emit(output,'held.json',{'phase':'held','automatic_replay':False,'publication_acceptance':False})
   raise
 # Connection is closed before observing exact committed pair.
 facts=pair(db)
 observed=observe_copy(db,plan,admission.root)
 check(observed==(expected_master,expected,plan['after_rows']),'postcommit preserved')
 check(pair(db)==facts,'postcommit pair drift');admission.revalidate();close_parents(nodes)
 check(set(p.name for p in output.iterdir())=={'raw-restore','intent.json'},'operation census before commit receipt')
 emit(output,'committed.json',{'phase':'reader-committed','expected':expected,'reference_transfer_verified':False,'live_apply_enabled':False,'publication_acceptance':False})
 return ReaderPreservationReservation(_KEY,admission,db,plan,expected_master,expected,facts,nodes,output,custody)

def reconcile_fixture(admission,db,operation):
 check(type(admission) is FixtureStoppedAdmission,'typed reconciliation');admission.revalidate()
 db=canonical(db);operation=canonical(operation)
 check(db.is_relative_to(admission.root) and operation.is_relative_to(admission.root),'recovery scope')
 intent=json.loads((operation/'intent.json').read_bytes())
 plan=intent['plan'];observed=observe_copy(db,plan,admission.root)[1]
 state='pre-state' if observed==intent['before'] else 'committed-state' if observed==intent['expected'] else 'unknown-state'
 # Recovery observes durable state; no new capability or automatic replay.
 return dict(reconciliation_observed=True,state=state,automatic_replay=False,token_issued=False,mutation_authority=False,publication_acceptance=False)

def rollback_fixture(reservation):
 check(type(reservation) is ReaderPreservationReservation,'typed rollback');reservation.revalidate()
 db=reservation._db;raw=reservation.rollback;check(not reservation._used,'one-shot rollback')
 intended=json.loads((reservation.operation/'intent.json').read_bytes())
 saved=pair(raw/db.name)
 check(saved==reservation._custody,'rollback custody bytes and attributes')
 restored=observe_copy(raw/db.name,reservation._plan,reservation._admission.root)
 check(restored==(reservation._schema,intended['before'],reservation._plan['before_rows']),'rollback custody logical')
 # All potentially expensive custody observations precede renewed current CAS.
 current=pair(db);check(current==reservation._facts,'rollback final current pair CAS')
 reservation._admission.revalidate();close_parents(reservation._nodes)
 check(pair(raw/db.name)==reservation._custody,'rollback final custody CAS')
 for p,(expected,digest) in reservation._evidence.items():
  check(sig(p)==expected and hashlib.sha256(p.read_bytes()).hexdigest()==digest,'rollback evidence CAS')
 # Durable rollback intent exists before first source removal; failed/unknown
 # restoration consumes this fixture reservation and cannot be replayed.
 rollback_value={'phase':'rollback-intent','committed_pair':current,'restored_pair':saved,'automatic_replay':False,'mutation_authority':False}
 rollback_sha=hashlib.sha256(k.encode(rollback_value)).hexdigest()
 rollback_fact=emit(reservation.operation,'rollback-intent.json',rollback_value)
 rollback_path=reservation.operation/'rollback-intent.json'
 check(type(rollback_fact) is dict and rollback_fact['path']==rollback_path and rollback_fact['sha256']==rollback_sha,'rollback bound intent')
 check(sig(rollback_path)==rollback_fact['signature9'] and hashlib.sha256(rollback_path.read_bytes()).hexdigest()==rollback_sha,'rollback intended digest')
 check(set(p.name for p in reservation.operation.iterdir())=={*(p.name for p in reservation._evidence),'raw-restore','rollback-intent.json'},'rollback closed output census')
 operation9=sig(reservation.operation)
 # Pure final incarnation/namespace checks AFTER the last hashes/write callback.
 close_parents(reservation._nodes)
 for p,(expected,digest) in reservation._evidence.items():check(sig(p)==expected,'rollback terminal evidence')
 for base,facts in ((db,current),(raw/db.name,saved)):
  for suffix,fact in facts.items():check(sig(Path(str(base)+suffix))==fact['signature9'],'rollback terminal pair')
  for suffix in ('-journal','-wal','-shm'):
   if suffix not in facts:check(not os.path.lexists(str(base)+suffix),'rollback terminal companion')
 check(sig(rollback_path)==rollback_fact['signature9'],'rollback intent incarnation')
 check(sig(raw)==reservation._custody_stamp and sig(reservation.operation)==operation9,'rollback terminal namespace')
 reservation._used=True
 try:
  for suffix in ('','-wal','-shm'):
   p=Path(str(db)+suffix);retained=raw/(db.name+suffix)
   if p.exists():p.unlink()
   if retained.exists():
    shutil.copy2(retained,p)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
  fd=os.open(db.parent,os.O_DIRECTORY|os.O_RDONLY|os.O_NOFOLLOW)
  try:os.fsync(fd)
  finally:os.close(fd)
  after=pair(db)
  check(set(after)==set(saved),'rollback restored companion census')
  for suffix,fact in after.items():
   origin=intended['baseline_pair'][suffix]
   check(fact['sha256']==origin['sha256'] and fact['xattrs']==origin['xattrs'] and all(fact['signature9'][i]==origin['signature9'][i] for i in (2,3,5,6,7)),'rollback restored attributes')
  observed=observe_copy(db,reservation._plan,reservation._admission.root)
  check(observed==(reservation._schema,intended['before'],reservation._plan['before_rows']),'rollback full tables')
  check(pair(db)==after,'rollback final restored CAS')
  check(set(p.name for p in reservation.operation.iterdir())=={*(p.name for p in reservation._evidence),'raw-restore','rollback-intent.json'},'rollback final output census')
  check(hashlib.sha256(rollback_path.read_bytes()).hexdigest()==rollback_sha,'rollback final intent digest')
  reservation._admission.revalidate();close_parents(reservation._nodes)
  for p,(expected,digest) in reservation._evidence.items():check(sig(p)==expected,'rollback final original evidence')
  check(sig(rollback_path)==rollback_fact['signature9'] and sig(reservation.operation)==operation9,'rollback final intent namespace')
  for suffix,fact in after.items():check(sig(Path(str(db)+suffix))==fact['signature9'],'rollback restored terminal')
  for suffix in ('-journal','-wal','-shm'):
   if suffix not in after:check(not os.path.lexists(str(db)+suffix),'rollback restored companion')
 except BaseException:
  emit(reservation.operation,'rollback-held.json',{'phase':'rollback-held','automatic_replay':False,'mutation_authority':False})
  raise
 return {'fixture_rollback_verified':True,'mutation_authority':False}

if __name__=='__main__':print(json.dumps({'execute':False,'live_apply_enabled':False,'mutation_authority':False}))
