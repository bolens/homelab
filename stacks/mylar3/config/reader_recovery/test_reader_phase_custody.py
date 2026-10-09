"""Real disposable SQLite; fake parent observations are not custody grants."""
import copy
import os
import threading
import hashlib
import importlib.util
from pathlib import Path
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('fixture',ROOT/'_reader_parent_fixtures/fixture_native_phase.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
a=f.a
class Controls(unittest.TestCase):
 def setUp(self):
  f.AdapterTests.setUp(self);self.current,self.restore=f.AdapterTests.pair_fixture(self)
  self.scratch=self.root/'scratch';self.scratch.mkdir(mode=0o700)
  self.plan['native']['data']='/config/mylar';self.plan['provider']=dict(path=str(ROOT/'comic_negative_reader_action.py'),sha256=hashlib.sha256((ROOT/'comic_negative_reader_action.py').read_bytes()).hexdigest());self.plan['birth_source_sha256']='f'*64
  self.plan['producer']['sha256']=hashlib.sha256((ROOT/'comic_native_evidence_adapter.py').read_bytes()).hexdigest()
  class Mapping:
   def child(obj,path):
    path=str(path)
    if path==str(self.config/'config.ini'):return '/config/mylar/config.ini'
    if path==str(self.library):return '/data/comics'
    return path
   def host(obj,path):return str(self.config/'config.ini') if path=='/config/mylar/config.ini' else str(path)
  self.parent.mapping=Mapping()
  controls=self.req['context']['controls'];self.values['reader']['State'].update(Paused=False,Restarting=False,Dead=False,OOMKilled=False)
  self.values['reader']['Mounts']=[dict(Type='bind',Source=str(self.current),Destination='/config',RW=True)]
  self.put('stopped_runtime',dict(version=1,kind='root-owned-reader-stopped-observation',nonce='a'*64,observed=int(time.time()),container=self.values['reader']))
  self.put('backup_manifest',dict(kind='verified-reader-backup-copies',source_sha256='f165a0cb5834dc62f400d6dbe9e4070310823f28ec4bc1c4ecb12ae250503be3',primitives_sha256='e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0'))
  self.put('rows',dict(kind='reader-restored-eleven-row-observation',source_sha256='ebac3228fa3c6055b86e3636fb33368f4ccf21950b452e7d6c10070af4a2c99a',backup_manifest_sha256=controls['backup_manifest']['sha256'],schema_sha256=controls['schema']['sha256']))
  self.put('reviewed_plan',dict(timestamp_encoding_evidence_sha256=controls['timestamp_evidence']['sha256']))
  self.put('backup_acceptance',dict(kind='stopped-reader-full-backup-acceptance',backup_verified=False,final_ack_required=True,container_id=self.values['reader']['Id'],image=self.values['reader']['Image']))
  self.put('backup_ack',dict(backup_verified=True,targeted_eleven_row_observation_verified=True,acceptance_sha256=controls['backup_acceptance']['sha256'],backup_manifest_sha256=controls['backup_manifest']['sha256'],rows_report_sha256=controls['rows']['sha256'],repair_authority=False,mutation_authority=False,publication_acceptance=False,automatic_restart=False))
  self.req['context']['observations']=copy.deepcopy(self.values)
  self.req['context']['backup']=dict(restore_root=str(self.restore),manifest=copy.deepcopy(controls['backup_manifest']))
  self.inv=dict(input_path=str(self.root/'phase-input.json'),input_sha256='',parent_sha256=self.source['sha256'],provider_sha256=self.plan['provider']['sha256'],nonce='a'*64)
  command=['/lsiopy/bin/python3','-I','-B',self.plan['provider']['path'],'--phase','prepare','--input',self.inv['input_path'],'--input-sha256','<INPUT_SHA256>','--source-sha256',self.inv['provider_sha256']]
  doc=dict(version=1,nonce='a'*64,parent_sha256=self.source['sha256'],selected_image=self.plan['selected_image'],command_template=command,controls=copy.deepcopy(controls))
  path=Path(self.inv['input_path']);path.write_bytes(a.encode(doc));path.chmod(0o600);self.inv['input_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();self.inv['command']=copy.deepcopy(command);self.inv['command'][9]=self.inv['input_sha256'];self.req['context']['invocation']=self.inv
  self.refresh_plan()
 def refresh_plan(self):
  p=Path(self.planref['path']);p.write_bytes(a.encode(self.plan));self.planref.update(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),signature9=list(a.nine(p.lstat())))
 def put(self,role,value):
  ref=self.req['context']['controls'][role];p=Path(ref['path']);p.write_bytes(a.encode(value));p.chmod(0o600);ref.update(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),signature9=list(a.nine(p.lstat())))
 def call(self):return a.produce('phase-custody',self.req,watch=self.parent.continuous)['evidence']
 def test_full_nine_join_and_original_pair9(self):
  result=self.call();self.assertEqual(set(result),{'reader','proofs','birth_seed'});self.assertEqual(result['reader']['current_pairs'],f.a.decode(Path(self.req['context']['controls']['custody']['path']).read_bytes())['current_pairs']);self.assertNotIn('native_scope',result['proofs']);self.assertEqual(result['birth_seed']['invocation'],self.inv)
 def test_distinct_native_worker_destinations_same_physical_library(self):
  (self.config/'config.ini').write_text('[General]\ndestination_dir=/comics\n')
  self.plan['native']['roots']=['/comics'];self.values['held_native']['Mounts'][1]['Destination']='/comics'
  original=self.parent.mapping.child
  self.parent.mapping.child=lambda path:'/comics' if str(path)==str(self.library) else original(path)
  self.req['context']['observations']=copy.deepcopy(self.values);self.refresh_plan()
  result=self.call();self.assertEqual(result['birth_seed']['worker_library'],'/data/comics')
 def test_worker_source_ambiguity_refused(self):
  self.values['held_worker']['Mounts'].append(dict(Type='bind',Source=str(self.library),Destination='/another',RW=False))
  self.req['context']['observations']=copy.deepcopy(self.values)
  with self.assertRaisesRegex(a.Held,'worker-library-ambiguous'):self.call()
 def test_worker_destination_shadow_refused(self):
  self.values['held_worker']['Mounts'][1]['Source']=str(self.library.parent)
  self.values['held_worker']['Mounts'][1]['Destination']='/data'
  self.values['held_worker']['Mounts'].append(dict(Type='bind',Source=str(self.config),Destination='/data/comics',RW=False))
  self.req['context']['observations']=copy.deepcopy(self.values)
  with self.assertRaisesRegex(a.Held,'worker-library-shadow'):self.call()
 def test_health_updates_do_not_change_runtime_authority(self):
  self.values['held_native']['State']['Health']={'Log':['tick'],'FailingStreak':1}
  self.assertEqual(self.call()['birth_seed']['worker_library'],'/data/comics')
 def test_health_ticks_between_source_bound_callbacks(self):
  real=a.deadline;ticks=[]
  def tick(request):
   value=real(request);ticks.append(1)
   self.values['held_native']['State']['Health']={'Log':['tick'+str(len(ticks))],'FailingStreak':len(ticks)}
   return value
  with patch.object(a,'deadline',tick):result=self.call()
  self.assertGreater(len(ticks),1);self.assertEqual(result['birth_seed']['worker_library'],'/data/comics')
 def test_worker_longest_source_bind_is_selected(self):
  self.values['held_worker']['Mounts'].append(dict(Type='bind',Source=str(self.library.parent),Destination='/elsewhere',RW=False))
  self.req['context']['observations']=copy.deepcopy(self.values)
  self.assertEqual(self.call()['birth_seed']['worker_library'],'/data/comics')
 def test_critical_runtime_changes_are_not_health(self):
  for kind in ('pid','state','mount'):
   original=copy.deepcopy(self.values)
   if kind=='pid':self.values['held_native']['State']['Pid']+=1
   if kind=='state':self.values['held_native']['State']['Paused']=True
   if kind=='mount':self.values['held_native']['Mounts'][1]['RW']=True
   with self.assertRaisesRegex(a.Held,'custody-stopped-current'):self.call()
   self.values.clear();self.values.update(original)
 def lifecycle_fixture(self,result):
  spec=importlib.util.spec_from_file_location('lifecycle',ROOT/'_reader_parent_fixtures/fixture_reader_lifecycle.py');life=importlib.util.module_from_spec(spec);spec.loader.exec_module(life)
  doc=dict(version=1,kind='owning-reader-pipe-custody',nonce=self.req['nonce'],input_sha256=self.inv['input_sha256'],command=self.inv['command'],parent_source=self.source,reader=result['reader'],proofs=result['proofs'],deadline_seconds=60)
  control=Path(self.inv['input_path']).with_suffix('.lifecycle.json');control.write_bytes(life.encoded(doc));control.chmod(0o600)
  channel=life.ParentPipe.__new__(life.ParentPipe);channel.thread=threading.get_ident();channel.seq=0
  rd,wr=os.pipe();self.addCleanup(os.close,rd);self.addCleanup(os.close,wr);channel.input=rd;channel.output=wr;channel.facts=(tuple(life.five(os.fstat(rd))),tuple(life.five(os.fstat(wr))));life._PIPE_SEALS[channel]=(rd,wr,channel.thread,channel.facts)
  return life,channel
 def test_literal_lifecycle_schema_accepts_actual_matching_kernel9(self):
  result=self.call();life,channel=self.lifecycle_fixture(result)
  response=dict(reader=self.values['reader'],child_source_sha256=self.inv['provider_sha256'],child_image=self.plan['selected_image'])
  with patch.object(life.ParentPipe,'challenge',return_value=response):
   value=life.StoppedReaderCustody(life._KEY,self.inv['input_path'],self.inv['input_sha256'],self.req['nonce'],self.inv['parent_sha256'],self.inv['command'],channel)
   value.vectors()
  self.assertEqual(value.reader_files[self.current/'database.sqlite'],result['reader']['current_pairs']['database.sqlite']['']['signature9'])
 def test_literal_lifecycle_schema_refuses_actual_kernel9_mismatch(self):
  result=self.call();result['reader']['current_pairs']['database.sqlite']['']['signature9'][0]+=1;life,channel=self.lifecycle_fixture(result)
  with self.assertRaises(life.Held):life.StoppedReaderCustody(life._KEY,self.inv['input_path'],self.inv['input_sha256'],self.req['nonce'],self.inv['parent_sha256'],self.inv['command'],channel)
 def test_missing_nine(self):
  del self.req['context']['controls']['rows']
  with self.assertRaises(a.Held):self.call()
 def test_old_backup_source(self):
  self.put('backup_manifest',dict(kind='verified-reader-backup-copies',source_sha256='0'*64,primitives_sha256='0'*64))
  with self.assertRaises(a.Held):self.call()
 def test_unjoined_backup_ack(self):
  r=self.req['context']['controls']['backup_ack'];v=a.decode(Path(r['path']).read_bytes());v['rows_report_sha256']='0'*64;self.put('backup_ack',v)
  with self.assertRaisesRegex(a.Held,'backup-joins'):self.call()
 def test_stale_stop(self):
  r=self.req['context']['controls']['stopped_runtime'];v=a.decode(Path(r['path']).read_bytes());v['observed']-=121;self.put('stopped_runtime',v)
  with self.assertRaises(a.Held):self.call()
 def test_input_controls_must_join_same_nine(self):
  path=Path(self.inv['input_path']);value=a.decode(path.read_bytes());value['controls']['rows']['sha256']='0'*64;path.write_bytes(a.encode(value));self.inv['input_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();self.inv['command'][9]=self.inv['input_sha256']
  with self.assertRaisesRegex(a.Held,'input-nine-role-join'):self.call()
 def test_exact_command_no_duplicate(self):
  self.inv['command']+=['--phase','execute']
  with self.assertRaisesRegex(a.Held,'exact-command'):self.call()
 def test_foreign_worker_mount(self):
  self.values['held_worker']['Mounts'][1]['Source']=str(self.root/'foreign');self.req['context']['observations']=copy.deepcopy(self.values)
  with self.assertRaises(a.Held):self.call()
 def test_final_watch_db_mode(self):
  real=self.parent.continuous;n=[0]
  def changed():
   value=real();n[0]+=1
   if n[0]==4:(self.current/'database.sqlite').chmod(0o640)
   return value
  # Preserve the actual bound source-controlled watch; mutate through its state
  # access rather than replacing the callable identity.
  original=a.deadline;n=[0]
  def late(req):
   result=original(req)
   if 'phase_custody' in [x.function for x in __import__('inspect').stack()] and __import__('inspect').stack()[1].function=='phase_custody':(self.current/'database.sqlite').chmod(0o640)
   return result
  with patch.object(a,'deadline',late),self.assertRaisesRegex(a.Held,'custody-final-file'):self.call()
 def test_final_deadline_missing_journal(self):
  original=a.deadline
  def late(req):
   result=original(req)
   if __import__('inspect').stack()[1].function=='phase_custody':(self.restore/'tasks.sqlite-journal').write_bytes(b'foreign')
   return result
  with patch.object(a,'deadline',late),self.assertRaisesRegex(a.Held,'custody-final-(file|absence)'):self.call()
 def test_loader_rebuild_external_restore_ancestor_same_leaf9(self):
  external=self.root/'external';external.mkdir(mode=0o700);new=external/'restore';self.restore.rename(new);self.restore=new
  ref=self.req['context']['controls']['custody'];value=a.decode(Path(ref['path']).read_bytes());value['restore_root']=str(new);self.put('custody',value)
  self.req['context']['backup']['restore_root']=str(new)
  path=Path(self.inv['input_path']);v=a.decode(path.read_bytes());v['controls']=copy.deepcopy(self.req['context']['controls']);path.write_bytes(a.encode(v));self.inv['input_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();self.inv['command'][9]=self.inv['input_sha256']
  facts={str(x):a.nine(x.lstat()) for x in new.iterdir()};old=a.five(external.lstat());original=a.Reads.module;fired=[]
  def changed(obj,name,pin):
   result=original(obj,name,pin)
   if not fired:
    fired.append(True);retained=self.root/'retained';external.rename(retained);external.mkdir(mode=0o700);(retained/'restore').rename(external/'restore')
   return result
  with patch.object(a.Reads,'module',changed),self.assertRaises(a.Held):self.call()
  self.assertTrue(fired);self.assertNotEqual(a.five(external.lstat()),old);self.assertEqual(facts,{str(x):a.nine(x.lstat()) for x in new.iterdir()})
 def test_last_proposed_pair_copy_cannot_refresh_original(self):
  original=a.copy.deepcopy;fired=[]
  def changed(value,*args,**kwargs):
   if type(value) is dict and set(value)=={'database.sqlite','tasks.sqlite'} and not fired:
    main=self.current/'database.sqlite'
    if value['database.sqlite']['']['signature9']==list(a.nine(main.lstat())):
     fired.append(True);main.chmod(0o640);value['database.sqlite']['']['signature9']=list(a.nine(main.lstat()))
   return original(value,*args,**kwargs)
  with patch.object(a.copy,'deepcopy',changed),self.assertRaisesRegex(a.Held,'custody-final-file'):self.call()
  self.assertTrue(fired)
 def test_final_deadline_foreign_scratch(self):
  original=a.deadline
  def late(req):
   result=original(req)
   if __import__('inspect').stack()[1].function=='phase_custody':(self.scratch/'foreign').write_bytes(b'foreign')
   return result
  with patch.object(a,'deadline',late),self.assertRaisesRegex(a.Held,'custody-final-file'):self.call()
 def test_original_backup_restore_join(self):
  self.req['context']['backup']['restore_root']=str(self.current)
  with self.assertRaises(a.Held):self.call()
 def test_native_context_cannot_be_faked_by_phase_context(self):
  self.req['phase']='native-observation'
  with self.assertRaisesRegex(a.Held,'adapter-native-context'):a.produce('native-observation',self.req,watch=self.parent.continuous)
 def test_final_deadline_role_replacement(self):
  original=a.deadline
  def late(req):
   result=original(req)
   if __import__('inspect').stack()[1].function=='phase_custody':
    p=Path(self.req['context']['controls']['schema']['path']);raw=p.read_bytes();p.unlink();p.write_bytes(raw)
   return result
  with patch.object(a,'deadline',late),self.assertRaisesRegex(a.Held,'custody-final-file'):self.call()
if __name__=='__main__':unittest.main()
