"""Genuine SQLite/adopted history + Worker Writer; historical device data is fixture genesis."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from ordinary_observation_fixtures.identity_native.tests_tagger_identity import HistoricalFixture
PROGRAM=r'''
import json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
from media_writer import Writer
from publication_guard import scope,current
from writer_cycle import bind_state
p=json.loads(sys.argv[2]); root=Path(p['root'])
worker=SimpleNamespace(config={'writer_state':str(root/'media-writer'),'mylar':{'config_dir':str(root)},'publication_roots':[{'native':'/fixture-library','worker':str(root)}]},state=root/'worker-state',jobs=root/'worker-jobs')
writer=Writer(root/'media-writer',create=False)
with writer.hold(allow_pending=True,timeout=0):
 with scope(worker,writer) as authority:
  before=authority.admission()
  bind_state(writer,worker)
  writer.mark_pending()
  try:
   assert current(worker).admission()==before
  finally:writer.clear_pending()
assert not writer.fenced()
print('scope-bind-mark-admit-clear-exit')
'''
class OwnedPendingTests(HistoricalFixture):
    def test_real_adopted_scope_admits_its_fresh_owned_pending_and_preserves_native(self):
        (self.root/'worker-state').mkdir(mode=0o700)
        (self.root/'worker-jobs').mkdir(mode=0o700)
        result=subprocess.run([sys.executable,'-I','-B','-c',PROGRAM,str(HERE),json.dumps({'root':str(self.root)})],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'scope-bind-mark-admit-clear-exit')
        self.assertEqual(self.rows(),self.rows_original)
        self.assertEqual(self.marker.read_bytes(),self.marker_original)
        self.assertEqual(self.binding.read_bytes(),self.binding_original)

    def child(self,program):
        (self.root/'worker-state').mkdir(mode=0o700,exist_ok=True)
        (self.root/'worker-jobs').mkdir(mode=0o700,exist_ok=True)
        return subprocess.run([sys.executable,'-I','-B','-c',program,str(HERE),json.dumps({'root':str(self.root)})],capture_output=True,text=True,timeout=15)

    def test_preexisting_same_uid_protocol_fence_is_not_new_owned_evidence(self):
        program=PROGRAM.replace("with writer.hold(allow_pending=True,timeout=0):", "writer.create_file(writer.pending)\nwith writer.hold(allow_pending=True,timeout=0):")
        result=self.child(program)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('fresh-owned-marker-required',result.stderr)
        self.assertTrue((self.writer.root/'normalizer-v1.pending').exists())

    def test_replaced_same_uid_valid_marker_is_refused_and_retained(self):
        program=PROGRAM.replace("  try:\n   assert current(worker).admission()==before\n  finally:writer.clear_pending()", "  replacement=writer.root/'replacement'\n  replacement.write_bytes(writer.pending.read_bytes());replacement.chmod(0o600)\n  replacement.replace(writer.pending)\n  current(worker).admission()")
        result=self.child(program)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('original-marker9',result.stderr)
        self.assertTrue((self.writer.root/'normalizer-v1.pending').exists())

    def test_creator_sync_replacement_cannot_be_adopted_as_birth(self):
        program=PROGRAM.replace("  writer.mark_pending()", "  import media_writer\n  actual_sync=media_writer.sync\n  def replaced(directory):\n   actual_sync(directory)\n   if writer.pending.exists():\n    replacement=writer.root/'replacement'\n    replacement.write_bytes(writer.pending.read_bytes());replacement.chmod(0o600)\n    replacement.replace(writer.pending)\n  media_writer.sync=replaced\n  writer.mark_pending()")
        result=self.child(program)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('protocol file changed',result.stderr)
        self.assertTrue((self.writer.root/'normalizer-v1.pending').exists())

    def test_foreign_writer_instance_cannot_claim_another_instances_birth(self):
        program=PROGRAM.replace("   assert current(worker).admission()==before", "   authority.writer=Writer(writer.root,create=False)\n   current(worker).admission()")
        result=self.child(program)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('fresh-owned-marker-required',result.stderr)

    def test_not_currently_held_writer_cannot_open_pending_reader(self):
        program=PROGRAM[:PROGRAM.index('with writer.hold(allow_pending=True,timeout=0):')]+"from publication_identity_adoption import normalizer_pending_read\nwith normalizer_pending_read(writer):pass\n"
        result=self.child(program)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('fresh-owned-marker-required',result.stderr)

    def test_every_other_pending_marker_remains_an_unconditional_hold(self):
        for name in ('tagger-v2.pending','release-v1.pending','publication-recovery-v1.json','tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending','negative-retirement-v1.pending','negative-retirement-v1.terminal-pending','archive-repair-v1.pending','archive-repair-v1.terminal-pending'):
            with self.subTest(marker=name):
                program=PROGRAM.replace("   assert current(worker).admission()==before", "   other=writer.root/"+repr(name)+"\n   other.write_bytes(b'fixture pending');other.chmod(0o600)\n   current(worker).admission()")
                result=self.child(program)
                self.assertNotEqual(result.returncode,0)
                (self.writer.root/name).unlink(missing_ok=True)

    def test_full_read_final_callback_marker_replacement_is_refused(self):
        program=PROGRAM.replace("   assert current(worker).admission()==before", "   import publication_evidence as evidence\n   actual=evidence.cleanup_admission\n   def changed(database):\n    result=actual(database)\n    replacement=writer.root/'replacement'\n    replacement.write_bytes(writer.pending.read_bytes());replacement.chmod(0o600)\n    replacement.replace(writer.pending)\n    return result\n   evidence.cleanup_admission=changed\n   current(worker).admission()")
        result=self.child(program)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('original-marker9',result.stderr)

    def test_no_recovery_flag_cannot_mint_pending_or_read_witness(self):
        program=PROGRAM.replace('writer.hold(allow_pending=True,timeout=0)','writer.hold(timeout=0)')
        result=self.child(program)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Normalizer writer ownership required',result.stderr)

    def test_clear_and_outer_hold_exit_erase_birth_fact(self):
        program=PROGRAM.replace("  finally:writer.clear_pending()", "  finally:writer.clear_pending()\n  assert writer.local[1].normalizer_pending_original is None")
        program=program.replace("assert not writer.fenced()", "assert not writer.fenced()\nassert writer.local[1].normalizer_pending_original is None")
        result=self.child(program)
        self.assertEqual(result.returncode,0,result.stderr)


    def test_creator_fd_close_replacement_cannot_refresh_original_birth(self):
        program=PROGRAM.replace("  writer.mark_pending()", "  import media_writer,os\n  actual_close=os.close\n  fired=[]\n  def close(fd):\n   replace=not fired and writer.pending.exists() and os.fstat(fd).st_ino==writer.pending.stat().st_ino\n   actual_close(fd)\n   if replace:\n    fired.append(True)\n    replacement=writer.root/'replacement'\n    replacement.write_bytes(writer.pending.read_bytes());replacement.chmod(0o600)\n    replacement.replace(writer.pending)\n  os.close=close\n  writer.mark_pending()")
        result=self.child(program)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('New normalizer recovery marker changed',result.stderr)

    def test_actual_other_thread_cannot_borrow_held_marker_provenance(self):
        program=PROGRAM.replace("   assert current(worker).admission()==before", "   import threading\n   from publication_identity_adoption import normalizer_pending_read\n   errors=[]\n   def other():\n    try:\n     with normalizer_pending_read(writer):pass\n    except Exception as error:errors.append(str(error))\n   thread=threading.Thread(target=other);thread.start();thread.join(2)\n   assert not thread.is_alive() and len(errors)==1 and 'fresh-owned-marker-required' in errors[0]\n   assert current(worker).admission()==before")
        result=self.child(program)
        self.assertEqual(result.returncode,0,result.stderr)


    def test_actual_cycle_exits_publication_scope_before_clearing_own_fence(self):
        program=PROGRAM.replace("  try:\n   assert current(worker).admission()==before\n  finally:writer.clear_pending()", "  assert current(worker).admission()==before\n writer.clear_pending()")
        result=self.child(program)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_normalizer_reader_descriptor_close_cannot_hide_marker_replacement(self):
        program=PROGRAM.replace("   assert current(worker).admission()==before", "   import os\n   actual_close=os.close\n   fired=[]\n   def close(fd):\n    replace=not fired and sys._getframe(1).f_code.co_name=='normalizer_pending_read' and writer.pending.exists() and os.fstat(fd).st_ino==writer.pending.stat().st_ino\n    actual_close(fd)\n    if replace:\n     fired.append(True)\n     replacement=writer.root/'replacement'\n     replacement.write_bytes(writer.pending.read_bytes());replacement.chmod(0o600)\n     replacement.replace(writer.pending)\n   os.close=close\n   current(worker).admission()")
        result=self.child(program)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('final-original9',result.stderr)


    def test_late_sibling_fence(self):
        change="""   import os
   actual_close=os.close
   fired=[]
   def close(fd):
    mutate=not fired and sys._getframe(1).f_code.co_name=='normalizer_pending_read' and writer.pending.exists() and os.fstat(fd).st_ino==writer.pending.stat().st_ino
    actual_close(fd)
    if mutate:
     fired.append(True)
     other=writer.root/'tagger-v2.pending'
     other.write_bytes(b'fixture pending');other.chmod(0o600)
   os.close=close
   current(worker).admission()
   print('ADMISSION_RETURNED',flush=True)"""
        program=PROGRAM.replace("   assert current(worker).admission()==before",change)
        result=self.child(program)
        self.assertNotIn('ADMISSION_RETURNED',result.stdout,result.stderr)
        self.assertNotEqual(result.returncode,0,'Admission accepted after sibling pending fence appeared at final descriptor close: '+result.stdout)

if __name__=='__main__':unittest.main()
