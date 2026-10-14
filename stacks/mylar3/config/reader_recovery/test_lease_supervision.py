"""Real helper/Popen/FIFO/flock supervision, no Docker or Parent grant."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

import test_host_lease as t


class Supervision(t.RealLease):
    def bounded(self,seconds=3):
        helper=Path(__file__).with_name('comic_negative_nfs_active_lifecycle.py')
        p=subprocess.Popen([sys.executable,'-I','-B',str(helper),'--lease-child','--writer-source',str(t.WRITER),
                            '--writer-sha256',t.SHA,'--writer-root',str(self.root),'--token','a'*64,'--lease-seconds',str(seconds)],
                           stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.processes.append(p)
        c=t.m.LeaseChannel(p,'a'*64,self.root,t.SHA,10);c.receive('held');return c

    def unlocked(self):
        fd=os.open(self.root/'writer-v1.lock',os.O_RDWR)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)

    def test_real_total_deadline_releases_without_success_ACK(self):
        c=self.bounded(1)
        self.assertNotEqual(c.process.wait(timeout=4),0)
        self.assertEqual(c.process.stdout.read(),b'')
        self.assertIn(b'lease-original-deadline',c.process.stderr.read())
        self.unlocked();self.assertFalse(c.released)

    def test_real_competing_flock_stays_held_while_helper_budget_expires(self):
        fd=os.open(self.root/'writer-v1.lock',os.O_RDWR)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            helper=Path(__file__).with_name('comic_negative_nfs_active_lifecycle.py')
            p=subprocess.Popen([sys.executable,'-I','-B',str(helper),'--lease-child','--writer-source',str(t.WRITER),
                                '--writer-sha256',t.SHA,'--writer-root',str(self.root),'--token','a'*64,'--lease-seconds','1'],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.processes.append(p)
            self.assertNotEqual(p.wait(timeout=1.5),0)
            self.assertEqual(p.stdout.read(),b'')
            # The original competing holder is NOT released to let this pass.
            another=os.open(self.root/'writer-v1.lock',os.O_RDWR)
            try:
                with self.assertRaises(BlockingIOError):fcntl.flock(another,fcntl.LOCK_EX|fcntl.LOCK_NB)
            finally:os.close(another)
        finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

    def test_partial_line_cannot_block_helper_beyond_deadline(self):
        c=self.bounded(1);os.write(c.fds[0][0],b'{"token":')
        self.assertNotEqual(c.process.wait(timeout=4),0)
        self.assertEqual(c.process.stdout.read(),b'')
        self.unlocked();self.assertFalse(c.released)

    def test_real_parent_EOF_releases_without_success_ACK(self):
        c=self.bounded();c.process.stdin.close()
        self.assertNotEqual(c.process.wait(timeout=4),0)
        self.assertEqual(c.process.stdout.read(),b'')
        self.assertIn(b'lease-channel-lost',c.process.stderr.read())
        self.unlocked();self.assertFalse(c.released)

    def test_abort_original_after_host_deadline_closes_only_original_stdin(self):
        p=subprocess.Popen([sys.executable,'-I','-B',str(t.HELPER),'--lease-child','--writer-source',str(t.WRITER),
                            '--writer-sha256',t.SHA,'--writer-root',str(self.root),'--token','a'*64],
                           stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.processes.append(p);c=t.m.LeaseChannel(p,'a'*64,self.root,t.SHA,1);c.receive('held')
        time.sleep(1.05)
        self.assertLess(c.deadline,time.monotonic())
        result=c.abort_original()
        self.assertTrue(result['original_stdin_closed']);self.assertFalse(result['release_reviewed'])
        self.assertFalse(result['cleanup_accepted']);self.assertFalse(result['publication_authority'])
        self.assertTrue(c.aborted);self.assertFalse(c.released);self.unlocked()
        self.assertFalse(c.process.stdout.closed);self.assertFalse(c.process.stderr.closed)
        with self.assertRaises(t.m.Held):c.abort_original()

    def test_foreign_process_and_descriptor_refuse_before_close(self):
        c=self.launch();old=c.pid;c.pid+=1
        with self.assertRaises(t.m.Held):c.abort_original()
        self.assertFalse(c.process.stdin.closed);self.assertIsNone(c.process.poll())
        c.pid=old
        r,w=os.pipe()
        try:
            os.dup2(r,c.fds[0][0])
            with self.assertRaises(t.m.Held):c.abort_original()
            self.assertFalse(c.process.stdin.closed)
        finally:os.close(r);os.close(w)

    def test_bounded_normal_pulse_release_retains_real_ACK(self):
        c=self.bounded(3)
        self.assertEqual(c.pulse()['state'],'held')
        self.assertEqual(c.release([])['state'],'release-reviewed')
        self.unlocked();self.assertTrue(c.released);self.assertFalse(c.aborted)

    def test_bounded_pipe_accepts_two_finite_commands_without_loss(self):
        c=self.bounded(3)
        pulse=json.dumps(dict(token='a'*64,action='pulse',owned_absence_verified=False)).encode()+b'\n'
        os.write(c.fds[0][0],pulse+pulse)
        self.assertEqual(c.receive('held')['state'],'held')
        self.assertEqual(c.receive('held')['state'],'held')
        c.release([]);self.unlocked()


if __name__=='__main__':unittest.main()
