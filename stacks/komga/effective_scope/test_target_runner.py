import ast
import copy
import importlib.util
from pathlib import Path
import unittest
import json
HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('target_runner', HERE/'run_target.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
assert r.IMAGE is None, "portable-unbound-image"
r.IMAGE = "sha256:" + "b" * 64

class Tests(unittest.TestCase):
 def row(self, case='defaults'):
  code=Path('/private/owned'); env=['KOMGA_CONFIGDIR=/config']
  config=dict(Image=r.IMAGE, User='1000:1000',WorkingDir='/app',Entrypoint=['java'],Cmd=['-XX:-UsePerfData','-cp','/checks:/app/application.jar','TargetEffectiveScopeCase',case],Env=env,Labels={'com.homelab.isolated-verification':'nonce'},Healthcheck={'Test':['NONE']})
  host=dict(ReadonlyRootfs=True,NetworkMode='none',CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],Privileged=False,Memory=536870912,MemorySwap=536870912,PidsLimit=64,Binds=[str(code/n)+':/checks/'+n+':ro' for n in r.CLASSES],Tmpfs={'/config':r.TMPFS},Mounts=None,Devices=[],DeviceRequests=[],PortBindings={},PublishAllPorts=False)
  state=dict(Status='exited',Running=False,Pid=0,OOMKilled=False)
  mounts=[dict(Type='bind',Source=str(code/n),Destination='/checks/'+n,RW=False)for n in r.CLASSES]
  return dict(Image=r.IMAGE,Name='/case',Config=config,HostConfig=host,State=state,Mounts=mounts),code,env
 def check(self,row,code,env):r.profile(row,'case','nonce',code,'defaults',env)
 def test_actual_tmpfs_absent_from_mounts(self): self.check(*self.row())
 def test_bind_order_is_not_authority(self):
  row,code,env=self.row();row['HostConfig']['Binds'].reverse();self.check(row,code,env)
 def test_bind_duplicate_missing_and_changed_refuse(self):
  for change in ('duplicate','missing','changed','mapping'):
   row,code,env=self.row();binds=row['HostConfig']['Binds']
   if change=='duplicate':binds[1]=binds[0]
   if change=='missing':binds.pop()
   if change=='changed':binds[0]+='changed'
   if change=='mapping':row['HostConfig']['Binds']=dict.fromkeys(binds,1)
   with self.assertRaisesRegex(AssertionError,'sole-public'):self.check(row,code,env)
 def test_automatic_failure_summary_never_echoes_values(self):
  try:raise ValueError('SECRET_VALUE')
  except ValueError as error:value=r.failure_summary(error)
  self.assertNotIn('SECRET_VALUE',json.dumps(value));self.assertEqual(value['fixed_code'],'unclassified')

 def test_actual_tmpfs_present_in_mounts(self):
  row,code,env=self.row();row['Mounts'].append(dict(Type='tmpfs',Destination='/config',RW=True));self.check(row,code,env)
 def test_no_writable_public_source(self):
  row,code,env=self.row();row['Mounts'][0]['RW']=True
  with self.assertRaises(AssertionError):self.check(row,code,env)
 def test_mount_census_duplicate_refused(self):
  row,code,env=self.row();row['Mounts'][1]=copy.deepcopy(row['Mounts'][0])
  with self.assertRaises(AssertionError):self.check(row,code,env)
 def test_unknown_mount_refused(self):
  row,code,env=self.row();row['Mounts'].append(dict(Type='bind',Source='/live',Destination='/live',RW=False))
  with self.assertRaises(AssertionError):self.check(row,code,env)
 def test_no_agent_env_or_privilege(self):
  for change in ('env','privilege','network','running'):
   row,code,env=self.row()
   if change=='env':row['Config']['Env']=env+['JAVA_TOOL_OPTIONS=-javaagent:bad']
   if change=='privilege':row['HostConfig']['Privileged']=True
   if change=='network':row['HostConfig']['NetworkMode']='host'
   if change=='running':row['State']['Running']=True
   with self.assertRaises(AssertionError):self.check(row,code,env)
 def test_command_only_public_ro_binds_and_disposable_tmpfs(self):
  cmd=r.command('case','nonce',Path('/fd/cid'),Path('/code'),'defaults');binds=[cmd[i+1]for i,x in enumerate(cmd)if x=='--volume']
  self.assertEqual(binds,[str(Path('/code')/n)+':/checks/'+n+':ro'for n in r.CLASSES]);self.assertEqual(cmd[cmd.index('--tmpfs')+1],'/config:'+r.TMPFS);self.assertNotIn('compose',cmd)
 def test_unknown_stdout_or_duplicate_marker_refuses(self):
  marker=b'TARGET_CASE defaults PASS; CONFIGURED_ACCEPTANCE false\n'
  self.assertTrue(r.case_output(marker,'defaults'))
  for value in (b'unknown\n'+marker,marker+b'unknown\n',marker+marker,b' '+marker,marker+b'\n'):
   self.assertFalse(r.case_output(value,'defaults'))
 def test_disabled_main(self):
  with self.assertRaisesRegex(AssertionError,'disabled'):r.main()
 def test_finite_ten_cases_and_source310(self):
  self.assertEqual(len(r.CASES),10);ast.parse((HERE/'run_target.py').read_text(),feature_version=(3,10))

if __name__=='__main__':unittest.main(verbosity=2)
