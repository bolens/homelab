"""Pure captured-role boundary + real private control files; no Docker/NFS grant."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
def reader_restart_profiles(host_root=None):
 rows=json.loads((ROOT/'reader_restart_profiles.json').read_bytes())
 if host_root is not None:
  # Preserve the captured Docker shapes while mapping fixture bind sources into
  # the scheduling test's declared host mount. No engine path is dereferenced.
  def project(value):
   if isinstance(value,str) and value.startswith('/fixture/mount-'):
    return str(host_root)+value[len('/fixture'):]
   if isinstance(value,list):return [project(v)for v in value]
   if isinstance(value,dict):return {k:project(v)for k,v in value.items()}
   return value
  rows=project(rows)
 return rows
spec=importlib.util.spec_from_file_location('current_nfs',ROOT/'comic_negative_nfs_active_parent.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def image(n):return 'sha256:'+str(n)*64
def row(n,name,status):
 running=status=='running';state=dict(Status=status,Running=running,Paused=False,Restarting=False,Dead=False,OOMKilled=False,Pid=n+400 if running else 0,StartedAt='original-'+str(n),FinishedAt='',ExitCode=0,Error='')
 return dict(Id=str(n)*64,Name='/'+name,Image=image(n),Path='ordinary-entry',Args=['ordinary'],Config={'Env':['PUBLIC_FIXTURE=1']},HostConfig={'NetworkMode':'none'},Mounts=[],NetworkSettings={},State=state)
def ref(path,raw):
 path.write_bytes(raw);path.chmod(0o600);return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),signature9=m.stamp(path))

def bridge_profile(profile):
 value=copy.deepcopy(profile)
 value['Config']['ExposedPorts']={'25600/tcp':{}}
 value['HostConfig'].update(NetworkMode='a'*64,PortBindings={},PublishAllPorts=False)
 value['NetworkSettings']=dict(Ports={'25600/tcp':None},SandboxID='b'*64,SandboxKey='/var/run/docker/netns/'+'b'*12,Networks={'fixture':dict(NetworkID='a'*64,EndpointID='c'*64,IPAddress='10.251.242.98',IPPrefixLen=28,MacAddress='02:42:0a:fb:f2:62',Gateway='10.251.242.97',Aliases=['reader'])})
 return value

def release_bridge(profile):
 value=copy.deepcopy(profile);settings=value['NetworkSettings']
 settings.update(Ports={},SandboxID='',SandboxKey='')
 settings['Networks']['fixture'].update(EndpointID='',IPAddress='',IPPrefixLen=0,MacAddress='')
 return value

def resumed_bridge_profile(original):
 value=copy.deepcopy(original);settings=value['NetworkSettings']
 settings.update(SandboxID='d'*64,SandboxKey='/var/run/docker/netns/'+'d'*12)
 settings['Networks']['fixture'].update(EndpointID='e'*64,IPAddress='10.251.242.99',MacAddress='02:42:0a:fb:f2:63')
 value['State'].update(Status='running',Running=True,Pid=900,StartedAt='fresh-owned-start',FinishedAt='',ExitCode=0)
 return value

class Controls(unittest.TestCase):
 def test_captured_internal_reader_stop_uses_original_gateway(self):
  rows=reader_restart_profiles();before=rows['before'];stopped=rows['stopped']
  keys=('Id','Name','Image','Path','Args','Config','HostConfig','Mounts','NetworkSettings')
  original={k:before[k]for k in keys};current={k:stopped[k]for k in keys}
  self.assertTrue(m.reader_stopped_static(original,current,before['Id']))
  for gateway in ('192.0.2.1',None,False):
   changed=copy.deepcopy(current);changed['NetworkSettings']['Networks']['fixture-internal']['Gateway']=gateway
   with self.subTest(gateway=gateway):self.assertFalse(m.reader_stopped_static(original,changed,before['Id']))
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.rows=[row(1,'unique-native','running'),row(2,'unique-worker','created'),row(3,'unique-reader','running')]
  self.images=patch.multiple(m,NATIVE_IMAGE=image(1),WORKER=image(2),KOMGA=image(3));self.images.start();self.addCleanup(self.images.stop)
  self.roles={role:dict(id=r['Id'],image=r['Image'],profile={k:copy.deepcopy(r[k]) for k in m.ROLE_STATIC},epoch=copy.deepcopy(r['State'])) for role,r in zip(('native','worker','reader'),self.rows)}
  plan={key:dict(id=self.roles[role]['id'],profile=self.roles[role]['profile']) for role,key in m.ROLE_KEYS.items()}
  self.plan=ref(self.root/'plan.json',m.encode(plan));self.source=ref(self.root/'source.py',b'# public source fixture; no Parent factory claim\n')
  ancestors={}
  for control in (self.plan,self.source):ancestors.update(m.ancestry([Path(control['path'])]))
  self.payload=dict(version=1,kind='parent-original-current-three-role-selectors',plan=self.plan,source=self.source,roles=self.roles,ancestors=ancestors)
 def capture(self):return m.current_roles(m.encode(self.payload))
 def test_unique_original_ids_images_and_actual_names(self):
  roles=self.capture();selected=m.select_roles(list(reversed(self.rows)),roles)
  self.assertEqual(selected['native']['Name'],'/unique-native');self.assertEqual(selected['reader']['Name'],'/unique-reader')
  self.assertEqual(m.role_ids(roles),[r['Id'] for r in self.rows])
  self.assertEqual(m.identities(self.rows[:2],roles),[dict(id=r['Id'],image=r['Image'],pid=r['State']['Pid'],started_at=r['State']['StartedAt']) for r in self.rows[:2]])
 def test_foreign_image_not_adopted(self):
  roles=self.capture();foreign=copy.deepcopy(self.rows);foreign[0]['Image']=image(9)
  with self.assertRaisesRegex(m.Held,'static-original'):m.select_roles(foreign,roles)
  self.payload['roles']['native']['image']=image(9)
  with self.assertRaisesRegex(m.Held,'source-cohort-image-plan'):self.capture()
 def test_foreign_id_duplicate_or_missing_refused(self):
  roles=self.capture()
  for rows in (self.rows[:2],[self.rows[0],self.rows[0],self.rows[2]]):
   with self.assertRaises(m.Held):m.select_roles(rows,roles)
  self.payload['roles']['reader']['id']=self.payload['roles']['native']['id']
  with self.assertRaises(m.Held):self.capture()
 def test_original_epoch_refuses_restart_and_worker_start(self):
  roles=self.capture()
  for key,value in [('Pid',999),('StartedAt','new')]:
   rows=copy.deepcopy(self.rows);rows[0]['State'][key]=value
   with self.assertRaisesRegex(m.Held,'runtime-epoch'):m.select_roles(rows,roles)
  rows=copy.deepcopy(self.rows);rows[1]['State'].update(Status='running',Running=True,Pid=801)
  with self.assertRaisesRegex(m.Held,'runtime-epoch'):m.select_roles(rows,roles)
 def test_static_security_mount_changes_refused(self):
  roles=self.capture()
  for key,value in [('HostConfig',{'NetworkMode':'host'}),('Mounts',[{'Source':'/foreign'}]),('Config',{'Env':['foreign']})]:
   rows=copy.deepcopy(self.rows);rows[0][key]=value
   with self.assertRaisesRegex(m.Held,'static-original'):m.select_roles(rows,roles)
 def test_health_log_is_not_epoch(self):
  roles=self.capture();rows=copy.deepcopy(self.rows);rows[0]['State']['Health']={'Status':'healthy','Log':['advanced']}
  self.assertEqual(m.select_roles(rows,roles)['native']['State']['Pid'],401)
 def test_same_reader_owned_stop_projection_preserves_actual_name(self):
  roles=self.capture();rows=copy.deepcopy(self.rows);rows[2]['State'].update(Status='exited',Running=False,Pid=0,FinishedAt='owned-stop')
  with self.assertRaisesRegex(m.Held,'runtime-epoch'):m.select_roles(rows,roles)
  self.assertEqual(m.select_roles(rows,roles,stopped=True)['reader']['Name'],'/unique-reader')
  rows[2]['State']['StartedAt']='foreign-recreation'
  with self.assertRaisesRegex(m.Held,'reader-stopped'):m.select_roles(rows,roles,stopped=True)
 def test_control_same_bytes_replacement_refused(self):
  path=Path(self.plan['path']);raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600)
  with self.assertRaisesRegex(m.Held,'original9'):self.capture()
 def test_original_ancestor_mode_drift_refused(self):
  self.root.chmod(0o750)
  with self.assertRaisesRegex(m.Held,'ancestor5'):self.capture()
 def test_unbound_and_wrong_kind_refused(self):
  with self.assertRaisesRegex(m.Held,'bound-bytes'):m.current_roles(None)
  self.payload['kind']='saved-authority'
  with self.assertRaisesRegex(m.Held,'role-kind'):self.capture()
 def test_scope_freshness_remains_120_seconds(self):
  with patch.object(m.time,'time',return_value=1000):
   m.fresh_scope({'observed':880})
   for observed in (879,1001,True):
    with self.assertRaisesRegex(m.Held,'scope-expired'):m.fresh_scope({'observed':observed})
 def test_nfs4_gate_unchanged(self):
  # Actual owning mount validator remains NFS-specific; no local fstype projection.
  for fstype in ('tmpfs','btrfs','ext4'):
   with self.assertRaises(m.Held):m.mount_identity({'filesystems':[dict(source='public-fixture',target=str(self.root),fstype=fstype,fsroot='/',options='rw',**{'maj:min':'0:1'})]})

 def test_bridge_stop_derives_only_seven_teardown_fields(self):
  original=bridge_profile(self.roles['reader']['profile']);current=release_bridge(original)
  self.assertTrue(m.reader_stopped_static(original,current,original['Id']))
  self.assertFalse(m.reader_stopped_static(original,original,original['Id']))
  for name in ('EndpointID','IPAddress','IPPrefixLen','MacAddress'):
   changed=copy.deepcopy(current);changed['NetworkSettings']['Networks']['fixture'][name]=original['NetworkSettings']['Networks']['fixture'][name]
   self.assertFalse(m.reader_stopped_static(original,changed,original['Id']),name)
  for name in ('Ports','SandboxID','SandboxKey'):
   changed=copy.deepcopy(current);changed['NetworkSettings'][name]=original['NetworkSettings'][name]
   self.assertFalse(m.reader_stopped_static(original,changed,original['Id']),name)
 def test_bridge_stop_refuses_unrelated_static_and_network_drift(self):
  original=bridge_profile(self.roles['reader']['profile']);current=release_bridge(original)
  for key in m.ROLE_STATIC:
   changed=copy.deepcopy(current);changed[key]=None
   self.assertFalse(m.reader_stopped_static(original,changed,original['Id']),key)
  for key in ('NetworkID','Gateway','Aliases'):
   changed=copy.deepcopy(current);changed['NetworkSettings']['Networks']['fixture'][key]='foreign'
   self.assertFalse(m.reader_stopped_static(original,changed,original['Id']),key)
  changed=copy.deepcopy(current);changed['NetworkSettings']['Networks']['extra']={}
  self.assertFalse(m.reader_stopped_static(original,changed,original['Id']))
 def test_bridge_stop_refuses_published_ports_and_malformed_originals(self):
  original=bridge_profile(self.roles['reader']['profile'])
  for section,key,value in [('HostConfig','PortBindings',{'25600/tcp':[{'HostPort':'25600'}]}),('HostConfig','PublishAllPorts',True),('NetworkSettings','SandboxID',None),('Config','ExposedPorts',{})]:
   changed=copy.deepcopy(original);changed[section][key]=value
   self.assertFalse(m.reader_stopped_static(changed,release_bridge(changed),changed['Id']))
  malformed=copy.deepcopy(original);malformed['Config']=None
  self.assertFalse(m.reader_stopped_static(malformed,release_bridge(malformed),malformed['Id']))
  for key,value in [('IPPrefixLen',True),('IPAddress','999.1.1.1'),('EndpointID',None),('MacAddress',None)]:
   changed=copy.deepcopy(original);changed['NetworkSettings']['Networks']['fixture'][key]=value
   self.assertFalse(m.reader_stopped_static(changed,release_bridge(changed),changed['Id']))
 def test_bridge_stop_role_selection_preserves_other_epochs(self):
  self.rows[2]=dict(bridge_profile(self.roles['reader']['profile']),State=self.rows[2]['State'])
  self.roles['reader']['profile']={k:copy.deepcopy(self.rows[2][k]) for k in m.ROLE_STATIC}
  roles={'roles':self.roles};rows=copy.deepcopy(self.rows)
  rows[2]=dict(release_bridge(roles['roles']['reader']['profile']),State=copy.deepcopy(rows[2]['State']))
  rows[2]['State'].update(Status='exited',Running=False,Pid=0)
  self.assertEqual(m.select_roles(rows,roles,stopped=True)['reader']['Id'],rows[2]['Id'])
  for role in (0,1):
   changed=copy.deepcopy(rows);changed[role]['Config']['Env'].append('foreign')
   with self.assertRaises(m.Held):m.select_roles(changed,roles,stopped=True)
  rows[2]['State']['StartedAt']='foreign'
  with self.assertRaises(m.Held):m.select_roles(rows,roles,stopped=True)
 def test_parent_and_child_stop_projection_ast_parity(self):
  def body(path):return next(ast.dump(n,include_attributes=False) for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='reader_stopped_static')
  self.assertEqual(body(ROOT/'comic_reader_lifecycle_parent.py'),body(ROOT/'comic_negative_nfs_active_parent.py'))
 def test_active_canary_bridge_stop_and_later_static_drift(self):
  rows=copy.deepcopy(self.rows);rows[2]=dict(bridge_profile(self.roles['reader']['profile']),State=rows[2]['State'])
  current=copy.deepcopy(rows);current[2]=dict(release_bridge({k:rows[2][k] for k in m.ROLE_STATIC}),State=current[2]['State'])
  current[2]['State'].update(Status='exited',Running=False,Pid=0)
  # Actual sealed canary, with only the external runtime observer projected.
  canary=m.ActiveNFSCanaryObservation(m._ACTIVE_KEY,[],[],[],[],{},rows,{}, {},1,lambda:(current,{}, {},1),reader_id=rows[2]['Id'])
  self.assertEqual(canary.current(stopped=True),current)
  current[0]['Path']='foreign'
  with self.assertRaisesRegex(m.Held,'static-drift'):canary.current(stopped=True)
  current[0]['Path']=rows[0]['Path'];current[2]['State']['StartedAt']='foreign'
  with self.assertRaisesRegex(m.Held,'not-stopped'):canary.current(stopped=True)

if __name__=='__main__':unittest.main(verbosity=2)
