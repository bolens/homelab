"""Real full-reader terminal pairs; fake parent/type adapters do not mint authority."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent

def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
phase=load('phase_fixture',ROOT/'test_reader_phase_custody.py')
terminal=load('terminal_producer_fixture',ROOT/'test_terminal_observation_producer.py')
a=phase.a
class Controls(unittest.TestCase):
 def setUp(self):
  self.c=phase.Controls();self.c.setUp();self.addCleanup(self.c.doCleanups)
  self.t=terminal.Controls();self.t.setUp();self.addCleanup(self.t.doCleanups);c=self.c;t=self.t;f=t.f
  c.current=f.current;c.restore=f.restore;c.values['reader']['Mounts'][0]['Source']=str(c.current)
  c.put('stopped_runtime',dict(version=1,kind='root-owned-reader-stopped-observation',nonce=c.req['nonce'],observed=__import__('time').time().__int__(),container=c.values['reader']))
  reviewed=copy.deepcopy(f.plan);reviewed['timestamp_encoding_evidence_sha256']=c.req['context']['controls']['timestamp_evidence']['sha256'];c.put('reviewed_plan',reviewed)
  c.put('custody',dict(reader_root=str(c.current),restore_root=str(c.restore),current_pairs={name:{'':terminal.f.m.Observation().fact(c.restore/name)} for name in ('database.sqlite','tasks.sqlite')},pairs=f.pre['restore_pairs']))
  controls=c.req['context']['controls'];f.pre['backup_controls']=copy.deepcopy(controls);f.pre['reviewed_plan']=controls['reviewed_plan'];f.pre_ref=f.write(t.execute/'terminal-observation-preimage.json',f.pre);f.refresh_terminal()
  t.req['context']['controls']=copy.deepcopy(controls);t.req['context']['backup']['restore_root']=str(c.restore);t.req['context']['observations']['reader']['Mounts'][0]['Source']=str(c.current)
  t.refresh_execute_ack()
  self.terminal_ref=t.call()['manifest']
  c.req['operation']=str(f.root);c.plan['operation']=str(f.root);c.plan['action_inputs']={'execute':t.action};c.plan['producer']['sha256']=hashlib.sha256((ROOT/'comic_native_evidence_adapter.py').read_bytes()).hexdigest()
  c.req['context']['backup']=dict(restore_root=str(c.restore),manifest=copy.deepcopy(controls['backup_manifest']))
  c.req['context']['observations']=copy.deepcopy(c.values);c.req['context']['phase']='verify-terminal';c.req['context']['terminal_manifest']=self.terminal_ref;c.req['context']['execute_ack']=t.req['context']['execute_ack']
  c.inv['command'][5]='verify-terminal';c.inv['provider_sha256']=c.plan['provider']['sha256'];c.inv['command'][11]=c.inv['provider_sha256']
  doc=dict(version=1,nonce=c.req['nonce'],parent_sha256=c.source['sha256'],selected_image=c.plan['selected_image'],command_template=c.inv['command'][:9]+['<INPUT_SHA256>']+c.inv['command'][10:],controls=copy.deepcopy(controls),terminal_manifest=self.terminal_ref,execute_ack=t.req['context']['execute_ack'])
  path=Path(c.inv['input_path']);path.write_bytes(a.encode(doc));c.inv['input_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();c.inv['command'][9]=c.inv['input_sha256'];c.req['context']['invocation']=copy.deepcopy(c.inv);c.refresh_plan()
 def call(self):return a.produce('phase-custody',self.c.req,watch=self.c.parent.continuous)['evidence']
 def test_full_terminal_custody_joins_fresh_current_original_restore(self):
  result=self.call();self.assertEqual(result['reader']['current_pairs']['database.sqlite']['']['sha256'],self.t.f.commit['main_pair']['']['sha256']);self.assertEqual(result['proofs']['terminal_observation'],self.terminal_ref);self.assertEqual(result['reader']['restore_pairs']['database.sqlite']['']['signature9'],self.t.f.pre['restore_pairs']['database.sqlite']['']['signature9'])
 def test_original_custody_current_preimage_remains_unmodified(self):
  before=Path(self.c.req['context']['controls']['custody']['path']).read_bytes();result=self.call();self.assertEqual(before,Path(self.c.req['context']['controls']['custody']['path']).read_bytes());self.assertNotEqual(a.decode(before)['current_pairs']['database.sqlite']['']['sha256'],result['reader']['current_pairs']['database.sqlite']['']['sha256'])
 def test_last_watch_DB_mode_refuses_final_ack(self):
  real=a.current_observations;fired=[]
  def changed(w,e,r):
   real(w,e,r)
   if r=='custody-final-runtime':(self.c.current/'database.sqlite').chmod(0o640);fired.append(True)
  with patch.object(a,'current_observations',changed):
   with self.assertRaisesRegex(a.Held,'custody-final-file'):self.call()
  self.assertTrue(fired)
 def test_terminal_input_manifest_join_refused(self):
  self.c.req['context']['terminal_manifest']=dict(self.terminal_ref,sha256='f'*64)
  with self.assertRaises(Exception):self.call()
 def test_last_watch_original_execute_ACK_refuses(self):
  real=a.current_observations
  def changed(w,e,r):
   real(w,e,r)
   if r=='custody-final-runtime':Path(self.c.req['context']['execute_ack']['path']).chmod(0o640)
  with patch.object(a,'current_observations',changed):
   with self.assertRaisesRegex(a.Held,'custody-final-file'):self.call()
if __name__=='__main__':unittest.main()
