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
    def launch(self,owner=None):
        token='a'*64
        p=subprocess.Popen([sys.executable,'-I','-B',str(HELPER),'--lease-child','--writer-source',str(WRITER),'--writer-sha256',SHA,'--writer-root',str(self.root),'--token',token],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.processes.append(p);c=m.LeaseChannel(p,token,self.root,SHA,10,owner=owner);c.receive('held');return c
    def test_actual_release_closes_owner_geometry_vectors_before_and_after_ACK(self):
        from unittest import mock
        import threading
        import comic_reader_lifecycle_parent as parent
        common=Path(self.tmp.name)/('archive-publication-'+'c'*64);common.mkdir(mode=0o711);common.chmod(0o711)
        (common/'L').mkdir(mode=0o700);(common/'R').mkdir(mode=0o700)
        media=common/'L'/'original';media.write_bytes(b'original')
        geometry=dict(version=2,kind='searchable-common-root-nfs',**{role:dict(path=str(path),signature9=parent.nine(path.lstat())) for role,path in (('common_root',common),('library',common/'L'),('retention',common/'R'))})
        owner=object.__new__(parent.LifecycleParent);owner.thread=threading.get_ident();owner.core=b'explicit-source-fixture';owner.source_ref=dict(path=parent.__file__)
        parent._CORES[owner]=owner.core;uid=[0];events=[]
        def switch(real,effective,saved):uid[0]=effective;events.append(effective)
        with mock.patch.object(parent.os,'getresuid',side_effect=lambda:(0,uid[0],0)),mock.patch.object(parent.os,'getresgid',return_value=(0,0,0)),mock.patch.object(parent.os,'getgroups',return_value=[0]),mock.patch.object(parent.os,'setresuid',side_effect=switch):
            actor=parent.GeometryOwnerReads(geometry);parent._OWNER_READS=actor
            try:
                channel=self.launch(owner=owner);events.clear();real_write=parent.os.write
                def write(fd,data):
                    if b'"action":"release"' in data:self.assertEqual(uid[0],0)
                    return real_write(fd,data)
                with mock.patch.object(parent.os,'write',side_effect=write):
                    ack=channel.release([str(common/'R'/'absent')],[(str(media),parent.nine(media.stat()))],[(str(common/'L'),parent.five((common/'L').stat()))])
                self.assertEqual(ack['state'],'release-reviewed');self.assertTrue(channel.released)
                self.assertIn(1000,events);self.assertEqual(uid[0],0)
            finally:parent.release_owner_reads(actor);parent._CORES.pop(owner,None)

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
