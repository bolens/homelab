"""Real local canary/cleanup; explicit trusted parent/engine/NFS doubles only."""
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).parent))
import test_nfs_factual_successor as base
P=base.P;N=base.N
class Controls(unittest.TestCase):
 active=base.Controls.active
 stopped=base.Controls.stopped
 def setUp(self):
  base.Controls.setUp(self);x=self.x;x.plan['kind']='reviewed-archive-one-lifecycle-protocol'
  self.owner=dict(table='issues',issueid='123',parentcomicid='456',releasecomicid='456');self.operation_id='b'*64
  self.archive_request=base.ref(x.op.parent/'archive-request.json',P.encode(dict(version=1,owner=self.owner,operation_id=self.operation_id)))
  x.plan['producer_inputs']={'archive_request':self.archive_request};self.reseal()
 def reseal(self):
  x=self.x;x.core=P.encode(dict(plan=x.plan,files=x.files,nodes=x.nodes,source=x.source_ref,input=x.plan_ref,engine=id(x.engine),thread=x.thread,deadline=x.deadline));P._CORES[x]=x.core
 def request(self):
  x=self.x;controls={k:base.ref(x.op.parent/(k+'.json'),b'{}') for k in N.ARCHIVE_ROLES};scopes=base.ref(x.op.parent/'archive-scopes.json',b'{}')
  inp=x.emit('execute-input.json',dict(action='archive-one',owner=self.owner,operation_id=self.operation_id,controls={k:x.mapping.child_ref(v) for k,v in controls.items()},archive_scopes=x.mapping.child_ref(scopes)))
  command=['/lsiopy/bin/python3','-I','-B',x.mapping.child(x.plan['provider']['path']),'--phase','execute','--input',x.mapping.child(inp['path']),'--input-sha256',inp['sha256'],'--source-sha256',x.plan['provider']['sha256']]
  return dict(version=1,phase='archive-nfs-ready',nonce=x.plan['nonce'],operation=str(x.op),deadline_monotonic=x.deadline,parent_plan=x.plan_ref,parent_source=x.source_ref,context=dict(input=inp,command=command,context=dict(backup={},controls=controls,archive_scopes=scopes,observations=x.continuous())))
 def ready(self,request):return N.nfs_ready_archive(self.x,request,watch=self.x.continuous)
 def test_distinct_eight_role_fact_same_typed_canary_stop(self):
  self.stopped();result=self.ready(self.request());facts=P.decode(P.read(result['evidence']['evidence']))
  self.assertEqual(facts['kind'],'archive-one-owning-active-to-stopped-nfs-facts');self.assertEqual(facts['owner'],self.owner);self.assertTrue(facts['canary_writer_lease_released'])
  for key in ('continuous_action_lock','actual_library_platform_verified','native_grant','publication_authority','reader_resume_authority'):self.assertIs(facts[key],False)
 def test_negative_five_default_disabled(self):
  self.x.plan['kind']='reviewed-negative-five-lifecycle-protocol';self.reseal();self.stopped()
  with self.assertRaisesRegex(N.Held,'default-disabled'):self.ready(self.request())
 def test_nine_roles_not_archive_roles(self):
  self.stopped();request=self.request();request['context']['context']['controls']['plan']=self.archive_request
  with self.assertRaisesRegex(N.Held,'eight-roles'):self.ready(request)
 def test_source_bound_original_owner_mismatch(self):
  self.stopped();self.owner=dict(self.owner,issueid='999');request=self.request()
  with self.assertRaisesRegex(N.Held,'owner-command'):self.ready(request)
 def test_no_one_use_replay(self):
  self.stopped();request=self.request();self.ready(request)
  with self.assertRaisesRegex(N.Held,'owning-phase'):self.ready(request)
 def test_lost_ready_output_ack_consumption_uncertain(self):
  self.stopped();request=self.request();real=self.x.emit
  def lost(*args,**kwargs):real(*args,**kwargs);raise OSError('fixture output ACK lost')
  with patch.object(self.x,'emit',lost),self.assertRaises(OSError):self.ready(request)
  self.assertTrue((self.x.op/'archive-nfs-ready.json').exists())
  with self.assertRaisesRegex(N.Held,'owning-phase'):self.ready(request)
 def test_last_left_control_mode_refused(self):
  self.stopped();request=self.request();control=Path(request['context']['context']['controls']['schema']['path']);real=P.time.monotonic;fired=[]
  def late():
   value=real()
   if N._REG[self.x]['phase']=='consumed' and not fired:control.chmod(0o640);fired.append(True)
   return value
  with patch.object(P.time,'monotonic',late),self.assertRaises((N.Held,P.Held)):self.ready(request)
  self.assertTrue(fired)
 def test_original_ancestor_mode_closed_after_last_callback(self):
  self.stopped();request=self.request();real=P.time.monotonic;fired=[]
  def late():
   value=real()
   if N._REG[self.x]['phase']=='consumed' and not fired:self.x.op.parent.chmod(0o750);fired.append(True)
   return value
  with patch.object(P.time,'monotonic',late),self.assertRaises((N.Held,P.Held)):self.ready(request)
  self.assertTrue(fired)
if __name__=='__main__':unittest.main()
