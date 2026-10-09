"""Real temporary existing Writer/private journals, fake HTTP explicitly."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
PUBLIC=Path(os.environ.get('ARCHIVE_REPAIR_FIXTURE_PUBLIC',str(Path(__file__).parent)))
sys.path.insert(0,str(PUBLIC));sys.path.insert(0,str(Path(__file__).parent))
import archive_repair_handoff as m
from media_writer import Writer
class Controls(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.root.chmod(0o700);self.state=self.root/'state';self.state.mkdir(mode=0o700);self.jobs=self.state/'jobs';self.jobs.mkdir(mode=0o700);self.library=self.root/'library';self.library.mkdir();self.source=self.library/'original.cbz';self.source.write_bytes(b'original');self.wroot=self.root/'writer';Writer(self.wroot,create=True)
  self.worker=SimpleNamespace(state=self.state,jobs=self.jobs,roots=[self.library],config={'writer_state':str(self.wroot)});self.owner={'table':'issues','issueid':'123','parentcomicid':'456','releasecomicid':'456'};self.key='a'*64;self.calls=[]
 def response(self,worker,command,**values):
  self.assertIs(worker,self.worker);self.assertEqual(command,'publicationControl');q=json.loads(values['request']);self.calls.append(q);self.assertEqual(set(q),{'version','action','owner','operation_id'});self.assertFalse(getattr(Writer(self.wroot,create=False).local[1],'depth',0));return dict(version=1,operation_id=q['operation_id'],owner=q['owner'],outcome='queued-review',root_scoped_child_required=True,reader_preservation_verified=False,mutation_authority=False,publication_acceptance=False)
 def enqueue(self):return m.enqueue(self.worker,self.owner,self.key)
 def test_queue_then_maintenance_dispatch_status_only(self):
  self.enqueue()
  with patch.object(m,'api',side_effect=self.response):self.assertEqual(m.dispatch(self.worker),1);self.assertEqual(m.dispatch(self.worker),1)
  self.assertEqual([v['action'] for v in self.calls],['request-archive-repair-adoption','archive-repair-adoption-status']);self.assertEqual(self.source.read_bytes(),b'original')
 def test_explicit_status_returns_no_rights(self):
  self.enqueue()
  with patch.object(m,'api',side_effect=self.response):m.dispatch(self.worker);answer=m.status(self.worker,self.owner,self.key)
  self.assertFalse(answer['mutation_authority']);self.assertFalse(answer['publication_acceptance']);self.assertFalse(answer['reader_preservation_verified'])
 def test_durable_attempt_exists_before_HTTP(self):
  self.enqueue()
  def answer(*args,**kwargs):
   self.assertTrue((self.state/'archive-repair-requests'/(self.key+'.attempt.json')).exists());return self.response(*args,**kwargs)
  with patch.object(m,'api',side_effect=answer):m.dispatch(self.worker)
 def test_timeout_retained_no_request_replay(self):
  self.enqueue()
  with patch.object(m,'api',side_effect=TimeoutError):self.assertEqual(m.dispatch(self.worker),0)
  with patch.object(m,'api',side_effect=self.response):m.dispatch(self.worker)
  self.assertEqual([r['action'] for r in self.calls],['archive-repair-adoption-status'])
 def test_round_robin_reaches_jobs_after_first_batch(self):
  expected={format(i,'064x') for i in range(33)}
  for key in sorted(expected):m.enqueue(self.worker,self.owner,key)
  with patch.object(m,'api',side_effect=self.response):
   self.assertEqual(m.dispatch(self.worker),32);self.assertEqual(m.dispatch(self.worker),32)
  self.assertEqual({r['operation_id'] for r in self.calls},expected)
  self.assertEqual(sum(r['action']=='request-archive-repair-adoption' for r in self.calls),33)
 def test_transport_failure_does_not_block_other_jobs_or_maintenance(self):
  self.enqueue();other='b'*64;m.enqueue(self.worker,self.owner,other)
  def response(worker,command,**values):
   if json.loads(values['request'])['operation_id']==self.key:raise TimeoutError
   return self.response(worker,command,**values)
  spec=importlib.util.spec_from_file_location('maintenance_transport',Path(__file__).with_name('maintenance.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);maintenance=module.Maintenance.__new__(module.Maintenance);maintenance.worker=self.worker
  with patch('import_recovery.dispatch_prepared',return_value=2),patch('native_handoff.dispatch',return_value=3),patch.object(m,'api',side_effect=response):self.assertEqual(maintenance.dispatch(),6)
  path=self.state/'archive-repair-requests'
  self.assertTrue((path/(self.key+'.attempt.json')).exists());self.assertFalse((path/(self.key+'.ack.json')).exists());self.assertTrue((path/(other+'.ack.json')).exists())
 def test_no_duplicate_enqueue(self):
  self.enqueue()
  with self.assertRaises(m.Unavailable):self.enqueue()
 def test_status_cannot_create_attempt(self):
  self.enqueue()
  with patch.object(m,'api') as api,self.assertRaises(m.Unavailable):m.status(self.worker,self.owner,self.key)
  api.assert_not_called();self.assertFalse((self.state/'archive-repair-requests'/(self.key+'.attempt.json')).exists())
 def test_invalid_primary_keys_no_journal(self):
  for owner,key in [(dict(self.owner,source='/foreign'),self.key),(self.owner,'../../x'),(dict(self.owner,parentcomicid='99'),self.key)]:
   with self.subTest(owner=owner,key=key),self.assertRaises(m.Unavailable):m.enqueue(self.worker,owner,key)
  self.assertFalse((self.state/'archive-repair-requests').exists())
 def test_wrong_owner_status_refused_before_HTTP(self):
  self.enqueue()
  with patch.object(m,'api',side_effect=self.response):m.dispatch(self.worker)
  with patch.object(m,'api') as api,self.assertRaises(m.Unavailable):m.status(self.worker,dict(self.owner,issueid='999'),self.key)
  api.assert_not_called()
 def test_remote_work_underWriter_refused(self):
  self.enqueue()
  with Writer(self.wroot,create=False).hold(),patch.object(m,'api') as api,self.assertRaises(m.Unavailable):m.dispatch(self.worker)
  api.assert_not_called()
 def test_repair_pending_blocks_queue_and_dispatch(self):
  for name in ('archive-repair-v1.pending','archive-repair-v1.terminal-pending'):
   p=self.wroot/name;p.write_bytes(b'pending')
   try:
    with self.assertRaises(RuntimeError):self.enqueue()
   finally:p.unlink()
 def test_linked_private_journal_refused(self):
  (self.state/'archive-repair-requests').symlink_to(self.library)
  with self.assertRaises((m.Unavailable,OSError)):self.enqueue()
 def test_wrong_private_mode_refused(self):
  self.enqueue();(self.state/'archive-repair-requests').chmod(0o755)
  with self.assertRaises(m.Unavailable):m.dispatch(self.worker)
 def test_unknown_journal_child_refused(self):
  self.enqueue();(self.state/'archive-repair-requests'/'foreign.json').write_bytes(b'{}')
  with self.assertRaises(m.Unavailable):m.dispatch(self.worker)
 def test_orphan_ack_refused(self):
  self.enqueue();path=self.state/'archive-repair-requests'/('b'*64+'.ack.json');path.write_bytes(b'{}');path.chmod(0o600)
  with self.assertRaises(m.Unavailable):m.dispatch(self.worker)
 def test_native_ack_never_accepts_boolean_grant(self):
  self.enqueue()
  def answer(*a,**kw):return dict(self.response(*a,**kw),mutation_authority=True)
  with patch.object(m,'api',side_effect=answer),self.assertRaises(m.Unavailable):m.dispatch(self.worker)
  self.assertFalse((self.state/'archive-repair-requests'/(self.key+'.ack.json')).exists())
 def test_native_ack_owner_mismatch_held(self):
  self.enqueue()
  def answer(*a,**kw):return dict(self.response(*a,**kw),owner=dict(self.owner,issueid='999'))
  with patch.object(m,'api',side_effect=answer),self.assertRaises(m.Unavailable):m.dispatch(self.worker)
 def test_last_HTTP_callback_mutates_intent_held(self):
  self.enqueue()
  def answer(*a,**kw):
   value=self.response(*a,**kw);(self.state/'archive-repair-requests'/(self.key+'.intent.json')).chmod(0o640);return value
  with patch.object(m,'api',side_effect=answer),self.assertRaises(m.Unavailable):m.dispatch(self.worker)
 def test_last_HTTP_callback_unknown_child_held(self):
  self.enqueue()
  def answer(*a,**kw):
   value=self.response(*a,**kw);(self.state/'archive-repair-requests'/'foreign.json').write_bytes(b'{}');return value
  with patch.object(m,'api',side_effect=answer),self.assertRaises(m.Unavailable):m.dispatch(self.worker)
 def test_last_scandir_callback_foreign_after_snapshot_held(self):
  self.enqueue();path=self.state/'archive-repair-requests';real=m.os.scandir;fired=[]
  def changed(p):
   result=list(real(p))
   if Path(p)==path and not fired:fired.append(True);(path/'foreign.json').write_bytes(b'{}')
   return iter(result)
  with patch.object(m.os,'scandir',side_effect=changed),self.assertRaises(m.Unavailable):m.dispatch(self.worker)
  self.assertTrue(fired)
 def test_transient_leafFD_alias_not_adopted(self):
  self.enqueue();foreign=self.root/'foreign';foreign.write_bytes(b'{}');foreign.chmod(0o600);real=m.os.open;fired=[]
  def changed(p,flags,*args,**kw):
   if p==self.key+'.intent.json' and 'dir_fd' in kw and not fired:fired.append(True);return real(foreign,flags)
   return real(p,flags,*args,**kw)
  with patch.object(m.os,'open',side_effect=changed),self.assertRaises(m.Unavailable):m.dispatch(self.worker)
  self.assertTrue(fired)
 def test_journal_disjoint_library(self):
  self.worker.roots=[self.state]
  with self.assertRaises(m.Unavailable):self.enqueue()
 def test_new_module_has_no_mylar_import(self):
  self.assertNotIn('from mylar',Path(m.__file__).read_text());self.assertNotIn('import mylar',Path(m.__file__).read_text())
 def test_public_maintenance_queue_and_existing_dispatch_integration(self):
  spec=importlib.util.spec_from_file_location('maintenance_proposal',Path(__file__).with_name('maintenance.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);maintenance=module.Maintenance.__new__(module.Maintenance);maintenance.worker=self.worker;maintenance.enqueue_archive_repair(self.owner,self.key)
  with patch('import_recovery.dispatch_prepared',return_value=2),patch('native_handoff.dispatch',return_value=3),patch.object(m,'api',side_effect=self.response):self.assertEqual(maintenance.dispatch(),6);answer=maintenance.archive_repair_status(self.owner,self.key)
  self.assertEqual(answer['outcome'],'queued-review');self.assertEqual(len(self.calls),2)
 def test_last_append_callback_foreign_child_refused_enqueue(self):
  real=m.append;fired=[]
  def changed(*args):
   value=real(*args);(self.state/'archive-repair-requests'/'foreign.json').write_bytes(b'{}');fired.append(True);return value
  with patch.object(m,'append',side_effect=changed),self.assertRaises(m.Unavailable):self.enqueue()
  self.assertTrue(fired)
 def test_last_close_callback_after_ack_refused(self):
  self.enqueue();real=m.close;fired=[]
  def changed(*args):
   result=real(*args)
   if not fired and self.key+'.ack.json' in args[-1]:fired.append(True);(self.state/'archive-repair-requests'/(self.key+'.intent.json')).chmod(0o640)
   return result
  with patch.object(m,'api',side_effect=self.response),patch.object(m,'close',side_effect=changed),self.assertRaises(m.Unavailable):m.dispatch(self.worker)
  self.assertTrue(fired)
 def test_missing_existing_writer_not_created(self):
  self.worker.config['writer_state']=str(self.root/'missing')
  with self.assertRaises((ValueError,OSError)):self.enqueue()
  self.assertFalse((self.root/'missing').exists())
 def test_legacy_dispatch_unchanged_no_new_state(self):
  self.worker.config['writer_state']=None
  with patch.object(m,'api') as api:self.assertEqual(m.dispatch(self.worker),0)
  api.assert_not_called();self.assertFalse((self.state/'archive-repair-requests').exists())
 def test_no_queued_jobs_dispatch_does_not_read_remote(self):
  with patch.object(m,'api') as api:self.assertEqual(m.dispatch(self.worker),0)
  api.assert_not_called();self.assertFalse((self.state/'archive-repair-requests').exists())
if __name__=='__main__':unittest.main()
