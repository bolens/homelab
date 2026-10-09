"""Real disposable catalog/Writer, SQLite reader pairs and Linux filesystem exchange.
Host SDK/lifecycle origin substitution is explicit, not installed authority proof.
"""
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import types
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parent
sys.path.insert(0,str(SOURCE))
import publication_archive_owned as o
import test_publication_archive_owned as native
pkg=types.ModuleType('mylar');pkg.__path__=[str(SOURCE)];sys.modules['mylar']=pkg
sys.modules['mylar.publication_archive_owned']=o
HERE=Path(__file__).parent

def load(name):
 spec=importlib.util.spec_from_file_location('mylar.'+name,HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
r=load('publication_archive_reader');a=load('publication_archive_adoption');d=load('publication_archive_dispatch')

class Stopped:
 def __init__(self,cfg,restore,source):self.config_root=cfg;self.restore_root=restore;self.main=cfg/'database.sqlite';self.tasks=cfg/'tasks.sqlite';self.source=source;self.runtime={'fixture_only':True};self.running=False
 def revalidate_stopped(self):o.check(not self.running,'fixture-reader-running')
 def native_url(self,source):o.check(source==self.source,'fixture-mapping');return source.as_uri()
 def vectors(self):return {},o.ancestors([self.main,self.tasks,self.restore_root]),set()

class Tests(unittest.TestCase):
 def setUp(self):
  self.c=native.Controls('runTest');self.c.setUp();self.addCleanup(self.c.doCleanups)
  for module in (r,a):
   origin=patch.object(module,'installed');origin.start();self.addCleanup(origin.stop)
  self.patch=patch.object(r,'lifecycle',return_value=types.SimpleNamespace(StoppedReaderCustody=Stopped));self.patch.start();self.addCleanup(self.patch.stop)
  self.base=self.c.library.parent;self.cfg=self.base/'reader-config';self.cfg.mkdir(mode=0o700);self.restore=self.base/'reader-restore';self.restore.mkdir(mode=0o700);self.scratch=self.base/'reader-scratch';self.scratch.mkdir(mode=0o700);self.retention=self.base/'retention';self.retention.mkdir(mode=0o700)
  for name in ('database.sqlite','tasks.sqlite'):
   with sqlite3.connect(self.cfg/name) as db:
    db.execute('CREATE TABLE BOOK (ID TEXT, URL TEXT, DELETED_DATE TEXT)');db.execute('CREATE TABLE refs (BOOK_ID TEXT, USER_ID TEXT, PAGE INTEGER, opaque BLOB)');db.execute('CREATE TABLE MEDIA (BOOK_ID TEXT, STATUS TEXT, PAGE_COUNT INTEGER)');db.execute('CREATE TABLE MEDIA_PAGE (BOOK_ID TEXT, NUMBER INTEGER, FILE_NAME TEXT)')
    if name=='database.sqlite':
     db.executemany('INSERT INTO BOOK VALUES (?,?,?)',[('active',self.c.source.as_uri(),None),('deleted',self.c.source.as_uri(),'old')]);db.execute('INSERT INTO refs VALUES (?,?,?,?)',('active','other-user',7,b'opaque'));db.execute("INSERT INTO MEDIA VALUES ('active','READY',1)");db.execute("INSERT INTO MEDIA_PAGE VALUES ('active',0,'Folder/page01.jpg')")
   (self.restore/name).write_bytes((self.cfg/name).read_bytes())
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute('ALTER TABLE issues ADD COLUMN ComicSize TEXT');db.execute('UPDATE issues SET ComicSize=?',(str(self.c.source.stat().st_size),))
  self.life=Stopped(self.cfg,self.restore,self.c.source);self.original=self.c.source.read_bytes()
  self.hold=self.c.writer.hold();self.hold.__enter__();self.addCleanup(self.hold.__exit__,None,None,None)
 def lease(self):return r.from_stopped(self.life,self.c.source,self.scratch)
 def cap(self):
  self.prep=self.c.prepare();self.reader=self.lease();return a.prepare_existing(self.prep,self.reader,self.retention)
 def test_late_custody_cannot_refresh_reader_baseline(self):
  for method in ('close','binding'):
   for mutation in ('mode','samebytes'):
    with self.subTest(method=method,mutation=mutation):
     lease=self.lease();db=self.life.main;real=self.life.revalidate_stopped;fired=[]
     def late():
      real()
      if not fired:
       if mutation=='mode':db.chmod(0o640)
       else:
        replacement=db.with_name('replaced.sqlite');replacement.write_bytes(db.read_bytes());os.replace(replacement,db)
       lease._pairs[db]=r.pair(db,lease.deadline);lease._files[db]=o.signature(db);fired.append(True)
     with patch.object(self.life,'revalidate_stopped',side_effect=late),self.assertRaises(o.Held):
      if method=='close':lease.close()
      else:lease.binding
     self.assertTrue(fired)

 def test_connected_install_and_reverse(self):
  cap=self.cap();x=cap.install();self.assertTrue(x['native_archive_installed']);self.assertFalse(x['publication_acceptance']);self.assertNotEqual(self.c.source.read_bytes(),self.original)
  self.assertTrue((self.c.writer.root/a.PENDING).exists());cap.reverse();self.assertEqual(self.c.source.read_bytes(),self.original);self.assertEqual(cap.binding['phase'],'reversed')
 def test_all_reader_refs_and_deleted_ids_retained(self):
  lease=self.lease();self.assertEqual(len(lease.binding['book_rows']),2);self.assertIn('refs',lease._observations[str(self.life.main)]['tables'])
 def test_reader_any_user_progress_change_holds(self):
  lease=self.lease()
  with sqlite3.connect(self.life.main) as db:db.execute('UPDATE refs SET PAGE=8')
  with self.assertRaises(o.Held):lease.revalidate()
 def test_reader_unrelated_tasks_change_holds(self):
  lease=self.lease()
  with sqlite3.connect(self.life.tasks) as db:db.execute("INSERT INTO BOOK VALUES ('foreign','file:///x',NULL)")
  with self.assertRaises(o.Held):lease.close()
 def test_reader_running_holds(self):
  self.life.running=True
  with self.assertRaises(o.Held):self.lease()
 def test_reader_restore_changed_holds(self):
  with sqlite3.connect(self.restore/'database.sqlite') as db:db.execute('UPDATE refs SET PAGE=999')
  with self.assertRaises(o.Held):self.lease()
 def test_missing_exact_reader_url_holds(self):
  with sqlite3.connect(self.life.main) as db:db.execute("UPDATE BOOK SET URL='file:///foreign'")
  (self.restore/'database.sqlite').write_bytes(self.life.main.read_bytes())
  with self.assertRaises(o.Held):self.lease()
 def test_reader_missing_WAL_companion_holds(self):
  Path(str(self.life.main)+'-wal').write_bytes(b'bad')
  with self.assertRaises(o.Held):self.lease()
 def test_reader_hot_journal_holds(self):
  Path(str(self.life.main)+'-journal').write_bytes(b'bad')
  with self.assertRaises(o.Held):self.lease()
 def test_reader_linked_database_holds(self):
  p=self.life.main;q=p.with_name('real');p.rename(q);p.symlink_to(q)
  with self.assertRaises(o.Held):self.lease()
 def test_reader_same_bytes_inode_change_holds(self):
  lease=self.lease();p=self.life.main;q=p.with_name('replacement');q.write_bytes(p.read_bytes());os.replace(q,p)
  with self.assertRaises(o.Held):lease.close()
 def test_reader_mutable_baseline_reseal_holds(self):
  lease=self.lease();lease._pairs={}
  with self.assertRaises(o.Held):lease.close()
 def test_native_source_changed_holds_before_exchange(self):
  cap=self.cap();self.c.source.write_bytes(b'foreign')
  with self.assertRaises(o.Held):cap.install()
  self.assertFalse((self.c.writer.root/a.PENDING).exists())
 def test_native_catalog_other_row_change_holds(self):
  cap=self.cap()
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("UPDATE issues SET ComicSize='999999'")
  with self.assertRaises(o.Held):cap.install()
 def test_native_negative_terminal_holds(self):
  prep=self.c.prepare();lease=self.lease();(self.c.writer.root/a.OTHER_PENDING[1]).write_bytes(b'{}')
  with self.assertRaises((o.Held,self.c.modules[2].Unavailable)):a.prepare_existing(prep,lease,self.retention)
 def test_retention_in_library_holds(self):
  prep=self.c.prepare();lease=self.lease();p=self.c.library/'private';p.mkdir(mode=0o700)
  with self.assertRaises(o.Held):a.prepare_existing(prep,lease,p)
 def test_exclusive_operation_holds(self):
  cap=self.cap()
  with self.assertRaises(o.Held):a.prepare_existing(self.prep,self.reader,self.retention)
  self.assertEqual(cap._phase,'prepared')
 def test_lost_exchange_ACK_retains_marker_no_replay(self):
  cap=self.cap();real=a.exchange
  def lost(*args):real(*args);raise OSError('lost')
  with patch.object(a,'exchange',side_effect=lost),self.assertRaises(o.Held):cap.install()
  self.assertTrue((self.c.writer.root/a.PENDING).exists());self.assertEqual(cap._phase,'uncertain')
  with self.assertRaises(o.Held):cap.install()
  self.assertEqual(cap.uncertain_status()['outcome'],'held-after-swap-before-catalog')
 def test_journal_unknown_child_holds(self):
  cap=self.cap();(cap.journal/'foreign.json').write_text('{}')
  with self.assertRaises(o.Held):cap.install()
 def test_reader_late_lifecycle_callback_holds(self):
  lease=self.lease();real=self.life.revalidate_stopped
  def drift():real();os.chmod(self.life.main,0o640)
  with patch.object(self.life,'revalidate_stopped',side_effect=drift),self.assertRaises(o.Held):lease.close()
 def test_table_transition_changes_only_catalog_size(self):
  with sqlite3.connect(self.c.controller.native_database) as db:before=a.snapshot(db,__import__('time').monotonic()+20)
  after=a.transition(before,self.c.owner,999);self.assertNotEqual(before,after);self.assertEqual(before['schema'],after['schema']);self.assertEqual(before['tables']['comics'],after['tables']['comics'])
 def test_reader_coherent_WAL_and_all_reference_restore(self):
  db=sqlite3.connect(self.life.main);self.addCleanup(db.close);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA wal_autocheckpoint=0');db.execute("UPDATE refs SET opaque=?",(b'new WAL reference',));db.commit()
  for suffix in ('','-wal','-shm'):(self.restore/('database.sqlite'+suffix)).write_bytes(Path(str(self.life.main)+suffix).read_bytes())
  lease=self.lease();lease.revalidate();self.assertIn(self.life.main.with_name('database.sqlite-wal'),lease._pairs[self.life.main])
 def test_late_reader_pair_callback_cannot_add_sidecar(self):
  lease=self.lease();real=r.pair
  def late(*args):
   result=real(*args);Path(str(self.life.main)+'-journal').write_bytes(b'foreign');return result
  with patch.object(r,'pair',side_effect=late),self.assertRaises(o.Held):lease.close()
 def test_late_native_hash_callback_adds_catalog_alias(self):
  cap=self.cap();real=o.fact;claim=self.c.library/'shadow.cbz'
  # A previously missing catalog spelling must remain absent after hashing.
  cap._claims[claim]=None;cap._seal()
  def late(path,*args):
   value=real(path,*args)
   if Path(path)==cap.stage and not claim.exists():claim.symlink_to(cap.source)
   return value
  with patch.object(o,'fact',side_effect=late),self.assertRaises((o.Held,self.c.modules[2].Unavailable)):cap.close()
 def test_late_journal_census_new_child_holds(self):
  cap=self.cap();real=os.listdir
  def late(path):
   value=real(path)
   if Path(path)==cap.journal:(cap.journal/'late.json').write_text('{}')
   return value
  with patch.object(os,'listdir',side_effect=late),self.assertRaises(o.Held):cap.close()
 def test_reverse_foreign_reader_change_does_not_overwrite(self):
  cap=self.cap();cap.install();installed=self.c.source.read_bytes()
  with sqlite3.connect(self.life.main) as db:db.execute('UPDATE refs SET PAGE=100')
  with self.assertRaises(o.Held):cap.reverse()
  self.assertEqual(self.c.source.read_bytes(),installed)
 def test_reverse_foreign_native_change_does_not_overwrite(self):
  cap=self.cap();cap.install();installed=self.c.source.read_bytes()
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("UPDATE issues SET ComicSize='999999'")
  with self.assertRaises(o.Held):cap.reverse()
  self.assertEqual(self.c.source.read_bytes(),installed)
 def test_rejected_current_owner_never_mints(self):
  # Existing real owning preparation policy controls independently cover rejected
  # census; the consumer cannot manufacture preparation out of a serialized body.
  with self.assertRaises(o.Held):a.prepare_existing({'owner':self.c.owner},self.lease(),self.retention)
 def test_ready_reader_page_names_must_equal_owned_inventory(self):
  with sqlite3.connect(self.life.main) as db:db.execute("UPDATE MEDIA_PAGE SET FILE_NAME='foreign.jpg'")
  (self.restore/'database.sqlite').write_bytes(self.life.main.read_bytes());prep=self.c.prepare()
  with self.assertRaises(o.Held):a.prepare_existing(prep,self.lease(),self.retention)
 def test_unavailable_reader_MEDIA_holds_before_mutation(self):
  with sqlite3.connect(self.life.main) as db:db.execute("UPDATE MEDIA SET STATUS='ERROR'")
  (self.restore/'database.sqlite').write_bytes(self.life.main.read_bytes())
  with self.assertRaises(o.Held):self.lease()
 def test_ambiguous_active_book_URL_holds(self):
  with sqlite3.connect(self.life.main) as db:db.execute("UPDATE BOOK SET DELETED_DATE=NULL")
  (self.restore/'database.sqlite').write_bytes(self.life.main.read_bytes())
  with self.assertRaises(o.Held):self.lease()
 def test_reader_nonfinite_page_order_holds(self):
  with sqlite3.connect(self.life.main) as db:db.execute('UPDATE MEDIA_PAGE SET NUMBER=9')
  (self.restore/'database.sqlite').write_bytes(self.life.main.read_bytes())
  with self.assertRaises(o.Held):self.lease()
 def test_queue_is_durable_review_not_capability(self):
  import workflow_store
  request={'version':1,'action':'request-archive-repair-adoption','owner':self.c.owner,'operation_id':'d'*64}
  with patch.object(d,'_store',side_effect=lambda c:workflow_store.Store(c.root,existing_only=True)):
   result=d.dispatch(self.c.controller,self.c.writer,request)
   self.assertEqual(result['outcome'],'queued-review');self.assertFalse(result['mutation_authority']);self.assertTrue(result['root_scoped_child_required'])
   with self.assertRaises(o.Held):d.dispatch(self.c.controller,self.c.writer,request)
   result=d.dispatch(self.c.controller,self.c.writer,dict(request,action='archive-repair-adoption-status'));self.assertEqual(result['outcome'],'queued-review')
 def test_queue_forbids_caller_path_witness(self):
  body={'version':1,'action':'request-archive-repair-adoption','owner':self.c.owner,'operation_id':'e'*64,'source':str(self.c.source)}
  with self.assertRaises(o.Held):d.dispatch(self.c.controller,self.c.writer,body)
 def test_consumer_does_not_accept_saved_receipt(self):
  with self.assertRaises(o.Held):d.verify_existing({'phase':'installed','mutation_authority':True})
 def test_connected_complete_exact_refs_no_general_publication_grant(self):
  cap=self.cap();cap.install();result=d.complete_existing(cap);self.assertTrue(result['repair_accepted']);self.assertFalse(result['publication_acceptance']);self.assertFalse((self.c.writer.root/a.PENDING).exists());self.assertFalse((self.c.writer.root/a.TERMINAL).exists())
 def test_complete_reader_drift_keeps_marker(self):
  cap=self.cap();cap.install()
  with sqlite3.connect(self.life.main) as db:db.execute('UPDATE refs SET PAGE=9')
  with self.assertRaises(o.Held):cap.complete()
  self.assertTrue((self.c.writer.root/a.PENDING).exists())
 def test_lost_terminal_unlink_ACK_restores_successor(self):
  cap=self.cap();cap.install();real=os.unlink
  def lost(path,*args,**kw):
   result=real(path,*args,**kw)
   if path==a.TERMINAL:raise OSError('lost response')
   return result
  with patch.object(os,'unlink',side_effect=lost),self.assertRaises(o.Held):cap.complete()
  self.assertTrue((self.c.writer.root/a.TERMINAL).exists());self.assertEqual(cap._phase,'uncertain')
 def test_actual_SQLite_foreign_samebytes_open_holds_before_effect(self):
  cap=self.cap();foreign=self.base/'foreign.db';foreign.write_bytes(self.c.controller.native_database.read_bytes());raw=foreign.read_bytes();real=sqlite3.connect
  def alias(path,*args,**kw):
   if str(path)==self.c.controller.native_database.as_uri()+'?mode=rw':return real(foreign.as_uri()+'?mode=rw',*args,**kw)
   return real(path,*args,**kw)
  with patch.object(sqlite3,'connect',side_effect=alias),self.assertRaises(o.Held):cap.install()
  self.assertEqual(foreign.read_bytes(),raw);self.assertEqual(self.c.source.read_bytes(),self.original)
 def test_production_uninstalled_module_origin_holds(self):
  # The actual source of the check is compiled without mocking its body.
  source=(HERE/'publication_archive_adoption.py').read_text();tree=__import__('ast').parse(source);node=next(x for x in tree.body if isinstance(x,__import__('ast').FunctionDef) and x.name=='installed');ns={'Path':Path,'__file__':str(HERE/'publication_archive_adoption.py'),'reader':r,'o':o};exec(compile(__import__('ast').Module(body=[node],type_ignores=[]),'<origin>','exec'),ns)
  with self.assertRaises(o.Held):ns['installed']()
 def test_last_exchange_parent_callback_cannot_replace_foreign_source(self):
  cap=self.cap();real=o.directory_fd;fired=False
  from contextlib import contextmanager
  @contextmanager
  def late(path,*args):
   nonlocal fired
   with real(path,*args) as fd:
    if Path(path)==cap.stage.parent and not fired and cap._phase=='prepared' and (self.c.writer.root/a.PENDING).exists():
     fired=True;cap.source.write_bytes(b'foreign operator bytes')
    yield fd
  with patch.object(o,'directory_fd',side_effect=late),self.assertRaises(o.Held):cap.install()
  self.assertTrue(fired);self.assertEqual(cap.source.read_bytes(),b'foreign operator bytes')
 def test_actual_CRC_bad_original_cannot_prepare_or_swap(self):
  raw=self.c.source.read_bytes();self.c.source.write_bytes(raw.replace(b'page one',b'page BAD'))
  with self.assertRaises(o.Held):self.cap()
  self.assertFalse((self.c.writer.root/a.PENDING).exists())
 def test_actual_native_COMMIT_lost_ACK_passive_no_replay(self):
  cap=self.cap();real=a.connect_existing
  class Connection:
   def __init__(self,db):self.db=db
   def __getattr__(self,k):return getattr(self.db,k)
   def commit(self):self.db.commit();raise OSError('lost commit response')
  with patch.object(a,'connect_existing',side_effect=lambda *args:Connection(real(*args))),self.assertRaises(o.Held):cap.install()
  result=cap.uncertain_status();self.assertEqual(result['outcome'],'held-after-swap-and-catalog');self.assertFalse(result['automatic_replay']);self.assertTrue((self.c.writer.root/a.PENDING).exists())
 def test_no_generic_ctor_grant(self):
  with self.assertRaises(o.Held):r.RepairReaderLease(None,None,None,None,None,None,None,None,None,None,None)
 def test_no_arbitrary_reader_token(self):
  with self.assertRaises(o.Held):a.prepare_existing({},self.lease(),self.retention)

class BoundaryV2(unittest.TestCase):
 setUp=Tests.setUp
 lease=Tests.lease
 cap=Tests.cap
 def test_last_exchange_fd_shadow_holds_before_exchange(self):
  from contextlib import contextmanager
  import inspect
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("INSERT INTO issues VALUES ('777','456','late.cbz','Wanted','0')")
  cap=self.cap();shadow=self.c.library/'late.cbz';real=o.directory_fd;fired=[]
  @contextmanager
  def late(path,*args):
   with real(path,*args) as fd:
    if Path(path)==cap.stage.parent and any(x.function=='exchange' for x in inspect.stack()) and not fired:fired.append(True);shadow.symlink_to(cap.source)
    yield fd
  with patch.object(o,'directory_fd',late),self.assertRaises(o.Held):cap.install()
  self.assertTrue(fired);self.assertEqual(self.c.source.read_bytes(),self.original)
 def test_last_complete_direct_shadow_retains_successor(self):
  import inspect
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("INSERT INTO issues VALUES ('777','456','late.cbz','Wanted','0')")
  cap=self.cap();cap.install();real=a.direct;count=[];shadow=self.c.library/'late.cbz'
  def late(*args):
   real(*args)
   if cap._phase=='complete' and any(x.function=='binding' for x in inspect.stack()):
    count.append(1)
    if len(count)==2:shadow.symlink_to(cap.source)
  with patch.object(a,'direct',late),self.assertRaises(o.Held):cap.complete()
  self.assertEqual(len(count),2);self.assertTrue((self.c.writer.root/a.TERMINAL).exists())
 def test_lifecycle_tuple_absence_interface(self):
  real=self.life.vectors
  def vectors():
   f,n,x=real();return f,n,tuple(x)
  with patch.object(self.life,'vectors',vectors):self.assertEqual(self.lease().binding['active_book_id'],'active')
 def test_last_sql_body_shadow_holds_without_catalog_commit(self):
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("INSERT INTO issues VALUES ('777','456','late.cbz','Wanted','0')")
  cap=self.cap();real=a._set_size;shadow=self.c.library/'late.cbz';fired=[]
  def late(*args):real(*args);shadow.symlink_to(cap.source);fired.append(True)
  with patch.object(a,'_set_size',late),self.assertRaises(o.Held):cap.install()
  self.assertTrue(fired)
  with sqlite3.connect(self.c.controller.native_database) as db:self.assertEqual(db.execute("SELECT ComicSize FROM issues WHERE IssueID='123'").fetchone()[0],str(len(self.original)))

class FreshVerifierV2(unittest.TestCase):
 setUp=Tests.setUp
 lease=Tests.lease
 cap=Tests.cap
 def verify(self):
  self.v=load('publication_archive_verifier');baseline=self.op/'journal'/'baseline.json';real=self.life.vectors
  def bound():
   f,n,x=real();f[baseline]=o.signature(baseline);return f,n,tuple(x)
  with patch.object(self.v,'installed'),patch.object(self.life,'vectors',bound):return self.v.verify_existing(self.c.controller,self.c.writer,self.life,baseline,self.scratch)
 def installed_cap(self):
  cap=self.cap();cap.install();cap.complete();self.op=cap.root;return cap
 def test_independent_fresh_successful_verifier(self):
  self.installed_cap();result=self.verify();self.assertTrue(result['reader_reference_preservation']);self.assertFalse(result['mutation_authority'])
 def test_fresh_verifier_wrong_catalog_cell_holds(self):
  self.installed_cap()
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("UPDATE issues SET ComicSize='999999'")
  with self.assertRaises(o.Held):self.verify()
 def test_fresh_verifier_changed_reader_reference_holds(self):
  self.installed_cap()
  with sqlite3.connect(self.life.main) as db:db.execute('UPDATE refs SET PAGE=444')
  with self.assertRaises(o.Held):self.verify()
 def test_fresh_verifier_changed_original_custody_holds(self):
  self.installed_cap();original=Path(self.prep._binding['custody']['original']['path']);original.write_bytes(b'x'+original.read_bytes()[1:])
  with self.assertRaises(o.Held):self.verify()
 def test_fresh_verifier_pending_marker_holds(self):
  self.installed_cap();(self.c.writer.root/a.TERMINAL).write_bytes(b'{}')
  with self.assertRaises((o.Held,self.c.modules[2].Unavailable)):self.verify()
 def test_fresh_verifier_unbound_baseline_holds(self):
  self.installed_cap();v=load('publication_archive_verifier')
  with patch.object(v,'installed'),self.assertRaises(o.Held):v.verify_existing(self.c.controller,self.c.writer,self.life,self.op/'journal'/'baseline.json',self.scratch)

class FreshVerifierBoundaryV2(unittest.TestCase):
 setUp=Tests.setUp
 lease=Tests.lease
 cap=Tests.cap
 verify=FreshVerifierV2.verify
 installed_cap=FreshVerifierV2.installed_cap
 # Declared below as an independent class to avoid duplicate inherited controls.
 def test_final_direct_callback_claim_alias_holds(self):
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("INSERT INTO issues VALUES ('777','456','late.cbz','Wanted','0')")
  self.installed_cap();real=r.direct;shadow=self.c.library/'late.cbz';count=[]
  import inspect
  def late(*args):
   real(*args)
   if inspect.stack()[1].function=='verify_existing':
    count.append(1)
    if len(count)==2:shadow.symlink_to(self.c.source)
  with patch.object(r,'direct',late),self.assertRaises(o.Held):self.verify()
  self.assertEqual(len(count),2)
 def test_last_sdk_callback_companion_holds(self):
  self.installed_cap();real=o.catalog;count=[]
  def late(*args):
   result=real(*args);count.append(1)
   if len(count)==2:Path(str(self.c.controller.native_database)+'-wal').write_bytes(b'foreign')
   return result
  with patch.object(o,'catalog',late),self.assertRaises(o.Held):self.verify()
  self.assertEqual(len(count),2)

class RawClosureV3(unittest.TestCase):
 setUp=Tests.setUp
 lease=Tests.lease
 cap=Tests.cap
 def test_last_exchange_encoding_helper_reader_mode_holds_before_swap(self):
  cap=self.cap();real=os.fsencode;fired=[]
  import inspect
  def late(value):
   result=real(value)
   if inspect.stack()[1].function=='exchange' and value==cap.stage.name and not fired:fired.append(True);self.life.main.chmod(0o640)
   return result
  with patch.object(os,'fsencode',late),self.assertRaises(o.Held):cap.install()
  self.assertTrue(fired);self.assertEqual(self.c.source.read_bytes(),self.original)
 def test_last_precommit_fd_helper_reader_mode_holds_without_catalog_commit(self):
  cap=self.cap();real=a._valid_fd;fired=[]
  def late(fd):
   result=real(fd)
   if not fired:fired.append(True);self.life.main.chmod(0o640)
   return result
  with patch.object(a,'_valid_fd',late),self.assertRaises(o.Held):cap.install()
  self.assertTrue(fired);self.assertEqual(cap._phase,'uncertain')
  with sqlite3.connect(self.c.controller.native_database) as db:self.assertEqual(db.execute("SELECT ComicSize FROM issues WHERE IssueID='123'").fetchone()[0],str(len(self.original)))
 def test_binding_copy_callback_claim_holds_and_retains_successor(self):
  with sqlite3.connect(self.c.controller.native_database) as db:db.execute("INSERT INTO issues VALUES ('777','456','late.cbz','Wanted','0')")
  cap=self.cap();cap.install();real=a.copy.deepcopy;fired=[];shadow=self.c.library/'late.cbz'
  import inspect
  def late(value,*args,**kw):
   result=real(value,*args,**kw)
   if cap._phase=='complete' and inspect.stack()[1].function=='binding' and not fired:fired.append(True);shadow.symlink_to(self.c.source)
   return result
  with patch.object(a.copy,'deepcopy',late),self.assertRaises(o.Held):cap.complete()
  self.assertTrue(fired);self.assertTrue((self.c.writer.root/a.TERMINAL).exists())
 def test_postcommit_failed_reader_proof_is_uncertain(self):
  cap=self.cap();real=o.fact;fired=[]
  import inspect
  def late(path,*args):
   result=real(path,*args)
   if Path(path)==cap.source and cap.source.read_bytes()!=self.original and inspect.stack()[1].function=='_change' and not fired:fired.append(True);self.life.main.chmod(0o640)
   return result
  with patch.object(o,'fact',late),self.assertRaises(o.Held):cap.install()
  self.assertTrue(fired);self.assertEqual(cap._phase,'uncertain');self.assertTrue((self.c.writer.root/a.PENDING).exists())

if __name__=='__main__':unittest.main()
