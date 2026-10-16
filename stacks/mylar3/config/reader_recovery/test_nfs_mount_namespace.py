"""Explicit NFS row fixtures + real pipes; no Docker/NFS/remount claim."""
import ast,copy,inspect,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_nfs_host_probe as h
import comic_negative_nfs_hardlink_probe as k
import test_gated_host_probe as gate

class Bridge(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);z=Path(t.name).stat();self.root9=list(k.nine(z))
  self.host=dict(source='server:/export',target='/host',fstype='nfs4',fsroot='/export',options='rw,nosuid,nodev,relatime,vers=4.2',**{'maj:min':str(os.major(z.st_dev))+':'+str(os.minor(z.st_dev))})
  row=dict(self.host,source='server:/export[/export/fixture]',target='/child/fixture',fsroot='/export/fixture');self.rows=dict(source=row,target=dict(row))
 def call(self):return h.mount_namespace(self.host,self.rows,'/host/fixture','/child/fixture',self.root9,self.root9)
 def test_exact_subtree_bridge_keeps_raw_rows(self):
  p=self.call();self.assertEqual(p['host'],self.host);self.assertEqual(p['rows'],self.rows);self.assertEqual(p['root9'],self.root9)
 def test_plain_source_formatter_preserves_export(self):
  for r in self.rows.values():r['source']='server:/export'
  self.call()
 def test_each_child_field_and_security_drift_refuse(self):
  values=dict(source='foreign:/export',target='/foreign',fstype='ext4',fsroot='/export/foreign',options='rw,relatime',**{'maj:min':'1:999'})
  for key,value in values.items():
   with self.subTest(key=key):
    old=copy.deepcopy(self.rows)
    for r in self.rows.values():r[key]=value
    with self.assertRaises(h.Held):self.call()
    self.rows=old
  for option in ('ro,nosuid,nodev,relatime,vers=4.2','rw,nosuid,nodev,relatime,vers=4.1'):
   for r in self.rows.values():r['options']=option
   with self.assertRaises(h.Held):self.call()
 def test_missing_or_divergent_child_row_refuses(self):
  self.rows['target']['target']='/other'
  with self.assertRaises(h.Held):self.call()
  self.rows.pop('target')
  with self.assertRaises(h.Held):self.call()
 def test_host_prefix_source_and_inode_device_swap_refuse(self):
  for key,value in dict(target='/foreign',fsroot='/foreign',source='foreign:/export').items():
   old=self.host[key];self.host[key]=value
   with self.assertRaises(h.Held):self.call()
   self.host[key]=old
  for i in (0,1):
   other=list(self.root9);other[i]+=1
   with self.assertRaises(h.Held):h.mount_namespace(self.host,self.rows,'/host/fixture','/child/fixture',self.root9,other)
 def test_bool_owner_and_mode_refuse(self):
  for i,v in ((0,True),(6,0),(5,self.root9[5]|0o022)):
   row=list(self.root9);row[i]=v
   with self.assertRaises(h.Held):h.mount_namespace(self.host,self.rows,'/host/fixture','/child/fixture',row,row)
 def test_bridge_functions_exact(self):
  self.assertEqual(ast.dump(ast.parse(inspect.getsource(h.mount_namespace))),ast.dump(ast.parse(inspect.getsource(k.mount_namespace))))

class Prepared(gate.Gated):
 def setUp(self):
  super().setUp();x=Bridge();x.setUp();self.addCleanup(x.doCleanups);self.proof=x.call()
  n={key:self.proof[key] for key in ('host','host_root','child_root','root9')}
  self.process=h.ProbeProcess(self.spec,['docker'],self.engine,self.close,gated=True,launcher=self.launch,namespace=n)
 def launch(self,cid):
  self.assertFalse(self.block);self.assertEqual(cid,self.cid);p=Path(__file__).with_name('comic_negative_nfs_hardlink_child.py')
  code="import runpy,json;g=runpy.run_path("+repr(str(p))+",run_name='fixture_gate');g['wait_original_execute']("+repr(self.spec['input_sha256'])+",3,"+repr(self.spec['probe_sha256'])+",namespace="+repr(self.proof)+");print(json.dumps({'fixture_kernel_not_executed':True}),flush=True)"
  self.client=subprocess.Popen([sys.executable,'-I','-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.addCleanup(self.release);return self.client
 def test_missing_actual_namespace_refuses_prepared(self):
  self.proof=None;self.process.create()
  with self.assertRaisesRegex(h.Held,'actual-namespace-required'):self.process.start_prepare()
  self.assertFalse(self.process.execution_sent)
 def test_namespace_after_ack_swap_refuses(self):
  self.process.create();self.process.start_prepare();self.process.namespace_proof['root9'][1]+=1
  b=h.HostProbe.__new__(h.HostProbe);b.process=self.process;b.close=self.close
  with self.assertRaises(h.Held):h.HostProbe.prepared_descriptor(b)
 def test_wrong_original_role_cid_refuses(self):
  self.process.create();self.row['Id']='f'*64
  with self.assertRaises(h.Held):self.process.start_prepare()
  self.assertIsNone(self.client)
 def test_original_prepared_pid_swap_refuses(self):
  self.process.create();self.process.start_prepare();self.process.pid_original+=1
  with self.assertRaises(h.Held):self.process.local()

class KernelLocal(unittest.TestCase):
 def setUp(self):
  import test_hardlink_nfs_probe as f
  self.f=f;f.Controls.setUp(self)
  z=self.root.stat();target=str(self.base.parent)
  self.host_row=dict(source='fixture-server:/export',target=target,fstype='nfs4',fsroot='/export',options='rw,nosuid,nodev',**{'maj:min':str(os.major(z.st_dev))+':'+str(os.minor(z.st_dev))})
  self.child_row=dict(self.host_row,target=str(self.root),fsroot=str(Path('/export')/self.root.relative_to(target)))
  self.plan['mount']=self.host_row;self.refresh()
 refresh=__import__('test_hardlink_nfs_probe').Controls.refresh
 def test_actual_kernel_bridge_route_completes_local_syscalls(self):
  p=self.f.p
  with patch.object(p,'mount',return_value=self.child_row),patch.object(p,'nfs_magic',return_value=0x6969):
   proof=p.observe_namespace(self.plan)
   observed=p.run(self.ref,self.source,namespace=proof)
   self.assertEqual(len(observed.binding['transitions']),5)
   self.assertFalse(observed.binding['actual_library_platform_verified'])
 def test_default_exact_host_row_still_refuses_child_bind(self):
  p=self.f.p
  with patch.object(p,'mount',return_value=self.child_row),patch.object(p,'nfs_magic',return_value=0x6969),self.assertRaises(p.Held):p.run(self.ref,self.source)
  self.assertEqual(list(self.src.iterdir()),[])
 def test_changed_local_row_after_prepared_refuses_before_syscalls(self):
  p=self.f.p
  with patch.object(p,'mount',return_value=self.child_row),patch.object(p,'nfs_magic',return_value=0x6969):proof=p.observe_namespace(self.plan)
  changed=dict(self.child_row,options='rw')
  with patch.object(p,'mount',return_value=changed),patch.object(p,'nfs_magic',return_value=0x6969),self.assertRaises(p.Held):p.run(self.ref,self.source,namespace=proof)
  self.assertEqual(list(self.src.iterdir()),[])

if __name__=='__main__':unittest.main()
