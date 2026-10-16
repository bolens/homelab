"""Real SQLite/Writer control adoption; public historical genesis and ioctl fixtures.
No operational backup, real remount, native network or worker activation grant.
"""
import json
from pathlib import Path
import subprocess
import sys
import unittest
HERE=Path(__file__).absolute().parent
sys.path.insert(0,str(HERE))
from ordinary_observation_fixtures.identity_native.tests_tagger_identity import HistoricalFixture

PROGRAM=r'''import copy,hashlib,json,os,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
import normalizer_state_binding as binding
from writer_cycle import bind_state
from publication_guard import scope,Unavailable
from media_writer import Writer
p=json.loads(sys.argv[2]); scenario=sys.argv[3]
writer=Writer(p['writer'],create=False);root=Path(p['root']);state=root/'worker-state';jobs=state/'jobs'
state.mkdir(mode=0o700);jobs.mkdir(mode=0o700);(state/'worker.lock').write_bytes(b'');(state/'worker.lock').chmod(0o600)
worker=SimpleNamespace(state=state,jobs=jobs,config=dict(state=str(state),writer_state=str(writer.root),mylar=dict(config_dir=str(root)),publication_roots=[dict(native='/library',worker=str(root))]))
old=p['old'];marker=writer.root/binding.LEGACY
raw=binding.legacy_digest(old,[state.stat().st_ino,jobs.stat().st_ino]);marker.write_bytes(raw);marker.chmod(0o600)
original9=binding.nine(marker.stat());fs=dict(fstype='btrfs',filesystem_uuid='1'*32,subvolume='5:'+'2'*32)
def save(path,value):
 path.write_bytes(value if type(value)is bytes else binding.encoded(value));path.chmod(0o600)
 return dict(path=str(path),signature9=binding.nine(path.stat()),sha256=binding.digest(path.read_bytes()))
backup=root/'control-backup';backup.mkdir(mode=0o700)
(backup/'backup').mkdir();(backup/'restore').mkdir()
a=save(backup/'backup'/'marker',raw);b=save(backup/'restore'/'marker',raw)
manifest=dict(version=1,kind='owned-publication-state',scope=dict(output_root=str(backup)),scopes=[dict(name='marker',path=str(marker),kind='file',records=[dict(path='.',kind='file',stamp=original9,sha256=binding.digest(raw))])])
m=save(backup/'manifest.json',manifest)
v=save(backup/'verification.json',dict(version=1,restore_verified=True,source_checked=True,application_recovery_verified=False,manifest_sha256=m['sha256']))
review=dict(version=1,kind='reviewed-worker-state-control-adoption-v1',native_edge_token=p['token'],manifest_ref=m,verification_ref=v,backup_marker_ref=a,restore_marker_ref=b)
ref=save(backup/'review.json',review)
def held():return writer.hold(allow_pending=True,timeout=0)
def refuse(call):
 try:call()
 except (Unavailable,OSError,ValueError,TypeError,KeyError):return
 raise AssertionError('expected refusal '+scenario)
with patch.object(binding.filesystem,'query',return_value=fs):
 with held(),scope(worker,writer):
  if scenario=='normal':
   marker.write_bytes(binding.legacy_digest(state.stat().st_dev,[state.stat().st_ino,jobs.stat().st_ino]));bind_state(writer,worker);assert not (writer.root/binding.NAME).exists()
  elif scenario=='fence-normal':
   marker.write_bytes(binding.legacy_digest(state.stat().st_dev,[state.stat().st_ino,jobs.stat().st_ino]));save(writer.root/binding.FENCE,b'uncertain control commit');refuse(lambda:bind_state(writer,worker))
  elif scenario=='unreviewed':refuse(lambda:bind_state(writer,worker))
  else:
   if scenario=='pending':
    writer.mark_pending();refuse(lambda:binding.prepare(writer,worker,ref));writer.clear_pending()
   elif scenario=='unfinished':
    j=jobs/'one';j.mkdir();save(j/'receipt.json',dict(phase='converted'));refuse(lambda:binding.prepare(writer,worker,ref))
   elif scenario=='foreign-owner':
    uid=os.geteuid()
    # Candidate owner-policy input only; no chown or actual foreign owner claim.
    with patch.object(binding.os,'geteuid',return_value=uid+1):refuse(lambda:binding.prepare(writer,worker,ref))
   elif scenario=='unsupported':
    with patch.object(binding.filesystem,'query',side_effect=Unavailable('unsupported')):refuse(lambda:binding.prepare(writer,worker,ref))
   elif scenario=='wrong-proof':
    save(backup/'verification.json',dict(version=1,restore_verified=False));refuse(lambda:binding.prepare(writer,worker,ref))
   else:
    plan=binding.prepare(writer,worker,ref);token=binding.digest(binding.encoded(plan))
    if scenario=='wrong-token':refuse(lambda:binding.commit(writer,worker,ref,plan,accepted_token='f'*64))
    elif scenario=='changed-plan':
     plan['state_facts_digest']='a'*64;refuse(lambda:binding.commit(writer,worker,ref,plan,accepted_token=token))
    elif scenario=='partial':
     save(writer.root/binding.NAME,b'{');refuse(lambda:binding.commit(writer,worker,ref,plan,accepted_token=token));assert (writer.root/binding.NAME).read_bytes()==b'{'
    elif scenario=='late-proof':
     actual_facts=binding.state_facts;calls=[0];fired=[False]
     def changed(*args):
      value=actual_facts(*args);calls[0]+=1
      if calls[0]==2:
       (backup/'verification.json').write_bytes(b'changed original proof');fired[0]=True
      return value
     with patch.object(binding,'state_facts',side_effect=changed):refuse(lambda:binding.commit(writer,worker,ref,plan,accepted_token=token))
     assert fired[0] and not (writer.root/binding.NAME).exists()
     assert marker.read_bytes()==raw and binding.nine(marker.stat())==original9
    elif scenario in ('final-caller','foreign-hold','restore-failure','moved-root'):
     import ast,inspect
     commit_node=next(n for n in ast.parse(Path(binding.__file__).read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='commit')
     last_close=max(n.lineno for n in ast.walk(commit_node) if isinstance(n,ast.Call) and ((isinstance(n.func,ast.Name) and n.func.id=='close_originals') or (isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='tape' and n.func.attr=='close')))
     original_close=binding.Originals.close;fired=[False]
     def late(tape):
      result=original_close(tape)
      frame=inspect.currentframe().f_back
      caller=frame.f_back if frame.f_code.co_name=='close_originals' else frame
      if not fired[0] and caller.f_code.co_name=='commit' and caller.f_lineno==last_close:
       plan['proof']['review_sha256']='e'*64;fired[0]=True
       if scenario=='moved-root':
        writer.root.rename(root/'moved-writer');writer.root.mkdir(mode=0o700)
       if scenario=='foreign-hold':save(writer.root/binding.FENCE,b'foreign pending original')
      return result
     actual_open=binding.os.open
     def interrupted_open(path,flags,*args,**kwargs):
      if scenario=='restore-failure' and (Path(path)==writer.root/binding.FENCE or (str(path)==binding.FENCE and kwargs.get('dir_fd') is not None)) and flags&os.O_EXCL and (writer.root/binding.NAME).exists():raise OSError('injected hold restoration error')
      return actual_open(path,flags,*args,**kwargs)
     with patch.object(binding.Originals,'close',new=late),patch.object(binding.os,'open',side_effect=interrupted_open):
      try:binding.commit(writer,worker,ref,plan,accepted_token=token)
      except Unavailable as error:message=str(error)
      else:raise AssertionError('final fault returned success')
     assert fired[0] and binding.digest(binding.encoded(plan))!=token
     if scenario=='moved-root':
      assert message=='worker-binding-control-hold-restoration-failed'
      assert not (writer.root/binding.FENCE).exists() and (root/'moved-writer'/binding.FENCE).read_bytes()==(token+'\n').encode()
      # Disposable fixture topology only; helper never rolls back original roots.
      writer.root.rmdir();(root/'moved-writer').rename(writer.root)
      refuse(lambda:bind_state(writer,worker))
     elif scenario=='final-caller':
      assert (writer.root/binding.FENCE).read_bytes()==(token+'\n').encode();refuse(lambda:bind_state(writer,worker))
     elif scenario=='foreign-hold':
      assert message=='worker-binding-control-hold-restoration-failed' and (writer.root/binding.FENCE).read_bytes()==b'foreign pending original';refuse(lambda:bind_state(writer,worker))
     else:assert message=='worker-binding-control-hold-restoration-failed' and not (writer.root/binding.FENCE).exists()
     assert marker.read_bytes()==raw and binding.nine(marker.stat())==original9
    elif scenario in ('partial-write','mutated-caller'):
     original_write=binding.os.write
     def uncertain(fd,data):
      result=original_write(fd,data)
      if len(data)>100:
       if scenario=='partial-write':raise OSError('injected receipt write interruption')
       plan['proof']['review_sha256']='e'*64
      return result
     with patch.object(binding.os,'write',side_effect=uncertain):refuse(lambda:binding.commit(writer,worker,ref,plan,accepted_token=token))
     assert (writer.root/binding.FENCE).is_file();refuse(lambda:bind_state(writer,worker))
     assert marker.read_bytes()==raw and binding.nine(marker.stat())==original9
    else:
     assert binding.commit(writer,worker,ref,plan,accepted_token=token)==token
     assert marker.read_bytes()==raw and binding.nine(marker.stat())==original9
     if scenario=='marker':marker.write_bytes(b'f'*64+b'\n');refuse(lambda:bind_state(writer,worker))
     elif scenario=='directory':jobs.rename(state/'old-jobs');jobs.mkdir();refuse(lambda:bind_state(writer,worker))
     elif scenario=='mode':jobs.chmod(0o750);refuse(lambda:bind_state(writer,worker))
     elif scenario=='filesystem':
      with patch.object(binding.filesystem,'query',return_value=dict(fs,filesystem_uuid='3'*32)):refuse(lambda:bind_state(writer,worker))
     elif scenario=='edge':
      edge=writer.root/'identity-adoptions-v1'/(p['token']+'.json');saved=edge.read_bytes();edge.unlink()
      try:refuse(lambda:bind_state(writer,worker))
      finally:save(edge,saved)
     elif scenario=='unaccepted':
      receipt=writer.root/binding.NAME;value=json.loads(receipt.read_bytes());value['accepted']=False;save(receipt,value);refuse(lambda:bind_state(writer,worker))
     elif scenario=='future':
      j=jobs/'next';j.mkdir();save(j/'receipt.json',dict(phase='done'));bind_state(writer,worker)
     elif scenario=='reboot':
      # Only observed device fields projected; actual current files/FDs remain real.
      original_roles=binding.roles
      def future_roles(w,k,t):
       a,b,rows,r,m=original_roles(w,k,t);return a,b,[[z[0]+9,*z[1:]]for z in rows],r,[m[0]+9,*m[1:]]
      with patch.object(binding,'roles',side_effect=future_roles):bind_state(writer,worker)
     else:
      bind_state(writer,worker);assert binding.commit(writer,worker,ref,plan,accepted_token=token)==token
     if scenario not in ('marker','directory','mode','edge','unaccepted'):assert marker.read_bytes()==raw
print('worker-binding-case-passed:'+scenario)
'''

class WorkerStateBindingTests(HistoricalFixture):
    def run_case(self,scenario):
        packet=dict(root=str(self.root),writer=str(self.writer.root),token=self.token,old=self.old['database_identity'][0])
        result=subprocess.run([sys.executable,'-I','-B','-c',PROGRAM,str(HERE),json.dumps(packet),scenario],capture_output=True,text=True,timeout=25)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'worker-binding-case-passed:'+scenario)
        self.assertEqual(self.rows(),self.rows_original)
        self.assertEqual(self.marker.read_bytes(),self.marker_original)
    def test_normal_binding_unchanged(self):self.run_case('normal')
    def test_unreviewed_mismatch_refuses(self):self.run_case('unreviewed')
    def test_explicit_control_commit_preserves_marker_and_is_idempotent(self):self.run_case('accepted')
    def test_pending_refuses_prepare(self):self.run_case('pending')
    def test_unfinished_job_refuses_prepare(self):self.run_case('unfinished')
    def test_unverified_backup_refuses(self):self.run_case('wrong-proof')
    def test_wrong_accepted_token_refuses(self):self.run_case('wrong-token')
    def test_changed_reviewed_plan_refuses(self):self.run_case('changed-plan')
    def test_partial_record_is_not_repaired(self):self.run_case('partial')
    def test_changed_marker_refuses(self):self.run_case('marker')
    def test_replaced_jobs_inode_refuses(self):self.run_case('directory')
    def test_changed_directory_mode_refuses(self):self.run_case('mode')
    def test_changed_stable_filesystem_refuses(self):self.run_case('filesystem')
    def test_missing_native_edge_refuses(self):self.run_case('edge')
    def test_unaccepted_envelope_refuses(self):self.run_case('unaccepted')
    def test_future_completed_job_does_not_freeze_commit_census(self):self.run_case('future')
    def test_future_device_only_projection_uses_stable_identity(self):self.run_case('reboot')
    def test_late_preparation_proof_change_refuses_before_effect(self):self.run_case('late-proof')
    def test_final_close_caller_change_cannot_return_success(self):self.run_case('final-caller')
    def test_foreign_pending_is_never_overwritten_by_exception_hold(self):self.run_case('foreign-hold')
    def test_exception_hold_failure_is_explicit_and_not_success(self):self.run_case('restore-failure')
    def test_restoration_uses_original_directory_fd_not_replacement_root(self):self.run_case('moved-root')
    def test_pending_control_refuses_even_matching_legacy_digest(self):self.run_case('fence-normal')
    def test_foreign_owner_policy_input_refuses(self):self.run_case('foreign-owner')
    def test_unsupported_filesystem_refuses(self):self.run_case('unsupported')
    def test_interrupted_control_write_retains_fence_and_originals(self):self.run_case('partial-write')
    def test_original_caller_change_retains_fence_and_originals(self):self.run_case('mutated-caller')

if __name__=='__main__':unittest.main()
