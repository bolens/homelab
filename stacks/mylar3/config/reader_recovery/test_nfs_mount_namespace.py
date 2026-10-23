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

class RetentionBridge(unittest.TestCase):
 def setUp(self):
  base=Bridge();base.setUp();self.addCleanup(base.doCleanups)
  self.host,self.rows,self.root9=base.host,base.rows,base.root9
  self.retention='/host/archive-publication-'+'a'*64+'/R'
  self.fixture=self.retention+'/.comic-nfs-private-'+'b'*32+'/.comic-nfs-probe-'+'c'*32
  self.binding=dict(host_root=self.retention,child_root=self.retention,root5=[self.root9[i] for i in (0,1,5,6,7)])
  self.retention9=list(self.root9);self.retention9[1]+=1;self.binding['root5'][1]+=1
  row=dict(self.host,target=self.retention,fsroot='/export/'+self.retention.removeprefix('/host/'))
  self.rows=dict(source=row,target=dict(row))
 def call(self):
  return h.mount_namespace(self.host,self.rows,self.fixture,self.fixture,self.root9,self.root9,binding=self.binding,retention9=self.retention9)
 def test_retention_proof_keeps_distinct_original_fixture_and_retention(self):
  proof=self.call();self.assertEqual(proof['version'],2);self.assertEqual(proof['root9'],self.root9)
  self.assertEqual(proof['binding'],self.binding);self.assertEqual(proof['retention9'],self.retention9)
 def test_retention_requires_exact_dedicated_ancestor(self):
  for name in ('/host','/host/archive-publication-'+'a'*64,'/host/archive-publication-'+'a'*64+'/L',self.retention+'/.comic-nfs-private-'+'b'*32):
   with self.subTest(name=name):
    old=copy.deepcopy(self.binding);self.binding.update(host_root=name,child_root=name)
    with self.assertRaises(h.Held):self.call()
    self.binding=old
 def test_retention_alias_identity_and_full9_refuse(self):
  old=copy.deepcopy(self.binding);self.binding['child_root']='/alias'
  with self.assertRaises(h.Held):self.call()
  self.binding=old
  for index in (0,1,5,6,7):
   old=list(self.retention9);self.retention9[index]+=1
   with self.assertRaises(h.Held):self.call()
   self.retention9=old
 def test_legacy_bridge_does_not_infer_retention(self):
  with self.assertRaises(h.Held):h.mount_namespace(self.host,self.rows,self.fixture,self.fixture,self.root9,self.root9)
 def test_retention_descriptor_extra_keys_and_malformed_suffixes_refuse(self):
  self.binding['foreign']=True
  with self.assertRaises(h.Held):self.call()
  self.binding.pop('foreign')
  original=self.fixture
  for root in (original+'/child',original.replace('.comic-nfs-private-','.foreign-'),original.replace('.comic-nfs-probe-','.foreign-')):
   self.fixture=root
   with self.assertRaises(h.Held):self.call()
  self.fixture=original
 def test_retention_export_security_and_row_substitution_refuse(self):
  original=copy.deepcopy(self.rows)
  for key,value in (('source','foreign:/export'),('target',self.retention+'/foreign'),('fsroot','/foreign'),('fstype','ext4'),('options','ro,nosuid,nodev'),('maj:min','1:999')):
   with self.subTest(key=key):
    self.rows=copy.deepcopy(original)
    for row in self.rows.values():row[key]=value
    with self.assertRaises(h.Held):self.call()
  self.rows=original

class RetentionPrepared(unittest.TestCase):
 setUp=RetentionBridge.setUp
 call=RetentionBridge.call
 def process(self):
  process=h.ProbeProcess.__new__(h.ProbeProcess)
  process.spec=dict(input_sha256='a'*64,probe_sha256='b'*64)
  process.namespace_original=copy.deepcopy(dict(host=self.host,host_root=self.fixture,child_root=self.fixture,root9=self.root9,binding=self.binding))
  process.namespace_tape=h.encode(process.namespace_original)
  return process
 def test_prepared_retention_proof_joins_original_identity(self):
  self.assertEqual(self.process().prepared_ack(self.call())['namespace'],self.call())
 def test_prepared_version_descriptor_and_identity_substitutions_refuse(self):
  original=self.call()
  for key,value in (('version',1),('version',2.0),('kind','original-nfs-bind-namespace-v1'),('binding',dict(self.binding,child_root='/foreign')),('retention9',self.root9)):
   with self.subTest(key=key):
    proof=copy.deepcopy(original);proof[key]=value
    with self.assertRaises(h.Held):self.process().prepared_ack(proof)
 def test_prepared_namespace_original_mutation_refuses(self):
  process=self.process();process.namespace_original['binding']['root5'][1]+=1
  with self.assertRaisesRegex(h.Held,'original-tape'):process.prepared_ack(self.call())

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

class RetentionKernel(KernelLocal):
 def setUp(self):
  super().setUp()
  old=self.root;common=self.base/('archive-publication-'+'a'*64);common.mkdir(mode=0o711)
  self.retention=common/'R';self.retention.mkdir(mode=0o700)
  private=self.retention/('.comic-nfs-private-'+'b'*32);private.mkdir(mode=0o700)
  self.root=private/('.comic-nfs-probe-'+'c'*32);old.rename(self.root)
  self.src,self.dst=self.root/'source',self.root/'target'
  self.plan.update(root=str(self.root),root9=self.f.p.nine(self.root.lstat()),source_parent9=self.f.p.nine(self.src.lstat()),target_parent9=self.f.p.nine(self.dst.lstat()))
  self.child_row.update(target=str(self.retention),fsroot=str(Path('/export')/self.retention.relative_to(self.host_row['target'])))
  self.sentinel=self.retention/'unrelated';self.sentinel.write_bytes(b'preserved retention original')
  self.sentinel9=self.f.p.nine(self.sentinel.lstat());self.refresh()
 def test_retention_kernel_preserves_unrelated_entry(self):
  self.test_actual_kernel_bridge_route_completes_local_syscalls()
  self.assertEqual(self.f.p.nine(self.sentinel.lstat()),self.sentinel9)
  self.assertEqual(self.sentinel.read_bytes(),b'preserved retention original')
 def test_retention_metadata_drift_after_prepared_refuses_before_write(self):
  p=self.f.p
  with patch.object(p,'mount',return_value=self.child_row),patch.object(p,'nfs_magic',return_value=0x6969):
   proof=p.observe_namespace(self.plan);z=self.retention.stat();os.utime(self.retention,ns=(z.st_atime_ns,z.st_mtime_ns+1))
   with self.assertRaises(p.Held):p.run(self.ref,self.source,namespace=proof)
  self.assertEqual(list(self.src.iterdir()),[])
 def test_noninteger_retention_proof_version_refuses_before_write(self):
  p=self.f.p
  with patch.object(p,'mount',return_value=self.child_row),patch.object(p,'nfs_magic',return_value=0x6969):
   proof=p.observe_namespace(self.plan);proof['version']=2.0
   with self.assertRaises(p.Held):p.run(self.ref,self.source,namespace=proof)
  self.assertEqual(list(self.src.iterdir()),[])
 def test_retention_drift_after_namespace_observation_refuses_first_write(self):
  p=self.f.p
  with patch.object(p,'mount',return_value=self.child_row),patch.object(p,'nfs_magic',return_value=0x6969):
   proof=p.observe_namespace(self.plan);original_encode=p.encode;calls=[]
   def mutate(value):
    raw=original_encode(value)
    if value is proof:
     calls.append(True)
     if len(calls)==2:(self.retention/'late-entry').write_bytes(b'foreign')
    return raw
   with patch.object(p,'encode',mutate),self.assertRaises(p.Held):p.run(self.ref,self.source,namespace=proof)
  self.assertEqual(len(calls),2);self.assertEqual(list(self.src.iterdir()),[])
 def test_retention_drift_after_closure_callback_refuses_first_write(self):
  p=self.f.p
  with patch.object(p,'mount',return_value=self.child_row),patch.object(p,'nfs_magic',return_value=0x6969):
   proof=p.observe_namespace(self.plan);original_close=p.raw_close;calls=[]
   def mutate(*args):
    result=original_close(*args);calls.append(True)
    if len(calls)==2:
     z=self.retention.stat();os.utime(self.retention,ns=(z.st_atime_ns,z.st_mtime_ns+1))
    return result
   with patch.object(p,'raw_close',mutate),self.assertRaises(p.Held):p.run(self.ref,self.source,namespace=proof)
  self.assertEqual(len(calls),2);self.assertEqual(list(self.src.iterdir()),[])
 def test_retention_inode_swap_after_prepared_refuses(self):
  p=self.f.p
  with patch.object(p,'mount',return_value=self.child_row),patch.object(p,'nfs_magic',return_value=0x6969):
   proof=p.observe_namespace(self.plan);self.retention.rename(self.retention.with_name('retained-original'));self.retention.mkdir(mode=0o700)
   with self.assertRaises((p.Held,FileNotFoundError)):p.run(self.ref,self.source,namespace=proof)

if __name__=='__main__':unittest.main()
