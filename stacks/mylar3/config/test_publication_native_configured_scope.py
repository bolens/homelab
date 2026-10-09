"""Actual FD/INI and authored AST fixtures; parent observations, source pins and origins are explicitly substituted.
No genuine installed/live scope grant is claimed by these host controls.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load('scope_fixture',Path(__file__).resolve().with_name('publication_native_configured_scope.py'))
ltests=load('lifecycle_tests',Path(__file__).resolve().with_name('test_publication_reader_lifecycle.py'));l=ltests.m
class Controls(unittest.TestCase):
 def setUp(self):
  self.c=ltests.Tests('runTest');self.c.setUp();self.addCleanup(self.c.doCleanups);self.root=self.c.root
  self.data=self.root/'native-data';self.data.mkdir(mode=0o700);self.library=self.root/'native-library';self.library.mkdir(mode=0o700)
  self.config=self.data/'config.ini';self.config.write_text('[General]\ndestination_dir = '+str(self.library)+'\n');self.config.chmod(0o600)
  self.cfg=self.root/'config.py';self.cfg.write_bytes(b"definitions = {'DESTINATION_DIR': (str, 'General', None)}\n");self.cfg.chmod(0o600)
  self.main=self.root/'Mylar.py';self.main.write_bytes(b"if args_datadir:\n mylar.DATA_DIR = args_datadir\nif args_config:\n mylar.CONFIG_FILE = args_config\nelse:\n mylar.CONFIG_FILE = os.path.join(mylar.DATA_DIR, 'config.ini')\nmylar.initialize(mylar.CONFIG_FILE)\n");self.main.chmod(0o600)
  self.native={'Id':'a'*64,'Image':'sha256:'+'b'*64,'Name':'/native','Path':'/init','Args':[],'Config':{},'HostConfig':{},'NetworkSettings':{},'Mounts':[self.mount('/host/native',str(self.data)),self.mount('/host/library',str(self.library))],'State':{'Running':True,'Status':'running','Pid':101,'StartedAt':'original','Paused':False,'Restarting':False,'Dead':False,'OOMKilled':False}}
  self.worker=copy.deepcopy(self.native);self.worker.update(Id='c'*64,Name='/worker',Mounts=[self.mount('/host/library','/data/comics')]);self.worker['State'].update(Running=False,Status='created',Pid=0)
  self.nvalue={'inspect':self.native,'process':{'pid':157,'start_ticks':42,'argv':['python3','/app/mylar3/Mylar.py','--datadir',str(self.data)]},'publication':{'state':'held','reason':'startup-restart-required','census':{'version':1,'epoch':'d'*64,'revision':1,'keys':['a'*64],'digest':hashlib.sha256(l.encoded(['a'*64])).hexdigest()},'request_counter':1}}
  self.c.response.update(native=copy.deepcopy(self.nvalue),worker=copy.deepcopy(self.worker),child_mounts=copy.deepcopy(self.native['Mounts']))
  self.patch=patch.object(m,'installed');self.patch.start();self.addCleanup(self.patch.stop)
  for name,value in [('lifecycle',lambda:l),('CONFIG_PATH',str(self.cfg)),('MAIN_PATH',str(self.main)),('CONFIG_SHA',hashlib.sha256(self.cfg.read_bytes()).hexdigest()),('MAIN_SHA',hashlib.sha256(self.main.read_bytes()).hexdigest())]:
   p=patch.object(m,name,value);p.start();self.addCleanup(p.stop)
  self.write_proof()
 def mount(self,source,dest):return {'Type':'bind','Source':source,'Destination':dest,'RW':False}
 def ref(self,p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'signature9':m.nine(p.lstat())}
 def write_proof(self):
  p=self.root/'native-scope.json';p.write_bytes(b'{}');p.chmod(0o600)
  self.doc={'version':1,'kind':'existing-native-configured-scope','invocation':{'input_path':self.c.input['path'],'input_sha256':self.c.input['sha256'],'parent_sha256':self.c.parent['sha256'],'provider_sha256':'3'*64,'command':['fixture'],'nonce':self.c.nonce},'native':copy.deepcopy(self.nvalue),'worker':copy.deepcopy(self.worker),'child_mounts':copy.deepcopy(self.c.response['child_mounts']),'config':self.ref(self.config),'config_module':self.ref(self.cfg),'main_module':self.ref(self.main),'worker_library':'/data/comics','tool_root':'/opt/archiving-utils','ancestors':{str(k):v for k,v in m.ancestors([p,self.config,self.cfg,self.main,self.library/'.scope-placeholder']).items()}}
  p.write_bytes(l.encoded(self.doc));self.c.doc['proofs']['native_scope']=self.ref(p);self.c.write('input.lifecycle.json',l.encoded(self.c.doc));self.custody=self.c.make()
 def make(self):return m.from_checked_parent(self.custody)
 def test_positive_scope_geometry_no_authority(self):
  x=self.make().binding;self.assertEqual(x['data'],str(self.data));self.assertEqual(x['roots'],[str(self.library)]);self.assertEqual(x['host_scopes'],{'data':'/host/native','library':'/host/library'});self.assertFalse(x['mutation_authority'])
 def test_actual_source_AST_mapping(self):m.source_contract(self.cfg.read_bytes(),self.main.read_bytes())
 def test_reader_only_response_refused(self):
  for k in ('native','worker','child_mounts'):self.c.response.pop(k)
  with self.assertRaises(l.Held):self.make()
 def test_foreign_custody_refused(self):
  with self.assertRaises(m.Held):m.from_checked_parent(object())
 def test_fresh_native_PID_drift(self):
  x=self.make();self.c.response['native']['inspect']['State']['Pid']=102
  with self.assertRaises(m.Held):x.revalidate()
 def test_application_process_ticks_drift(self):
  x=self.make();self.c.response['native']['process']['start_ticks']=43
  with self.assertRaises(m.Held):x.revalidate()
 def test_native_static_env_drift(self):
  x=self.make();self.c.response['native']['inspect']['Config']['Env']=['FOREIGN=1']
  with self.assertRaises(m.Held):x.revalidate()
 def test_health_counter_not_identity(self):
  x=self.make();self.c.response['native']['publication']['request_counter']=9;x.revalidate()
 def test_census_drift_refused(self):
  x=self.make();self.c.response['native']['publication']['census']['revision']=14
  with self.assertRaises(m.Held):x.revalidate()
 def test_worker_not_created(self):
  x=self.make();self.c.response['worker']['State']['Running']=True
  with self.assertRaises(m.Held):x.revalidate()
 def test_selected_child_mount_RW_drift(self):
  x=self.make();self.c.response['child_mounts'][0]['RW']=True
  with self.assertRaises(m.Held):x.revalidate()
 def test_worker_geometry_wrong(self):
  self.worker['Mounts'][0]['Source']='/host/foreign';self.write_proof()
  with self.assertRaises(m.Held):self.make()
 def test_child_geometry_wrong(self):
  self.c.response['child_mounts'][0]['Source']='/host/foreign';self.write_proof()
  with self.assertRaises(m.Held):self.make()
 def test_duplicate_most_specific_mount(self):
  self.native['Mounts'].append(copy.deepcopy(self.native['Mounts'][0]));self.nvalue['inspect']=self.native;self.write_proof()
  with self.assertRaises(m.Held):self.make()
 def test_explicit_config_switch_refused(self):
  self.nvalue['process']['argv']+=['--config','/foreign'];self.write_proof()
  with self.assertRaises(m.Held):self.make()
 def test_config_path_default_unchanged(self):
  self.doc['config']['path']=str(self.cfg);p=self.root/'native-scope.json';p.write_bytes(l.encoded(self.doc));self.c.doc['proofs']['native_scope']=self.ref(p);self.c.write('input.lifecycle.json',l.encoded(self.c.doc));self.custody=self.c.make()
  with self.assertRaises(m.Held):self.make()
 def test_interpolated_config_held_not_guessed(self):
  self.config.write_text('[General]\ndestination_dir = /data/%(other)s\n');self.write_proof()
  with self.assertRaises(m.Held):self.make()
 def test_native_proof_seal_cannot_rebaseline(self):
  x=self.make();x._native['state']['Pid']=999
  with self.assertRaises(m.Held):x.revalidate()
 def test_last_source_read_callback_mode_drift(self):
  x=self.make();real=m.bounded_read;fired=[]
  def changed(p,*args):
   raw=real(p,*args)
   if Path(p)==self.main and not fired:fired.append(True);self.config.chmod(0o640)
   return raw
  with patch.object(m,'bounded_read',changed),self.assertRaises(m.Held):x.revalidate()
  self.assertTrue(fired)
 def test_initial_control_callback_mode_drift(self):
  x=self.make();old=self.root.lstat().st_ino;real=l.read;fired=[]
  def changed(p,*args):
   raw=real(p,*args)
   if Path(p)==self.root/'native-scope.json' and not fired:
    fired.append(True);self.config.chmod(0o640)
   return raw
  with patch.object(l,'read',changed),self.assertRaises(m.Held):x.revalidate()
  self.assertTrue(fired);self.assertEqual(self.root.lstat().st_ino,old)
 def test_FD_parent_alias_returns_original_or_holds(self):
  x=self.make();foreign=self.root/'foreign';foreign.mkdir();(foreign/'config.ini').write_bytes(b'FOREIGN');before=self.config.read_bytes();real=m.os.open;fired=[]
  def changed(p,flags,*args,**kwargs):
   if p=='config.ini' and 'dir_fd' in kwargs and not fired:
    fired.append(True);return real(foreign/'config.ini',flags)
   return real(p,flags,*args,**kwargs)
  with patch.object(m.os,'open',changed),self.assertRaises(m.Held):x.revalidate()
  self.assertTrue(fired);self.assertEqual(self.config.read_bytes(),before)
 def test_true_initial_native_control_parent_rebuild_same_leaves(self):
  external=self.root/'external';external.mkdir(mode=0o700);self.data.rename(external/'inputs');self.data=external/'inputs';self.config=self.data/'config.ini';self.native['Mounts'][0]['Destination']=str(self.data);self.nvalue['inspect']=self.native;self.nvalue['process']['argv'][-1]=str(self.data);self.c.response.update(native=copy.deepcopy(self.nvalue),child_mounts=copy.deepcopy(self.native['Mounts']));self.write_proof();old=m.nine(self.config.lstat());oldinode=external.lstat().st_ino;real=l.read;fired=[]
  def changed(p,*args):
   value=real(p,*args)
   if Path(p)==self.root/'native-scope.json' and not fired:
    fired.append(True);external.rename(self.root/'retained');external.mkdir(mode=0o700);(self.root/'retained'/'inputs').rename(external/'inputs')
   return value
  with patch.object(l,'read',changed),self.assertRaises((m.Held,l.Held)):self.make()
  self.assertTrue(fired);self.assertEqual(m.nine(self.config.lstat()),old);self.assertNotEqual(external.lstat().st_ino,oldinode)
 def test_paused_native_exact_phase_supported(self):
  self.native['State'].update(Paused=True,Status='paused');self.nvalue['inspect']=self.native;self.c.response['native']=copy.deepcopy(self.nvalue);self.write_proof();self.make().revalidate()
 def test_paused_native_phase_drift_refused(self):
  x=self.make();self.c.response['native']['inspect']['State']['Paused']=True
  with self.assertRaises(m.Held):x.revalidate()
 def test_no_config_default_definition_AST(self):
  with self.assertRaises(m.Held):m.source_contract(self.cfg.read_bytes(),self.main.read_bytes().replace(b"os.path.join(mylar.DATA_DIR, 'config.ini')",b"os.path.join(mylar.DATA_DIR, 'foreign.ini')"))
 def test_changed_DESTINATION_mapping_AST(self):
  with self.assertRaises(m.Held):m.source_contract(self.cfg.read_bytes().replace(b"'DESTINATION_DIR': (str, 'General', None)",b"'DESTINATION_DIR': (str, 'Foreign', None)"),self.main.read_bytes())
 def test_census_bool_revision_refused(self):
  self.nvalue['publication']['census']['revision']=True;self.write_proof()
  with self.assertRaises(m.Held):self.make()
 def test_last_source_callback_cannot_reseal_configured_roots(self):
  x=self.make();real=m.bounded_read;fired=[]
  def changed(p,*args):
   raw=real(p,*args)
   if Path(p)==self.main and not fired:fired.append(True);x._binding['roots']=['/foreign']
   return raw
  with patch.object(m,'bounded_read',changed),self.assertRaises(m.Held):x.revalidate()
  self.assertTrue(fired)
if __name__=='__main__':unittest.main()
