"""Real SQLite/file terminal observations with an explicit fixture parent adapter."""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
p=load('terminal_producer',ROOT/'comic_terminal_observation_producer.py')
a=load('native_adapter',ROOT/'comic_native_evidence_adapter.py')
f=load('observer_fixture',ROOT/'test_negative_terminal_observer.py')

class Controls(unittest.TestCase):
 def setUp(self):
  self.f=f.Controls();self.f.setUp();self.addCleanup(self.f.doCleanups);c=self.f
  self.execute=c.root/'execute';self.execute.mkdir(mode=0o700)
  c.journal.rename(self.execute/'batch');c.journal=self.execute/'batch'
  c.terminal.rename(self.execute/'batch.terminal-v1');c.terminal=self.execute/'batch.terminal-v1'
  c.phase_ref=c.ref(c.journal/'00.json')
  action_members=[]
  for b in c.native:
   b['owner']={'issueid':'fixture','comicid':'fixture'}
   extra=[q for q in b['file_facts'] if q not in (b['source'],b['counterpart'])]
   action_members.append(dict(source=b['source'],counterpart=b['counterpart'],owner=b['owner'],retained=extra[0],restore=extra[1]))
  controls=c.pre['backup_controls'];custody=dict(reader_root=str(c.current),restore_root=str(c.restore),current_pairs={'database.sqlite':c.commit['main_pair'],'tasks.sqlite':c.commit['tasks_pair']},pairs=c.pre['restore_pairs'])
  controls['custody']=c.write(Path(controls['custody']['path']),custody)
  c.pre_ref=c.write(self.execute/'terminal-observation-preimage.json',c.pre);c.refresh_terminal()
  action=dict(operation=str(self.execute),members=action_members,targets=[v['target'] for v in c.members],batch_journal=str(c.journal),start_journal=str(self.execute/'sql-start'),commit_journal=str(self.execute/'sql-commit'))
  self.action=c.write(c.root/'execute-action.json',action)
  self.plan=dict(action_inputs={'execute':self.action},provider=dict(path=str(ROOT/'comic_negative_reader_action.py'),sha256=hashlib.sha256((ROOT/'comic_negative_reader_action.py').read_bytes()).hexdigest()))
  class Mapping:
   def child(self,path):return str(path)
   def host(self,path):return str(path)
  class Parent:
   mapping=Mapping()
   def continuous(self):return self.observations
  self.parent=Parent();self.parent.observations={'reader':{'Mounts':[dict(Type='bind',Source=str(c.current),Destination='/config')]}}
  self.req=dict(nonce='a'*64,operation=str(c.root),context=dict(backup=dict(restore_root=str(c.restore)),controls=copy.deepcopy(controls),observations=copy.deepcopy(self.parent.observations),execute_action=self.action),parent_source=c.write(c.root/'parent.py',{'fixture':'explicit fake parent'}),parent_plan=c.write(c.root/'parent-plan.json',self.plan))
  def context(request,watch):
   reads=a.Reads();reads.ref(request['parent_source']);reads.ref(request['parent_plan'])
   for ref in request['context']['controls'].values():reads.ref(ref)
   return reads,self.plan,None,None,None
  self.adapter=types.SimpleNamespace(context=context,nine=a.nine,five=a.five,current_observations=lambda w,e,r: p.need(w()==e,r),deadline=lambda r:None)
  self.refresh_execute_ack()
 def refresh_execute_ack(self):
  c=self.f;outcome='observed-forward' if c.forward else 'observed-rollback'
  evidence=dict(version=1,outcome=outcome,binding_sha256='a'*64,clear_ready=c.manifest['clear_ready'],cleared=c.manifest['cleared'])
  report=c.write(self.execute/'execute-report.json',dict(kind='negative-five-owning-terminal-observation' if c.forward else 'negative-five-owning-rollback-observation',preimage=c.ref(self.execute/'terminal-observation-preimage.json'),terminal_refs=evidence,terminal=dict(marker_cleared=True),phase='execute',nonce=self.req['nonce'],final_ack_required=True,provider_continuity_verified=False,publication_acceptance=False,reader_resume_authority=False))
  self.req['context']['execute_ack']=c.write(c.root/'execute-ack.json',dict(nonce=self.req['nonce'],phase='execute',source_sha256=self.plan['provider']['sha256'],report=report,publication_acceptance=False,reader_resume_authority=False))
 def call(self):return p.produce(self.req,watch=self.parent.continuous,adapter=self.adapter)
 def test_forward_actual_fulltables_and_five_files(self):
  value=self.call();self.assertEqual(value['outcome'],'observed-forward');self.assertTrue(Path(value['manifest']['path']).is_file())
  report=f.m.observe(value['manifest'],source_sha256=hashlib.sha256(Path(f.m.__file__).read_bytes()).hexdigest());self.assertFalse(report['recovery_capability'])
 def test_rollback_exact_owned_layout(self):
  c=self.f;c.test_rollback_exact_original();c.terminal.rename(self.execute/'batch.rollback-terminal-v1');c.terminal=self.execute/'batch.rollback-terminal-v1';c.refresh_terminal();self.refresh_execute_ack()
  self.assertEqual(self.call()['outcome'],'observed-rollback')
 def test_dual_terminal_layout_refused(self):
  (self.execute/'batch.rollback-terminal-v1').mkdir(mode=0o700)
  with self.assertRaisesRegex(p.Held,'exactly-one'):self.call()
 def test_original_control_join_refused(self):
  c=self.f;c.pre['backup_controls']['rows']['sha256']='f'*64;c.write(self.execute/'terminal-observation-preimage.json',c.pre)
  with self.assertRaisesRegex(Exception,'ref-incarnation|ref-SHA|adapter-ref-CAS'):self.call()
 def test_late_watch_current_DB_mode_no_manifest_ack(self):
  real=self.adapter.current_observations
  def changed(w,e,r):
   real(w,e,r)
   if r=='terminal-runtime-after':(self.f.current/'database.sqlite').chmod(0o640)
  self.adapter.current_observations=changed
  with self.assertRaisesRegex(p.Held,'final-file'):self.call()
 def test_write_unknown_child_not_adopted(self):
  real=p.emit
  def changed(*args):
   result=real(*args)
   if Path(args[0]).name=='terminal-observation-candidate.json':(self.execute/'foreign').write_bytes(b'foreign')
   return result
  with patch.object(p,'emit',changed):
   with self.assertRaisesRegex(p.Held,'namespace|census|dir-CAS'):self.call()
 def test_first_output_corruption_held(self):
  real=p.emit
  def changed(*args):
   result=real(*args)
   Path(args[0]).write_bytes(b'{}');return result
  with patch.object(p,'emit',changed):
   with self.assertRaisesRegex(Exception,'ref-incarnation|ref-SHA'):self.call()
 def test_output_no_replay(self):
  self.call()
  with self.assertRaisesRegex(p.Held,'no-replay'):self.call()
 def test_terminal_pairs_fresh_not_original_custody(self):
  ref=self.call()['manifest'];req=dict(self.req,context=dict(self.req['context'],terminal_manifest=ref))
  reads=a.Reads();pairs,originals=p.current_pairs(req,watch=self.parent.continuous,adapter=self.adapter,reads=reads,plan=self.plan)
  self.assertEqual(pairs['database.sqlite']['']['sha256'],self.f.commit['main_pair']['']['sha256']);self.assertIn(str(self.f.current/'database.sqlite'),originals['files'])
 def test_terminal_pair_late_observer_mode_is_carried_original(self):
  ref=self.call()['manifest'];req=dict(self.req,context=dict(self.req['context'],terminal_manifest=ref));real=a.Reads.module
  def module(o,name,pin):
   m=real(o,name,pin)
   if name=='comic_negative_terminal_observer.py':
    run=m.observe_mapped_with_originals
    def changed(*args,**kwargs):
     value=run(*args,**kwargs);(self.f.current/'database.sqlite').chmod(0o640);return value
    m.observe_mapped_with_originals=changed
   return m
  with patch.object(a.Reads,'module',module):
   pairs,originals=p.current_pairs(req,watch=self.parent.continuous,adapter=self.adapter,reads=a.Reads(),plan=self.plan)
  self.assertNotEqual(a.nine(os.lstat(self.f.current/'database.sqlite')),tuple(originals['files'][str(self.f.current/'database.sqlite')]))
  self.assertEqual(pairs['database.sqlite']['']['signature9'],self.f.commit['main_pair']['']['signature9'])
 def test_samebyte_original_preimage_inode_replacement_refused(self):
  path=self.execute/'terminal-observation-preimage.json';raw=path.read_bytes();path.rename(path.with_name('original-preimage.retained'));path.write_bytes(raw);path.chmod(0o600)
  with self.assertRaisesRegex(Exception,'ref-incarnation|adapter-ref-CAS'):self.call()
 def test_original_ready_inode_replacement_refused(self):
  path=self.f.terminal/'clear-ready.json';raw=path.read_bytes();path.rename(self.execute/'ready.retained');path.write_bytes(raw);path.chmod(0o600)
  with self.assertRaisesRegex(Exception,'ref-incarnation|adapter-ref-CAS'):self.call()
 def test_original_ack_inode_replacement_refused(self):
  path=Path(self.req['context']['execute_ack']['path']);raw=path.read_bytes();path.rename(path.with_suffix('.retained'));path.write_bytes(raw);path.chmod(0o600)
  with self.assertRaisesRegex(Exception,'ref-incarnation|adapter-ref-CAS'):self.call()
 def test_original_report_inode_replacement_refused(self):
  path=self.execute/'execute-report.json';raw=path.read_bytes();path.rename(path.with_suffix('.retained'));path.write_bytes(raw);path.chmod(0o600)
  with self.assertRaisesRegex(Exception,'ref-incarnation|adapter-ref-CAS'):self.call()
 def test_output_fsync_private_mode_refused_before_adoption(self):
  real=os.fsync;fired=[]
  def changed(fd):
   result=real(fd)
   if __import__('stat').S_ISREG(os.fstat(fd).st_mode):os.fchmod(fd,0o640);fired.append(True)
   return result
  with patch.object(p.os,'fsync',changed):
   with self.assertRaisesRegex(p.Held,'intended-metadata'):self.call()
  self.assertTrue(fired)
 def test_output_hardlink_before_adoption_refused(self):
  real=os.fsync;fired=[]
  def changed(fd):
   result=real(fd)
   if __import__('stat').S_ISREG(os.fstat(fd).st_mode) and not fired:
    (self.execute/'output-alias').hardlink_to(self.execute/'terminal-observation-candidate.json');fired.append(True)
   return result
  with patch.object(p.os,'fsync',changed):
   with self.assertRaisesRegex(p.Held,'intended-metadata'):self.call()
  self.assertTrue(fired)
 def test_last_watch_original_execute_ACK_refuses(self):
  real=self.adapter.current_observations
  def changed(w,e,r):
   real(w,e,r)
   if r=='terminal-runtime-after':Path(self.req['context']['execute_ack']['path']).chmod(0o640)
  self.adapter.current_observations=changed
  with self.assertRaisesRegex(p.Held,'final-file'):self.call()
 def test_last_watch_original_execute_report_refuses(self):
  real=self.adapter.current_observations
  def changed(w,e,r):
   real(w,e,r)
   if r=='terminal-runtime-after':(self.execute/'execute-report.json').chmod(0o640)
  self.adapter.current_observations=changed
  with self.assertRaisesRegex(p.Held,'final-file'):self.call()
 def test_directory_fsync_late_leaf_metadata_refused(self):
  real=os.fsync;fired=[]
  def changed(fd):
   result=real(fd);candidate=self.execute/'terminal-observation-candidate.json'
   if __import__('stat').S_ISDIR(os.fstat(fd).st_mode) and candidate.exists() and not fired:candidate.chmod(0o640);fired.append(True)
   return result
  with patch.object(p.os,'fsync',changed):
   with self.assertRaisesRegex(p.Held,'output-file-final'):self.call()
  self.assertTrue(fired)
if __name__=='__main__':unittest.main()
