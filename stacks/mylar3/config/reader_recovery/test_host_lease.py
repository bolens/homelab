"""Real helper/Popen/FIFO/Writer controls; Docker/profile launch remains unrun."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('hostlease',ROOT/'comic_nfs_host_lease.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
HELPER=ROOT/'comic_negative_nfs_active_lifecycle.py'
WRITER=ROOT.parent/'media_writer.py'
SHA=hashlib.sha256(WRITER.read_bytes()).hexdigest()
w=importlib.util.spec_from_file_location('real_writer',WRITER);writer=importlib.util.module_from_spec(w);exec(compile(WRITER.read_bytes(),str(WRITER),'exec'),writer.__dict__)

@unittest.skipUnless(os.geteuid()==1000 and os.getegid()==1000,'genuine UID1000 Writer/helper required')
class RealLease(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'writer';writer.Writer(self.root,create=True)
        self.processes=[];self.addCleanup(self.cleanup)
    def cleanup(self):
        for p in self.processes:
            for s in (p.stdin,p.stdout,p.stderr):
                if s is not None:s.close()
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.terminate();p.wait(timeout=3)
    def launch(self):
        token='a'*64
        p=subprocess.Popen([sys.executable,'-I','-B',str(HELPER),'--lease-child','--writer-source',str(WRITER),'--writer-sha256',SHA,'--writer-root',str(self.root),'--token',token],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.processes.append(p);c=m.LeaseChannel(p,token,self.root,SHA,10);c.receive('held');return c
    def test_real_lock_held_pulse_and_release(self):
        c=self.launch();before=m.namespace(self.root)
        fd=os.open(self.root/'writer-v1.lock',os.O_RDWR)
        try:
            with self.assertRaises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertEqual(c.pulse()['state'],'held');self.assertIs(c.process,self.processes[0]);self.assertEqual(c.pid,self.processes[0].pid)
            ack=c.release([]);self.assertEqual(ack['state'],'release-reviewed')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
            self.assertEqual(m.namespace(self.root),before)
        finally:os.close(fd)
    def test_present_owned_path_refuses_release_and_retains_lease(self):
        c=self.launch();owned=Path(self.tmp.name)/'owned';owned.write_bytes(b'retained')
        with self.assertRaisesRegex(m.Held,'owned-present'):c.release([owned])
        self.assertEqual(owned.read_bytes(),b'retained');self.assertIsNone(c.process.poll());c.pulse()
        owned.unlink();c.release([owned])
    def test_original_marker_metadata_drift_refuses(self):
        c=self.launch();(self.root/'writer-v1.lock').chmod(0o640)
        with self.assertRaisesRegex(m.Held,'original-file'):c.check()
    def test_wrong_token_refuses_before_any_command(self):
        c=self.launch();c.token='b'*64
        with self.assertRaisesRegex(m.Held,'original-logical'):c.pulse()
        self.assertIsNone(c.process.poll())
    def test_real_pipe_replacement_refuses(self):
        c=self.launch();r,w=os.pipe()
        try:
            os.dup2(r,c.fds[1][0])
            with self.assertRaisesRegex(m.Held,'process-pipes'):c.check()
        finally:os.close(r);os.close(w)

    def test_wait_callback_cannot_reseal_supplied_original(self):
        c=self.launch();original=Path(self.tmp.name)/'original';original.write_bytes(b'original');original.chmod(0o600)
        old=m.nine(os.lstat(original));real=c.process.wait;fired=[]
        def changed(*args,**kwargs):
            result=real(*args,**kwargs)
            if not fired:original.chmod(0o640);fired.append(True)
            return result
        c.process.wait=changed
        with self.assertRaisesRegex(m.Held,'final-release-original9'):c.release([],files=((str(original),old),))
        self.assertTrue(fired);self.assertEqual(original.read_bytes(),b'original');self.assertEqual(c.process.poll(),0)

class ActualType(unittest.TestCase):
    def test_non_popen_is_never_an_original_process(self):
        with self.assertRaises(m.Held):m.LeaseChannel(object(),'a'*64,'/missing','b'*64)

class ProfileRules(unittest.TestCase):
    def test_real_dockerfile_labels_retained_with_own_label(self):
        import json
        fixture=json.loads((ROOT/'image-labels.json').read_text())
        labels=dict(fixture['labels'],**{'com.homelab.nfs.lease':'owned'})
        before=dict(labels);m.required_label(labels,'owned');self.assertEqual(labels,before)
        with self.assertRaises(m.Held):m.required_label(labels,'foreign')
    def test_stopped_epoch_is_original(self):
        m.stopped_epoch({'StartedAt':'original'},(123,'original'))
        with self.assertRaises(m.Held):m.stopped_epoch({'StartedAt':'restarted'},(123,'original'))

if __name__=='__main__':unittest.main()
