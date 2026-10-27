"""Real private files/fsync/closure, explicit child/NFS/type scheduling doubles."""
import copy
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
from test_nfs_current_roles import bridge_profile,release_bridge,row as role_row,resumed_bridge_profile as resumed_row
import test_reader_lifecycle_parent as old
p=old.p
import comic_archive_terminal_vectors as vector_module


class Tests(unittest.TestCase):
 setUp=old.Tests.setUp
 def setup_archive(self,fault=None,outcome='observed-forward'):
  x=self.parent;calls=[];phases=[];self.codepatch=patch.object(p,'pinned_module',return_value=types.SimpleNamespace(PARENT_SOURCE_SHA=self.source['sha256']));self.codepatch.start();self.addCleanup(self.codepatch.stop);self.calls=calls;self.phases=phases
  x.plan.update(action='archive-one',backup_provider=self.provider,reader={'id':'1'*64},observer=self.proof)
  x.plan['producer_inputs']={'archive_request':old.fixture_ref(self.root/'request.json',p.encode(dict(version=1,owner={'kind':'issue','issue_id':'123','comic_id':'456'},operation_id='d'*64))),'archive_scopes':old.fixture_ref(self.root/'scopes.json',p.encode(dict(version=1,scratch=str(self.root/'scratch'),retention_root=str(self.root/'retention'))))}
  x.plan['sdk_map']=old.fixture_ref(self.root/'sdk-map.json',p.encode({'publication_api.py':'f'*64}));x.plan['mounts'][0]['child']=str(self.root);x.mapping=p.Paths(x.plan['mounts'])
  controls={role:old.fixture_ref(self.root/(role+'.json'),b'{}') for role in p.ARCHIVE_ROLES};scopes=old.fixture_ref(self.root/'actual-scopes.json',b'{}')
  row=bridge_profile(role_row(1,'reader','running'));row['Image']=x.plan['selected_image']
  stopped=release_bridge(row);stopped['State'].update(Status='exited',Running=False,Pid=0,FinishedAt='owned-stop')
  x.baselines={'reader':row};x.files={self.source['path']:tuple(self.source['signature9'])};x.nodes={};x.observer=vector_module
  claims=self.root/'claims';claims.mkdir(mode=0o700);self.claims=claims
  class Engine:
   def run(_,args,seconds):
    calls.append(tuple(args));return b'1'*64
  x.engine=Engine();x.inspect=lambda cid:resumed_row(row)
  def continuous():
   if (x.op/'resume-intent.json').exists():
    if fault=='source':Path(self.source['path']).chmod(0o640)
    if fault=='claim':(claims/'late').write_bytes(b'foreign')
    if fault=='census':(claims/'other').write_bytes(b'foreign')
    if fault=='report':(x.op/'verify-terminal/verify-terminal-report.json').chmod(0o640)
   return {'reader':stopped}
  x.continuous=continuous
  def stop(owner):owner.engine.run(['stop',owner.plan['reader']['id']],owner.left());return owner.continuous()
  p._NFS_ADAPTERS[x]=types.SimpleNamespace(preflight=lambda _:None,run_active=lambda _:None,stop_owned=stop)
  def produce(phase,context):
   if phase=='backup-controls':return dict(controls=controls,archive_scopes=scopes)
   if phase=='archive-nfs-ready':return {'evidence':self.proof}
   self.assertEqual(phase,'phase-custody');self.assertEqual(set(context['controls']),p.ARCHIVE_ROLES)
   seed=dict(version=1,kind='selected-child-native-scope-birth',invocation=context['invocation'],parent_source=x.mapping.child_ref(self.source),birth_source=dict(path='/app/mylar3/mylar/publication_native_scope_birth.py',sha256=x.plan['birth_source_sha256']),config={'path':'/data/config.ini','sha256':'b'*64},worker_library='/worker/library',selected_image=x.plan['selected_image'])
   return dict(reader={},proofs={'archive_sdk_map':x.plan['sdk_map']},birth_seed=seed)
  x.produce=produce
  def child(phase,ref,command,**kwargs):
   phases.append(phase)
   if phase=='backup':
    backup_root=x.op/'backup'/'reader-backup';backup_root.mkdir(mode=0o700)
    manifest=old.fixture_ref(backup_root/'manifest.json',b'{}')
    return dict(manifest=x.mapping.child_ref(manifest),restore_root=x.mapping.child(self.root),phase='backup')
   if phase=='execute':
    original=old.fixture_ref(x.op/'execute/execution-originals.json',b'{}');self.original=original
    result=dict(kind='archive-one-owning-execute-observation',owner={'kind':'issue','issue_id':'123','comic_id':'456'},operation_id='d'*64,outcome=outcome,originals=x.mapping.child_ref(original),baseline=self.proof,reader_index_acceptance=False,ordinary_import_grant=False,publication_acceptance=False,mutation_authority=False,automatic_replay=False)
   else:
    if fault=='ACK':raise p.Held('unknown-child-ACK')
    native={'config_module':dict(path='/app/mylar3/mylar/config.py',sha256='a'*64,signature9=[1,2,3,4,5,0o100644,1000,1000,1]),'main_module':dict(path='/app/mylar3/Mylar.py',sha256='b'*64,signature9=[1,3,3,4,5,0o100644,1000,1000,1])}
    native_ref=old.fixture_ref(x.op/'verify-terminal-input.native-scope.json',p.encode(native));x.generated[native_ref['path']]=native_ref;p._GENERATED[x]=p.encode(x.generated)
    result=dict(kind='archive-one-independent-terminal-observation',owner={'kind':'issue','issue_id':'123','comic_id':'456'},operation_id='d'*64,outcome=outcome,originals=x.mapping.child_ref(self.original),baseline=self.proof,reader_index_acceptance=False,ordinary_import_grant=False,publication_acceptance=False,mutation_authority=False,automatic_replay=False,original_vectors={'files':[[self.source['path'],self.source['signature9']]],'nodes':[[str(claims),p.five(claims.lstat())]],'claims':[[str(claims/'late'),None]],'absent':[str(claims/'sidecar')],'censuses':[[str(claims),[]]]})
   report=old.fixture_ref(x.op/phase/(phase+'-report.json'),p.encode(result));x.generated[report['path']]=report;p._GENERATED[x]=p.encode(x.generated)
   x.emit(phase+'-ack.json',dict(nonce=x.plan['nonce'],phase=phase,source_sha256=self.provider['sha256'],report=x.mapping.child_ref(report),publication_acceptance=False,reader_resume_authority=False))
   return result
  x.child_phase=child
  x.core=p.encode(dict(plan=x.plan,files=x.files,nodes=x.nodes,source=x.source_ref,input=x.plan_ref,engine=id(x.engine),thread=x.thread,deadline=x.deadline));p._CORES[x]=x.core
  return x
 def with_completion_lock(self,fault=None):
  import os,fcntl
  x=self.setup_archive(fault=fault);root=self.root/'media-writer';root.mkdir(mode=0o700)
  lockpath=root/'writer-v1.lock';lockpath.write_bytes(b'mylar-media-writer-v1\n');lockpath.chmod(0o600)
  marker=root/'publication-v1.json';marker.write_bytes(b'{}');marker.chmod(0o600)
  frames=(((str(root),tuple(p.five(root.lstat()))),),tuple((str(path),tuple(p.nine(path.lstat()))) for path in (lockpath,marker)))
  child=x.child_phase;run=x.engine.run;checks=[]
  def exclusion():
   fd=os.open(lockpath,os.O_RDWR)
   try:
    with self.assertRaises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
   finally:os.close(fd)
   checks.append(True)
  def wrapped_child(phase,ref,command,**kwargs):
   if phase=='execute':
    lock=p.ArchiveCompletionExclusion(frames)
    record=(lock,lock.fd,lock.nodes,lock.files,type(lock).check,type(lock).check.__code__,lock.witness,type(lock).close)
    kwargs['completion_slot'][0]=record;p._ARCHIVE_COMPLETION_LOCKS[x]=record
   if phase in ('execute','verify-terminal'):exclusion()
   return child(phase,ref,command,**kwargs)
  def wrapped_run(args,seconds):
   if args[0]=='start':exclusion()
   return run(args,seconds)
  x.child_phase=wrapped_child;x.engine.run=wrapped_run
  return x,lockpath,checks
 def assert_completion_released(self,x,path):
  import os,fcntl
  self.assertNotIn(x,p._ARCHIVE_COMPLETION_LOCKS)
  fd=os.open(path,os.O_RDWR)
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  finally:os.close(fd)
 def test_completion_exclusion_retained_through_reader_resume_then_released(self):
  x,path,checks=self.with_completion_lock();x.execute()
  self.assertEqual(len(checks),3);self.assert_completion_released(x,path)
 def test_completion_exclusion_failure_releases_without_reader_resume(self):
  x,path,checks=self.with_completion_lock(fault='ACK')
  self.assertRaises(p.Held,x.execute);self.assertEqual([c[0] for c in self.calls],['stop'])
  self.assertEqual(len(checks),2);self.assert_completion_released(x,path)
 def test_completion_original_registry_loss_never_resumes_and_releases(self):
  x,path,checks=self.with_completion_lock();continuous=x.continuous
  def changed():
   value=continuous()
   if (x.op/'resume-intent.json').exists():p._ARCHIVE_COMPLETION_LOCKS.pop(x,None)
   return value
  x.continuous=changed
  self.assertRaises(p.Held,x.execute);self.assertEqual([c[0] for c in self.calls],['stop'])
  self.assert_completion_released(x,path)
 def test_completion_cleanup_never_calls_changed_kernel_checker_code(self):
  x,path,checks=self.with_completion_lock();continuous=x.continuous;child=x.child_phase;records=[]
  kernel=p.completion_fd_locked;code=kernel.__code__;p.foreign_cleanup_executed=False
  def foreign(fd,identity9):
   globals()['foreign_cleanup_executed']=True
   return True
  def capture(*args,**kwargs):
   result=child(*args,**kwargs)
   if args[0]=='execute':records.append(kwargs['completion_slot'][0])
   return result
  def changed():
   result=continuous()
   if (x.op/'resume-intent.json').exists():kernel.__code__=foreign.__code__
   return result
  x.child_phase=capture;x.continuous=changed
  try:
   self.assertRaises(p.Held,x.execute);self.assertFalse(p.foreign_cleanup_executed)
   self.assertEqual([c[0] for c in self.calls],['stop'])
  finally:
   kernel.__code__=code
   for record in records:record[-1](record[0])
  self.assert_completion_released(x,path)
 def test_finite_backup_execute_verify_resume(self):
  x=self.setup_archive();x.execute();self.assertEqual(self.phases,['backup','execute','verify-terminal']);self.assertEqual([c[0] for c in self.calls],['stop','start']);self.assertFalse(p.decode(p.read(x.generated[str(x.op/'complete.json')]))['publication_acceptance'])
 def test_independent_rollback_outcome_same_schedule(self):
  self.setup_archive(outcome='observed-rollback').execute();self.assertEqual(self.calls[-1][0],'start')
 def test_unknown_verify_ACK_never_resume(self):
  x=self.setup_archive(fault='ACK');self.assertRaises(p.Held,x.execute);self.assertEqual([c[0] for c in self.calls],['stop']);self.assertEqual(x.phase,'uncertain')
 def test_last_source_never_resume(self):
  x=self.setup_archive(fault='source');self.assertRaises(p.Held,x.execute);self.assertEqual([c[0] for c in self.calls],['stop'])
 def test_last_claim_never_resume(self):
  x=self.setup_archive(fault='claim');self.assertRaises(p.Held,x.execute);self.assertEqual([c[0] for c in self.calls],['stop'])
 def test_last_census_never_resume(self):
  x=self.setup_archive(fault='census');self.assertRaises(p.Held,x.execute);self.assertEqual([c[0] for c in self.calls],['stop'])
 def test_last_verify_report_never_resume(self):
  x=self.setup_archive(fault='report');self.assertRaises(p.Held,x.execute);self.assertEqual([c[0] for c in self.calls],['stop'])
 def test_last_resume_intent_callback_never_resume(self):
  x=self.setup_archive();real=x.emit
  def emit(name,value):
   ref=real(name,value)
   if name=='resume-intent.json':Path(ref['path']).chmod(0o640)
   return ref
  x.emit=emit;self.assertRaises(p.Held,x.execute);self.assertEqual([c[0] for c in self.calls],['stop'])
 def test_phase_keeps_exact_SDK_ref_and_no_five_fields(self):
  x=self.setup_archive();self.assertEqual(x.plan['action'],'archive-one');x.execute();doc=p.decode(p.read(x.generated[str(x.op/'execute-input.json')]))
  self.assertEqual(doc['sdk_map'],x.mapping.child_ref(x.plan['sdk_map']));self.assertNotIn('action_input',doc);self.assertNotIn('admission_source_sha256',doc);self.assertEqual(set(doc['controls']),p.ARCHIVE_ROLES)
 def test_verify_scratch_only_extra_RW(self):
  x=self.setup_archive();scopes=p.decode(p.read(x.plan['producer_inputs']['archive_scopes']))
  for key in ('scratch','retention_root'):
   self.assertEqual(x.phase_write(dict(host=scopes[key],child='/private/'+key,write=True),'verify-terminal'),key=='scratch')
 def test_unaccepted_parent_pin_no_stop_or_canary(self):
  x=self.setup_archive();self.codepatch.stop()
  with patch.object(p,'pinned_module',return_value=types.SimpleNamespace(PARENT_SOURCE_SHA=None)),self.assertRaises(p.Held):x.execute()
  self.assertEqual(self.calls,[])
 def test_source_parent_pin_stays_unset(self):
  import comic_archive_backup_action as backup
  import comic_archive_repair_action as action
  self.assertIsNone(backup.PARENT_SOURCE_SHA);self.assertIsNone(action.PARENT_SOURCE_SHA)

 def test_resume_original_profile_new_endpoint_and_fresh_epoch(self):
  x=self.setup_archive();row=resumed_row(x.baselines['reader']);self.assertTrue(p.checked_reader_resumed_profile(x.baselines['reader'],row,x.plan['reader']['id']))
  for key,value in (('StartedAt',x.baselines['reader']['State']['StartedAt']),('Pid',0),('Restarting',True),('Dead',True),('ExitCode',1)):
   changed=copy.deepcopy(row);changed['State'][key]=value
   with self.subTest(key=key):self.assertFalse(p.checked_reader_resumed_profile(x.baselines['reader'],changed,x.plan['reader']['id']))
 def test_resume_network_and_immutable_drift_refuse(self):
  x=self.setup_archive();row=resumed_row(x.baselines['reader'])
  for key,value in (('NetworkID','f'*64),('Gateway','10.251.242.100'),('Aliases',['foreign']),('IPAddress','10.251.243.99'),('IPPrefixLen',24),('IPAddress','10.251.242.97'),('IPAddress','10.251.242.111'),('MacAddress','01:00:00:00:00:01')):
   changed=copy.deepcopy(row);changed['NetworkSettings']['Networks']['fixture'][key]=value
   with self.subTest(key=key,value=value):self.assertFalse(p.checked_reader_resumed_profile(x.baselines['reader'],changed,x.plan['reader']['id']))
  for key,value in (('Id','f'*64),('Config',{}),('HostConfig',{}),('Mounts',[{'Source':'/foreign'}])):
   changed=copy.deepcopy(row);changed[key]=value
   with self.subTest(key=key):self.assertFalse(p.checked_reader_resumed_profile(x.baselines['reader'],changed,x.plan['reader']['id']))
 def test_resume_configured_ip_and_mac_stay_exact(self):
  x=self.setup_archive();old=x.baselines['reader'];endpoint=old['NetworkSettings']['Networks']['fixture']
  endpoint['IPAMConfig']={'IPv4Address':endpoint['IPAddress']};old['Config']['MacAddress']=endpoint['MacAddress']
  row=resumed_row(old);self.assertFalse(p.checked_reader_resumed_profile(x.baselines['reader'],row,x.plan['reader']['id']))
  row['NetworkSettings']['Networks']['fixture'].update(IPAddress=endpoint['IPAddress'],MacAddress=endpoint['MacAddress'])
  self.assertTrue(p.checked_reader_resumed_profile(x.baselines['reader'],row,x.plan['reader']['id']))

 def test_final_inspect_cannot_override_resume_acceptance(self):
  x=self.setup_archive()
  def inspect(cid):
   x.reader_resumed=lambda row:True
   row=resumed_row(x.baselines['reader']);row['Config']={};return row
  x.inspect=inspect
  with self.assertRaises(p.Held):x.execute()
  self.assertEqual(x.phase,'uncertain');self.assertFalse((x.op/'complete.json').exists())

if __name__=='__main__':unittest.main()
