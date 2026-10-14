"""Real process/FIFO transport controls; no NFS/Parent/SDK authority projected."""
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
sys.path.insert(0,str(Path(__file__).parent))
import comic_nfs_parent_session as m

class Pump(unittest.TestCase):
    def start(self,body,guard=lambda:None):
        p=subprocess.Popen([sys.executable,'-I','-B','-u','-c',body],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        original=(p.stdin,p.stdout,p.stderr)
        def cleanup():
            if p.poll() is None:p.kill()
            p.wait(timeout=5)
            for v in original:
                if not v.closed:v.close()
        self.addCleanup(cleanup);return p,m.OriginalPump(p,time.monotonic()+5,guard)
    def test_actual_process_retained_across_two_rounds(self):
        p,pump=self.start("import json,sys;print('{\"phase\":1}',flush=True);a=json.loads(input());assert a=={'operation':'current'};print('{\"phase\":2}',flush=True);a=json.loads(input());assert a=={'operation':'release'}")
        self.assertEqual(pump.read(),{'phase':1});self.assertIsNone(p.poll())
        pump.write({'operation':'current'});self.assertEqual(pump.read(),{'phase':2});self.assertIsNone(p.poll())
        pump.write({'operation':'release'});pump.finish();self.assertTrue(pump.finished)
    def test_duplicate_json_refuses(self):
        p,pump=self.start("print('{\"x\":1,\"x\":2}',flush=True)")
        with self.assertRaisesRegex(m.Held,'duplicate'):pump.read()
        self.assertTrue(pump.failed);self.assertIs(pump.process,p)
    def test_unexpected_eof_retains_original_handle(self):
        p,pump=self.start('pass')
        with self.assertRaisesRegex(m.Held,'unexpected-EOF'):pump.read()
        self.assertTrue(pump.failed);self.assertIs(pump.process,p)
        with self.assertRaisesRegex(m.Held,'original-seal'):pump.read()
    def test_process_stream_substitution_refuses(self):
        p,pump=self.start("import time;time.sleep(1)")
        p.stdout=p.stderr
        with self.assertRaisesRegex(m.Held,'original-process'):pump.check()
    def test_guard_callback_seal_drift_refuses(self):
        state={}
        def guard():
            if 'pump' in state:state['pump'].pid+=1
        p,pump=self.start("import time;time.sleep(1)",guard);state['pump']=pump
        with self.assertRaisesRegex(m.Held,'callback-seal'):pump.check()
        self.assertIs(pump.process,p)
    def test_stderr_eof_does_not_spin_or_hide_stdout(self):
        _,pump=self.start("import os,time;os.close(2);time.sleep(.05);print('{\"value\":true}',flush=True)")
        self.assertEqual(pump.read(),{'value':True});pump.finish()
    def test_nonzero_terminal_exit_refuses(self):
        _,pump=self.start("import sys;print('{}',flush=True);sys.exit(2)")
        self.assertEqual(pump.read(),{})
        with self.assertRaisesRegex(m.Held,'child-exit'):pump.finish()
    def test_original_fifo_metadata_retained(self):
        _,pump=self.start("print('{}',flush=True)")
        before=tuple((fd,m.five(os.fstat(fd))) for fd,_ in pump.descriptors)
        self.assertEqual(pump.read(),{});self.assertEqual(before,pump.descriptors);pump.finish()

    def test_failed_original_input_eof_releases_own_waiting_process(self):
        p,pump=self.start("import sys;print('{invalid}',flush=True);assert input()=='never'")
        with self.assertRaises(Exception):pump.read()
        result=pump.close_original_input_after_failure()
        self.assertTrue(result['original_input_closed']);self.assertFalse(result['terminal_accepted']);self.assertFalse(result['cleanup_accepted'])
        self.assertNotEqual(p.wait(timeout=5),0)
    def test_failure_input_substitution_cannot_close_foreign_descriptor(self):
        p,pump=self.start("import time;print('{invalid}',flush=True);time.sleep(.1)")
        with self.assertRaises(Exception):pump.read()
        p.stdin=p.stdout
        with self.assertRaisesRegex(m.Held,'failure-original-process'):pump.close_original_input_after_failure()
        self.assertFalse(pump.streams[0].closed)

class FailureCaller(unittest.TestCase):
    """Real outer process/EOF, projected handler only; no Parent factory grant."""
    def fixture(self):
        import types
        p=subprocess.Popen([sys.executable,'-I','-B','-u','-c',"import sys;print('{\"type\":\"nfs-engine\",\"nonce\":\"n\",\"sequence\":1,\"payload\":{}}',flush=True);assert input()=='never'"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        streams=(p.stdin,p.stdout,p.stderr)
        def cleanup():
            if p.poll() is None:p.kill()
            p.wait(timeout=5)
            for stream in streams:
                if not stream.closed:stream.close()
        self.addCleanup(cleanup)
        pump=m.OriginalPump(p,time.monotonic()+5,lambda:None)
        session=object.__new__(m.RetainedChild);session.state='starting';session.pump=pump;session.close=lambda:None
        def fail(frame):raise ValueError('projected-original-handler-failure')
        session.engine_replies=types.SimpleNamespace(accept=fail);session.probe_replies=session.engine_replies
        session.lease_replies=types.SimpleNamespace(lease=None,done=False)
        m._SESSION_PUMPS[session]=pump
        return p,pump,session
    def test_handler_failure_closes_original_input_even_read_succeeded(self):
        p,pump,session=self.fixture()
        with self.assertRaisesRegex(ValueError,'projected-original-handler-failure'):
            session.until('nfs-ready')
        self.assertTrue(pump.failed);self.assertTrue(pump.streams[0].closed)
        self.assertNotEqual(p.wait(timeout=5),0);self.assertEqual(session.state,'failed')
    def test_initial_owner_failure_closes_original_input(self):
        p,pump,session=self.fixture()
        def fail():raise ValueError('projected-owner-failure')
        session.close=fail
        with self.assertRaisesRegex(ValueError,'projected-owner-failure'):
            session.until('nfs-ready')
        self.assertTrue(pump.streams[0].closed);self.assertNotEqual(p.wait(timeout=5),0)
    def test_nested_abort_refusal_still_closes_original_outer_input(self):
        p,pump,session=self.fixture()
        class Lease:
            def abort_original(self):raise ValueError('projected-abort-refusal')
        session.lease_class=Lease;session.abort_method=Lease.abort_original;session.abort_code=Lease.abort_original.__code__;session.created_static=b'original';session.seal=('partial-failure-fixture',)
        session.lease_replies.lease=Lease()
        m._SESSION_SEALS[session]=(*session.seal,session.created_static,session.lease_class,session.abort_method,session.abort_code)
        with self.assertRaisesRegex(ValueError,'projected-abort-refusal'):
            session.until('nfs-ready')
        self.assertTrue(pump.streams[0].closed);self.assertNotEqual(p.wait(timeout=5),0)

if __name__=='__main__':unittest.main()
