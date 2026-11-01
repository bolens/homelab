"""Real neutral backup/SQLite facts; explicit parent/profile/mapping doubles."""
import copy
import hashlib
import importlib.util
import inspect
import io
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
  reader={'Id':'reader','State':state,'Mounts':[{'Destination':'/config','Type':'bind','RW':True,'Source':str(self.config)}]}
  self.observations={'reader':reader,'held_native':{'State':{'Pid':123},'Mounts':[{'Type':'bind','RW':True,'Source':str(self.native),'Destination':'/config/mylar'},{'Type':'bind','RW':True,'Source':str(self.library),'Destination':'/comics'}]},'held_worker':{'State':{'Status':'created'},'Mounts':[{'Type':'bind','RW':True,'Source':str(self.library),'Destination':'/data/comics'}]}}
  parent=self.root/'parent.py';parent.write_text('''import copy\nfrom pathlib import Path\nfrom comic_reader_lifecycle_parent import Paths,LifecycleParent\ndef same_runtime(a,b):return a==b\nclass Mapping(Paths):\n def __init__(self,pairs):\n  super().__init__([dict(host=str(Path(pairs[0][0]).parent),child=str(Path(pairs[0][0]).parent),write=True)])\n  self.pairs=pairs\n def child(self,value):\n  for host,child in self.pairs:\n   if value==host or value.startswith(host+"/"):return child+value[len(host):]\n  return value\n def host(self,value):\n  for host,child in self.pairs:\n   if value==child or value.startswith(child+"/"):return host+value[len(child):]\n  return value\nclass Parent:\n child_control=LifecycleParent.child_control\n def continuous(self):return copy.deepcopy(self.observations)\n''');parent.chmod(0o600)
  sp=importlib.util.spec_from_file_location('parent_fixture',parent);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);self.parent=m.Parent();self.parent.observations=self.observations;self.parent.mapping=m.Mapping([(str(self.native),'/config/mylar'),(str(self.library),'/comics')])
  self.parentref={'path':str(parent),'sha256':hashlib.sha256(parent.read_bytes()).hexdigest(),'signature9':a.nine(parent.stat())}
  self.sdkmap=ref(self.root/'sdk-map.json',{});self.plan=ref(self.root/'parent-plan.json',{'version':10,'action':'archive-one','nonce':'b'*64,'operation':str(self.operation),'producer_inputs':{'archive_request':self.archive_request,'archive_scopes':self.scopes},'sdk_map':self.sdkmap,'provider':{'path':str(HERE/'comic_archive_repair_action.py'),'sha256':p.PINS['comic_archive_repair_action.py']},'native':{'data':'/config/mylar','roots':['/comics']},'selected_image':'sha256:'+'c'*64,'birth_source_sha256':'d'*64})
  inp=ref(self.root/'backup-input.json',{'version':1,'kind':'approved-komga-reader-backup','approved_scope':True,'config_root':str(self.config),'retention_files':[],'forbidden_roots':[str(self.forbidden)],'output_root':str(self.root/'full-backup'),'max_files':100,'max_bytes':10**7,'deadline_seconds':60})
  ack=self.backupmod.run(types.SimpleNamespace(input=Path(inp['path']),input_sha256=inp['sha256'],source_sha256=p.PINS['comic_reader_backup.py']))
  manifest=self.root/'full-backup/manifest.json';self.backup={'manifest':{'path':str(manifest),'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'signature9':a.nine(manifest.stat())},'restore_root':str(self.root/'full-backup/restore/config'),'backup_helper_ack':ack}
  self.request={'version':1,'phase':'backup-controls','nonce':'b'*64,'operation':str(self.operation),'deadline_monotonic':time.monotonic()+60,'parent_plan':self.plan,'parent_source':self.parentref,'context':{'backup':self.backup,'observations':copy.deepcopy(self.observations)}}
 def go(self):return p.produce(self.request['phase'],self.request,watch=self.parent.continuous)
 def copied_manifest_view(self):
  original=self.backup['manifest'];self.original_manifest=copy.deepcopy(original)
  views=self.operation/'child-output-views';views.mkdir(mode=0o700)
  view=views/'manifest-view.json';view.write_bytes(Path(original['path']).read_bytes());view.chmod(0o600)
  self.backup['manifest']=dict(path=str(view),sha256=original['sha256'],signature9=a.nine(view.stat()))
 def test_stopped_named_volume_preserves_original_config_source(self):
  row=copy.deepcopy(self.observations['reader']);row['Mounts'][0].update(Type='volume',Driver='local',Name='reader_config')
  before=copy.deepcopy(row);self.assertEqual(p.stopped(row),self.config);self.assertEqual(row,before)
 def test_stopped_config_rejects_foreign_volume_and_shadow(self):
  for fault in ('driver','shadow','readonly','name'):
   row=copy.deepcopy(self.observations['reader']);row['Mounts'][0].update(Type='volume',Driver='local',Name='reader_config')
   if fault=='driver':row['Mounts'][0]['Driver']='foreign'
   elif fault=='shadow':row['Mounts'].append(dict(Type='bind',Source='/other',Destination='/config/index',RW=True))
   elif fault=='readonly':row['Mounts'][0]['RW']=False
   else:row['Mounts'][0].pop('Name')
   with self.subTest(fault=fault),self.assertRaisesRegex(p.Held,'archive-producer-config-bind'):p.stopped(row)
 def test_backup_manifest_config_inverse_projection_is_required(self):
  mapping=self.parent.mapping;child=mapping.child
  mapping.child=lambda value:'/wrong-reader' if str(value)==str(self.config)else child(value)
  with self.assertRaisesRegex(p.Held,'archive-producer-config-restore-join'):self.go()
 def test_copied_manifest_view_keeps_original_backup_geometry(self):
  self.copied_manifest_view();evidence=self.go()['evidence']
  self.assertEqual(evidence['controls']['backup_manifest'],self.backup['manifest'])
  self.assertFalse((Path(self.backup['manifest']['path']).parent/'backup').exists())
  self.assertEqual(json.loads(Path(evidence['controls']['custody']['path']).read_bytes())['restore_root'],self.backup['restore_root'])
 def test_copied_manifest_view_phase_custody_uses_original_restore(self):
  self.copied_manifest_view();request=self.phase()
  result=p.produce('phase-custody',request,watch=self.parent.continuous)['evidence']
  self.assertEqual(result['proofs']['backup_manifest'],self.backup['manifest'])
 def test_copied_manifest_original_read_allows_uid1000_under_root_observer(self):
  self.copied_manifest_view();checked=a.checked
  def root_reader(ref,private=True):
   if ref['path']==self.original_manifest['path']:
    # Project only the Root reader identity; the real original keeps UID1000
    # and its helper-bound bytes/full9. Other local fixture reads are unchanged.
    with patch.object(a.os,'geteuid',return_value=0):return checked(ref,private)
   return checked(ref,private)
  with patch.object(a,'checked',side_effect=root_reader):self.go()
 def test_copied_manifest_view_requires_original_completion_vector(self):
  self.copied_manifest_view()
  vectors=self.backup['backup_helper_ack']['original_vectors']
  vectors['files']=[row for row in vectors['files'] if row[0]!=self.original_manifest['path']]
  with self.assertRaisesRegex(p.Held,'archive-producer-original-manifest-completion'):self.go()
 def test_copied_manifest_view_refuses_changed_original_manifest(self):
  self.copied_manifest_view();path=Path(self.original_manifest['path']);path.write_bytes(path.read_bytes()+b' ')
  with self.assertRaises(p.Held):self.go()

 def phase(self):
  result=self.go()['evidence'];request=copy.deepcopy(self.request);request['phase']='phase-custody'
  controls=result['controls'];input_path=self.root/'execute-input.json';provider=str(HERE/'comic_archive_repair_action.py');command=['/lsiopy/bin/python3','-I','-B',provider,'--phase','execute','--input',str(input_path),'--input-sha256','<INPUT_SHA256>','--source-sha256',p.PINS['comic_archive_repair_action.py']]
  doc={'version':1,'action':'archive-one','nonce':'b'*64,'controls':controls,'archive_scopes':result['archive_scopes'],'command_template':command,'operation':str(self.operation/'execute'),'sdk_map':self.sdkmap,'parent_sha256':self.parentref['sha256'],'selected_image':'sha256:'+'c'*64,'owner':OWNER,'operation_id':'a'*64};iref=a.write(input_path,doc);actual=[iref['sha256'] if x=='<INPUT_SHA256>' else x for x in command]
  inv={'input_path':str(input_path),'input_sha256':iref['sha256'],'command':actual,'nonce':'b'*64,'parent_sha256':self.parentref['sha256'],'provider_sha256':p.PINS['comic_archive_repair_action.py']}
  request['context']={'backup':self.backup,'controls':controls,'archive_scopes':result['archive_scopes'],'observations':copy.deepcopy(self.observations),'phase':'execute','invocation':inv,'stage':'prebirth'};return request
 def copied_provider_phase(self):
  # Runtime/backup remain explicit doubles; all custody paths use real copies,
  # scopes, full9 checks and Paths dispatch from this boundary onward.
  import os
  import comic_child_control_projection as projection
  import comic_reader_lifecycle_parent as parent
  request=self.phase();plan=json.loads(Path(self.plan['path']).read_bytes())
  provider=self.root/'private-code'/'comic_archive_repair_action.py'
  provider.write_bytes((HERE/'comic_archive_repair_action.py').read_bytes());provider.chmod(0o600)
  original=dict(path=str(provider),sha256=p.digest(provider.read_bytes()),signature9=a.nine(provider.stat()))
  tree=projection.Tree(self.root/'child-controls','/_operation',self.operation,lambda ref:a.checked(ref,False)[0],uid=os.geteuid(),gid=os.getegid())
  mapping=parent.Paths([dict(host=str(self.root),child=str(self.root),write=True),dict(host=str(self.native),child='/config/mylar',write=True),dict(host=str(self.library),child='/comics',write=True)])
  mapping.owner=self.parent;self.parent.mapping=mapping;self.parent.left=tree.check
  parent._CHILD_TREES[self.parent]=tree;self.addCleanup(parent._CHILD_TREES.pop,self.parent,None)
  projected=mapping.child_ref(original)
  self.assertNotEqual(mapping.host(projected['path']),original['path'])
  self.assertEqual(mapping.original_host(mapping.host(projected['path'])),original['path'])
  plan['provider']=original;path=Path(self.plan['path']);path.write_bytes(a.encoded(plan))
  request['parent_plan']=dict(path=str(path),sha256=p.digest(path.read_bytes()),signature9=a.nine(path.stat()))
  ctx=request['context'];scope_path=Path(ctx['archive_scopes']['path'])
  scope_doc=dict(version=1,**{role:mapping.child(mapping.private_scope(str(path),role)) for role,path in [('scratch',self.scratch),('retention_root',self.retention)]})
  scope_path.write_bytes(a.encoded(scope_doc));ctx['archive_scopes']=dict(path=str(scope_path),sha256=p.digest(scope_path.read_bytes()),signature9=a.nine(scope_path.stat()))
  inv=ctx['invocation'];old_path=Path(inv['input_path']);doc=json.loads(old_path.read_bytes())
  path=self.operation/'execute-input.json';child_input=mapping.child(str(path))
  doc['command_template'][3]=projected['path'];doc['command_template'][7]=child_input
  doc['controls']={role:mapping.child_ref(ref) for role,ref in ctx['controls'].items()}
  doc['archive_scopes']=mapping.child_ref(ctx['archive_scopes']);doc['sdk_map']=mapping.child_ref(self.sdkmap);doc['operation']=mapping.child(str(self.operation/'execute'))
  path.write_bytes(a.encoded(doc));path.chmod(0o600)
  input_ref=dict(path=str(path),sha256=p.digest(path.read_bytes()),signature9=a.nine(path.stat()))
  inv['input_path']=mapping.child_ref(input_ref)['path'];inv['input_sha256']=input_ref['sha256']
  inv['command']=[input_ref['sha256'] if v=='<INPUT_SHA256>' else v for v in doc['command_template']]
  return request,tree,original,projected
 def test_phase_custody_joins_real_projected_provider_to_original(self):
  request,tree,original,projected=self.copied_provider_phase()
  result=p.produce('phase-custody',request,watch=self.parent.continuous)['evidence']
  self.assertEqual(result['birth_seed']['invocation']['command'][3],projected['path'])
  tree.check();self.assertEqual(a.nine(Path(original['path']).stat()),original['signature9'])
 def test_phase_custody_refuses_changed_projected_provider(self):
  request,tree,_,projected=self.copied_provider_phase()
  Path(tree.host(projected['path'])).write_bytes(b'foreign')
  with self.assertRaisesRegex(ValueError,'child-control-final9'):p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_phase_custody_refuses_foreign_original_provider_roundtrip(self):
  request,tree,_,projected=self.copied_provider_phase();physical=tree.host(projected['path']);original_host=self.parent.mapping.original_host
  self.parent.mapping.original_host=lambda path:'/foreign/provider.py' if path==physical else original_host(path)
  with self.assertRaisesRegex(p.Held,'archive-producer-path-roundtrip'):p.produce('phase-custody',request,watch=self.parent.continuous)
 def live_data_phase(self):
  self.observations['held_worker']['Mounts'].append(dict(Type='bind',RW=False,Source=str(self.native),Destination='/mylar'))
  self.request['context']['observations']=copy.deepcopy(self.observations)
  return self.phase()
 def final_runtime_activity(self,activity):
  original=p.runtime;calls=[]
  def callback(watch,expected):
   result=original(watch,expected);calls.append(True)
   if len(calls)==2:activity()
   return result
  return callback
 def test_prebirth_live_data_journal_roundtrip_keeps_original_identity_and_file_guards(self):
  path=self.native/'workflow.sqlite'
  with sqlite3.connect(path) as db:db.execute('CREATE TABLE state(value INTEGER)');db.execute('INSERT INTO state VALUES(1)')
  original=a.nine(path.stat());raw=path.read_bytes();config=a.nine((self.native/'config.ini').stat());observed=[]
  request=self.live_data_phase()
  def activity():
   with sqlite3.connect(path) as db:
    db.execute('BEGIN IMMEDIATE');db.execute('UPDATE state SET value=2');observed.append(Path(str(path)+'-journal').is_file());db.rollback()
   self.assertFalse(Path(str(path)+'-journal').exists())
  with patch.object(p,'runtime',self.final_runtime_activity(activity)):
   result=p.produce('phase-custody',request,watch=self.parent.continuous)
  self.assertEqual(observed,[True]);self.assertEqual(path.read_bytes(),raw);self.assertEqual(a.nine(path.stat()),original)
  self.assertEqual(a.nine((self.native/'config.ini').stat()),config);self.assertIn('birth_seed',result['evidence'])
 def test_live_data_inode_change_still_refuses_original_node(self):
  request=self.live_data_phase()
  def activity():self.native.rename(self.root/'retained-native');self.native.mkdir(mode=0o700)
  with patch.object(p,'runtime',self.final_runtime_activity(activity)),self.assertRaisesRegex(p.Held,'archive-producer-final-node'):
   p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_live_data_mode_change_still_refuses_original_node(self):
  request=self.live_data_phase()
  with patch.object(p,'runtime',self.final_runtime_activity(lambda:self.native.chmod(0o750))),self.assertRaisesRegex(p.Held,'archive-producer-final-node'):
   p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_live_data_config_file_incarnation_stays_immutable(self):
  request=self.live_data_phase();path=self.native/'config.ini';mode=path.stat().st_mode & 0o777
  def activity():path.chmod(mode ^ 0o040);path.chmod(mode)
  with patch.object(p,'runtime',self.final_runtime_activity(activity)),self.assertRaisesRegex(p.Held,'archive-producer-final-file'):
   p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_other_custody_directories_keep_full9(self):
  request=self.live_data_phase()
  for directory in (self.config,Path(self.backup['restore_root']),self.library,self.scratch,self.retention):
   with self.subTest(directory=directory.name):
    def activity():
     path=directory/'transient';path.write_bytes(b'');path.unlink()
    with patch.object(p,'runtime',self.final_runtime_activity(activity)),self.assertRaisesRegex(p.Held,'archive-producer-final-file'):
     p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_foreign_duplicate_or_writable_worker_data_binding_refuses(self):
  request=self.live_data_phase();mounts=request['context']['observations']['held_worker']['Mounts']
  original=copy.deepcopy(mounts)
  for change in ('foreign','duplicate','writable'):
   with self.subTest(change=change):
    mounts[:]=copy.deepcopy(original)
    if change=='foreign':mounts[-1]['Source']=str(self.forbidden)
    elif change=='duplicate':mounts.append(copy.deepcopy(mounts[-1]))
    else:mounts[-1]['RW']=True
    self.parent.observations['held_worker']['Mounts']=copy.deepcopy(mounts)
    with self.assertRaisesRegex(p.Held,'archive-producer-live-data-binding'):p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_missing_worker_data_witness_keeps_legacy_directory_full9(self):
  request=self.phase()
  def activity():
   path=self.native/'transient';path.write_bytes(b'');path.unlink()
  with patch.object(p,'runtime',self.final_runtime_activity(activity)),self.assertRaisesRegex(p.Held,'archive-producer-final-file'):
   p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_live_data_owner_stat_change_still_refuses_original_node(self):
  request=self.live_data_phase();active=[];original=p._host_stat
  def metadata(owner,path):
   z=original(owner,path)
   if active and Path(path)==self.native:
    fields={name:getattr(z,name) for name in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_gid','st_nlink')};fields['st_uid']+=1;return types.SimpleNamespace(**fields)
   return z
  with patch.object(p,'runtime',self.final_runtime_activity(lambda:active.append(True))),patch.object(p,'_host_stat',metadata),self.assertRaisesRegex(p.Held,'archive-producer-final-node'):
   p.produce('phase-custody',request,watch=self.parent.continuous)
 def test_file_change_diagnostic_is_bounded_metadata_and_does_not_mask_refusal(self):
  path=self.root/'original-private-name';ref=a.write(path,{'version':1});o=p.Originals([path]);o.ref(ref);originals=o.frozen();path.write_bytes(b'changed')
  stderr=io.StringIO()
  with patch.object(sys,'stderr',stderr),self.assertRaisesRegex(p.Held,'^archive-producer-final-file$'):p.close(originals)
  detail=json.loads(stderr.getvalue());self.assertLess(len(stderr.getvalue()),1024);self.assertNotIn(str(path),stderr.getvalue())
  self.assertEqual(detail['path_sha256'],hashlib.sha256(str(path).encode()).hexdigest());self.assertEqual(detail['original9'],ref['signature9']);self.assertEqual(detail['current9'],a.nine(path.stat()));self.assertTrue(detail['changed_fields'])
  with patch.object(sys.stderr,'write',side_effect=OSError('diagnostic unavailable')),self.assertRaisesRegex(p.Held,'^archive-producer-final-file$'):p.close(originals)
  path.unlink()
  with self.assertRaises(FileNotFoundError):p.close(originals)
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
  def late(originals,**kwargs):real(originals,**kwargs);(self.config/'database.sqlite').chmod(0o640);fired.append(True)
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
