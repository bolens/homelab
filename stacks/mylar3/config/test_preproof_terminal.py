"""Real OS child waits for exact original terminal ACK; profiles remain synthetic."""
import inspect
from pathlib import Path
import sqlite3
from unittest.mock import patch
import test_preproof_composed as prior
p=prior.parent

class Terminal(prior.Preproof):
 def test_last_result_schema_source_drift_holds(self):
  real=p.need;fired=[];source=Path(p.__file__);before=source.stat().st_mode&0o7777
  def callback(ok,reason):
   out=real(ok,reason)
   if reason=='parent-factual-only-result' and not fired:source.chmod(0o640);fired.append(True)
   return out
  try:
   with patch.object(p,'need',callback),self.assertRaises(ValueError):self.run_barrier()
   self.assertTrue(fired);self.assertEqual(self.requests,['retainedDeliveryFinalize'])
  finally:source.chmod(before)
 def test_last_result_schema_restore_drift_holds(self):
  real=p.need;fired=[]
  def callback(ok,reason):
   out=real(ok,reason)
   if reason=='parent-factual-only-result' and not fired:
    f=next(row.frame for row in inspect.stack() if row.function=='collect');core=f.f_locals['c'];rec=p.backup_module._OBS[core['backup']]
    file=rec['out']/'restore/native_config/mylar.db';file.write_bytes(file.read_bytes()+b'foreign');fired.append(True)
   return out
  with patch.object(p,'need',callback),self.assertRaises(ValueError):self.run_barrier()
  self.assertTrue(fired);self.assertEqual(self.requests,['retainedDeliveryFinalize'])
 def test_last_raw_helper_source_drift_holds(self):
  real=p.raw;fired=[];source=Path(p.__file__);before=source.stat().st_mode&0o7777
  def callback(frame):
   out=real(frame)
   if any(row.function=='_final_close' for row in inspect.stack()) and not fired:source.chmod(0o640);fired.append(True)
   return out
  try:
   with patch.object(p,'raw',callback),self.assertRaises(ValueError):self.run_barrier()
   self.assertTrue(fired)
  finally:source.chmod(before)
 def test_original_process_alive_until_same_pipe_ACK_then_natural_exit(self):
  real=p.Pipe.receive;facts=[]
  def receive(pipe,kind,challenge):
   value=real(pipe,kind,challenge)
   if kind in ('worker-result','observed-final-ACK'):
    f=next(row.frame for row in inspect.stack() if row.function=='run_barrier');proc=f.f_locals['proc'];self.assertIsNone(proc.poll());self.assertEqual((pipe.read_fd,pipe.write_fd),(proc.stdout.fileno(),proc.stdin.fileno()));facts.append(kind)
   return value
  with patch.object(p.Pipe,'receive',receive):self.run_barrier()
  self.assertEqual(facts,['worker-result','observed-final-ACK']);self.assertEqual(self.requests,['retainedDeliveryFinalize'])
 def test_postCAS_foreign_journal_leaf_holds(self):
  real=p.Pipe.receive;fired=[]
  def receive(pipe,kind,challenge):
   value=real(pipe,kind,challenge)
   if kind=='worker-result' and not fired:
    f=next(row.frame for row in inspect.stack() if row.function=='run_barrier');state=f.f_locals['state'];journal=state/'maintenance/retained-pack-handoffs';(journal/'foreign').write_bytes(b'foreign');fired.append(True)
   return value
  with patch.object(p.Pipe,'receive',receive),self.assertRaises(ValueError):self.run_barrier()
  self.assertTrue(fired);self.assertEqual(self.requests,['retainedDeliveryFinalize'])
 def test_postCAS_foreign_SQL_holds(self):
  real=p.Pipe.receive;fired=[]
  def receive(pipe,kind,challenge):
   value=real(pipe,kind,challenge)
   if kind=='worker-result' and not fired:
    from contextlib import closing
    with closing(sqlite3.connect(self.c.root/'workflow.sqlite')) as db:db.execute('CREATE TABLE foreign_terminal(k TEXT)');db.commit()
    fired.append(True)
   return value
  with patch.object(p.Pipe,'receive',receive),self.assertRaises(ValueError):self.run_barrier()
  self.assertTrue(fired);self.assertEqual(self.requests,['retainedDeliveryFinalize'])
 def test_wrong_original_result_digest_does_not_release_child(self):
  real=p.encode;fired=[]
  def encode(value):
   if type(value) is dict and value.get('kind')=='observed-release' and not fired:
    value=dict(value,payload=dict(value['payload'],result_sha256='e'*64));fired.append(True)
   return real(value)
  with patch.object(p,'encode',encode),self.assertRaises(ValueError):self.run_barrier()
  self.assertTrue(fired)
 def test_lost_reply_reconciles_once_and_keeps_same_terminal_pipe(self):
  self.run_barrier(lose=True);self.assertEqual(self.requests,['retainedDeliveryFinalize','retainedDeliveryStatus'])

 def test_original_selected_PID_drift_holds(self):
  real=p.Pipe.receive;fired=[]
  def receive(pipe,kind,challenge):
   value=real(pipe,kind,challenge)
   if kind=='worker-result' and not fired:
    f=next(row.frame for row in inspect.stack() if row.function=='run_barrier');f.f_locals['states'][f.f_locals['selected']]['Pid']+=1;fired.append(True)
   return value
  with patch.object(p.Pipe,'receive',receive),self.assertRaises(ValueError):self.run_barrier()
  self.assertTrue(fired)
 def test_unknown_original_child_exit_before_ACK_holds(self):
  real=p.Pipe.receive;fired=[]
  def receive(pipe,kind,challenge):
   value=real(pipe,kind,challenge)
   if kind=='worker-result' and not fired:
    f=next(row.frame for row in inspect.stack() if row.function=='run_barrier');proc=f.f_locals['proc'];proc.kill();proc.wait(timeout=3);fired.append(True)
   return value
  with patch.object(p.Pipe,'receive',receive),self.assertRaises((ValueError,BrokenPipeError)):self.run_barrier()
  self.assertTrue(fired);self.assertEqual(self.requests,['retainedDeliveryFinalize'])
 def test_postCAS_receipt_foreign_bytes_holds(self):
  real=p.Pipe.receive;fired=[]
  def receive(pipe,kind,challenge):
   value=real(pipe,kind,challenge)
   if kind=='worker-result' and not fired:
    f=next(row.frame for row in inspect.stack() if row.function=='run_barrier');state=f.f_locals['state'];receipts=list((state/'maintenance/packs').glob('*/receipt.json'));self.assertEqual(len(receipts),1);receipts[0].write_bytes(b'{"foreign":true}');fired.append(True)
   return value
  with patch.object(p.Pipe,'receive',receive),self.assertRaises(ValueError):self.run_barrier()
  self.assertTrue(fired)
 def test_last_runtime_profile_callback_source_drift_holds(self):
  real=p.need;fired=[];source=Path(p.__file__);before=source.stat().st_mode&0o7777
  def callback(ok,reason):
   out=real(ok,reason)
   if reason=='selected-original-worker' and any(row.function=='_final_close' for row in inspect.stack()) and not fired:source.chmod(0o640);fired.append(True)
   return out
  try:
   with patch.object(p,'need',callback),self.assertRaises(ValueError):self.run_barrier()
   self.assertTrue(fired)
  finally:source.chmod(before)

 def _late_registry_fault(self,kind):
  real=p.raw;fired=[]
  def callback(frame):
   out=real(frame);call=next((row.frame for row in inspect.stack() if row.function=='_final_close'),None)
   if call is not None and inspect.stack()[1].function=='_final_close' and not fired:
    runtime=call.f_locals['c']['runtime']
    if runtime.process.poll() is not None:
     if kind=='change':p._RUNTIMES[runtime]=b'foreign'
     elif kind=='erase':del p._RUNTIMES[runtime]
     elif kind=='forged':p._RUNTIMES[runtime]=bytes(bytearray(p._RUNTIMES[runtime]))
     elif kind=='terminal':p._TERMINALS[runtime]=tuple(list(p._TERMINALS[runtime]))
     elif kind=='terminal-foreign':p._TERMINALS[runtime]=('foreign',)
     elif kind=='terminal-erase':del p._TERMINALS[runtime]
     fired.append(True)
   return out
  with patch.object(p,'raw',callback),self.assertRaises(ValueError):self.run_barrier()
  self.assertTrue(fired);self.assertEqual(self.requests,['retainedDeliveryFinalize'])
 def test_final_original_runtime_registry_change_holds(self):self._late_registry_fault('change')
 def test_final_original_runtime_registry_erasure_holds(self):self._late_registry_fault('erase')
 def test_final_original_runtime_registry_forged_equal_bytes_holds(self):self._late_registry_fault('forged')
 def test_final_original_terminal_registry_equal_replacement_holds(self):self._late_registry_fault('terminal')

 def test_final_original_terminal_registry_foreign_holds(self):self._late_registry_fault('terminal-foreign')
 def test_final_original_terminal_registry_erasure_holds(self):self._late_registry_fault('terminal-erase')
 def test_initial_runtime_registry_change_before_first_factory_callback_holds(self):
  real=p.need;fired=[]
  def callback(ok,reason):
   out=real(ok,reason);call=next((row.frame for row in inspect.stack() if row.function=='from_original_pipe'),None)
   if call is not None and reason=='parent-default-disabled' and not fired:
    p._RUNTIMES[call.f_locals['runtime']]=b'foreign';fired.append(True)
   return out
  with patch.object(p,'need',callback),self.assertRaises(ValueError):self.run_barrier()
  self.assertTrue(fired);self.assertEqual(self.requests,[])

 def _terminal_presence_fault(self,where,value):
  real=p.need if where=='first' else p.raw;fired=[]
  def callback(*args):
   out=real(*args);name='from_original_pipe' if where=='first' else '_final_close'
   call=next((row.frame for row in inspect.stack() if row.function==name),None)
   if call is not None and not fired and (where!='first' or args[1]=='parent-default-disabled'):
    runtime=call.f_locals['runtime'] if where=='first' else call.f_locals['c']['runtime']
    p._TERMINALS[runtime]=value;fired.append(True)
   return out
  with patch.object(p,'need' if where=='first' else 'raw',callback),self.assertRaises(ValueError):self.run_barrier()
  self.assertTrue(fired);self.assertEqual(self.requests,[] if where=='first' else ['retainedDeliveryFinalize'])
 def test_initial_presentNone_terminal_entry_is_not_original_absence(self):self._terminal_presence_fault('first',None)
 def test_late_presentNone_terminal_entry_is_not_original_absence(self):self._terminal_presence_fault('late',None)
 def test_initial_nested_foreign_terminal_entry_holds(self):self._terminal_presence_fault('first',{'terminal':None})
 def test_initial_stale_terminal_phase_holds(self):self._terminal_presence_fault('first',('foreign','stale-phase'))
