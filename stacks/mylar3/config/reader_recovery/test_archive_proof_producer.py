"""Real neutral backup/SQLite facts; explicit parent/profile/mapping doubles."""
import copy
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import comic_archive_proof_producer as p
import comic_archive_repair_action as a
OWNER={'table':'issues','issueid':'123','parentcomicid':'456','releasecomicid':'456'}
class Controls(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='archive-proof-fixture-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  code=self.root/'private-code';code.mkdir(mode=0o700)
  for name in ('comic_reader_backup.py','comic_reader_backup_primitives.py'):
   (code/name).write_bytes((HERE/name).read_bytes());(code/name).chmod(0o600)
  spec=importlib.util.spec_from_file_location('neutral_backup',code/'comic_reader_backup.py');self.backupmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.backupmod)
  self.config=self.root/'reader';self.config.mkdir(mode=0o700);self.forbidden=self.root/'forbidden';self.forbidden.mkdir(mode=0o700);self.operation=self.root/'operation';self.operation.mkdir(mode=0o700)
  self.scratch=self.root/'scratch';self.scratch.mkdir(mode=0o700);self.retention=self.root/'retention';self.retention.mkdir(mode=0o700)
  self.native=self.root/'native';self.native.mkdir(mode=0o700);self.library=self.root/'library';self.library.mkdir(mode=0o700)
  (self.native/'config.ini').write_text('[General]\ndestination_dir=/comics\n')
  for name in ('database.sqlite','tasks.sqlite'):
   with sqlite3.connect(self.config/name) as db:
    db.execute('CREATE TABLE BOOK (ID TEXT, URL TEXT, DELETED_DATE TEXT)');db.execute('CREATE TABLE opaque (kind TEXT, value BLOB)');db.execute('INSERT INTO opaque VALUES (?,?)',('unknown',b'opaque'))
    if name=='database.sqlite':db.executemany('INSERT INTO BOOK VALUES (?,?,?)',[('active','file:///data/comics/book.cbz',None),('deleted','file:///data/comics/book.cbz','old')])
  if self._testMethodName=='test_coherent_WAL_full_table_observation':
   wal=sqlite3.connect(self.config/'database.sqlite');self.addCleanup(wal.close);wal.execute('PRAGMA journal_mode=WAL');wal.execute('INSERT INTO opaque VALUES (?,?)',('wal',b'committed'));wal.commit()
  def ref(path,value):return a.write(path,value)
  self.archive_request=ref(self.root/'request.json',{'version':1,'owner':OWNER,'operation_id':'a'*64});self.scopes=ref(self.root/'scopes.json',{'version':1,'scratch':str(self.scratch),'retention_root':str(self.retention)})
  state={'Running':False,'Status':'exited','Pid':0,'Paused':False,'Restarting':False,'Dead':False,'OOMKilled':False}
  reader={'Id':'reader','State':state,'Mounts':[{'Destination':'/config','Type':'bind','Source':str(self.config)}]}
  self.observations={'reader':reader,'held_native':{'State':{'Pid':123},'Mounts':[{'Type':'bind','RW':True,'Source':str(self.native),'Destination':'/config/mylar'},{'Type':'bind','RW':True,'Source':str(self.library),'Destination':'/comics'}]},'held_worker':{'State':{'Status':'created'},'Mounts':[{'Type':'bind','RW':True,'Source':str(self.library),'Destination':'/data/comics'}]}}
  parent=self.root/'parent.py';parent.write_text('''import copy\nfrom pathlib import Path\ndef same_runtime(a,b):return a==b\nclass Mapping:\n def __init__(self,pairs):self.pairs=pairs\n def child(self,value):\n  for host,child in self.pairs:\n   if value==host or value.startswith(host+"/"):return child+value[len(host):]\n  return value\n def host(self,value):\n  for host,child in self.pairs:\n   if value==child or value.startswith(child+"/"):return host+value[len(child):]\n  return value\nclass Parent:\n def continuous(self):return copy.deepcopy(self.observations)\n''');parent.chmod(0o600)
  sp=importlib.util.spec_from_file_location('parent_fixture',parent);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);self.parent=m.Parent();self.parent.observations=self.observations;self.parent.mapping=m.Mapping([(str(self.native),'/config/mylar'),(str(self.library),'/comics')])
  self.parentref={'path':str(parent),'sha256':hashlib.sha256(parent.read_bytes()).hexdigest(),'signature9':a.nine(parent.stat())}
  self.sdkmap=ref(self.root/'sdk-map.json',{});self.plan=ref(self.root/'parent-plan.json',{'version':10,'action':'archive-one','nonce':'b'*64,'operation':str(self.operation),'producer_inputs':{'archive_request':self.archive_request,'archive_scopes':self.scopes},'sdk_map':self.sdkmap,'provider':{'path':str(HERE/'comic_archive_repair_action.py'),'sha256':p.PINS['comic_archive_repair_action.py']},'native':{'data':'/config/mylar','roots':['/comics']},'selected_image':'sha256:'+'c'*64,'birth_source_sha256':'d'*64})
  inp=ref(self.root/'backup-input.json',{'version':1,'kind':'approved-komga-reader-backup','approved_scope':True,'config_root':str(self.config),'retention_files':[],'forbidden_roots':[str(self.forbidden)],'output_root':str(self.root/'full-backup'),'max_files':100,'max_bytes':10**7,'deadline_seconds':60})
  ack=self.backupmod.run(types.SimpleNamespace(input=Path(inp['path']),input_sha256=inp['sha256'],source_sha256=p.PINS['comic_reader_backup.py']))
  manifest=self.root/'full-backup/manifest.json';self.backup={'manifest':{'path':str(manifest),'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'signature9':a.nine(manifest.stat())},'restore_root':str(self.root/'full-backup/restore/config'),'backup_helper_ack':ack}
  self.request={'version':1,'phase':'backup-controls','nonce':'b'*64,'operation':str(self.operation),'deadline_monotonic':time.monotonic()+60,'parent_plan':self.plan,'parent_source':self.parentref,'context':{'backup':self.backup,'observations':copy.deepcopy(self.observations)}}
 def go(self):return p.produce(self.request['phase'],self.request,watch=self.parent.continuous)
 def phase(self):
  result=self.go()['evidence'];request=copy.deepcopy(self.request);request['phase']='phase-custody'
  controls=result['controls'];input_path=self.root/'execute-input.json';provider=str(HERE/'comic_archive_repair_action.py');command=['/lsiopy/bin/python3','-I','-B',provider,'--phase','execute','--input',str(input_path),'--input-sha256','<INPUT_SHA256>','--source-sha256',p.PINS['comic_archive_repair_action.py']]
  doc={'version':1,'action':'archive-one','nonce':'b'*64,'controls':controls,'archive_scopes':result['archive_scopes'],'command_template':command,'operation':str(self.operation/'execute'),'sdk_map':self.sdkmap,'parent_sha256':self.parentref['sha256'],'selected_image':'sha256:'+'c'*64,'owner':OWNER,'operation_id':'a'*64};iref=a.write(input_path,doc);actual=[iref['sha256'] if x=='<INPUT_SHA256>' else x for x in command]
  inv={'input_path':str(input_path),'input_sha256':iref['sha256'],'command':actual,'nonce':'b'*64,'parent_sha256':self.parentref['sha256'],'provider_sha256':p.PINS['comic_archive_repair_action.py']}
  request['context']={'backup':self.backup,'controls':controls,'archive_scopes':result['archive_scopes'],'observations':copy.deepcopy(self.observations),'phase':'execute','invocation':inv,'stage':'prebirth'};return request
 def test_original_SDK_map_proof_retained(self):
  request=self.phase();result=p.produce('phase-custody',request,watch=self.parent.continuous)['evidence'];self.assertEqual(result['proofs']['archive_sdk_map'],self.sdkmap)
 def test_input_SDK_map_mismatch_held(self):
  request=self.phase();inv=request['context']['invocation'];path=Path(inv['input_path']);value=json.loads(path.read_bytes());value['sdk_map']=a.write(self.root/'foreign-map.json',{})
  raw=a.encoded(value);path.write_bytes(raw);new=hashlib.sha256(raw).hexdigest();inv['input_sha256']=new;inv['command'][9]=new
  with self.assertRaises(p.Held):p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_first_runtime_SDK_map_incarnation_never_refreshes(self):
  original=p.runtime;fired=[]
  def callback(watch,expected):
   result=original(watch,expected)
   if not fired:
    fired.append(True);path=Path(self.sdkmap['path']);path.chmod(0o640);path.chmod(0o600)
   return result
  with patch.object(p,'runtime',side_effect=callback),self.assertRaises(p.Held):self.go()
  self.assertTrue(fired)
 def test_real_neutral_full_backup_eight_roles(self):
  result=self.go()['evidence'];self.assertEqual(set(result['controls']),a.ROLES);self.assertNotIn('rows',result['controls']);self.assertNotIn('timestamp_evidence',result['controls'])
  snapshot=json.loads(Path(result['controls']['reader_snapshot']['path']).read_bytes());self.assertEqual(snapshot['databases']['config:database.sqlite']['tables']['BOOK']['rows'],2);self.assertFalse(snapshot['reader_sql_mutation'])
 def test_coherent_WAL_full_table_observation(self):
  result=self.go()['evidence'];snapshot=json.loads(Path(result['controls']['reader_snapshot']['path']).read_bytes());self.assertEqual(set(snapshot['current_pairs']['database.sqlite']),{'','-wal','-shm'});self.assertEqual(snapshot['databases']['config:database.sqlite']['tables']['opaque']['rows'],2)
 def test_original_source_attributes_not_relabelled(self):
  (self.config/'database.sqlite').chmod(0o640)
  with self.assertRaises(ValueError):self.go()
 def test_five_selection_roles_not_inherited(self):
  path=Path(self.plan['path']);value=json.loads(path.read_bytes());value['producer_inputs']['reviewed_selection']=self.archive_request;raw=a.encoded(value);path.write_bytes(raw);self.plan.update(sha256=hashlib.sha256(raw).hexdigest(),signature9=a.nine(path.stat()))
  with self.assertRaises(p.Held):self.go()
 def test_real_phase_different_worker_destination(self):
  request=self.phase();result=p.produce('phase-custody',request,watch=self.parent.continuous)['evidence'];self.assertEqual(result['birth_seed']['worker_library'],'/data/comics');self.assertEqual(result['reader']['config_root'],str(self.config));self.assertEqual(set(result['proofs']),set(a.ROLES)|{'archive_scopes','archive_sdk_map'})
 def test_original_current_content_change_refused(self):
  with sqlite3.connect(self.config/'database.sqlite') as db:db.execute('UPDATE BOOK SET ID="foreign"')
  with self.assertRaises((p.Held,self.backupmod.Held)):self.go()
 def test_restore_content_corruption_refused(self):
  target=Path(self.backup['restore_root'])/'database.sqlite';raw=target.read_bytes();target.write_bytes(b'X'+raw[1:])
  with self.assertRaises(ValueError):self.go()
 def test_historical_backup_source_label_refused(self):
  path=Path(self.backup['manifest']['path']);value=json.loads(path.read_bytes());value['source_sha256']='e'*64;raw=a.encoded(value);path.write_bytes(raw);self.backup['manifest'].update(sha256=hashlib.sha256(raw).hexdigest(),signature9=a.nine(path.stat()))
  with self.assertRaises(p.Held):self.go()
 def test_no_caller_boolean_watch(self):
  with self.assertRaises(p.Held):p.produce('backup-controls',self.request,watch=lambda:True)
 def test_output_replay_refused(self):
  self.go()
  with self.assertRaises(p.Held):self.go()
 def test_last_runtime_callback_source_change_held(self):
  # Preserve genuine source-bound method code; inject only its copy callback.
  namespace=self.parent.continuous.__func__.__globals__;original=namespace['copy'].deepcopy;count=[]
  def late(value):
   result=original(value)
   if value is self.parent.observations:
    count.append(True)
    if len(count)==2:(self.config/'database.sqlite').chmod(0o640)
   return result
  with patch.object(namespace['copy'],'deepcopy',side_effect=late),self.assertRaises(p.Held):self.go()
 def test_phase_original_companion_absence_held(self):
  request=self.phase();Path(str(self.config/'database.sqlite')+'-journal').write_bytes(b'foreign')
  with self.assertRaises(p.Held):p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_phase_initial_source_parent_rebuild_held(self):
  request=self.phase();real=a.checked;fired=[]
  def late(ref,*args,**kw):
   result=real(ref,*args,**kw)
   if ref['path']==self.parentref['path'] and not fired:
    retained=self.config.with_name('retained-reader');self.config.rename(retained);self.config.mkdir(mode=0o700)
    for item in retained.iterdir():item.rename(self.config/item.name)
    fired.append(True)
   return result
  with patch.object(a,'checked',side_effect=late),self.assertRaises(p.Held):p.produce('phase-custody',request,watch=self.parent.continuous)
  self.assertTrue(fired)
 def test_last_output_callback_mode_refused(self):
  real=p.emit;fired=[]
  def late(o,out,name,value):
   result=real(o,out,name,value)
   if name=='archive-scopes.json':Path(result['path']).chmod(0o640);fired.append(True)
   return result
  with patch.object(p,'emit',side_effect=late),self.assertRaises(p.Held):self.go()
  self.assertTrue(fired)
 def test_phase_last_plan_read_source_change_held(self):
  request=self.phase();real=p.Originals.ref;calls=[]
  def late(o,ref,*args,**kw):
   result=real(o,ref,*args,**kw)
   if ref['path']==self.plan['path']:
    calls.append(True)
    if len(calls)==2:(self.config/'database.sqlite').chmod(0o640)
   return result
  with patch.object(p.Originals,'ref',new=late),self.assertRaises(p.Held):p.produce('phase-custody',request,watch=self.parent.continuous)
  self.assertEqual(len(calls),2)
 def test_nonprivate_scratch_held_before_projection_write(self):
  self.scratch.chmod(0o755)
  with self.assertRaises(p.Held):self.go()
  self.assertFalse((self.operation/'archive-proofs').exists())
 def verification_request(self):
  request=self.phase();stage=self.native/('archive-repair-'+'a'*64);stage.mkdir(mode=0o700);metadata=a.write(stage/'preparation.json',{'fixture_only':True});journal=self.retention/('adopt-'+'a'*64)/'journal';journal.mkdir(parents=True,mode=0o700);baseline=a.write(journal/'baseline.json',{'fixture_only':True})
  metadata['path']='/config/mylar/'+stage.name+'/preparation.json'
  value={'version':1,'kind':'archive-one-original-custody','owner':OWNER,'operation_id':'a'*64,'baseline':baseline,'preparation':metadata,'preparation_directory9':a.nine(stage.stat()),'reader':{'fixture_only':True},'publication_acceptance':False,'mutation_authority':False}
  ref=a.write(self.root/'execution-originals.json',value);ctx=request['context'];ctx.update(phase='verify-terminal',execution_originals=ref)
  inv=ctx['invocation'];inv['command'][5]='verify-terminal';old=Path(inv['input_path']);doc=json.loads(old.read_bytes());doc.update(execution_originals=ref);doc['command_template'][5]='verify-terminal';path=self.root/'verify-input.json';doc['command_template'][7]=str(path);iref=a.write(path,doc);inv.update(input_path=str(path),input_sha256=iref['sha256']);inv['command'][7]=str(path);inv['command'][9]=iref['sha256'];return request,stage,metadata
 def test_verification_original_metadata_and_directory_CAS(self):
  request,stage,metadata=self.verification_request();result=p.produce('phase-custody',request,watch=self.parent.continuous)['evidence'];self.assertIn('archive_preparation_metadata',result['proofs']);self.assertEqual(result['proofs']['archive_preparation_metadata']['signature9'],metadata['signature9'])
 def test_verification_original_metadata_change_not_refreshed(self):
  request,stage,metadata=self.verification_request();(stage/'preparation.json').write_bytes(b'{"foreign":true}')
  with self.assertRaises(p.Held):p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_last_close_callback_never_acknowledged(self):
  real=p.close;fired=[]
  def late(originals):real(originals);(self.config/'database.sqlite').chmod(0o640);fired.append(True)
  with patch.object(p,'close',side_effect=late),self.assertRaises(p.Held):self.go()
  self.assertTrue(fired)
 def test_worker_shadow_refused(self):
  request=self.phase();self.parent.observations['held_worker']['Mounts'].append({'Type':'volume','RW':True,'Source':str(self.forbidden),'Destination':'/data/comics'})
  request['context']['observations']=copy.deepcopy(self.parent.observations)
  with self.assertRaises(ValueError):p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_first_watch_never_refreshes_restore_original_ctime(self):
  path=self.root/'full-backup/restore/config/database.sqlite';original=p.a.nine(path.stat());fired=[]
  # Patch the first callback's actual deepcopy, retaining the source-bound method.
  original_copy=copy.deepcopy
  def changed(value,*args,**kwargs):
   result=original_copy(value,*args,**kwargs)
   if not fired and any(frame.function=='continuous' for frame in inspect.stack()[1:7]):
    fired.append(True);path.chmod(0o640);path.chmod(0o644)
   return result
  with patch.object(copy,'deepcopy',side_effect=changed),self.assertRaises(p.Held):self.go()
  self.assertTrue(fired);self.assertEqual(original[:4],p.a.nine(path.stat())[:4]);self.assertNotEqual(original[4],p.a.nine(path.stat())[4])

 def test_first_emit_cannot_refresh_created_output_incarnation(self):
  original_emit=p.emit;fired=[];out=self.operation/'archive-proofs';retained=self.operation/'original-output'
  def changed(originals,path,name,value):
   if not fired:
    fired.append(True);path.rename(retained);path.mkdir(mode=0o700)
   return original_emit(originals,path,name,value)
  with patch.object(p,'emit',side_effect=changed),self.assertRaises(p.Held):self.go()
  self.assertTrue(fired);self.assertEqual(list(out.iterdir()),[]);self.assertEqual(list(retained.iterdir()),[])

if __name__=='__main__':unittest.main()
