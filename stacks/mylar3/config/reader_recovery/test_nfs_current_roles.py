"""Pure captured-role boundary + real private control files; no Docker/NFS grant."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('current_nfs',ROOT/'comic_negative_nfs_active_parent.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def image(n):return 'sha256:'+str(n)*64
def row(n,name,status):
 running=status=='running';state=dict(Status=status,Running=running,Paused=False,Restarting=False,Dead=False,OOMKilled=False,Pid=n+400 if running else 0,StartedAt='original-'+str(n),FinishedAt='',ExitCode=0,Error='')
 return dict(Id=str(n)*64,Name='/'+name,Image=image(n),Path='ordinary-entry',Args=['ordinary'],Config={'Env':['PUBLIC_FIXTURE=1']},HostConfig={'NetworkMode':'none'},Mounts=[],NetworkSettings={},State=state)
def ref(path,raw):
 path.write_bytes(raw);path.chmod(0o600);return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),signature9=m.stamp(path))

class Controls(unittest.TestCase):
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
 def test_nfs4_gate_unchanged(self):
  # Actual owning mount validator remains NFS-specific; no local fstype projection.
  for fstype in ('tmpfs','btrfs','ext4'):
   with self.assertRaises(m.Held):m.mount_identity({'filesystems':[dict(source='public-fixture',target=str(self.root),fstype=fstype,fsroot='/',options='rw',**{'maj:min':'0:1'})]})
if __name__=='__main__':unittest.main(verbosity=2)
