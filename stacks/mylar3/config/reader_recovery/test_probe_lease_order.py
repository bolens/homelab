"""Actual source slice/Writer/Popen; Parent/Docker/NFS remain projected or unrun."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import ast,types,unittest
import test_local_lease_window as leases
import test_gated_host_probe as probes
import comic_negative_nfs_active_parent as active
class Order(leases.Window):
 def probe(self,owner):
  case=probes.Gated('test_prelease_real_pipe_held_execution_no_remote_postrelease_terminal');case.setUp();self.addCleanup(case.doCleanups)
  original=case.engine
  def remote(argv,**kwargs):
   case.block=owner.blocked
   return original(argv,**kwargs)
  case.process.execute=remote;return case
 def test_actual_prelease_source_slice_then_real_Writer_local_probe_postrelease(self):
  lease,owner=self.window();case=self.probe(owner)
  # Execute the exact maintained configured lease-prepare statement block,
  # with only owning constructor/profile observations explicitly projected.
  lease.prepare=types.MethodType(lambda value:value.window_state(),lease)
  source=Path(active.__file__).read_bytes();fn=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='_run_owned_lifecycle')
  begin=next(i for i,x in enumerate(fn.body) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='lease' for t in x.targets))
  last=next(i for i in range(begin+1,len(fn.body)) if isinstance(fn.body[i],ast.Expr) and isinstance(fn.body[i].value,ast.Call) and isinstance(fn.body[i].value.func,ast.Attribute) and fn.body[i].value.func.attr=='update')
  ns=dict(lease_type=lambda output,engine:lease,output=None,engine=None,host_control={'source_only':True},probe_type=lambda _:None,check=active.check,controls={},active_lease=None)
  exec(compile(ast.Module(body=fn.body[begin:last+1],type_ignores=[]),'actual maintained prelease slice','exec'),ns)
  self.assertEqual(lease.window_state(),'PREPARED');self.assertFalse(owner.blocked);self.free()
  case.process.create();case.process.start_prepare();before=len(case.calls)
  lease.acquire();self.assertTrue(owner.blocked)
  with self.assertRaises(BlockingIOError):self.free()
  result=case.process.execute_local();self.assertTrue(result['local_exit_verified']);self.assertFalse(result['terminal_profile_verified']);self.assertEqual(len(case.calls),before)
  with self.assertRaisesRegex(ValueError,'actual-remote-under-Writer-refused'):case.process.finish_after_release()
  lease.channel.release(());seal=leases.t.m._WINDOWS[lease][1];leases.t.m._WINDOWS[lease]=('RELEASED_PHYSICAL',seal);owner.end_nfs_writer_window(lease);self.free()
  terminal=case.process.finish_after_release();self.assertEqual(terminal['profile']['State']['Status'],'exited')
 def test_retained_prior_order_attempts_remote_under_actual_Writer(self):
  lease,owner=self.window();lease.acquire()
  with self.assertRaisesRegex(ValueError,'remote-under-original-Writer'):owner.inspect()
  self.assertTrue(owner.blocked);self.assertEqual(lease.window_state(),'HELD');lease.channel.release(())
 def test_default_inert_entry_does_not_birth_or_grant(self):
  result=active._execute_factual(types.SimpleNamespace(execute=False))
  self.assertFalse(result['executable']);self.assertFalse(result['native_grant']);self.assertFalse(result['publication_authority'])
if __name__=='__main__':unittest.main()
